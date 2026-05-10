"""No-key coding-agent repo memory benchmark for OpenBook."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sqlite3
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from openbook import __version__
from openbook.core.config import Config
from openbook.core.context_pack import build_context_pack
from openbook.core.db import get_connection, initialize_database
from openbook.core.memory import delete_memory, remember
from openbook.core.security import ensure_openbookignore


DEFAULT_REPORT_DIR = Path("benchmarks/repo-memory/results/openbook-repo-memory")


@dataclass(frozen=True)
class SeedMemory:
    key: str
    content: str
    memory_type: str
    chapter: str
    title: str
    tags: list[str]
    file_path: str
    line_start: int
    line_end: int
    writer: str
    status: str = "approved"


@dataclass(frozen=True)
class RepoTask:
    task_id: str
    category: str
    query: str
    expected_keys: list[str]
    unexpected_keys: list[str]
    reader: str


SEED_MEMORIES = [
    SeedMemory(
        key="test-command",
        content="Run the Python test suite with .\\.venv\\Scripts\\python.exe -m pytest -q.",
        memory_type="command",
        chapter="commands",
        title="Python test command",
        tags=["tests", "pytest", "windows"],
        file_path="README.md",
        line_start=28,
        line_end=33,
        writer="codex",
    ),
    SeedMemory(
        key="db-decision",
        content=(
            "SQLite is the source of truth for OpenBook memory. Markdown and JSON files are "
            "exports, not the primary memory store."
        ),
        memory_type="decision",
        chapter="decisions",
        title="SQLite source of truth",
        tags=["sqlite", "architecture", "storage"],
        file_path="docs/architecture.md",
        line_start=12,
        line_end=20,
        writer="claude-code",
    ),
    SeedMemory(
        key="mcp-project-pin",
        content=(
            "MCP installs must set OPENBOOK_PROJECT so each client opens the correct repo "
            "memory book even when launched from another working directory."
        ),
        memory_type="warning",
        chapter="handoffs",
        title="Project-pinned MCP config",
        tags=["mcp", "setup", "agents"],
        file_path="docs/mcp.md",
        line_start=5,
        line_end=12,
        writer="cursor",
    ),
    SeedMemory(
        key="frontend-convention",
        content=(
            "Frontend task surfaces should be dense, restrained, and workflow-focused; do "
            "not turn operational tools into marketing landing pages."
        ),
        memory_type="convention",
        chapter="conventions",
        title="Operational frontend style",
        tags=["frontend", "design", "convention"],
        file_path="AGENTS.md",
        line_start=40,
        line_end=55,
        writer="codex",
    ),
    SeedMemory(
        key="timeout-failure",
        content=(
            "Long provider-backed benchmarks can hit read timeouts; rerun with the same "
            "report directory because checkpoint.records.jsonl resumes completed items."
        ),
        memory_type="failure",
        chapter="failures",
        title="Benchmark timeout recovery",
        tags=["benchmark", "checkpoint", "timeout"],
        file_path="benchmarks/README.md",
        line_start=52,
        line_end=70,
        writer="gemini-cli",
    ),
    SeedMemory(
        key="handoff-memory",
        content=(
            "Before handing off to another coding agent, run openbook handoff so the next "
            "agent gets a compact context pack instead of rereading all project docs."
        ),
        memory_type="handoff",
        chapter="handoffs",
        title="Use handoff packs",
        tags=["handoff", "agents", "context"],
        file_path="docs/slash-commands.md",
        line_start=18,
        line_end=30,
        writer="opencode",
    ),
    SeedMemory(
        key="provider-defaults",
        content=(
            "Gemini provider examples use gemini-embedding-2 for embeddings, "
            "gemini-3-flash-preview for the reader, and gemini-3.1-pro-preview for judging."
        ),
        memory_type="dependency",
        chapter="dependencies",
        title="Gemini benchmark provider defaults",
        tags=["gemini", "provider", "benchmark"],
        file_path="docs/providers.md",
        line_start=40,
        line_end=98,
        writer="codex",
    ),
    SeedMemory(
        key="release-key-rotation",
        content=(
            "Before public release, rotate temporary benchmark API keys and confirm no key "
            "appears in tracked files or published benchmark artifacts."
        ),
        memory_type="warning",
        chapter="security",
        title="Rotate benchmark keys before release",
        tags=["release", "security", "api-key"],
        file_path="docs/releasing.md",
        line_start=20,
        line_end=26,
        writer="claude-code",
    ),
    SeedMemory(
        key="published-benchmark-artifacts",
        content=(
            "Clean public benchmark reports live under benchmarks/published; scratch runs "
            "under benchmarks/**/results are ignored."
        ),
        memory_type="fact",
        chapter="tests",
        title="Published benchmark artifact location",
        tags=["benchmark", "artifacts", "reports"],
        file_path="benchmarks/README.md",
        line_start=10,
        line_end=18,
        writer="cursor",
    ),
    SeedMemory(
        key="no-docker-default",
        content=(
            "The default OpenBook path requires no Docker, no external vector database, "
            "and no model provider account; SQLite FTS works with no API key."
        ),
        memory_type="fact",
        chapter="architecture",
        title="No-service default path",
        tags=["sqlite", "fts", "local-first"],
        file_path="docs/installation.md",
        line_start=3,
        line_end=8,
        writer="codex",
    ),
    SeedMemory(
        key="old-test-command",
        content="Outdated note: use npm test for the project test suite.",
        memory_type="command",
        chapter="commands",
        title="Old test command",
        tags=["tests", "stale"],
        file_path="README.md",
        line_start=1,
        line_end=1,
        writer="legacy-agent",
        status="approved",
    ),
    SeedMemory(
        key="old-vector-requirement",
        content="Outdated note: OpenBook requires Qdrant and Docker for every search.",
        memory_type="fact",
        chapter="architecture",
        title="Old vector database requirement",
        tags=["stale", "docker", "vector"],
        file_path="README.md",
        line_start=1,
        line_end=1,
        writer="legacy-agent",
        status="approved",
    ),
    SeedMemory(
        key="noise-marketing-site",
        content=(
            "A marketing landing page can use large hero imagery, but operational coding "
            "tools should prioritize compact task surfaces."
        ),
        memory_type="convention",
        chapter="conventions",
        title="Marketing page exception",
        tags=["frontend", "noise"],
        file_path="AGENTS.md",
        line_start=60,
        line_end=70,
        writer="legacy-agent",
        status="approved",
    ),
    SeedMemory(
        key="quarantined-secret",
        content="password: benchmark_fixture_value should never be retrieved as useful context.",
        memory_type="fact",
        chapter="security",
        title="Quarantined secret fixture",
        tags=["security", "secret"],
        file_path=".env",
        line_start=1,
        line_end=1,
        writer="legacy-agent",
        status="approved",
    ),
]


TASKS = [
    RepoTask(
        task_id="command-recall",
        category="command",
        query="What command should the next agent run for Python tests?",
        expected_keys=["test-command"],
        unexpected_keys=["old-test-command"],
        reader="cursor",
    ),
    RepoTask(
        task_id="storage-decision",
        category="decision",
        query="Is SQLite or Markdown the source of truth for OpenBook memory?",
        expected_keys=["db-decision"],
        unexpected_keys=[],
        reader="codex",
    ),
    RepoTask(
        task_id="mcp-setup-gotcha",
        category="setup",
        query="Why should MCP config pin the project path?",
        expected_keys=["mcp-project-pin"],
        unexpected_keys=[],
        reader="claude-code",
    ),
    RepoTask(
        task_id="frontend-convention",
        category="convention",
        query="How should operational frontend task surfaces be styled?",
        expected_keys=["frontend-convention"],
        unexpected_keys=[],
        reader="codex",
    ),
    RepoTask(
        task_id="benchmark-timeout",
        category="failure",
        query="What should I do if a long provider benchmark times out?",
        expected_keys=["timeout-failure"],
        unexpected_keys=[],
        reader="gemini-cli",
    ),
    RepoTask(
        task_id="handoff-cross-agent",
        category="handoff",
        query="What should one coding agent do before handing off to another agent?",
        expected_keys=["handoff-memory"],
        unexpected_keys=[],
        reader="cursor",
    ),
    RepoTask(
        task_id="secret-exclusion",
        category="security",
        query="Should a benchmark secret password appear in retrieved useful context?",
        expected_keys=[],
        unexpected_keys=["quarantined-secret"],
        reader="codex",
    ),
    RepoTask(
        task_id="provider-defaults",
        category="provider",
        query="Which Gemini models should the benchmark examples use for embeddings reader and judge?",
        expected_keys=["provider-defaults"],
        unexpected_keys=[],
        reader="claude-code",
    ),
    RepoTask(
        task_id="release-key-rotation",
        category="release",
        query="What must happen to temporary benchmark API keys before public release?",
        expected_keys=["release-key-rotation"],
        unexpected_keys=[],
        reader="codex",
    ),
    RepoTask(
        task_id="published-artifacts",
        category="benchmark",
        query="Where should clean benchmark reports live, and which scratch outputs are ignored?",
        expected_keys=["published-benchmark-artifacts"],
        unexpected_keys=[],
        reader="cursor",
    ),
    RepoTask(
        task_id="no-service-default",
        category="setup",
        query="Does the default OpenBook path require Docker, an external vector DB, or an API key?",
        expected_keys=["no-docker-default"],
        unexpected_keys=["old-vector-requirement"],
        reader="opencode",
    ),
]


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def percentile(values: Sequence[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def mean(values: Sequence[float]) -> float:
    return round(float(statistics.fmean(values)), 4) if values else 0.0


def latency_stats(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "mean": round(float(statistics.fmean(values)), 3),
        "p50": round(percentile(values, 0.50), 3),
        "p95": round(percentile(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def run_benchmark(*, work_dir: Path, top_k: int = 3) -> dict[str, Any]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    project_root = prepare_project(work_dir)
    conn = get_connection(project_root)
    try:
        project_id = get_project_id(conn, project_root)
        agents = {name: get_or_create_agent(conn, project_id, name) for name in agent_names()}
        key_to_memory_id = ingest_seed_memories(conn, project_id, agents)
        archive_stale_fixture(conn, project_id, key_to_memory_id)
        records = run_tasks(conn, project_id, agents, key_to_memory_id, top_k)
    finally:
        conn.close()

    return {
        "benchmark": "openbook-repo-memory",
        "description": "No-key coding-agent repo memory retrieval benchmark.",
        "openbook_version": __version__,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "config": {
            "top_k": top_k,
            "tasks": len(TASKS),
            "seed_memories": len(SEED_MEMORIES),
            "work_dir": str(work_dir),
        },
        "overall": summarize(records),
        "by_category": summarize_by_category(records),
        "records": records,
    }


def prepare_project(work_dir: Path) -> Path:
    project_root = work_dir / "repo-memory-project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / ".git").mkdir(exist_ok=True)
    (project_root / "README.md").write_text("# Repo Memory Benchmark\n", encoding="utf-8")
    (project_root / "docs").mkdir(exist_ok=True)
    (project_root / "docs" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    initialize_database(project_root)
    Config.create_default(project_root)
    ensure_openbookignore(project_root)
    return project_root


def get_project_id(conn: sqlite3.Connection, project_root: Path) -> int:
    row = conn.execute(
        "SELECT id FROM projects WHERE root_path = ?",
        (str(project_root.resolve()),),
    ).fetchone()
    if row is None:
        raise RuntimeError("Benchmark project was not initialized")
    return int(row["id"])


def agent_names() -> set[str]:
    names = {memory.writer for memory in SEED_MEMORIES}
    names.update(task.reader for task in TASKS)
    return names


def get_or_create_agent(conn: sqlite3.Connection, project_id: int, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM agents WHERE project_id = ? AND client_name = ? AND agent_name = ?",
        (project_id, name, f"{name}-benchmark"),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO agents (project_id, client_name, agent_name, version, hostname, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, name, f"{name}-benchmark", __version__, "benchmark", time.time(), time.time()),
    )
    if cur.lastrowid is None:
        raise RuntimeError("Agent insert did not return id")
    return int(cur.lastrowid)


def ingest_seed_memories(
    conn: sqlite3.Connection,
    project_id: int,
    agents: dict[str, int],
) -> dict[str, int]:
    key_to_memory_id: dict[str, int] = {}
    for item in SEED_MEMORIES:
        citation_id = insert_citation(conn, project_id, item)
        memory_id = remember(
            conn=conn,
            project_id=project_id,
            content=item.content,
            memory_type=item.memory_type,
            chapter=item.chapter,
            title=item.title,
            tags=item.tags,
            status=item.status,
            trust_score=0.85,
            importance=0.8,
            citation_id=citation_id,
            agent_id=agents[item.writer],
            idempotency_key=f"repo-memory::{item.key}",
        )
        key_to_memory_id[item.key] = memory_id
    return key_to_memory_id


def insert_citation(conn: sqlite3.Connection, project_id: int, item: SeedMemory) -> int:
    cur = conn.execute(
        """
        INSERT INTO citations (project_id, file_path, line_start, line_end, quote)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, item.file_path, item.line_start, item.line_end, item.content[:240]),
    )
    if cur.lastrowid is None:
        raise RuntimeError("Citation insert did not return id")
    return int(cur.lastrowid)


