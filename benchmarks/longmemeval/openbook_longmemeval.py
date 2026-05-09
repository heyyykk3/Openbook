"""Run OpenBook on the LongMemEval retrieval benchmark.

This evaluates the memory/retrieval layer, not answer generation. For each
LongMemEval item, OpenBook ingests the haystack sessions, searches with the
question, and scores whether the retrieved sessions include the gold evidence
sessions from ``answer_session_ids``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

from openbook import __version__  # noqa: E402
from openbook.core.config import Config  # noqa: E402
from openbook.core.db import get_connection, initialize_database  # noqa: E402
from openbook.core.memory import remember  # noqa: E402
from openbook.core.search import search_memories  # noqa: E402
from openbook.core.security import ensure_openbookignore  # noqa: E402
from openbook.providers.embeddings import get_embedding_provider  # noqa: E402
from openbook.providers.llm import get_llm_provider  # noqa: E402


OFFICIAL_DATASETS = {
    "oracle": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json",
    "s": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json",
    "m": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_m_cleaned.json",
}


@dataclass(frozen=True)
class LongMemEvalInstance:
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: str
    haystack_session_ids: list[str]
    haystack_dates: list[str]
    haystack_sessions: list[list[dict[str, Any]]]
    answer_session_ids: list[str]


@dataclass(frozen=True)
class RetrievalHit:
    session_id: str
    memory_id: int
    score: float
    source: str


def load_instances(path: Path, limit: int | None = None) -> list[LongMemEvalInstance]:
    """Load official LongMemEval JSON or JSONL data."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if text.startswith("["):
        raw_items = json.loads(text)
    else:
        raw_items = [json.loads(line) for line in text.splitlines() if line.strip()]

    instances = [_parse_instance(item) for item in raw_items]
    return instances[:limit] if limit else instances


def download_official_dataset(name: str, output_dir: Path) -> Path:
    """Download one official cleaned LongMemEval dataset from Hugging Face."""
    if name not in OFFICIAL_DATASETS:
        valid = ", ".join(sorted(OFFICIAL_DATASETS))
        raise ValueError(f"Unknown dataset '{name}'. Choose one of: {valid}")

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = OFFICIAL_DATASETS[name].rsplit("/", 1)[-1]
    output_path = output_dir / filename
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    with httpx.stream("GET", OFFICIAL_DATASETS[name], follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_bytes():
                if chunk:
                    f.write(chunk)
    return output_path


def _parse_instance(item: dict[str, Any]) -> LongMemEvalInstance:
    session_ids = [str(x) for x in item.get("haystack_session_ids", [])]
    sessions = item.get("haystack_sessions", [])
    dates = [str(x) for x in item.get("haystack_dates", [])]

    if len(dates) < len(session_ids):
        dates = dates + [""] * (len(session_ids) - len(dates))

    answer_session_ids = [str(x) for x in item.get("answer_session_ids", [])]
    if not answer_session_ids:
        answer_session_ids = _infer_answer_sessions(session_ids, sessions)

    return LongMemEvalInstance(
        question_id=str(item["question_id"]),
        question_type=str(item.get("question_type", "unknown")),
        question=str(item["question"]),
        answer=str(item.get("answer", "")),
        question_date=str(item.get("question_date", "")),
        haystack_session_ids=session_ids,
        haystack_dates=dates,
        haystack_sessions=sessions,
        answer_session_ids=answer_session_ids,
    )


def is_abstention(instance: LongMemEvalInstance) -> bool:
    return instance.question_id.endswith("_abs")


def _infer_answer_sessions(
    session_ids: list[str],
    sessions: list[list[dict[str, Any]]],
) -> list[str]:
    inferred: list[str] = []
    for session_id, turns in zip(session_ids, sessions):
        if any(bool(turn.get("has_answer")) for turn in turns):
            inferred.append(session_id)
    return inferred


def run_benchmark(
    dataset_path: Path,
    k_values: list[int],
    limit: int | None = None,
    retrieval_mode: str = "fts",
    embedding_config: dict[str, Any] | None = None,
    embedding_batch_size: int = 32,
    include_abstention: bool = False,
    qa: bool = False,
    reader_config: dict[str, Any] | None = None,
    judge_config: dict[str, Any] | None = None,
    qa_top_k: int | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    loaded_instances = load_instances(dataset_path, limit=limit)
    skipped_abstention = 0 if include_abstention else sum(
        1 for instance in loaded_instances if is_abstention(instance)
    )
    instances = [
        instance for instance in loaded_instances if include_abstention or not is_abstention(instance)
    ]
    if not instances:
        raise ValueError(f"No LongMemEval instances found in {dataset_path}")

    max_k = max(k_values)
    qa_top_k = qa_top_k or max_k
    embedder = get_embedding_provider(embedding_config or {"provider": "none"})
    if retrieval_mode in {"vector", "hybrid"} and embedder.name == "none":
        raise ValueError(
            "--retrieval-mode vector/hybrid requires --embedding-provider "
            "ollama, sentence-transformers, gemini, or openai-compatible"
        )
    reader = get_llm_provider(reader_config or {"provider": "none"})
    judge = get_llm_provider(judge_config or {"provider": "none"})
    records = load_checkpoint_records(checkpoint_path)
    completed_question_ids = {str(record.get("question_id", "")) for record in records}
    if checkpoint_path and records:
        print(f"[longmemeval] resuming from {len(records)} checkpoint records", flush=True)

    with tempfile.TemporaryDirectory(prefix="openbook-longmemeval-") as tmp:
        tmp_root = Path(tmp)
        total = len(instances)
        for index, instance in enumerate(instances, start=1):
            if instance.question_id in completed_question_ids:
                print(
                    f"[longmemeval] {index}/{total} {instance.question_id} "
                    f"({instance.question_type}) skipped checkpoint",
                    flush=True,
                )
                continue
            print(
                f"[longmemeval] {index}/{total} {instance.question_id} "
                f"({instance.question_type})",
                flush=True,
            )
            project_root = tmp_root / f"item-{index:04d}"
            project_root.mkdir(parents=True, exist_ok=True)
            (project_root / ".git").mkdir()

            initialize_database(project_root)
            Config.create_default(project_root)
            ensure_openbookignore(project_root)
            conn = get_connection(project_root)
            try:
                project_id = _get_project_id(conn, project_root)
                ingest_start = time.perf_counter()
                memory_to_session = ingest_instance(conn, project_id, instance)
                ingest_ms = (time.perf_counter() - ingest_start) * 1000
                session_to_memory = {session_id: memory_id for memory_id, session_id in memory_to_session.items()}
                session_texts = {
                    session_id: format_session(session_id=session_id, date=date, turns=turns)
                    for session_id, date, turns in zip(
                        instance.haystack_session_ids,
                        instance.haystack_dates,
                        instance.haystack_sessions,
                    )
                }

                search_start = time.perf_counter()
                hits = retrieve_sessions(
                    conn=conn,
                    project_id=project_id,
                    question=instance.question,
                    retrieval_mode=retrieval_mode,
                    memory_to_session=memory_to_session,
                    session_to_memory=session_to_memory,
                    session_texts=session_texts,
                    embedder=embedder,
                    limit=max_k,
                    embedding_batch_size=embedding_batch_size,
                )
                search_ms = (time.perf_counter() - search_start) * 1000

                retrieved = [hit.session_id for hit in hits]
                record = score_record(
                    instance=instance,
                    retrieved_session_ids=retrieved,
                    k_values=k_values,
                    ingest_ms=ingest_ms,
                    search_ms=search_ms,
                    citation_count=len(hits),
                )
                record["retrieval_mode"] = retrieval_mode
                record["retrieval_hits"] = [
                    {
                        "session_id": hit.session_id,
                        "memory_id": hit.memory_id,
                        "score": round(hit.score, 6),
                        "source": hit.source,
                    }
                    for hit in hits
                ]
                if qa:
                    qa_start = time.perf_counter()
                    retrieved_context = [
                        session_texts[session_id]
                        for session_id in retrieved[:qa_top_k]
                        if session_id in session_texts
                    ]
                    hypothesis = generate_answer(reader, instance, retrieved_context)
                    qa_ms = (time.perf_counter() - qa_start) * 1000
                    record["qa"] = score_qa(judge, instance, hypothesis, qa_ms)
                records.append(record)
                append_checkpoint_record(checkpoint_path, record)
            finally:
                conn.close()

    return {
        "benchmark": "LongMemEval retrieval",
        "dataset": str(dataset_path),
        "metadata": build_run_metadata(dataset_path),
        "track": "qa" if qa else "retrieval",
        "retrieval_mode": retrieval_mode,
        "k_values": k_values,
        "instances": len(records),
        "loaded_instances": len(loaded_instances),
        "skipped_abstention": skipped_abstention,
        "qa_enabled": qa,
        "embedding_provider": embedder.name,
        "embedding_model": embedder.model,
        "reader": reader.name,
        "reader_model": reader.model,
        "judge": judge.name,
        "judge_model": judge.model,
        "overall": summarize(records, k_values),
        "by_question_type": summarize_by_question_type(records, k_values),
        "records": records,
    }


def build_run_metadata(dataset_path: Path) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "openbook_version": __version__,
        "git_commit": detect_git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dataset_sha256": sha256_file(dataset_path),
    }


def detect_git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get_project_id(conn: Any, project_root: Path) -> int:
    row = conn.execute(
        "SELECT id FROM projects WHERE root_path = ?",
        (str(project_root.resolve()),),
    ).fetchone()
    if row is None:
        raise RuntimeError("OpenBook project was not initialized")
    return int(row["id"])


def load_checkpoint_records(checkpoint_path: Path | None) -> list[dict[str, Any]]:
    if checkpoint_path is None or not checkpoint_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def append_checkpoint_record(checkpoint_path: Path | None, record: dict[str, Any]) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def ingest_instance(
    conn: Any,
    project_id: int,
    instance: LongMemEvalInstance,
) -> dict[int, str]:
    """Ingest one LongMemEval haystack as approved OpenBook memories."""
    memory_to_session: dict[int, str] = {}
    for session_id, date, turns in zip(
        instance.haystack_session_ids,
        instance.haystack_dates,
        instance.haystack_sessions,
    ):
        content = format_session(session_id=session_id, date=date, turns=turns)
        source_id = _insert_source(conn, project_id, instance, session_id, date)
        citation_id = _insert_citation(conn, project_id, source_id, session_id, content)
        memory_id = remember(
            conn=conn,
            project_id=project_id,
            content=content,
            memory_type="source_note",
            title=f"LongMemEval session {session_id}",
            summary=f"Conversation session {session_id} from {date}",
            tags=["longmemeval", instance.question_type],
            confidence=0.8,
            trust_score=0.8,
            importance=0.5,
            status="approved",
            source_id=source_id,
            citation_id=citation_id,
            idempotency_key=f"longmemeval::{instance.question_id}::{session_id}",
        )
        memory_to_session[memory_id] = session_id
    return memory_to_session


def _insert_source(
    conn: Any,
    project_id: int,
    instance: LongMemEvalInstance,
    session_id: str,
    date: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO sources (project_id, type, uri, title, metadata_json, trust_score)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            "longmemeval_session",
            f"longmemeval://{instance.question_id}/{session_id}",
            f"LongMemEval {instance.question_id} session {session_id}",
            json.dumps(
                {
                    "question_id": instance.question_id,
                    "question_type": instance.question_type,
                    "question_date": instance.question_date,
                    "session_id": session_id,
                    "session_date": date,
                }
            ),
            0.8,
        ),
    )
    if cur.lastrowid is None:
        raise RuntimeError("Source insert did not return a row id")
    return int(cur.lastrowid)


def _insert_citation(
    conn: Any,
    project_id: int,
    source_id: int,
    session_id: str,
    content: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO citations (project_id, source_id, transcript_span_id, quote)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, source_id, session_id, content[:500]),
    )
    if cur.lastrowid is None:
        raise RuntimeError("Citation insert did not return a row id")
    return int(cur.lastrowid)


