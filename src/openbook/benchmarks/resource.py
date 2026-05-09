"""Measure OpenBook's practical local resource footprint.

This benchmark intentionally uses only the Python standard library so it can run
from an installed package without API keys, Docker, or model downloads. It gives
users a quick baseline for the core local promise: SQLite size, write/search
latency, context-pack size, and process RSS when the platform exposes it.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sqlite3
import statistics
import string
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence, cast

_resource: Any | None
try:
    import resource as _resource
except ModuleNotFoundError:
    _resource = None


DEFAULT_MEMORIES = 100
DEFAULT_SEARCHES = 20
DEFAULT_CONTEXT_LIMIT = 20


@dataclass(frozen=True)
class Memory:
    title: str
    body: str
    tags: str


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


def latency_stats_ms(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "min": round(min(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "p50": round(percentile(values, 0.50), 3),
        "p95": round(percentile(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def generate_memories(count: int, seed: int) -> list[Memory]:
    rng = random.Random(seed)
    topics = [
        "agents",
        "context",
        "retrieval",
        "sqlite",
        "benchmark",
        "memory",
        "search",
        "pack",
    ]
    adjectives = ["small", "fresh", "durable", "portable", "local", "fast"]
    memories: list[Memory] = []
    for index in range(count):
        topic = topics[index % len(topics)]
        companion = topics[(index * 3 + 2) % len(topics)]
        marker = "".join(rng.choice(string.ascii_lowercase) for _ in range(10))
        title = f"{topic.title()} note {index:04d}"
        body = (
            f"{adjectives[index % len(adjectives)]} OpenBook memory {index} "
            f"tracks {topic}, {companion}, and deterministic marker {marker}. "
            f"This synthetic note gives search and context packing realistic text."
        )
        tags = f"{topic},{companion},synthetic"
        memories.append(Memory(title=title, body=body, tags=tags))
    return memories


def connect_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute(
        """
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            tags TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE VIRTUAL TABLE memory_fts USING fts5(
            title,
            body,
            tags,
            content='memories',
            content_rowid='id'
        )
        """
    )
    return connection


def insert_memories(connection: sqlite3.Connection, memories: Iterable[Memory]) -> list[float]:
    latencies: list[float] = []
    for memory in memories:
        started = time.perf_counter()
        cursor = connection.execute(
            "INSERT INTO memories (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
            (memory.title, memory.body, memory.tags, time.time()),
        )
        connection.execute(
            "INSERT INTO memory_fts (rowid, title, body, tags) VALUES (?, ?, ?, ?)",
            (cursor.lastrowid, memory.title, memory.body, memory.tags),
        )
        connection.commit()
        latencies.append((time.perf_counter() - started) * 1000)
    return latencies


def run_searches(connection: sqlite3.Connection, queries: Sequence[str]) -> list[float]:
    latencies: list[float] = []
    for query in queries:
        started = time.perf_counter()
        list(
            connection.execute(
                """
                SELECT memories.id, memories.title, memories.body
                FROM memory_fts
                JOIN memories ON memories.id = memory_fts.rowid
                WHERE memory_fts MATCH ?
                ORDER BY bm25(memory_fts)
                LIMIT 10
                """,
                (query,),
            )
        )
        latencies.append((time.perf_counter() - started) * 1000)
    return latencies


def build_context_pack(connection: sqlite3.Connection, limit: int) -> str:
    rows = connection.execute(
        """
        SELECT title, body, tags
        FROM memories
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    sections = [
        f"### {title}\nTags: {tags}\n{body}"
        for title, body, tags in reversed(rows)
    ]
    return "\n\n".join(sections)


def directory_size_bytes(path: Path) -> int:
    return sum(file.stat().st_size for file in path.iterdir() if file.is_file())


def process_memory() -> dict[str, int | None]:
    resource_module = cast(Any, _resource)
    if resource_module is None:
        return {"peak_rss_bytes": None}

    try:
        max_rss = resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss
    except (AttributeError, ValueError):
        return {"peak_rss_bytes": None}

    # Linux reports KiB, macOS reports bytes. Windows usually lacks resource.
    if platform.system() == "Darwin":
        peak_rss_bytes = int(max_rss)
    else:
        peak_rss_bytes = int(max_rss) * 1024
    return {"peak_rss_bytes": peak_rss_bytes}