def archive_stale_fixture(
    conn: sqlite3.Connection,
    project_id: int,
    key_to_memory_id: dict[str, int],
) -> None:
    delete_memory(conn, project_id, key_to_memory_id["old-test-command"])
    delete_memory(conn, project_id, key_to_memory_id["old-vector-requirement"])


def run_tasks(
    conn: sqlite3.Connection,
    project_id: int,
    agents: dict[str, int],
    key_to_memory_id: dict[str, int],
    top_k: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for task in TASKS:
        started = time.perf_counter()
        pack = build_context_pack(
            conn=conn,
            project_id=project_id,
            query=task.query,
            budget="normal",
            agent_id=agents[task.reader],
        )
        latency_ms = (time.perf_counter() - started) * 1000
        retrieved_ids = [card.memory_id for card in pack.cards[:top_k]]
        expected_ids = [key_to_memory_id[key] for key in task.expected_keys]
        unexpected_ids = [key_to_memory_id[key] for key in task.unexpected_keys]
        expected_ranks = {
            memory_id: retrieved_ids.index(memory_id) + 1
            for memory_id in expected_ids
            if memory_id in retrieved_ids
        }
        first_rank = min(expected_ranks.values()) if expected_ranks else None
        unexpected_present = [memory_id for memory_id in unexpected_ids if memory_id in retrieved_ids]
        expected_cards = [card for card in pack.cards[:top_k] if card.memory_id in expected_ids]
        citation_present = bool(expected_cards) and all(bool(card.citation) for card in expected_cards)
        if not expected_ids:
            hit_at_1 = 1.0 if not unexpected_present else 0.0
            hit_at_k = hit_at_1
            mrr = hit_at_1
            citation_score = 1.0
        else:
            hit_at_1 = 1.0 if retrieved_ids[:1] and retrieved_ids[0] in expected_ids else 0.0
            hit_at_k = 1.0 if expected_ranks else 0.0
            mrr = (1.0 / first_rank) if first_rank else 0.0
            citation_score = 1.0 if citation_present else 0.0
        records.append(
            {
                "task_id": task.task_id,
                "category": task.category,
                "query": task.query,
                "reader": task.reader,
                "expected_memory_ids": expected_ids,
                "unexpected_memory_ids": unexpected_ids,
                "retrieved_memory_ids": retrieved_ids,
                "expected_ranks": expected_ranks,
                "unexpected_present": unexpected_present,
                "metrics": {
                    "hit@1": hit_at_1,
                    f"hit@{top_k}": hit_at_k,
                    "mrr": mrr,
                    "citation_presence": citation_score,
                    "stale_or_secret_excluded": 1.0 if not unexpected_present else 0.0,
                },
                "timing_ms": round(latency_ms, 3),
                "context_tokens": pack.total_tokens,
                "cards": [
                    {
                        "rank": card.rank,
                        "memory_id": card.memory_id,
                        "summary": card.summary,
                        "citation": card.citation,
                        "trust": card.trust,
                    }
                    for card in pack.cards[:top_k]
                ],
            }
        )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(record["timing_ms"]) for record in records]
    tokens = [float(record["context_tokens"]) for record in records]
    metric_names = sorted({name for record in records for name in record["metrics"]})
    summary = {
        "task_count": len(records),
        "latency_ms": latency_stats(latencies),
        "mean_context_tokens": round(mean(tokens), 2),
    }
    for name in metric_names:
        summary[name] = mean([float(record["metrics"].get(name, 0.0)) for record in records])
    return summary