def format_session(session_id: str, date: str, turns: list[dict[str, Any]]) -> str:
    lines = [f"Session ID: {session_id}"]
    if date:
        lines.append(f"Session date: {date}")
    for turn in turns:
        role = str(turn.get("role", "unknown"))
        content = str(turn.get("content", ""))
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def retrieve_sessions(
    *,
    conn: Any,
    project_id: int,
    question: str,
    retrieval_mode: str,
    memory_to_session: dict[int, str],
    session_to_memory: dict[str, int],
    session_texts: dict[str, str],
    embedder: Any,
    limit: int,
    embedding_batch_size: int,
) -> list[RetrievalHit]:
    fts_hits = retrieve_fts(conn, project_id, question, memory_to_session, limit)
    if retrieval_mode == "fts":
        return fts_hits

    vector_hits = retrieve_vector(
        question=question,
        session_to_memory=session_to_memory,
        session_texts=session_texts,
        embedder=embedder,
        limit=limit,
        batch_size=embedding_batch_size,
    )
    if retrieval_mode == "vector":
        return vector_hits
    if retrieval_mode == "hybrid":
        return merge_hybrid_hits(fts_hits, vector_hits, limit)
    raise ValueError(f"Unknown retrieval mode: {retrieval_mode}")


def retrieve_fts(
    conn: Any,
    project_id: int,
    question: str,
    memory_to_session: dict[int, str],
    limit: int,
) -> list[RetrievalHit]:
    cards = search_memories(
        conn=conn,
        project_id=project_id,
        query=question,
        memory_type="source_note",
        status="approved",
        limit=limit,
    )
    hits: list[RetrievalHit] = []
    for card in cards:
        if card.memory_id not in memory_to_session:
            continue
        # Reciprocal rank is stable and simple for combining with vector scores.
        score = 1.0 / max(card.rank, 1)
        hits.append(
            RetrievalHit(
                session_id=memory_to_session[card.memory_id],
                memory_id=card.memory_id,
                score=score,
                source="fts",
            )
        )
    return hits


