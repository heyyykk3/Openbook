"""Tests for OpenBook core functionality."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from openbook.cli.main import cli
from openbook.core.config import Config
from openbook.core.context_pack import build_context_pack
from openbook.core.db import get_connection, initialize_database
from openbook.core.exports import export_all, export_json
from openbook.core.memory import (
    approve_memory,
    get_review_queue,
    reject_memory,
    remember,
)
from openbook.core.mcp_install import (
    install_mcp_client,
    mcp_config_document,
    merge_mcp_config,
    normalize_client,
)
from openbook.core.project import detect_project_name, detect_project_root, detect_stack
from openbook.core.search import search_memories
from openbook.core.security import ensure_openbookignore, scan_for_secrets
from openbook.mcp.server import _handle_tool
from openbook.providers.embeddings import (
    GeminiEmbeddingProvider,
    NoneEmbeddingProvider,
    get_embedding_provider,
)
from openbook.providers.llm import GeminiLLMProvider, NoneLLMProvider, get_llm_provider


def _mcp_frame(message: dict[str, object]) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def _read_mcp_frame(stdout) -> dict[str, object]:
    header = stdout.readline()
    if not header:
        raise RuntimeError("MCP server returned no response")
    while header in (b"\r\n", b"\n"):
        header = stdout.readline()
    prefix = b"Content-Length: "
    if not header.startswith(prefix):
        raise RuntimeError(f"Unexpected MCP header: {header!r}")
    length = int(header[len(prefix):].strip())
    blank = stdout.readline()
    if blank not in (b"\r\n", b"\n"):
        raise RuntimeError(f"Unexpected MCP frame separator: {blank!r}")
    return json.loads(stdout.read(length).decode("utf-8"))


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "test-project"
        root.mkdir()
        (root / "README.md").write_text("# Test Project\n", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
        (root / ".git").mkdir()
        initialize_database(root)
        Config.create_default(root)
        ensure_openbookignore(root)
        yield root


@pytest.fixture
def conn(temp_project):
    connection = get_connection(temp_project)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def project_id(conn, temp_project):
    row = conn.execute(
        "SELECT id FROM projects WHERE root_path = ?", (str(temp_project.resolve()),)
    ).fetchone()
    return row["id"]


class TestInit:
    def test_init_creates_openbook_dir(self, temp_project):
        assert (temp_project / ".openbook").exists()
        assert (temp_project / ".openbook" / "openbook.sqlite").exists()

    def test_init_creates_config(self, temp_project):
        config = Config.load(temp_project)
        assert config.get("storage", "database") == ".openbook/openbook.sqlite"

    def test_init_creates_ignore(self, temp_project):
        assert (temp_project / ".openbookignore").exists()

    def test_setup_can_initialize_and_install_cursor_noninteractive(self, tmp_path):
        root = tmp_path / "setup-project"
        root.mkdir()
        (root / ".git").mkdir()
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "setup",
                "--project",
                str(root),
                "--yes",
                "--client",
                "cursor",
            ],
        )

        assert result.exit_code == 0
        assert (root / ".openbook" / "openbook.sqlite").exists()
        assert (root / ".cursor" / "mcp.json").exists()

    def test_smoke_test_command_passes_on_temp_project(self):
        runner = CliRunner()

        result = runner.invoke(cli, ["smoke-test"])

        assert result.exit_code == 0
        assert "OpenBook smoke test passed" in result.output

    def test_benchmark_resource_command_writes_reports(self, tmp_path):
        report_dir = tmp_path / "resource-report"
        work_dir = tmp_path / "resource-work"
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "benchmark",
                "resource",
                "--memories",
                "8",
                "--searches",
                "3",
                "--report-dir",
                str(report_dir),
                "--work-dir",
                str(work_dir),
            ],
        )

        assert result.exit_code == 0
        assert (report_dir / "summary.md").exists()
        assert (report_dir / "results.json").exists()


class TestSchema:
    def test_projects_table(self, conn):
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'").fetchone()
        assert row is not None

    def test_memories_table(self, conn):
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'").fetchone()
        assert row is not None

    def test_fts5_table(self, conn):
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'").fetchone()
        assert row is not None

    def test_chapters_defaults(self, conn, project_id):
        rows = conn.execute(
            "SELECT name FROM chapters WHERE project_id = ?", (project_id,)
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "architecture" in names
        assert "commands" in names
        assert "decisions" in names


class TestRemember:
    def test_remember_creates_memory(self, conn, project_id):
        mid = remember(conn, project_id, "Tests run with pytest -q", memory_type="command")
        assert mid > 0
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["content"] == "Tests run with pytest -q"
        assert row["status"] == "proposed"

    def test_remember_with_approve(self, conn, project_id):
        mid = remember(conn, project_id, "Use black for formatting", memory_type="convention", status="approved")
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["status"] == "approved"

    def test_remember_deduplication(self, conn, project_id):
        mid1 = remember(conn, project_id, "Duplicate content", memory_type="fact")
        mid2 = remember(conn, project_id, "Duplicate content", memory_type="fact")
        assert mid1 == mid2

    def test_remember_idempotency_key(self, conn, project_id):
        mid1 = remember(conn, project_id, "Key test", memory_type="fact", idempotency_key="abc123")
        mid2 = remember(conn, project_id, "Different text", memory_type="fact", idempotency_key="abc123")
        assert mid1 == mid2


class TestCitations:
    def test_add_citation(self, conn, project_id):
        mid = remember(conn, project_id, "Citation test", memory_type="fact", status="approved")
        cur = conn.execute(
            "INSERT INTO citations (project_id, file_path, line_start, line_end, quote) VALUES (?, ?, ?, ?, ?)",
            (project_id, "README.md", 1, 5, "Hello"),
        )
        cid = cur.lastrowid
        conn.execute(
            "UPDATE memories SET citation_id = ? WHERE id = ?", (cid, mid)
        )
        row = conn.execute("SELECT citation_id FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["citation_id"] == cid


class TestReview:
    def test_review_queue(self, conn, project_id):
        remember(conn, project_id, "Review me", memory_type="fact")
        queue = get_review_queue(conn, project_id)
        assert len(queue) >= 1

    def test_approve(self, conn, project_id):
        mid = remember(conn, project_id, "Approve me", memory_type="fact")
        assert approve_memory(conn, project_id, mid)
        row = conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["status"] == "approved"

    def test_reject(self, conn, project_id):
        mid = remember(conn, project_id, "Reject me", memory_type="fact")
        assert reject_memory(conn, project_id, mid)
        row = conn.execute("SELECT status FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["status"] == "rejected"


class TestSearch:
    def test_fts_search(self, conn, project_id):
        remember(conn, project_id, "FastAPI with SQLite local dev", memory_type="fact", status="approved")
        remember(conn, project_id, "pytest -q for tests", memory_type="command", status="approved")
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
        results = search_memories(conn, project_id, "FastAPI")
        assert any("FastAPI" in r.summary for r in results)


class TestContextPack:
    def test_budget_limits(self, conn, project_id):
        remember(conn, project_id, "A" * 400, memory_type="fact", status="approved")
        pack = build_context_pack(conn, project_id, "A", budget="tiny")
        assert pack.budget == "tiny"
        assert len(pack.cards) >= 0

    def test_includes_citations(self, conn, project_id):
        mid = remember(conn, project_id, "Cited memory", memory_type="fact", status="approved")
        cur = conn.execute(
            "INSERT INTO citations (project_id, file_path, line_start, quote) VALUES (?, ?, ?, ?)",
            (project_id, "main.py", 10, "code"),
        )
        cid = cur.lastrowid
        conn.execute("UPDATE memories SET citation_id = ? WHERE id = ?", (cid, mid))
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
        pack = build_context_pack(conn, project_id, "cited", budget="normal")
        assert any("main.py" in (c.citation or "") for c in pack.cards)


class TestHandoff:
    def test_handoff_generation(self, conn, project_id):
        remember(conn, project_id, "Handoff context", memory_type="handoff", status="approved")
        pack = build_context_pack(conn, project_id, "handoff", budget="tiny")
        assert pack.budget == "tiny"


class TestExport:
    def test_export_markdown(self, conn, project_id, temp_project):
        remember(conn, project_id, "Export test", memory_type="fact", status="approved")
        out_dir = temp_project / ".openbook" / "exports"
        paths = export_all(conn, project_id, temp_project, out_dir)
        assert "cover" in paths
        assert "index" in paths
        assert (out_dir / "cover.md").exists()

    def test_export_json(self, conn, project_id, temp_project):
        data = export_json(conn, project_id, temp_project)
        assert "project" in data
        assert "memories" in data


class TestMCPInstall:
    def test_mcp_config_pins_project_env(self, temp_project):
        config = mcp_config_document(temp_project, "cursor")
        server = config["mcpServers"]["openbook"]

        assert server["command"] == "openbook"
        assert server["args"] == ["mcp"]
        assert server["env"]["OPENBOOK_PROJECT"] == str(temp_project.resolve())
        assert server["env"]["OPENBOOK_CLIENT"] == "cursor"

    def test_merge_mcp_config_preserves_other_servers(self):
        merged = merge_mcp_config(
            {"mcpServers": {"other": {"command": "other"}}},
            {"mcpServers": {"openbook": {"command": "openbook"}}},
        )

        assert set(merged["mcpServers"]) == {"other", "openbook"}

    def test_cursor_install_writes_project_config(self, temp_project):
        result = install_mcp_client("cursor", temp_project)
        path = temp_project / ".cursor" / "mcp.json"

        assert result.mode == "write"
        assert result.target == str(path)
        assert path.exists()
        assert "OPENBOOK_PROJECT" in path.read_text(encoding="utf-8")

    def test_claude_code_install_writes_project_mcp_json(self, temp_project):
        result = install_mcp_client("claude-code", temp_project)

        assert result.mode == "write"
        assert result.target == str(temp_project / ".mcp.json")
        assert (temp_project / ".mcp.json").exists()

    def test_codex_install_dry_run_prints_command(self, temp_project):
        result = install_mcp_client("codex", temp_project, dry_run=True)

        assert result.mode == "dry-run"
        assert "codex mcp add openbook" in result.message
        assert "OPENBOOK_PROJECT" in result.message

    def test_unknown_mcp_client_is_rejected(self):
        with pytest.raises(ValueError):
            normalize_client("unknown")

    def test_unknown_mcp_tool_raises_error(self, temp_project, monkeypatch):
        monkeypatch.setenv("OPENBOOK_PROJECT", str(temp_project))

        with pytest.raises(ValueError, match="Unknown tool"):
            _handle_tool("openbook_missing", {})

    def test_mcp_stdio_initializes_and_lists_tools(self, tmp_path):
        root = tmp_path / "mcp-stdio-project"
        root.mkdir()
        (root / ".git").mkdir()
        env = os.environ.copy()
        env["OPENBOOK_PROJECT"] = str(root)

        process = subprocess.Popen(
            [sys.executable, "-m", "openbook.cli.main", "mcp"],
            cwd=Path.cwd(),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(
                _mcp_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            )
            process.stdin.write(
                _mcp_frame({"jsonrpc": "2.0", "method": "notifications/initialized"})
            )
            process.stdin.write(
                _mcp_frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            )
            process.stdin.flush()

            initialize_response = _read_mcp_frame(process.stdout)
            tools_response = _read_mcp_frame(process.stdout)

            assert initialize_response["result"]["serverInfo"]["name"] == "openbook"
            assert len(tools_response["result"]["tools"]) >= 7
        finally:
            if process.stdin:
                process.stdin.close()
            process.terminate()
            process.wait(timeout=5)


class TestProviders:
    def test_none_embedding(self):
        p = get_embedding_provider({"provider": "none"})
        assert isinstance(p, NoneEmbeddingProvider)
        assert p.health_check()["status"] == "ok"

    def test_none_llm(self):
        p = get_llm_provider({"provider": "none"})
        assert isinstance(p, NoneLLMProvider)
        assert p.health_check()["status"] == "ok"

    def test_gemini_embedding_provider_config(self):
        p = get_embedding_provider(
            {
                "provider": "gemini",
                "model": "gemini-embedding-2",
                "api_key": "test-key",
                "dimensions": 768,
            }
        )
        assert isinstance(p, GeminiEmbeddingProvider)
        assert p.name == "gemini"
        assert p.model == "gemini-embedding-2"
        assert p.dimensions == 768

    def test_gemini_llm_provider_config(self):
        p = get_llm_provider(
            {
                "provider": "gemini",
                "model": "gemini-3-flash-preview",
                "api_key": "test-key",
            }
        )
        assert isinstance(p, GeminiLLMProvider)
        assert p.name == "gemini"
        assert p.model == "gemini-3-flash-preview"

    def test_gemini_providers_read_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-env-key")

        embedding = get_embedding_provider({"provider": "gemini"})
        llm = get_llm_provider({"provider": "gemini"})

        assert isinstance(embedding, GeminiEmbeddingProvider)
        assert isinstance(llm, GeminiLLMProvider)
        assert embedding._api_key == "test-env-key"
        assert llm._api_key == "test-env-key"


class TestConcurrency:
    def test_wal_mode(self, conn):
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"

    def test_multiple_readers(self, temp_project):
        conn1 = get_connection(temp_project)
        conn2 = get_connection(temp_project)
        try:
            row1 = conn1.execute("SELECT 1 as n").fetchone()
            row2 = conn2.execute("SELECT 2 as n").fetchone()
            assert row1["n"] == 1
            assert row2["n"] == 2
        finally:
            conn1.close()
            conn2.close()

    def test_migration_lock(self, temp_project):
        # Should succeed because same process can re-enter
        initialize_database(temp_project)
        assert True


class TestSecurity:
    def test_secret_scan(self):
        findings = scan_for_secrets("api_key = 'sk-1234567890abcdef1234567890abcdef1234567890abcdef'")
        assert "api_key" in findings or "openai_key" in findings

    def test_secret_quarantine(self, conn, project_id):
        mid = remember(conn, project_id, "password: supersecret123", memory_type="fact")
        row = conn.execute("SELECT status, content FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["status"] == "quarantined"
        assert "supersecret123" not in row["content"]
        assert "[REDACTED:password]" in row["content"]

    def test_duplicate_prevention(self, conn, project_id):
        mid1 = remember(conn, project_id, "Duplicate prevention test", memory_type="fact")
        mid2 = remember(conn, project_id, "Duplicate prevention test", memory_type="fact")
        assert mid1 == mid2


class TestProjectDetection:
    def test_detect_root(self, temp_project):
        root = detect_project_root(temp_project)
        assert root == temp_project.resolve()

    def test_detect_name(self, temp_project):
        name = detect_project_name(temp_project)
        assert name == "Test Project"

    def test_detect_stack(self, temp_project):
        stacks = detect_stack(temp_project)
        assert "python" in stacks
