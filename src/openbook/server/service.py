"""Canonical OpenBook service boundary.

This module keeps agent-facing behavior behind one service object. Storage
details stay internal so MCP, CLI, and future HTTP transports do not each manage
their own project setup, identity, and database connection lifecycle.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from openbook.core.config import Config
from openbook.core.context_pack import build_context_pack
from openbook.core.db import get_connection, initialize_database
from openbook.core.exports import export_all as export_all_files
from openbook.core.exports import export_json as export_json_data
from openbook.core.memory import (
    approve_memory,
    delete_memory,
    get_review_queue,
    reject_memory,
    remember as remember_memory,
)
from openbook.core.models import ContextPack
from openbook.core.project import detect_project_name, detect_project_root
from openbook.core.search import get_project_brief
from openbook.core.security import ensure_openbookignore


@dataclass
class OpenBookContext:
    project_root: Path
    conn: sqlite3.Connection
    project_id: int
    agent_id: int


class OpenBookService:
    """Single owner for OpenBook project memory operations."""

    def __init__(
        self,
        project_root: Path | str | None = None,
        *,
        client: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        self.project_root = self._resolve_project_root(project_root)
        self.client = client or os.environ.get("OPENBOOK_CLIENT", "cli")
        self.agent_name = agent_name or os.environ.get("OPENBOOK_AGENT", "openbook-cli")

    @staticmethod
    def _resolve_project_root(project_root: Path | str | None = None) -> Path:
        if project_root is not None:
            return Path(project_root).expanduser().resolve()
        configured = os.environ.get("OPENBOOK_PROJECT")
        if configured:
            return Path(configured).expanduser().resolve()
        return detect_project_root()

    def initialize(self) -> Path:
        """Ensure the local OpenBook project store exists."""
        initialize_database(self.project_root)
        Config.create_default(self.project_root)
        ensure_openbookignore(self.project_root)
        return self.project_root / ".openbook"

    @contextmanager
    def open(self) -> Iterator[OpenBookContext]:
        """Open a request-scoped project context and always close its DB handle."""
        self.initialize()
        conn = get_connection(self.project_root)
        try:
            project_id = self._get_or_create_project(conn)
            agent_id = self._get_or_create_agent(conn, project_id)
            yield OpenBookContext(
                project_root=self.project_root,
                conn=conn,
                project_id=project_id,
                agent_id=agent_id,
            )
        finally:
            conn.close()

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "fact",
        title: str | None = None,
        summary: str | None = None,
        chapter: str | None = None,
        tags: list[str] | None = None,
        trust_score: float = 0.5,
        status: str = "proposed",
    ) -> dict[str, Any]:
        with self.open() as ctx:
            memory_id = remember_memory(
                conn=ctx.conn,
                project_id=ctx.project_id,
                content=content,
                memory_type=memory_type,
                title=title,
                summary=summary,
                chapter=chapter,
                tags=tags or [],
                trust_score=trust_score,
                status=status,
                agent_id=ctx.agent_id,
            )
            return {"memory_id": memory_id, "status": status, "project_root": str(ctx.project_root)}

    def search(
        self,
        query: str,
        *,
        budget: str = "normal",
        chapter: str | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        include_raw: bool = False,
    ) -> ContextPack:
        with self.open() as ctx:
            return build_context_pack(
                conn=ctx.conn,
                project_id=ctx.project_id,
                query=query,
                budget=budget,
                chapter=chapter,
                memory_type=memory_type,
                tags=tags or [],
                include_raw=include_raw,
                agent_id=ctx.agent_id,
            )

    def brief(self) -> dict[str, Any]:
        with self.open() as ctx:
            return get_project_brief(ctx.conn, ctx.project_id)

    def handoff(self, *, to_agent_hint: str | None = None) -> ContextPack:
        with self.open() as ctx:
            session_id = self._get_or_create_session(ctx.conn, ctx.project_id, ctx.agent_id)
            pack = build_context_pack(
                conn=ctx.conn,
                project_id=ctx.project_id,
                query="handoff context",
                budget="tiny",
                agent_id=ctx.agent_id,
                session_id=str(session_id),
            )
            ctx.conn.execute(
                "INSERT INTO handoffs (project_id, from_agent_id, to_agent_hint, summary, context_pack_json) VALUES (?, ?, ?, ?, ?)",
                (
                    ctx.project_id,
                    ctx.agent_id,
                    to_agent_hint,
                    pack.to_text(),
                    json.dumps({"cards": [card.memory_id for card in pack.cards]}),
                ),
            )
            return pack

    def cite(
        self,
        *,
        memory_id: int,
        file_path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        commit_hash: str | None = None,
        url: str | None = None,
        quote: str | None = None,
    ) -> int:
        with self.open() as ctx:
            cur = ctx.conn.execute(
                """
                INSERT INTO citations (project_id, file_path, line_start, line_end, commit_hash, url, quote)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ctx.project_id, file_path, line_start, line_end, commit_hash, url, quote),
            )
            citation_id = self._lastrowid(cur)
            ctx.conn.execute(
                "UPDATE memories SET citation_id = ? WHERE id = ? AND project_id = ?",
                (citation_id, memory_id, ctx.project_id),
            )
            return citation_id

    def review_queue(self) -> list[dict[str, Any]]:
        with self.open() as ctx:
            return get_review_queue(ctx.conn, ctx.project_id)

    def approve(self, memory_id: int) -> bool:
        with self.open() as ctx:
            return approve_memory(ctx.conn, ctx.project_id, memory_id)

    def reject(self, memory_id: int) -> bool:
        with self.open() as ctx:
            return reject_memory(ctx.conn, ctx.project_id, memory_id)

    def delete(self, memory_id: int, *, hard: bool = False) -> bool:
        with self.open() as ctx:
            return delete_memory(ctx.conn, ctx.project_id, memory_id, hard=hard)

    def status(self) -> dict[str, Any]:
        with self.open() as ctx:
            approved = ctx.conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE project_id = ? AND status = 'approved'",
                (ctx.project_id,),
            ).fetchone()["c"]
            pending = ctx.conn.execute(
                "SELECT COUNT(*) as c FROM review_queue WHERE project_id = ? AND status = 'pending'",
                (ctx.project_id,),
            ).fetchone()["c"]
            total = ctx.conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE project_id = ?",
                (ctx.project_id,),
            ).fetchone()["c"]
            return {
                "project": ctx.project_root.name,
                "project_root": str(ctx.project_root),
                "memories": int(total),
                "approved_memories": int(approved),
                "pending_reviews": int(pending),
            }

    def export_json(self) -> dict[str, Any]:
        with self.open() as ctx:
            return export_json_data(ctx.conn, ctx.project_id, ctx.project_root)

    def export_markdown(self, output_dir: Path) -> dict[str, Path]:
        with self.open() as ctx:
            return export_all_files(ctx.conn, ctx.project_id, ctx.project_root, output_dir)

    def database_diagnostics(self) -> dict[str, Any]:
        openbook_dir = self.project_root / ".openbook"
        db_path = openbook_dir / "openbook.sqlite"
        config_path = openbook_dir / "config.toml"
        result: dict[str, Any] = {
            "project_root": str(self.project_root),
            "openbook_exists": openbook_dir.exists(),
            "database_exists": db_path.exists(),
            "config_exists": config_path.exists(),
        }
        if not db_path.exists():
            return result

        try:
            with self.open() as ctx:
                row = ctx.conn.execute("PRAGMA journal_mode").fetchone()
                result["journal_mode"] = row[0] if row else "unknown"
                result["projects"] = int(ctx.conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
                result["memories"] = int(ctx.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
                result["pending_reviews"] = int(
                    ctx.conn.execute(
                        "SELECT COUNT(*) FROM review_queue WHERE status = 'pending'"
                    ).fetchone()[0]
                )
        except Exception as exc:
            result["database_error"] = str(exc)
        return result

    def prune(
        self,
        *,
        older_than_days: int = 90,
        min_trust: float = 0.0,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        cutoff = time.time() - (older_than_days * 86400)
        with self.open() as ctx:
            rows = ctx.conn.execute(
                """
                SELECT id, content
                FROM memories
                WHERE project_id = ?
                  AND updated_at < ?
                  AND trust_score < ?
                  AND status != 'archived'
                """,
                (ctx.project_id, cutoff, min_trust),
            ).fetchall()
            candidates = [{"id": int(row["id"]), "content": str(row["content"])} for row in rows]
            if dry_run:
                return {"candidates": candidates, "pruned": 0, "dry_run": True}

            for row in rows:
                ctx.conn.execute(
                    "UPDATE memories SET status = 'archived', updated_at = ? WHERE id = ?",
                    (time.time(), row["id"]),
                )
            return {"candidates": candidates, "pruned": len(rows), "dry_run": False}

    def reindex(self) -> dict[str, bool]:
        with self.open() as ctx:
            ctx.conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
            vector_available = True
            try:
                ctx.conn.execute("SELECT vec_version()")
            except Exception:
                vector_available = False
            return {"fts_rebuilt": True, "vector_available": vector_available}

    def agents(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.open() as ctx:
            rows = ctx.conn.execute(
                "SELECT * FROM agents WHERE project_id = ? ORDER BY last_seen_at DESC LIMIT ?",
                (ctx.project_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def sessions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.open() as ctx:
            rows = ctx.conn.execute(
                "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC LIMIT ?",
                (ctx.project_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def _get_or_create_project(self, conn: sqlite3.Connection) -> int:
        root_str = str(self.project_root.resolve())
        row = conn.execute("SELECT id FROM projects WHERE root_path = ?", (root_str,)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO projects (root_path, name) VALUES (?, ?)",
            (root_str, detect_project_name(self.project_root)),
        )
        return self._lastrowid(cur)

    def _get_or_create_agent(self, conn: sqlite3.Connection, project_id: int) -> int:
        hostname = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
        row = conn.execute(
            "SELECT id FROM agents WHERE project_id = ? AND client_name = ? AND agent_name = ?",
            (project_id, self.client, self.agent_name),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE agents SET last_seen_at = ? WHERE id = ?",
                (time.time(), row["id"]),
            )
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO agents (project_id, client_name, agent_name, version, hostname, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, self.client, self.agent_name, "0.1.0", hostname, time.time(), time.time()),
        )
        return self._lastrowid(cur)

    def _get_or_create_session(
        self,
        conn: sqlite3.Connection,
        project_id: int,
        agent_id: int,
    ) -> int:
        cur = conn.execute(
            "INSERT INTO sessions (project_id, agent_id, client_name, process_id, cwd, started_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (project_id, agent_id, self.client, os.getpid(), str(Path.cwd().resolve()), time.time()),
        )
        return self._lastrowid(cur)

    @staticmethod
    def _lastrowid(cur: sqlite3.Cursor) -> int:
        if cur.lastrowid is None:
            raise RuntimeError("Insert did not return a row id")
        return int(cur.lastrowid)
