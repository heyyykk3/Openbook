"""OpenBook CLI entrypoint."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import click

from openbook.core.config import Config
from openbook.core.context_pack import build_context_pack
from openbook.core.db import get_connection, initialize_database
from openbook.core.exports import export_all, export_json
from openbook.core.memory import (
    approve_memory,
    delete_memory,
    get_review_queue,
    reject_memory,
    remember,
)
from openbook.core.mcp_install import install_mcp_client, mcp_config_document
from openbook.core.models import ContextPack
from openbook.core.project import detect_project_name, detect_project_root, detect_stack
from openbook.core.search import get_project_brief
from openbook.core.security import ensure_openbookignore
from openbook.benchmarks.resource import run_benchmark as run_resource_benchmark
from openbook.benchmarks.resource import write_reports as write_resource_reports
from openbook.providers.embeddings import get_embedding_provider
from openbook.providers.llm import get_llm_provider


def _get_project_root(path: Optional[str]) -> Path:
    if path:
        return Path(path).resolve()
    return detect_project_root()


def _lastrowid(cur: sqlite3.Cursor) -> int:
    if cur.lastrowid is None:
        raise RuntimeError("Insert did not return a row id")
    return int(cur.lastrowid)


def _get_or_create_project(conn: sqlite3.Connection, project_root: Path) -> int:
    root_str = str(project_root.resolve())
    row = conn.execute(
        "SELECT id FROM projects WHERE root_path = ?", (root_str,)
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO projects (root_path, name) VALUES (?, ?)",
        (root_str, detect_project_name(project_root)),
    )
    return _lastrowid(cur)


def _get_current_agent_id(conn: sqlite3.Connection, project_id: int) -> int:
    client = os.environ.get("OPENBOOK_CLIENT", "cli")
    agent_name = os.environ.get("OPENBOOK_AGENT", "openbook-cli")
    hostname = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
    row = conn.execute(
        "SELECT id FROM agents WHERE project_id = ? AND client_name = ? AND agent_name = ?",
        (project_id, client, agent_name),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE agents SET last_seen_at = ? WHERE id = ?",
            (time.time(), row["id"]),
        )
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO agents (project_id, client_name, agent_name, version, hostname, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, client, agent_name, "0.1.0", hostname, time.time(), time.time()),
    )
    return _lastrowid(cur)


def _get_or_create_session(conn: sqlite3.Connection, project_id: int, agent_id: int) -> int:
    pid = os.getpid()
    cwd = str(Path.cwd().resolve())
    client = os.environ.get("OPENBOOK_CLIENT", "cli")
    cur = conn.execute(
        "INSERT INTO sessions (project_id, agent_id, client_name, process_id, cwd, started_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
        (project_id, agent_id, client, pid, cwd, time.time()),
    )
    return _lastrowid(cur)


@click.group()
@click.version_option(version="0.1.0", prog_name="openbook")
def cli() -> None:
    """OpenBook: one folder, one shared memory book, every coding agent."""
    pass


@cli.command()
@click.argument("path", default=".")
def init(path: str) -> None:
    """Initialize .openbook in the given path."""
    project_root = _get_project_root(path)
    if not project_root.exists():
        click.echo(f"Path does not exist: {project_root}", err=True)
        sys.exit(1)

    initialize_database(project_root)
    Config.create_default(project_root)
    ensure_openbookignore(project_root)
    click.echo(f"Initialized OpenBook at {project_root / '.openbook'}")


@cli.command()
@click.option("--project", default=None, help="Project path. Defaults to detected repo root.")
@click.option("--client", multiple=True, help="MCP client to install after init.")
@click.option("--yes", is_flag=True, help="Run non-interactively.")
@click.option("--dry-run", is_flag=True, help="Preview MCP config changes without writing.")
def setup(
    project: Optional[str],
    client: tuple[str, ...],
    yes: bool,
    dry_run: bool,
) -> None:
    """Run guided setup wizard."""
    project_root = _get_project_root(project)
    click.echo("OpenBook Setup Wizard")
    click.echo(f"Detected project root: {project_root}")
    click.echo(f"Project name: {detect_project_name(project_root)}")
    click.echo(f"Stack: {', '.join(detect_stack(project_root)) or 'unknown'}")

    should_init = yes or click.confirm("Initialize OpenBook here?")
    if should_init:
        initialize_database(project_root)
        Config.create_default(project_root)
        ensure_openbookignore(project_root)
        click.echo("Initialized OpenBook.")
    else:
        click.echo("Aborted.")
        return

    for mcp_client in client:
        try:
            result = install_mcp_client(mcp_client, project_root, dry_run=dry_run)
        except (RuntimeError, ValueError) as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"MCP {result.client}: {result.mode} -> {result.target}")
        if result.mode == "dry-run":
            click.echo(result.message)

    click.echo("Done.")


@cli.command("remember")
@click.argument("content")
@click.option("--type", "memory_type", default="fact", help="Memory type")
@click.option("--chapter", default=None, help="Chapter name")
@click.option("--title", default=None, help="Memory title")
@click.option("--summary", default=None, help="Short summary")
@click.option("--tag", multiple=True, help="Tags")
@click.option("--trust", default=0.5, type=float, help="Trust score")
@click.option("--approve", is_flag=True, help="Auto-approve")
@click.option("--project", default=None, help="Project path")
def remember_cmd(
    content: str,
    memory_type: str,
    chapter: Optional[str],
    title: Optional[str],
    summary: Optional[str],
    tag: tuple[str, ...],
    trust: float,
    approve: bool,
    project: Optional[str],
) -> None:
    """Store a memory."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    agent_id = _get_current_agent_id(conn, project_id)

    status = "approved" if approve else "proposed"
    memory_id = remember(
        conn=conn,
        project_id=project_id,
        content=content,
        memory_type=memory_type,
        title=title,
        summary=summary,
        chapter=chapter,
        tags=list(tag),
        trust_score=trust,
        status=status,
        agent_id=agent_id,
    )
    click.echo(f"Stored memory {memory_id} ({status})")