def summarize_by_category(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["category"]), []).append(record)
    return {category: summarize(items) for category, items in sorted(grouped.items())}


def write_reports(results: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = report_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    with (report_dir / "records.jsonl").open("w", encoding="utf-8") as f:
        for record in results["records"]:
            f.write(json.dumps(record) + "\n")
    write_metrics_csv(results, report_dir / "metrics.csv")
    write_scorecard(charts_dir / "scorecard.svg", results)
    (report_dir / "summary.md").write_text(render_summary(results), encoding="utf-8")


def write_metrics_csv(results: dict[str, Any], path: Path) -> None:
    fields = ["group", "task_count", "hit@1", "hit@3", "mrr", "citation_presence", "stale_or_secret_excluded"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(summary_row("overall", results["overall"], fields))
        for category, summary in results["by_category"].items():
            writer.writerow(summary_row(category, summary, fields))


def summary_row(group: str, summary: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    row = {field: summary.get(field, "") for field in fields}
    row["group"] = group
    return row


def render_summary(results: dict[str, Any]) -> str:
    overall = results["overall"]
    lines = [
        "# OpenBook Repo Memory Benchmark",
        "",
        "Track: coding-agent repo memory",
        f"OpenBook version: `{results['openbook_version']}`",
        f"Tasks: **{overall['task_count']}**",
        "",
        "## Headline Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Hit@1 | {format_percent(overall['hit@1'])} |",
        f"| Hit@3 | {format_percent(overall['hit@3'])} |",
        f"| MRR | {overall['mrr']:.4f} |",
        f"| Citation presence | {format_percent(overall['citation_presence'])} |",
        f"| Stale/secret excluded | {format_percent(overall['stale_or_secret_excluded'])} |",
        f"| Mean context tokens | {overall['mean_context_tokens']:.2f} |",
        f"| Search latency mean/p95 | {overall['latency_ms']['mean']} ms / {overall['latency_ms']['p95']} ms |",
        "",
        "## By Category",
        "",
        "| Category | Tasks | Hit@3 | MRR | Citation | Exclusion |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category, summary in results["by_category"].items():
        lines.append(
            "| "
            f"{category} | "
            f"{summary['task_count']} | "
            f"{format_percent(summary['hit@3'])} | "
            f"{summary['mrr']:.4f} | "
            f"{format_percent(summary['citation_presence'])} | "
            f"{format_percent(summary['stale_or_secret_excluded'])} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This is a no-key local benchmark. It measures whether OpenBook retrieves "
            "repo-scoped coding memories across simulated agents, includes citations, "
            "and excludes archived or quarantined memory. It is not comparable to "
            "LoCoMo, LongMemEval, or BEAM scores.",
            "",
            "## Artifacts",
            "",
            "- `results.json`",
            "- `records.jsonl`",
            "- `metrics.csv`",
            "- `charts/scorecard.svg`",
            "",
        ]
    )
    return "\n".join(lines)


def write_scorecard(path: Path, results: dict[str, Any]) -> None:
    overall = results["overall"]
    bars = [
        ("HIT@1", float(overall["hit@1"])),
        ("HIT@3", float(overall["hit@3"])),
        ("MRR", float(overall["mrr"])),
        ("CITATION", float(overall["citation_presence"])),
        ("EXCLUSION", float(overall["stale_or_secret_excluded"])),
    ]
    width = 900
    left = 180
    right = 80
    top = 72
    row_height = 54
    bar_height = 28
    chart_width = width - left - right
    height = top + len(bars) * row_height + 42
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="OpenBook repo memory benchmark scorecard">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#111827}",
        ".title{font-size:24px;font-weight:800}",
        ".label{font-size:15px;font-weight:700}",
        ".value{font-size:15px;font-weight:800}",
        ".bg{fill:#eef2f7}",
        ".bar{fill:#0f766e}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        '<text class="title" x="28" y="38">OpenBook Repo Memory Scorecard</text>',
    ]
    for index, (label, value) in enumerate(bars):
        y = top + index * row_height
        clamped = max(0.0, min(1.0, value))
        bar_width = int(clamped * chart_width)
        parts.extend(
            [
                f'<text class="label" x="28" y="{y + 20}">{label}</text>',
                f'<rect class="bg" x="{left}" y="{y}" width="{chart_width}" height="{bar_height}" rx="3"/>',
                f'<rect class="bar" x="{left}" y="{y}" width="{bar_width}" height="{bar_height}" rx="3"/>',
                f'<text class="value" x="{left + chart_width + 16}" y="{y + 20}">{clamped * 100:.1f}</text>',
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def format_percent(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OpenBook repo memory benchmark.")
    parser.add_argument("--top-k", type=positive_int, default=3)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--work-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="openbook-repo-memory-") as temp_dir:
            results = run_benchmark(work_dir=Path(temp_dir), top_k=args.top_k)
            write_reports(results, args.report_dir)
    else:
        results = run_benchmark(work_dir=args.work_dir, top_k=args.top_k)
        write_reports(results, args.report_dir)
    print(f"Wrote {args.report_dir / 'summary.md'}")
    print(f"Wrote {args.report_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