def retrieve_vector(
    *,
    question: str,
    session_to_memory: dict[str, int],
    session_texts: dict[str, str],
    embedder: Any,
    limit: int,
    batch_size: int,
) -> list[RetrievalHit]:
    if embedder.name == "none":
        return []
    if hasattr(embedder, "embed_query"):
        query_vector = embedder.embed_query(question)
    else:
        query_vector = embedder.embed_text(question)
    if not query_vector:
        return []

    session_ids = list(session_texts)
    texts = [session_texts[session_id] for session_id in session_ids]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        if hasattr(embedder, "embed_documents"):
            vectors.extend(embedder.embed_documents(batch))
        else:
            vectors.extend(embedder.embed_batch(batch))

    hits: list[RetrievalHit] = []
    for session_id, vector in zip(session_ids, vectors):
        if not vector:
            continue
        cosine = cosine_similarity(query_vector, vector)
        score = (cosine + 1.0) / 2.0
        hits.append(
            RetrievalHit(
                session_id=session_id,
                memory_id=session_to_memory[session_id],
                score=score,
                source="vector",
            )
        )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


def merge_hybrid_hits(
    fts_hits: list[RetrievalHit],
    vector_hits: list[RetrievalHit],
    limit: int,
) -> list[RetrievalHit]:
    merged: dict[str, dict[str, Any]] = {}
    for hit in fts_hits:
        item = merged.setdefault(
            hit.session_id,
            {"session_id": hit.session_id, "memory_id": hit.memory_id, "fts": 0.0, "vector": 0.0},
        )
        item["fts"] = max(float(item["fts"]), hit.score)
    for hit in vector_hits:
        item = merged.setdefault(
            hit.session_id,
            {"session_id": hit.session_id, "memory_id": hit.memory_id, "fts": 0.0, "vector": 0.0},
        )
        item["vector"] = max(float(item["vector"]), hit.score)

    hybrid_hits: list[RetrievalHit] = []
    for item in merged.values():
        score = 0.5 * float(item["fts"]) + 0.5 * float(item["vector"])
        source = "hybrid"
        if item["fts"] == 0:
            source = "vector"
        elif item["vector"] == 0:
            source = "fts"
        hybrid_hits.append(
            RetrievalHit(
                session_id=str(item["session_id"]),
                memory_id=int(item["memory_id"]),
                score=score,
                source=source,
            )
        )
    return sorted(hybrid_hits, key=lambda hit: hit.score, reverse=True)[:limit]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def score_record(
    instance: LongMemEvalInstance,
    retrieved_session_ids: list[str],
    k_values: list[int],
    ingest_ms: float,
    search_ms: float,
    citation_count: int,
) -> dict[str, Any]:
    gold = set(instance.answer_session_ids)
    answerable = bool(gold) and not instance.question_id.endswith("_abs")
    ranks = {
        session_id: rank
        for rank, session_id in enumerate(retrieved_session_ids, start=1)
        if session_id in gold
    }

    metrics: dict[str, float] = {}
    for k in k_values:
        top_k = retrieved_session_ids[:k]
        hits = sum(1 for session_id in top_k if session_id in gold)
        if answerable:
            metrics[f"hit@{k}"] = 1.0 if hits > 0 else 0.0
            metrics[f"recall@{k}"] = hits / len(gold)
            metrics[f"precision@{k}"] = hits / k
            metrics[f"ndcg@{k}"] = ndcg(top_k, gold, k)
        else:
            metrics[f"abstention_accuracy@{k}"] = 1.0 if not top_k else 0.0

    first_rank = min(ranks.values()) if ranks else None
    metrics["mrr"] = (1.0 / first_rank) if first_rank else 0.0

    return {
        "question_id": instance.question_id,
        "question_type": instance.question_type,
        "answerable": answerable,
        "question": instance.question,
        "gold_session_ids": instance.answer_session_ids,
        "retrieved_session_ids": retrieved_session_ids,
        "gold_ranks": ranks,
        "metrics": metrics,
        "timing_ms": {
            "ingest": round(ingest_ms, 3),
            "search": round(search_ms, 3),
        },
        "retrieved_count": len(retrieved_session_ids),
        "citation_count": citation_count,
    }