@cli.command("search")
@click.argument("query")
@click.option("--budget", default="normal", type=click.Choice(["tiny", "normal", "deep"]))
@click.option("--chapter", default=None)
@click.option("--type", "memory_type", default=None)
@click.option("--tag", multiple=True)
@click.option("--raw", is_flag=True, help="Include raw excerpts")
@click.option("--project", default=None)
def search_cmd(
    query: str,
    budget: str,
    chapter: Optional[str],
    memory_type: Optional[str],
    tag: tuple[str, ...],
    raw: bool,
    project: Optional[str],
) -> None:
    """Search memory and return compact results."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    agent_id = _get_current_agent_id(conn, project_id)

    pack = build_context_pack(
        conn=conn,
        project_id=project_id,
        query=query,
        budget=budget,
        chapter=chapter,
        memory_type=memory_type,
        tags=list(tag),
        include_raw=raw,
        agent_id=agent_id,
    )
    click.echo(pack.to_text(include_raw=raw))


@cli.command("smoke-test")
@click.option("--project", default=None, help="Project path. Defaults to a temporary project.")
@click.option("--multi-agent", is_flag=True, help="Verify two simulated agents share one book.")
def smoke_test(project: Optional[str], multi_agent: bool) -> None:
    """Run a no-key init/write/search smoke test."""
    if project:
        _run_smoke_test(_get_project_root(project), multi_agent=multi_agent)
        return

    with tempfile.TemporaryDirectory(prefix="openbook-smoke-") as tmp:
        project_root = Path(tmp) / "repo"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "README.md").write_text("# OpenBook smoke test\n", encoding="utf-8")
        _run_smoke_test(project_root, multi_agent=multi_agent)


def _run_smoke_test(project_root: Path, *, multi_agent: bool = False) -> None:
    initialize_database(project_root)
    Config.create_default(project_root)
    ensure_openbookignore(project_root)
    conn = get_connection(project_root)
    try:
        project_id = _get_or_create_project(conn, project_root)
        if multi_agent:
            memory_id, pack = _run_multi_agent_smoke(project_root, project_id)
        else:
            memory_id = remember(
                conn=conn,
                project_id=project_id,
                content="OpenBook smoke test memory: tests run with pytest -q.",
                memory_type="command",
                title="Smoke test command",
                tags=["smoke-test"],
                status="approved",
            )
            pack = build_context_pack(conn, project_id, "pytest smoke test", budget="tiny")
    finally:
        conn.close()

    if not pack.cards:
        raise click.ClickException("Smoke test failed: search returned no memories")
    click.echo(f"OpenBook smoke test passed at {project_root}")
    click.echo(f"Stored memory: {memory_id}")
    click.echo(f"Retrieved memories: {len(pack.cards)}")
    if multi_agent:
        click.echo("Multi-agent check: writer=openbook-smoke-writer reader=openbook-smoke-reader")


def _run_multi_agent_smoke(project_root: Path, project_id: int) -> tuple[int, ContextPack]:
    previous = {
        "OPENBOOK_CLIENT": os.environ.get("OPENBOOK_CLIENT"),
        "OPENBOOK_AGENT": os.environ.get("OPENBOOK_AGENT"),
    }
    try:
        os.environ["OPENBOOK_CLIENT"] = "codex"
        os.environ["OPENBOOK_AGENT"] = "openbook-smoke-writer"
        writer_conn = get_connection(project_root)
        try:
            writer_agent_id = _get_current_agent_id(writer_conn, project_id)
            memory_id = remember(
                conn=writer_conn,
                project_id=project_id,
                content="OpenBook multi-agent smoke: shared SQLite memory works across clients.",
                memory_type="handoff",
                title="Multi-agent smoke handoff",
                tags=["smoke-test", "multi-agent"],
                status="approved",
                agent_id=writer_agent_id,
            )
        finally:
            writer_conn.close()

        os.environ["OPENBOOK_CLIENT"] = "cursor"
        os.environ["OPENBOOK_AGENT"] = "openbook-smoke-reader"
        reader_conn = get_connection(project_root)
        try:
            reader_agent_id = _get_current_agent_id(reader_conn, project_id)
            pack = build_context_pack(
                reader_conn,
                project_id,
                "shared SQLite memory across clients",
                budget="tiny",
                agent_id=reader_agent_id,
            )
        finally:
            reader_conn.close()
        return memory_id, pack
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@cli.group("benchmark")
def benchmark_group() -> None:
    """Run OpenBook benchmarks."""
    pass


@benchmark_group.command("list")
def benchmark_list() -> None:
    """List benchmark tracks."""
    click.echo("Available benchmark tracks:")
    click.echo("  resource    No-key SQLite footprint and latency benchmark")
    click.echo("  longmemeval External harness in benchmarks/longmemeval")


@benchmark_group.command("resource")
@click.option("--memories", type=int, default=100, show_default=True)
@click.option("--searches", type=int, default=20, show_default=True)
@click.option("--context-limit", type=int, default=20, show_default=True)
@click.option("--seed", type=int, default=1337, show_default=True)
@click.option(
    "--report-dir",
    type=click.Path(path_type=Path),
    default=Path("benchmarks/resource/results/openbook-resource"),
    show_default=True,
)
@click.option("--work-dir", type=click.Path(path_type=Path), default=None)
def benchmark_resource(
    memories: int,
    searches: int,
    context_limit: int,
    seed: int,
    report_dir: Path,
    work_dir: Optional[Path],
) -> None:
    """Run the no-key SQLite resource benchmark."""
    if memories < 1 or searches < 1 or context_limit < 1:
        raise click.ClickException("memories, searches, and context-limit must be at least 1")

    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="openbook-resource-") as temp_dir:
            results = run_resource_benchmark(
                memories=memories,
                searches=searches,
                context_limit=context_limit,
                seed=seed,
                work_dir=Path(temp_dir),
            )
            write_resource_reports(results, report_dir)
    else:
        results = run_resource_benchmark(
            memories=memories,
            searches=searches,
            context_limit=context_limit,
            seed=seed,
            work_dir=work_dir,
        )
        write_resource_reports(results, report_dir)

    click.echo(f"Wrote {report_dir / 'summary.md'}")
    click.echo(f"Wrote {report_dir / 'results.json'}")


@benchmark_group.command("longmemeval")
def benchmark_longmemeval() -> None:
    """Print how to run the LongMemEval harness from a source checkout."""
    click.echo("LongMemEval is the full memory benchmark track.")
    click.echo("Run it from a source checkout so the dataset and report templates are available:")
    click.echo(
        "python benchmarks/longmemeval/openbook_longmemeval.py "
        "--download s --retrieval-mode fts --k 1,3,5,10 "
        "--report-dir benchmarks/longmemeval/results/openbook-longmemeval-s"
    )
    click.echo("See benchmarks/README.md and docs/benchmarks.md for QA and provider examples.")


@cli.command("brief")
@click.option("--project", default=None)
def brief(project: Optional[str]) -> None:
    """Return a small project briefing."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    info = get_project_brief(conn, project_id)
    click.echo(f"# {info.get('project_name', 'Unknown')}")
    click.echo(f"Root: {info.get('root_path', '')}")
    click.echo("")
    if info.get("commands"):
        click.echo("## Commands")
        for m in info["commands"]:
            click.echo(f"- {m['summary']}")
        click.echo("")
    if info.get("warnings"):
        click.echo("## Warnings")
        for m in info["warnings"]:
            click.echo(f"- {m['summary']}")
        click.echo("")
    if info.get("decisions"):
        click.echo("## Decisions")
        for m in info["decisions"]:
            click.echo(f"- {m['summary']}")
        click.echo("")


