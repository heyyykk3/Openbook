"""Tests for the LongMemEval benchmark harness."""

from __future__ import annotations

from pathlib import Path

from benchmarks.longmemeval.openbook_longmemeval import (
    build_embedding_config,
    build_llm_config,
    cosine_similarity,
    load_instances,
    merge_hybrid_hits,
    retrieve_vector,
    run_benchmark,
    write_report,
)
from openbook.core.search import build_fts_query


SAMPLE_DATASET = Path("benchmarks/longmemeval/sample_longmemeval.json")


class FakeEmbeddingProvider:
    name = "fake"
    model = "keyword"

    def embed_text(self, text: str) -> list[float]:
        text = text.lower()
        return [
            1.0 if "pytest" in text else 0.0,
            1.0 if "linear" in text else 0.0,
            1.0 if "toronto" in text else 0.0,
        ]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


def test_load_sample_longmemeval_instances() -> None:
    instances = load_instances(SAMPLE_DATASET)

    assert len(instances) == 3
    assert instances[0].question_id == "sample_single_user"
    assert instances[0].answer_session_ids == ["s2"]


def test_fts_query_handles_natural_language_punctuation() -> None:
    query = build_fts_query("What command does Jordan use to run the test suite?")

    assert "What*" in query
    assert "suite*" in query
    assert "?" not in query


def test_vector_search_can_use_local_embedding_provider_shape() -> None:
    hits = retrieve_vector(
        question="How do tests run with pytest?",
        session_to_memory={"a": 1, "b": 2},
        session_texts={
            "a": "The project planning tool is Linear.",
            "b": "The test suite runs with pytest -q.",
        },
        embedder=FakeEmbeddingProvider(),
        limit=2,
        batch_size=2,
    )

    assert hits[0].session_id == "b"
    assert hits[0].source == "vector"


def test_hybrid_merge_keeps_best_sources() -> None:
    fts_hits = retrieve_vector(
        question="Linear",
        session_to_memory={"a": 1},
        session_texts={"a": "Linear planning"},
        embedder=FakeEmbeddingProvider(),
        limit=1,
        batch_size=1,
    )
    vector_hits = retrieve_vector(
        question="pytest",
        session_to_memory={"b": 2},
        session_texts={"b": "pytest -q"},
        embedder=FakeEmbeddingProvider(),
        limit=1,
        batch_size=1,
    )

    merged = merge_hybrid_hits(fts_hits, vector_hits, limit=2)

    assert {hit.session_id for hit in merged} == {"a", "b"}
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_gemini_configs_default_to_gemini_api_key_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    embedding_config = build_embedding_config("gemini", "", "", "")
    llm_config = build_llm_config("gemini", "", "", "")

    assert embedding_config["model"] == "gemini-embedding-2"
    assert embedding_config["api_key"] == "test-gemini-key"
    assert llm_config["model"] == "gemini-3-flash-preview"
    assert llm_config["api_key"] == "test-gemini-key"


def test_sample_longmemeval_benchmark_runs() -> None:
    results = run_benchmark(SAMPLE_DATASET, k_values=[1, 3], limit=2)

    assert results["benchmark"] == "LongMemEval retrieval"
    assert results["instances"] == 2
    assert results["overall"]["answerable_count"] == 2
    assert results["overall"]["recall@3"] > 0
    assert results["records"][0]["retrieved_session_ids"]


def test_longmemeval_report_outputs(tmp_path: Path) -> None:
    results = run_benchmark(SAMPLE_DATASET, k_values=[1, 3], limit=2)
    report_dir = tmp_path / "report"

    write_report(results, report_dir)

    assert (report_dir / "summary.md").exists()
    assert (report_dir / "results.json").exists()
    assert (report_dir / "records.jsonl").exists()
    assert (report_dir / "metrics.csv").exists()
    assert (report_dir / "charts" / "scorecard.svg").exists()
    assert (report_dir / "charts" / "recall_at_k.svg").exists()
    assert (report_dir / "charts" / "latency_ms.svg").exists()
