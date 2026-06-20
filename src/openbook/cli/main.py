"""OpenBook CLI entrypoint."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from openbook.core.config import Config
from openbook.core.mcp_install import install_mcp_client, mcp_config_document
from openbook.core.project import detect_project_name, detect_project_root, detect_stack
from openbook.benchmarks.repo_memory import run_benchmark as run_repo_memory_benchmark
from openbook.benchmarks.repo_memory import write_reports as write_repo_memory_reports
from openbook.benchmarks.resource import run_benchmark as run_resource_benchmark
from openbook.benchmarks.resource import write_reports as write_resource_reports
from openbook.providers.embeddings import get_embedding_provider
from openbook.providers.llm import get_llm_provider
from openbook.server.service import OpenBookService


def _get_project_root(path: Optional[str]) -> Path:
    if path:
        return Path(path).resolve()
    return detect_project_root()


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

    OpenBookService(project_root).initialize()
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
        OpenBookService(project_root).initialize()
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
    status = "approved" if approve else "proposed"
    stored = OpenBookService(_get_project_root(project)).remember(
        content=content,
        memory_type=memory_type,
        title=title,
        summary=summary,
        chapter=chapter,
        tags=list(tag),
        trust_score=trust,
        status=status,
    )
    click.echo(f"Stored memory {stored['memory_id']} ({status})")


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
    pack = OpenBookService(_get_project_root(project)).search(
        query=query,
        budget=budget,
        chapter=chapter,
        memory_type=memory_type,
        tags=list(tag),
        include_raw=raw,
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
    if multi_agent:
        stored = OpenBookService(
            project_root,
            client="codex",
            agent_name="openbook-smoke-writer",
        ).remember(
            content="OpenBook multi-agent smoke: shared service memory works across clients.",
            memory_type="handoff",
            title="Multi-agent smoke handoff",
            tags=["smoke-test", "multi-agent"],
            status="approved",
        )
        pack = OpenBookService(
            project_root,
            client="cursor",
            agent_name="openbook-smoke-reader",
        ).search("shared service memory across clients", budget="tiny")
    else:
        stored = OpenBookService(project_root).remember(
            content="OpenBook smoke test memory: tests run with pytest -q.",
            memory_type="command",
            title="Smoke test command",
            tags=["smoke-test"],
            status="approved",
        )
        pack = OpenBookService(project_root).search("pytest smoke test", budget="tiny")

    if not pack.cards:
        raise click.ClickException("Smoke test failed: search returned no memories")
    click.echo(f"OpenBook smoke test passed at {project_root}")
    click.echo(f"Stored memory: {stored['memory_id']}")
    click.echo(f"Retrieved memories: {len(pack.cards)}")
    if multi_agent:
        click.echo("Multi-agent check: writer=openbook-smoke-writer reader=openbook-smoke-reader")


@cli.group("benchmark")
def benchmark_group() -> None:
    """Run OpenBook benchmarks."""
    pass


@benchmark_group.command("list")
def benchmark_list() -> None:
    """List benchmark tracks."""
    click.echo("Available benchmark tracks:")
    click.echo("  repo-memory No-key coding-agent repo memory benchmark")
    click.echo("  resource    No-key SQLite footprint and latency benchmark")
    click.echo("  longmemeval External harness in benchmarks/longmemeval")


@benchmark_group.command("repo-memory")
@click.option("--top-k", type=int, default=3, show_default=True)
@click.option(
    "--report-dir",
    type=click.Path(path_type=Path),
    default=Path("benchmarks/repo-memory/results/openbook-repo-memory"),
    show_default=True,
)
@click.option("--work-dir", type=click.Path(path_type=Path), default=None)
def benchmark_repo_memory(top_k: int, report_dir: Path, work_dir: Optional[Path]) -> None:
    """Run the no-key coding-agent repo memory benchmark."""
    if top_k < 1:
        raise click.ClickException("top-k must be at least 1")
    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="openbook-repo-memory-") as temp_dir:
            results = run_repo_memory_benchmark(work_dir=Path(temp_dir), top_k=top_k)
            write_repo_memory_reports(results, report_dir)
    else:
        results = run_repo_memory_benchmark(work_dir=work_dir, top_k=top_k)
        write_repo_memory_reports(results, report_dir)

    click.echo(f"Wrote {report_dir / 'summary.md'}")
    click.echo(f"Wrote {report_dir / 'results.json'}")


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
    info = OpenBookService(_get_project_root(project)).brief()
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
    click.echo(OpenBookService(_get_project_root(project)).handoff(to_agent_hint=to_hint).to_text())


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
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    if lines:
        parts = lines.split("-")
        line_start = int(parts[0])
        line_end = int(parts[1]) if len(parts) > 1 else line_start

    citation_id = OpenBookService(_get_project_root(project)).cite(
        memory_id=memory_id,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        commit_hash=commit,
        url=url,
        quote=quote,
    )
    click.echo(f"Added citation {citation_id} to memory {memory_id}")


@cli.command("review")
@click.option("--project", default=None)
def review(project: Optional[str]) -> None:
    """Show memory proposals waiting for approval."""
    queue = OpenBookService(_get_project_root(project)).review_queue()
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
    if OpenBookService(_get_project_root(project)).approve(memory_id):
        click.echo(f"Approved memory {memory_id}")
    else:
        click.echo(f"Memory {memory_id} not found.", err=True)
        sys.exit(1)


@cli.command("reject")
@click.argument("memory_id", type=int)
@click.option("--project", default=None)
def reject_cmd(memory_id: int, project: Optional[str]) -> None:
    """Reject a memory proposal."""
    if OpenBookService(_get_project_root(project)).reject(memory_id):
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
    if OpenBookService(_get_project_root(project)).delete(memory_id, hard=hard):
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
    service = OpenBookService(_get_project_root(project))

    if json_export:
        data = service.export_json()
        out = json.dumps(data, indent=2, default=str)
        if output:
            Path(output).write_text(out, encoding="utf-8")
            click.echo(f"Exported JSON to {output}")
        else:
            click.echo(out)
    else:
        out_dir = Path(output) if output else service.project_root / ".openbook" / "exports"
        paths = service.export_markdown(out_dir)
        for name, path in paths.items():
            click.echo(f"Exported {name}: {path}")


@cli.command("doctor")
@click.option("--project", default=None)
def doctor(project: Optional[str]) -> None:
    """Check database, config, providers, MCP setup, and concurrency mode."""
    service = OpenBookService(_get_project_root(project))
    project_root = service.project_root
    database = service.database_diagnostics()
    click.echo(f"Project root: {project_root}")
    click.echo(f".openbook exists: {database['openbook_exists']}")
    click.echo(f"Database exists: {database['database_exists']}")
    click.echo(f"Config exists: {database['config_exists']}")
    if "journal_mode" in database:
        click.echo(f"Journal mode: {database['journal_mode']}")
        click.echo(f"Projects: {database['projects']}")
        click.echo(f"Memories: {database['memories']}")
        click.echo(f"Pending reviews: {database['pending_reviews']}")
    if "database_error" in database:
        click.echo(f"Database error: {database['database_error']}", err=True)

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
    result = OpenBookService(_get_project_root(project)).prune(
        older_than_days=older_than_days,
        min_trust=min_trust,
        dry_run=dry_run,
    )
    rows = result["candidates"]
    click.echo(f"Found {len(rows)} memories to prune")
    if dry_run:
        for r in rows:
            click.echo(f"Would prune: {r['id']} {r['content'][:60]}")
        return
    click.echo(f"Pruned {result['pruned']} memories")


@cli.command("reindex")
@click.option("--project", default=None)
def reindex(project: Optional[str]) -> None:
    """Rebuild FTS/vector indexes."""
    result = OpenBookService(_get_project_root(project)).reindex()
    click.echo("FTS index rebuilt.")
    if result["vector_available"]:
        click.echo("sqlite-vec is available; vector reindex not yet implemented in MVP.")
    else:
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
    for agent in OpenBookService(_get_project_root(project)).agents():
        click.echo(
            f"[{agent['id']}] {agent['client_name']} / {agent['agent_name']} "
            f"@ {agent['hostname']} (last seen {agent['last_seen_at']})"
        )


@cli.command("sessions")
@click.option("--project", default=None)
def sessions_cmd(project: Optional[str]) -> None:
    """Show session history."""
    for session in OpenBookService(_get_project_root(project)).sessions():
        click.echo(
            f"[{session['id']}] pid={session['process_id']} cwd={session['cwd']} "
            f"status={session['status']} started={session['started_at']}"
        )


@cli.group("runtime")
def runtime_group() -> None:
    """Optional runtime daemon controls."""
    pass


@runtime_group.command("start")
@click.option("--project", default=None)
def runtime_start(project: Optional[str]) -> None:
    """Start runtime daemon (MVP: not implemented)."""
    OpenBookService(_get_project_root(project)).initialize()
    click.echo("Runtime daemon start is not implemented in MVP. OpenBookService is active in-process.")


@runtime_group.command("stop")
def runtime_stop() -> None:
    """Stop runtime daemon (MVP: not implemented)."""
    click.echo("Runtime daemon stop is not implemented in MVP.")


@runtime_group.command("status")
def runtime_status() -> None:
    """Check runtime daemon status (MVP: not implemented)."""
    click.echo("Runtime daemon status: not running (OpenBookService in-process mode)")


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
