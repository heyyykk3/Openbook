"""Search and retrieval for OpenBook using SQLite FTS5."""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Optional

from openbook.core.models import MemoryCard, parse_tags

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def build_fts_query(query: str) -> str:
    """Convert a natural-language query into a safe FTS5 prefix query."""
    tokens = TOKEN_RE.findall(query)
    return " OR ".join(f"{token}*" for token in tokens)


def search_memories(
    conn: sqlite3.Connection,
    project_id: int,
    query: str,
    chapter: Optional[str] = None,
    memory_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    status: Optional[str] = "approved",
    limit: int = 20,
) -> list[MemoryCard]:
    # Build FTS query
    fts_query = build_fts_query(query)
    if not fts_query:
        return []

    sql = """
        SELECT
            m.id,
            m.chapter_id,
            m.type,
            m.title,
            m.summary,
            m.content,
            m.tags_json,
            m.confidence,
            m.trust_score,
            m.importance,
            m.status,
            m.valid_from,
            m.valid_to,
            m.source_id,
            m.citation_id,
            m.content_hash,
            m.idempotency_key,
            m.created_by_agent_id,
            m.created_at,
            m.updated_at,
            c.file_path,
            c.line_start,
            c.line_end,
            c.commit_hash,
            c.terminal_session_id,
            c.url,
            c.quote,
            rank AS fts_rank
        FROM memories_fts
        JOIN memories m ON memories_fts.rowid = m.id
        LEFT JOIN citations c ON m.citation_id = c.id
        WHERE memories_fts MATCH ? AND m.project_id = ?
    """
    params: list[Any] = [fts_query, project_id]

    if status:
        sql += " AND m.status = ?"
        params.append(status)
    if chapter:
        sql += " AND m.chapter_id IN (SELECT id FROM chapters WHERE name = ? AND project_id = ?)"
        params.extend([chapter, project_id])
    if memory_type:
        sql += " AND m.type = ?"
        params.append(memory_type)
    if tags:
        for tag in tags:
            sql += " AND m.tags_json LIKE ?"
            params.append(f'%"{tag}"%')

    sql += """
        ORDER BY
            (m.trust_score * 2 + m.importance + m.confidence - coalesce(rank, 0)) DESC,
            m.updated_at DESC
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    cards: list[MemoryCard] = []
    for idx, row in enumerate(rows, start=1):
        citation_parts = []
        if row["file_path"]:
            cp = row["file_path"]
            if row["line_start"] is not None:
                cp += f" lines {row['line_start']}"
                if row["line_end"] is not None and row["line_end"] != row["line_start"]:
                    cp += f"-{row['line_end']}"
            citation_parts.append(cp)
        if row["commit_hash"]:
            citation_parts.append(f"commit {row['commit_hash']}")
        if row["terminal_session_id"]:
            citation_parts.append(f"terminal session {row['terminal_session_id']}")
        if row["url"]:
            citation_parts.append(row["url"])
        if row["quote"]:
            citation_parts.append(f'"{row["quote"][:200]}"')
        citation_str = " | ".join(citation_parts) if citation_parts else None

        trust_label = _trust_label(row["trust_score"])
        summary = row["summary"] or row["content"][:200]
        cards.append(
            MemoryCard(
                rank=idx,
                memory_id=row["id"],
                title=row["title"],
                summary=summary,
                tags=parse_tags(row["tags_json"]),
                trust=trust_label,
                citation=citation_str,
                raw_excerpt=row["content"] if len(row["content"]) <= 800 else row["content"][:800] + "...",
            )
        )
    return cards


def _trust_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def get_project_brief(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not project:
        return {}

    cover = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND type = 'fact' AND chapter_id = (SELECT id FROM chapters WHERE project_id = ? AND name = 'architecture') ORDER BY updated_at DESC LIMIT 5",
        (project_id, project_id),
    ).fetchall()

    commands = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND type = 'command' AND status = 'approved' ORDER BY updated_at DESC LIMIT 5",
        (project_id,),
    ).fetchall()

    decisions = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND type = 'decision' AND status = 'approved' ORDER BY updated_at DESC LIMIT 5",
        (project_id,),
    ).fetchall()

    warnings = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND type = 'warning' AND status = 'approved' ORDER BY updated_at DESC LIMIT 5",
        (project_id,),
    ).fetchall()

    return {
        "project_name": project["name"],
        "root_path": project["root_path"],
        "cover_memories": [_memory_preview(r) for r in cover],
        "commands": [_memory_preview(r) for r in commands],
        "decisions": [_memory_preview(r) for r in decisions],
        "warnings": [_memory_preview(r) for r in warnings],
    }


def _memory_preview(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "summary": row["summary"] or row["content"][:200],
        "tags": parse_tags(row["tags_json"]),
    }