def generate_answer(
    reader: Any,
    instance: LongMemEvalInstance,
    retrieved_context: list[str],
) -> str:
    if reader.name == "none":
        raise ValueError("--qa requires a reader model provider such as ollama, gemini, or openai-compatible")
    context = "\n\n---\n\n".join(retrieved_context) if retrieved_context else "(no retrieved context)"
    prompt = f"""You are answering a LongMemEval long-term memory question.

Use only the retrieved conversation history below. If the history is insufficient,
answer "I don't know."

Question date: {instance.question_date}
Question: {instance.question}

Retrieved history:
{context}

Answer concisely:"""
    return str(reader.complete(prompt, temperature=0.0)).strip()


def score_qa(
    judge: Any,
    instance: LongMemEvalInstance,
    hypothesis: str,
    qa_ms: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "hypothesis": hypothesis,
        "expected_answer": instance.answer,
        "label": None,
        "judge_response": "",
        "timing_ms": round(qa_ms, 3),
    }
    if judge.name == "none":
        result["evaluation"] = "not_evaluated"
        return result

    prompt = f"""Evaluate whether the hypothesis correctly answers the question.

Return only JSON with:
{{"autoeval_label": true or false, "explanation": "short reason"}}

Question: {instance.question}
Reference answer: {instance.answer}
Hypothesis: {hypothesis}
"""
    judge_response = str(judge.complete(prompt, temperature=0.0)).strip()
    result["judge_response"] = judge_response
    result["label"] = parse_judge_label(judge_response)
    result["evaluation"] = "judged"
    return result