@cli.command("handoff")
@click.option("--to", "to_hint", default=None, help="Target agent hint")
@click.option("--project", default=None)
def handoff_cmd(to_hint: Optional[str], project: Optional[str]) -> None:
    """Create a next-agent handoff context pack."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    agent_id = _get_current_agent_id(conn, project_id)
    session_id = _get_or_create_session(conn, project_id, agent_id)

    # Build a handoff pack: recent approved memories across key chapters
    pack = build_context_pack(
        conn=conn,
        project_id=project_id,
        query="handoff context",
        budget="tiny",
        agent_id=agent_id,
        session_id=str(session_id),
    )
    summary = pack.to_text()
    conn.execute(
        "INSERT INTO handoffs (project_id, from_agent_id, to_agent_hint, summary, context_pack_json) VALUES (?, ?, ?, ?, ?)",
        (project_id, agent_id, to_hint, summary, json.dumps({"cards": [c.memory_id for c in pack.cards]})),
    )
    click.echo(summary)


@cli.command("cite")
@click.option("--memory-id", type=int, required=True)
@click.option("--file", "file_path", default=None)
@click.option("--lines", default=None)
@click.option("--commit", default=None)
@click.option("--url", default=None)
@click.option("--quote", default=None)
@click.option("--project", default=None)
def cite_cmd(
    memory_id: int,
    file_path: Optional[str],
    lines: Optional[str],
    commit: Optional[str],
    url: Optional[str],
    quote: Optional[str],
    project: Optional[str],
) -> None:
    """Add a citation to a memory."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)

    line_start: Optional[int] = None
    line_end: Optional[int] = None
    if lines:
        parts = lines.split("-")
        line_start = int(parts[0])
        line_end = int(parts[1]) if len(parts) > 1 else line_start

    cur = conn.execute(
        """
        INSERT INTO citations (project_id, file_path, line_start, line_end, commit_hash, url, quote)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, file_path, line_start, line_end, commit, url, quote),
    )
    citation_id = cur.lastrowid
    conn.execute(
        "UPDATE memories SET citation_id = ? WHERE id = ? AND project_id = ?",
        (citation_id, memory_id, project_id),
    )
    click.echo(f"Added citation {citation_id} to memory {memory_id}")


@cli.command("review")
@click.option("--project", default=None)
def review(project: Optional[str]) -> None:
    """Show memory proposals waiting for approval."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    queue = get_review_queue(conn, project_id)
    if not queue:
        click.echo("No pending proposals.")
        return
    for item in queue:
        click.echo(f"[{item['id']}] {item['type']}: {item['summary'] or item['content'][:80]}")


@cli.command("approve")
@click.argument("memory_id", type=int)
@click.option("--project", default=None)
def approve_cmd(memory_id: int, project: Optional[str]) -> None:
    """Approve a memory proposal."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    if approve_memory(conn, project_id, memory_id):
        click.echo(f"Approved memory {memory_id}")
    else:
        click.echo(f"Memory {memory_id} not found.", err=True)
        sys.exit(1)


@cli.command("reject")
@click.argument("memory_id", type=int)
@click.option("--project", default=None)
def reject_cmd(memory_id: int, project: Optional[str]) -> None:
    """Reject a memory proposal."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    if reject_memory(conn, project_id, memory_id):
        click.echo(f"Rejected memory {memory_id}")
    else:
        click.echo(f"Memory {memory_id} not found.", err=True)
        sys.exit(1)


@cli.command("delete")
@click.argument("memory_id", type=int)
@click.option("--hard", is_flag=True, help="Physically delete instead of archiving.")
@click.option("--project", default=None)
def delete_cmd(memory_id: int, hard: bool, project: Optional[str]) -> None:
    """Archive or delete a memory."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    if delete_memory(conn, project_id, memory_id, hard=hard):
        action = "Deleted" if hard else "Archived"
        click.echo(f"{action} memory {memory_id}")
    else:
        click.echo(f"Memory {memory_id} not found.", err=True)
        sys.exit(1)


@cli.command("export")
@click.option("--json", "json_export", is_flag=True)
@click.option("--project", default=None)
@click.option("--output", default=None)
def export_cmd(json_export: bool, project: Optional[str], output: Optional[str]) -> None:
    """Generate Markdown/JSON human-readable exports."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)

    if json_export:
        data = export_json(conn, project_id, project_root)
        out = json.dumps(data, indent=2, default=str)
        if output:
            Path(output).write_text(out, encoding="utf-8")
            click.echo(f"Exported JSON to {output}")
        else:
            click.echo(out)
    else:
        out_dir = Path(output) if output else project_root / ".openbook" / "exports"
        paths = export_all(conn, project_id, project_root, out_dir)
        for name, path in paths.items():
            click.echo(f"Exported {name}: {path}")


@cli.command("doctor")
@click.option("--project", default=None)
def doctor(project: Optional[str]) -> None:
    """Check database, config, providers, MCP setup, and concurrency mode."""
    project_root = _get_project_root(project)
    click.echo(f"Project root: {project_root}")

    openbook_dir = project_root / ".openbook"
    click.echo(f".openbook exists: {openbook_dir.exists()}")

    db_path = openbook_dir / "openbook.sqlite"
    click.echo(f"Database exists: {db_path.exists()}")

    config_path = openbook_dir / "config.toml"
    click.echo(f"Config exists: {config_path.exists()}")

    if db_path.exists():
        conn = get_connection(project_root)
        try:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            click.echo(f"Journal mode: {row[0] if row else 'unknown'}")
            row = conn.execute("SELECT COUNT(*) FROM projects").fetchone()
            click.echo(f"Projects: {row[0]}")
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            click.echo(f"Memories: {row[0]}")
            row = conn.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'pending'").fetchone()
            click.echo(f"Pending reviews: {row[0]}")
        except Exception as e:
            click.echo(f"Database error: {e}", err=True)

    config = Config.load(project_root)
    embed_provider = get_embedding_provider(config.section("embeddings"))
    click.echo(f"Embedding provider: {embed_provider.name}")
    click.echo(f"Embedding health: {embed_provider.health_check()}")

    llm_provider = get_llm_provider(config.section("llm"))
    click.echo(f"LLM provider: {llm_provider.name}")
    click.echo(f"LLM health: {llm_provider.health_check()}")

    ignore_path = project_root / ".openbookignore"
    click.echo(f".openbookignore exists: {ignore_path.exists()}")


@cli.command("prune")
@click.option("--older-than-days", type=int, default=90)
@click.option("--min-trust", type=float, default=0.0)
@click.option("--dry-run", is_flag=True)
@click.option("--project", default=None)
def prune(older_than_days: int, min_trust: float, dry_run: bool, project: Optional[str]) -> None:
    """Remove stale, duplicate, or low-value memories."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    cutoff = time.time() - (older_than_days * 86400)

    sql = "SELECT id, content FROM memories WHERE project_id = ? AND updated_at < ? AND trust_score < ? AND status != 'archived'"
    rows = conn.execute(sql, (project_id, cutoff, min_trust)).fetchall()
    click.echo(f"Found {len(rows)} memories to prune")
    if dry_run:
        for r in rows:
            click.echo(f"Would prune: {r['id']} {r['content'][:60]}")
        return
    for r in rows:
        conn.execute("UPDATE memories SET status = 'archived', updated_at = ? WHERE id = ?", (time.time(), r["id"]))
    click.echo(f"Pruned {len(rows)} memories")


@cli.command("reindex")
@click.option("--project", default=None)
def reindex(project: Optional[str]) -> None:
    """Rebuild FTS/vector indexes."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    _get_or_create_project(conn, project_root)

    # Rebuild FTS
    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
    click.echo("FTS index rebuilt.")

    # Optionally reindex vectors if sqlite-vec is available
    try:
        conn.execute("SELECT vec_version()")
        click.echo("sqlite-vec is available; vector reindex not yet implemented in MVP.")
    except Exception:
        click.echo("sqlite-vec not available; vector search disabled.")


@cli.group("providers")
def providers_group() -> None:
    """List and test providers."""
    pass


@providers_group.command("list")
def providers_list() -> None:
    """List embedding and LLM providers."""
    click.echo("Embedding providers:")
    click.echo("  - none")
    click.echo("  - ollama")
    click.echo("  - openai-compatible")
    click.echo("  - gemini")
    click.echo("  - sentence-transformers")
    click.echo("")
    click.echo("LLM providers:")
    click.echo("  - none")
    click.echo("  - ollama")
    click.echo("  - openai-compatible")
    click.echo("  - gemini")


@providers_group.command("test")
@click.option("--project", default=None)
def providers_test(project: Optional[str]) -> None:
    """Test configured providers."""
    project_root = _get_project_root(project)
    config = Config.load(project_root)
    embed_provider = get_embedding_provider(config.section("embeddings"))
    llm_provider = get_llm_provider(config.section("llm"))
    click.echo(f"Embedding: {embed_provider.health_check()}")
    click.echo(f"LLM: {llm_provider.health_check()}")


@cli.command("agents")
@click.option("--project", default=None)
def agents_cmd(project: Optional[str]) -> None:
    """Show active/recent agent sessions."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    rows = conn.execute(
        "SELECT * FROM agents WHERE project_id = ? ORDER BY last_seen_at DESC LIMIT 20",
        (project_id,),
    ).fetchall()
    for r in rows:
        click.echo(f"[{r['id']}] {r['client_name']} / {r['agent_name']} @ {r['hostname']} (last seen {r['last_seen_at']})")


@cli.command("sessions")
@click.option("--project", default=None)
def sessions_cmd(project: Optional[str]) -> None:
    """Show session history."""
    project_root = _get_project_root(project)
    conn = get_connection(project_root)
    project_id = _get_or_create_project(conn, project_root)
    rows = conn.execute(
        "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC LIMIT 20",
        (project_id,),
    ).fetchall()
    for r in rows:
        click.echo(f"[{r['id']}] pid={r['process_id']} cwd={r['cwd']} status={r['status']} started={r['started_at']}")


@cli.group("runtime")
def runtime_group() -> None:
    """Optional runtime daemon controls."""
    pass


@runtime_group.command("start")
@click.option("--project", default=None)
def runtime_start(project: Optional[str]) -> None:
    """Start runtime daemon (MVP: not implemented)."""
    click.echo("Runtime daemon start is not implemented in MVP. Direct SQLite access is the default.")


@runtime_group.command("stop")
def runtime_stop() -> None:
    """Stop runtime daemon (MVP: not implemented)."""
    click.echo("Runtime daemon stop is not implemented in MVP.")


@runtime_group.command("status")
def runtime_status() -> None:
    """Check runtime daemon status (MVP: not implemented)."""
    click.echo("Runtime daemon status: not running (direct mode)")


class DefaultGroup(click.Group):
    def invoke(self, ctx: click.Context) -> None:
        if ctx.args or ctx.invoked_subcommand:
            super().invoke(ctx)
            return
        # Default: run MCP server
        ctx.invoke(mcp_server_cmd)


@cli.group("mcp", cls=DefaultGroup, invoke_without_command=True)
def mcp_group() -> None:
    """MCP helpers and stdio server."""
    pass


@mcp_group.command("install")
@click.option("--client", default=None)
@click.option("--project", default=None, help="Project to pin in the MCP server env.")
@click.option("--dry-run", is_flag=True, help="Print the config/command without writing.")
@click.option("--config-path", type=click.Path(path_type=Path), default=None, help="Override client config path.")
def mcp_install(
    client: Optional[str],
    project: Optional[str],
    dry_run: bool,
    config_path: Optional[Path],
) -> None:
    """Install MCP config for Codex, Claude Code, Claude Desktop, or Cursor."""
    project_root = _get_project_root(project)
    try:
        result = install_mcp_client(
            client or "generic",
            project_root,
            dry_run=dry_run,
            config_path=config_path,
        )
    except (RuntimeError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Client: {result.client}")
    click.echo(f"Mode: {result.mode}")
    click.echo(f"Target: {result.target}")
    click.echo(result.message)


@mcp_group.command("print-config")
def mcp_print_config() -> None:
    """Print MCP config."""
    click.echo(json.dumps(mcp_config_document(detect_project_root(), "generic"), indent=2))


@mcp_group.command("run")
def mcp_server_cmd() -> None:
    """Run MCP stdio server."""
    from openbook.mcp.server import run_mcp_server
    run_mcp_server()


if __name__ == "__main__":
    cli()
