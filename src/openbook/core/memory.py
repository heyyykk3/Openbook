"""Memory operations for OpenBook."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Optional

from openbook.core.db import content_hash
from openbook.core.models import parse_tags
from openbook.core.security import scan_for_secrets


VALID_MEMORY_TYPES = {
    "fact",
    "decision",
    "command",
    "failure",
    "convention",
    "architecture",
    "dependency",
    "warning",
    "task",
    "handoff",
    "source_note",
    "user_preference",
    "agent_lesson",
}

VALID_STATUSES = {"proposed", "approved", "rejected", "archived", "quarantined"}


def _lastrowid(cur: sqlite3.Cursor) -> int:
    if cur.lastrowid is None:
        raise RuntimeError("Insert did not return a row id")
    return int(cur.lastrowid)


def remember(
    conn: sqlite3.Connection,
    project_id: int,
    content: str,
    memory_type: str = "fact",
    title: Optional[str] = None,
    summary: Optional[str] = None,
    chapter: Optional[str] = None,
    tags: Optional[list[str]] = None,
    confidence: float = 0.7,
    trust_score: float = 0.5,
    importance: float = 0.5,
    status: str = "proposed",
    citation_id: Optional[int] = None,
    source_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    agent_id: Optional[int] = None,
) -> int:
    if memory_type not in VALID_MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    # Secret scan
    secret_findings = scan_for_secrets(content)
    if secret_findings:
        status = "quarantined"
        if summary:
            summary += f" [QUARANTINED: potential secrets detected: {', '.join(secret_findings)}]"
        else:
            summary = f"[QUARANTINED: potential secrets detected: {', '.join(secret_findings)}]"

    # Deduplication via content hash
    c_hash = content_hash(content)
    existing = conn.execute(
        "SELECT id FROM memories WHERE project_id = ? AND content_hash = ?",
        (project_id, c_hash),
    ).fetchone()
    if existing:
        return int(existing["id"])

    # Idempotency key check
    if idempotency_key:
        existing_key = conn.execute(
            "SELECT id FROM memories WHERE project_id = ? AND idempotency_key = ?",
            (project_id, idempotency_key),
        ).fetchone()
        if existing_key:
            return int(existing_key["id"])

    # Resolve chapter
    chapter_id: Optional[int] = None
    if chapter:
        row = conn.execute(
            "SELECT id FROM chapters WHERE project_id = ? AND name = ?",
            (project_id, chapter),
        ).fetchone()
        if row:
            chapter_id = int(row["id"])

    now = time.time()
    cur = conn.execute(
        """
        INSERT INTO memories (
            project_id, chapter_id, type, title, summary, content, tags_json,
            confidence, trust_score, importance, status, valid_from, valid_to,
            source_id, citation_id, content_hash, idempotency_key, created_by_agent_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            chapter_id,
            memory_type,
            title,
            summary,
            content,
            json.dumps(tags or []),
            confidence,
            trust_score,
            importance,
            status,
            now,
            None,
            source_id,
            citation_id,
            c_hash,
            idempotency_key,
            agent_id,
            now,
            now,
        ),
    )
    memory_id = _lastrowid(cur)

    # Insert into review queue if proposed
    if status == "proposed":
        conn.execute(
            """
            INSERT INTO review_queue (project_id, proposed_memory_id, proposed_by_agent_id, reason, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (project_id, memory_id, agent_id, "Auto-submitted for review"),
        )

    # Create a single chunk for the memory
    conn.execute(
        """
        INSERT INTO chunks (memory_id, project_id, chunk_text, chunk_hash, token_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            memory_id,
            project_id,
            content,
            c_hash,
            len(content) // 4,
        ),
    )

    return memory_id


def approve_memory(conn: sqlite3.Connection, project_id: int, memory_id: int) -> bool:
    conn.execute(
        "UPDATE memories SET status = 'approved', updated_at = ? WHERE id = ? AND project_id = ?",
        (time.time(), memory_id, project_id),
    )
    conn.execute(
        "UPDATE review_queue SET status = 'approved', reviewed_at = ? WHERE proposed_memory_id = ? AND project_id = ?",
        (time.time(), memory_id, project_id),
    )
    return bool(conn.execute("SELECT changes()").fetchone()[0] > 0)


def reject_memory(conn: sqlite3.Connection, project_id: int, memory_id: int) -> bool:
    conn.execute(
        "UPDATE memories SET status = 'rejected', updated_at = ? WHERE id = ? AND project_id = ?",
        (time.time(), memory_id, project_id),
    )
    conn.execute(
        "UPDATE review_queue SET status = 'rejected', reviewed_at = ? WHERE proposed_memory_id = ? AND project_id = ?",
        (time.time(), memory_id, project_id),
    )
    return bool(conn.execute("SELECT changes()").fetchone()[0] > 0)


def get_review_queue(conn: sqlite3.Connection, project_id: int, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT rq.id, rq.proposed_memory_id, rq.reason, rq.status, rq.created_at,
               m.title, m.summary, m.content, m.type, m.tags_json
        FROM review_queue rq
        JOIN memories m ON rq.proposed_memory_id = m.id
        WHERE rq.project_id = ? AND rq.status = 'pending'
        ORDER BY rq.created_at DESC
        LIMIT ?
        """,
        (project_id, limit),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "memory_id": r["proposed_memory_id"],
            "title": r["title"],
            "summary": r["summary"],
            "content": r["content"],
            "type": r["type"],
            "tags": parse_tags(r["tags_json"]),
            "reason": r["reason"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