def parse_judge_label(text: str) -> bool | None:
    try:
        data = json.loads(text)
        value = data.get("autoeval_label", data.get("label"))
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "correct", "yes"}:
                return True
            if lowered in {"false", "incorrect", "no"}:
                return False
    except json.JSONDecodeError:
        pass

    lowered = text.lower()
    if "incorrect" in lowered or "false" in lowered:
        return False
    if "correct" in lowered or "true" in lowered:
        return True
    return None


def ndcg(retrieved_session_ids: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    dcg = 0.0
    for rank, session_id in enumerate(retrieved_session_ids[:k], start=1):
        if session_id in gold:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def summarize(records: list[dict[str, Any]], k_values: list[int]) -> dict[str, Any]:
    answerable = [r for r in records if r["answerable"]]
    abstention = [r for r in records if not r["answerable"]]
    summary: dict[str, Any] = {
        "count": len(records),
        "answerable_count": len(answerable),
        "abstention_count": len(abstention),
        "mean_ingest_ms": _mean([r["timing_ms"]["ingest"] for r in records]),
        "mean_search_ms": _mean([r["timing_ms"]["search"] for r in records]),
        "mean_retrieved": _mean([r["retrieved_count"] for r in records]),
        "citation_presence_rate": _mean(
            [1.0 if r["citation_count"] > 0 else 0.0 for r in records]
        ),
    }

    qa_records = [r for r in records if "qa" in r]
    judged_qa = [r for r in qa_records if r["qa"].get("label") is not None]
    if qa_records:
        summary["qa_count"] = len(qa_records)
        summary["mean_qa_ms"] = _mean([r["qa"]["timing_ms"] for r in qa_records])
    if judged_qa:
        summary["qa_accuracy"] = _mean(
            [1.0 if bool(r["qa"]["label"]) else 0.0 for r in judged_qa]
        )
        summary["qa_judged_count"] = len(judged_qa)

    if answerable:
        summary["mrr"] = _mean([r["metrics"]["mrr"] for r in answerable])
        for k in k_values:
            summary[f"hit@{k}"] = _mean([r["metrics"][f"hit@{k}"] for r in answerable])
            summary[f"recall@{k}"] = _mean(
                [r["metrics"][f"recall@{k}"] for r in answerable]
            )
            summary[f"precision@{k}"] = _mean(
                [r["metrics"][f"precision@{k}"] for r in answerable]
            )
            summary[f"ndcg@{k}"] = _mean([r["metrics"][f"ndcg@{k}"] for r in answerable])

    if abstention:
        for k in k_values:
            summary[f"abstention_accuracy@{k}"] = _mean(
                [r["metrics"][f"abstention_accuracy@{k}"] for r in abstention]
            )

    return summary


def summarize_by_question_type(
    records: list[dict[str, Any]],
    k_values: list[int],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["question_type"], []).append(record)
    return {
        question_type: summarize(items, k_values)
        for question_type, items in sorted(grouped.items())
    }


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(statistics.fmean(values)), 4)


def parse_k_values(value: str) -> list[int]:
    parsed = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    if not parsed or any(k <= 0 for k in parsed):
        raise argparse.ArgumentTypeError("--k must contain positive integers")
    return parsed


def build_llm_config(
    provider: str,
    model: str,
    base_url: str,
    api_key_env: str,
) -> dict[str, Any]:
    if provider == "none":
        return {"provider": "none"}
    config: dict[str, Any] = {"provider": provider}
    if provider == "gemini" and not model:
        model = "gemini-3-flash-preview"
    if model:
        config["model"] = model
    if base_url:
        config["base_url"] = base_url
    env_name = api_key_env or ("GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY")
    api_key = os.environ.get(env_name)
    if api_key:
        config["api_key"] = api_key
    return config


def build_embedding_config(
    provider: str,
    model: str,
    base_url: str,
    api_key_env: str,
) -> dict[str, Any]:
    if provider == "none":
        return {"provider": "none"}
    config: dict[str, Any] = {"provider": provider}
    if provider == "gemini" and not model:
        model = "gemini-embedding-2"
    if model:
        config["model"] = model
    if base_url:
        config["base_url"] = base_url
    env_name = api_key_env or ("GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY")
    api_key = os.environ.get(env_name)
    if api_key:
        config["api_key"] = api_key
    return config