def run_benchmark(
    *,
    memories: int,
    searches: int,
    context_limit: int,
    seed: int,
    work_dir: Path,
) -> dict[str, object]:
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = work_dir / "openbook_resource_benchmark.sqlite3"
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            sidecar.unlink()

    generated = generate_memories(memories, seed)
    connection = connect_database(db_path)
    try:
        insert_latencies = insert_memories(connection, generated)
        query_terms = ["memory", "context", "retrieval", "sqlite", "benchmark", "pack"]
        queries = [query_terms[index % len(query_terms)] for index in range(searches)]
        search_latencies = run_searches(connection, queries)
        context_pack = build_context_pack(connection, min(context_limit, memories))
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()

    db_size = directory_size_bytes(work_dir)
    context_pack_bytes = len(context_pack.encode("utf-8"))
    context_pack_chars = len(context_pack)
    return {
        "benchmark": "openbook-resource",
        "config": {
            "memories": memories,
            "searches": searches,
            "context_limit": context_limit,
            "seed": seed,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "database": {
            "path": str(db_path),
            "size_bytes": db_size,
            "bytes_per_memory": round(db_size / memories, 2),
        },
        "latency_ms": {
            "insert": latency_stats_ms(insert_latencies),
            "search": latency_stats_ms(search_latencies),
        },
        "context_pack": {
            "memories": min(context_limit, memories),
            "bytes": context_pack_bytes,
            "characters": context_pack_chars,
            "approx_tokens": max(1, context_pack_chars // 4),
        },
        "process_memory": process_memory(),
    }


def write_reports(results: dict[str, object], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    results_path = report_dir / "results.json"
    summary_path = report_dir / "summary.md"
    results_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(render_summary(results), encoding="utf-8")


def render_summary(results: dict[str, object]) -> str:
    config = cast(dict[str, Any], results["config"])
    database = cast(dict[str, Any], results["database"])
    latency = cast(dict[str, Any], results["latency_ms"])
    context_pack = cast(dict[str, Any], results["context_pack"])
    process = cast(dict[str, Any], results["process_memory"])
    peak_rss = process.get("peak_rss_bytes")
    peak_rss_text = "n/a" if peak_rss is None else f"{peak_rss:,} bytes"
    return (
        "# OpenBook Resource Benchmark\n\n"
        f"- Memories: {config['memories']}\n"
        f"- Searches: {config['searches']}\n"
        f"- Database size: {database['size_bytes']:,} bytes "
        f"({database['bytes_per_memory']} bytes/memory)\n"
        f"- Insert latency mean/p95: {latency['insert']['mean']} ms / "
        f"{latency['insert']['p95']} ms\n"
        f"- Search latency mean/p95: {latency['search']['mean']} ms / "
        f"{latency['search']['p95']} ms\n"
        f"- Context pack: {context_pack['bytes']:,} bytes, "
        f"~{context_pack['approx_tokens']:,} tokens\n"
        f"- Peak RSS: {peak_rss_text}\n"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OpenBook resource benchmark.")
    parser.add_argument("--memories", type=positive_int, default=DEFAULT_MEMORIES)
    parser.add_argument("--searches", type=positive_int, default=DEFAULT_SEARCHES)
    parser.add_argument("--context-limit", type=positive_int, default=DEFAULT_CONTEXT_LIMIT)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("benchmarks/resource/results/smoke"),
        help="Directory that receives summary.md and results.json.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional directory for benchmark scratch data. Defaults to a temporary directory.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="openbook-resource-") as temp_dir:
            results = run_benchmark(
                memories=args.memories,
                searches=args.searches,
                context_limit=args.context_limit,
                seed=args.seed,
                work_dir=Path(temp_dir),
            )
            write_reports(results, args.report_dir)
    else:
        results = run_benchmark(
            memories=args.memories,
            searches=args.searches,
            context_limit=args.context_limit,
            seed=args.seed,
            work_dir=args.work_dir,
        )
        write_reports(results, args.report_dir)

    print(f"Wrote {args.report_dir / 'summary.md'}")
    print(f"Wrote {args.report_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