def write_report(results: dict[str, Any], report_dir: Path) -> None:
    """Write a benchmark report with numbers and dependency-free SVG charts."""
    report_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = report_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_records_jsonl(results, report_dir / "records.jsonl")
    write_metrics_csv(results, report_dir / "metrics.csv")

    max_k = max(int(k) for k in results["k_values"])
    overall = results["overall"]
    recall_bars = [
        (f"R@{k}", float(overall.get(f"recall@{k}", 0.0)))
        for k in results["k_values"]
        if f"recall@{k}" in overall
    ]
    if recall_bars:
        write_horizontal_bar_chart(
            charts_dir / "recall_at_k.svg",
            "LongMemEval Retrieval Recall@K",
            recall_bars,
            percentage=True,
        )

    scorecard = headline_scorecard(results)
    if scorecard:
        write_public_scorecard_chart(
            charts_dir / "scorecard.svg",
            "OpenBook Benchmark Scorecard",
            scorecard,
        )

    type_bars = [
        (question_type, float(summary.get(f"recall@{max_k}", 0.0)))
        for question_type, summary in results["by_question_type"].items()
        if f"recall@{max_k}" in summary
    ]
    if type_bars:
        write_horizontal_bar_chart(
            charts_dir / f"recall_at_{max_k}_by_type.svg",
            f"Recall@{max_k} By Question Type",
            type_bars,
            percentage=True,
        )

    write_horizontal_bar_chart(
        charts_dir / "latency_ms.svg",
        "Mean Latency Per Benchmark Item",
        [
            ("Ingest", float(overall["mean_ingest_ms"])),
            ("Search", float(overall["mean_search_ms"])),
        ],
        percentage=False,
        unit=" ms",
    )
    (report_dir / "summary.md").write_text(build_summary_markdown(results), encoding="utf-8")


def headline_scorecard(results: dict[str, Any]) -> list[tuple[str, float]]:
    overall = results["overall"]
    max_k = max(int(k) for k in results["k_values"])
    rows: list[tuple[str, float]] = []
    if f"recall@{max_k}" in overall:
        rows.append((f"LONGMEMEVAL R@{max_k}", float(overall[f"recall@{max_k}"])))
    if "mrr" in overall:
        rows.append(("MRR", float(overall["mrr"])))
    if "qa_accuracy" in overall:
        rows.append(("QA ACCURACY", float(overall["qa_accuracy"])))
    rows.append(("CITATION PRESENCE", float(overall["citation_presence_rate"])))
    return rows


def write_records_jsonl(results: dict[str, Any], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in results["records"]:
            f.write(json.dumps(record) + "\n")


def write_metrics_csv(results: dict[str, Any], path: Path) -> None:
    k_values = [int(k) for k in results["k_values"]]
    fields = ["group", "count", "mrr"]
    for k in k_values:
        fields.extend([f"hit@{k}", f"recall@{k}", f"precision@{k}", f"ndcg@{k}"])
    fields.extend(["mean_ingest_ms", "mean_search_ms", "citation_presence_rate"])

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(_summary_csv_row("overall", results["overall"], fields))
        for question_type, summary in results["by_question_type"].items():
            writer.writerow(_summary_csv_row(question_type, summary, fields))


def _summary_csv_row(group: str, summary: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    row = {field: summary.get(field, "") for field in fields}
    row["group"] = group
    return row


def build_summary_markdown(results: dict[str, Any]) -> str:
    overall = results["overall"]
    metadata = results.get("metadata", {})
    max_k = max(int(k) for k in results["k_values"])
    lines = [
        "# OpenBook LongMemEval Retrieval Report",
        "",
        f"Dataset: `{results['dataset']}`",
        f"Track: `{results['track']}`",
        f"Retrieval mode: **{results.get('retrieval_mode', 'fts')}**",
        f"Embedding provider: **{results.get('embedding_provider', 'none')}**",
        f"Embedding model: **{results.get('embedding_model', '') or '(none)'}**",
        f"Loaded instances: **{results.get('loaded_instances', overall['count'])}**",
        f"Instances: **{overall['count']}**",
        f"Skipped abstention: **{results.get('skipped_abstention', 0)}**",
        f"Answerable: **{overall['answerable_count']}**",
        f"Abstention: **{overall['abstention_count']}**",
        f"QA enabled: **{results.get('qa_enabled', False)}**",
        "",
        "## Run Metadata",
        "",
        f"- Generated at UTC: `{metadata.get('generated_at_utc', 'unknown')}`",
        f"- OpenBook version: `{metadata.get('openbook_version', 'unknown')}`",
        f"- Git commit: `{metadata.get('git_commit') or 'unknown'}`",
        f"- Python: `{metadata.get('python', 'unknown')}`",
        f"- Platform: `{metadata.get('platform', 'unknown')}`",
        f"- Dataset SHA256: `{metadata.get('dataset_sha256', 'unknown')}`",
        *([f"- Command: `{metadata['command']}`"] if "command" in metadata else []),
        "",
        "## Headline Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for k in results["k_values"]:
        for metric in ("hit", "recall", "precision", "ndcg"):
            key = f"{metric}@{k}"
            if key in overall:
                lines.append(f"| {key.upper()} | {_format_percent(overall[key])} |")
    if "mrr" in overall:
        lines.append(f"| MRR | {_format_decimal(overall['mrr'])} |")
    if "qa_accuracy" in overall:
        lines.append(f"| QA Accuracy | {_format_percent(overall['qa_accuracy'])} |")
    lines.extend(
        [
            f"| Mean ingest | {_format_decimal(overall['mean_ingest_ms'])} ms |",
            f"| Mean search | {_format_decimal(overall['mean_search_ms'])} ms |",
            *(
                [f"| Mean QA | {_format_decimal(overall['mean_qa_ms'])} ms |"]
                if "mean_qa_ms" in overall
                else []
            ),
            f"| Citation presence | {_format_percent(overall['citation_presence_rate'])} |",
            "",
            "## Charts",
            "",
            "![Scorecard](charts/scorecard.svg)",
            "![Recall at K](charts/recall_at_k.svg)",
            f"![Recall at {max_k} by type](charts/recall_at_{max_k}_by_type.svg)",
            "![Latency](charts/latency_ms.svg)",
            "",
            "## By Question Type",
            "",
            f"| Question Type | Count | R@{max_k} | Hit@{max_k} | NDCG@{max_k} | MRR | Search ms |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for question_type, summary in results["by_question_type"].items():
        lines.append(
            "| "
            f"{question_type} | "
            f"{summary['count']} | "
            f"{_format_percent(summary.get(f'recall@{max_k}', 0.0))} | "
            f"{_format_percent(summary.get(f'hit@{max_k}', 0.0))} | "
            f"{_format_percent(summary.get(f'ndcg@{max_k}', 0.0))} | "
            f"{_format_decimal(summary.get('mrr', 0.0))} | "
            f"{_format_decimal(summary['mean_search_ms'])} |"
        )

    lines.extend(["", "## Notes", ""])
    if results.get("qa_enabled"):
        lines.extend(
            [
                "This is a retrieval-augmented QA benchmark. It reports retrieval metrics "
                "and, when a judge provider is configured, judged answer correctness. "
                "Public comparisons must disclose the reader, judge, embedding model, "
                "retrieval mode, and context depth.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "This is a retrieval benchmark. It measures whether OpenBook retrieves the gold "
                "evidence sessions from LongMemEval. It does not use an LLM judge and does not "
                "measure final answer correctness.",
                "",
            ]
        )
    return "\n".join(lines)


def write_horizontal_bar_chart(
    path: Path,
    title: str,
    bars: list[tuple[str, float]],
    *,
    percentage: bool,
    unit: str = "",
) -> None:
    width = 920
    left = 230
    right = 90
    top = 72
    row_height = 42
    bar_height = 22
    height = top + max(1, len(bars)) * row_height + 44
    chart_width = width - left - right
    max_value = 1.0 if percentage else max([value for _, value in bars] + [1.0])

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#17202a}",
        ".title{font-size:22px;font-weight:700}",
        ".label{font-size:13px}",
        ".value{font-size:13px;font-weight:700}",
        ".axis{stroke:#d5d8dc;stroke-width:1}",
        ".bar{fill:#2563eb}",
        ".bg{fill:#eef2f7}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="title" x="24" y="34">{escape(title)}</text>',
        f'<line class="axis" x1="{left}" y1="{top - 18}" x2="{left + chart_width}" y2="{top - 18}"/>',
    ]
    for index, (label, value) in enumerate(bars):
        y = top + index * row_height
        bar_width = 0 if max_value == 0 else int((value / max_value) * chart_width)
        parts.extend(
            [
                f'<text class="label" x="24" y="{y + 16}">{escape(label)}</text>',
                f'<rect class="bg" x="{left}" y="{y}" width="{chart_width}" height="{bar_height}" rx="3"/>',
                f'<rect class="bar" x="{left}" y="{y}" width="{bar_width}" height="{bar_height}" rx="3"/>',
                f'<text class="value" x="{left + chart_width + 14}" y="{y + 16}">'
                f'{escape(_format_value(value, percentage, unit))}</text>',
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_public_scorecard_chart(
    path: Path,
    title: str,
    bars: list[tuple[str, float]],
) -> None:
    width = 1200
    left = 250
    right = 95
    top = 95
    row_height = 105
    bar_height = 52
    chart_width = width - left - right
    height = top + len(bars) * row_height + 65
    purple = "#9b7cf3"
    bg = "#f3f3f4"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#08080a}",
        ".title{font-size:34px;font-weight:800}",
        ".label{font-size:22px;font-weight:800;letter-spacing:0}",
        ".value{font-size:24px;font-weight:900}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="title" x="44" y="50">{escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(bars):
        y = top + index * row_height
        value = max(0.0, min(1.0, value))
        bar_width = int(value * chart_width)
        parts.extend(
            [
                f'<rect x="{left}" y="{y}" width="{chart_width}" height="{bar_height}" fill="{bg}"/>',
                f'<rect x="{left}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{purple}"/>',
                f'<text class="label" x="{left + 24}" y="{y + 35}">{escape(label)}</text>',
                f'<text class="value" x="{left + max(28, bar_width) - 74}" y="{y + 35}">'
                f'{value * 100:.1f}</text>',
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _format_value(value: float, percentage: bool, unit: str = "") -> str:
    if percentage:
        return _format_percent(value)
    return f"{_format_decimal(value)}{unit}"


def _format_percent(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _format_decimal(value: Any) -> str:
    return f"{float(value):.4f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OpenBook on LongMemEval retrieval.")
    parser.add_argument("--dataset", type=Path, help="Path to LongMemEval JSON/JSONL")
    parser.add_argument("--download", choices=sorted(OFFICIAL_DATASETS), help="Download an official cleaned dataset")
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks/longmemeval/data"))
    parser.add_argument("--limit", type=int, default=None, help="Optional instance limit")
    parser.add_argument("--k", type=parse_k_values, default=[1, 3, 5], help="Comma list, e.g. 1,3,5")
    parser.add_argument("--retrieval-mode", default="fts", choices=["fts", "vector", "hybrid"])
    parser.add_argument("--embedding-provider", default="none", choices=["none", "ollama", "openai-compatible", "sentence-transformers", "gemini"])
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--embedding-base-url", default="")
    parser.add_argument("--embedding-api-key-env", default="")
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--include-abstention", action="store_true", help="Include abstention questions in retrieval scoring")
    parser.add_argument("--qa", action="store_true", help="Run retrieval-augmented QA after retrieval")
    parser.add_argument("--qa-top-k", type=int, default=None, help="Number of retrieved sessions passed to the reader")
    parser.add_argument("--reader-provider", default="none", choices=["none", "ollama", "openai-compatible", "gemini"])
    parser.add_argument("--reader-model", default="")
    parser.add_argument("--reader-base-url", default="")
    parser.add_argument("--reader-api-key-env", default="")
    parser.add_argument("--judge-provider", default="none", choices=["none", "ollama", "openai-compatible", "gemini"])
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-base-url", default="")
    parser.add_argument("--judge-api-key-env", default="")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON results path")
    parser.add_argument("--report-dir", type=Path, default=None, help="Write Markdown, CSV, JSONL, and SVG report files")
    args = parser.parse_args(argv)

    dataset_path = args.dataset
    if args.download:
        dataset_path = download_official_dataset(args.download, args.data_dir)
        print(f"Using official dataset: {dataset_path}")
    if dataset_path is None:
        parser.error("Provide --dataset or --download")

    results = run_benchmark(
        dataset_path=dataset_path,
        k_values=args.k,
        limit=args.limit,
        retrieval_mode=args.retrieval_mode,
        embedding_config=build_embedding_config(
            provider=args.embedding_provider,
            model=args.embedding_model,
            base_url=args.embedding_base_url,
            api_key_env=args.embedding_api_key_env,
        ),
        embedding_batch_size=args.embedding_batch_size,
        include_abstention=args.include_abstention,
        qa=args.qa,
        reader_config=build_llm_config(
            provider=args.reader_provider,
            model=args.reader_model,
            base_url=args.reader_base_url,
            api_key_env=args.reader_api_key_env,
        ),
        judge_config=build_llm_config(
            provider=args.judge_provider,
            model=args.judge_model,
            base_url=args.judge_base_url,
            api_key_env=args.judge_api_key_env,
        ),
        qa_top_k=args.qa_top_k,
        checkpoint_path=args.report_dir / "checkpoint.records.jsonl" if args.report_dir else None,
    )
    results["metadata"]["command"] = " ".join([Path(sys.argv[0]).name, *sys.argv[1:]])
    print_summary(results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote results: {args.output}")

    if args.report_dir:
        write_report(results, args.report_dir)
        print(f"\nWrote benchmark report: {args.report_dir}")

    return 0


def print_summary(results: dict[str, Any]) -> None:
    overall = results["overall"]
    print("LongMemEval retrieval benchmark")
    print(f"Dataset: {results['dataset']}")
    print(f"Retrieval mode: {results.get('retrieval_mode', 'fts')}")
    embedding_label = f"{results.get('embedding_provider', 'none')} {results.get('embedding_model', '') or ''}".strip()
    print(f"Embedding: {embedding_label}")
    print(f"Instances: {overall['count']}")
    if results.get("skipped_abstention"):
        print(f"Skipped abstention: {results['skipped_abstention']}")
    print(f"Answerable: {overall['answerable_count']}")
    print(f"Abstention: {overall['abstention_count']}")
    for k in results["k_values"]:
        if f"recall@{k}" in overall:
            print(
                f"R@{k}: {overall[f'recall@{k}']:.4f} | "
                f"Hit@{k}: {overall[f'hit@{k}']:.4f} | "
                f"NDCG@{k}: {overall[f'ndcg@{k}']:.4f}"
            )
    if "mrr" in overall:
        print(f"MRR: {overall['mrr']:.4f}")
    if "qa_accuracy" in overall:
        print(f"QA accuracy: {overall['qa_accuracy']:.4f}")
    print(f"Mean ingest: {overall['mean_ingest_ms']:.2f} ms")
    print(f"Mean search: {overall['mean_search_ms']:.2f} ms")
    if "mean_qa_ms" in overall:
        print(f"Mean QA: {overall['mean_qa_ms']:.2f} ms")
    print(f"Citation presence: {overall['citation_presence_rate']:.4f}")


if __name__ == "__main__":
    raise SystemExit(main())
