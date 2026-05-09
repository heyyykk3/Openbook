"""Export functionality for OpenBook."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from openbook.core.models import parse_tags
from openbook.core.project import detect_stack


def export_cover_md(conn: sqlite3.Connection, project_id: int, project_root: Path) -> str:
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return "# OpenBook Cover\n\nProject not found.\n"

    name = project["name"]
    lines = [
        f"# {name}",
        "",
        f"**Root:** {project['root_path']}",
        f"**Created:** {project['created_at']}",
        "",
        "## Stack",
        "",
    ]
    stacks = detect_stack(project_root)
    for s in stacks:
        lines.append(f"- {s}")
    if not stacks:
        lines.append("- (unknown)")

    lines.extend(["", "## Cover Memories", ""])
    rows = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND status = 'approved' ORDER BY updated_at DESC LIMIT 20",
        (project_id,),
    ).fetchall()
    for row in rows:
        lines.append(f"- **{row['type']}**: {row['summary'] or row['content'][:200]}")

    lines.append("")
    return "\n".join(lines)


def export_index_md(conn: sqlite3.Connection, project_id: int) -> str:
    lines = ["# Index", ""]
    chapters = conn.execute(
        "SELECT * FROM chapters WHERE project_id = ? ORDER BY name", (project_id,)
    ).fetchall()
    for ch in chapters:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM memories WHERE chapter_id = ? AND status = 'approved'",
            (ch["id"],),
        ).fetchone()["c"]
        lines.append(f"- **{ch['name']}** ({count} memories): {ch['description'] or ''}")

    lines.append("")
    return "\n".join(lines)


def export_chapter_md(conn: sqlite3.Connection, project_id: int, chapter_name: str) -> str:
    chapter = conn.execute(
        "SELECT * FROM chapters WHERE project_id = ? AND name = ?", (project_id, chapter_name)
    ).fetchone()
    if not chapter:
        return f"# {chapter_name}\n\nChapter not found.\n"

    lines = [f"# {chapter_name}", ""]
    if chapter["description"]:
        lines.append(f"{chapter['description']}")
        lines.append("")

    rows = conn.execute(
        """
        SELECT m.*, c.file_path, c.line_start, c.line_end
        FROM memories m
        LEFT JOIN citations c ON m.citation_id = c.id
        WHERE m.project_id = ? AND m.chapter_id = ? AND m.status = 'approved'
        ORDER BY m.updated_at DESC
        """,
        (project_id, chapter["id"]),
    ).fetchall()

    for row in rows:
        title = row["title"] or f"Memory {row['id']}"
        lines.append(f"## {title}")
        lines.append("")
        lines.append(row["content"])
        lines.append("")
        if row["file_path"]:
            loc = row["file_path"]
            if row["line_start"] is not None:
                loc += f" lines {row['line_start']}"
                if row["line_end"] is not None and row["line_end"] != row["line_start"]:
                    loc += f"-{row['line_end']}"
            lines.append(f"*Source: {loc}*")
        tags = parse_tags(row["tags_json"])
        if tags:
            lines.append(f"*Tags: {', '.join(tags)}*")
        lines.append("")

    return "\n".join(lines)


def export_all(
    conn: sqlite3.Connection,
    project_id: int,
    project_root: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = output_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Path] = {}

    cover_path = output_dir / "cover.md"
    with open(cover_path, "w", encoding="utf-8") as f:
        f.write(export_cover_md(conn, project_id, project_root))
    results["cover"] = cover_path

    index_path = output_dir / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(export_index_md(conn, project_id))
    results["index"] = index_path

    chapters = conn.execute(
        "SELECT name FROM chapters WHERE project_id = ?", (project_id,)
    ).fetchall()
    for ch in chapters:
        ch_name = ch["name"]
        ch_path = chapters_dir / f"{ch_name}.md"
        with open(ch_path, "w", encoding="utf-8") as f:
            f.write(export_chapter_md(conn, project_id, ch_name))
        results[ch_name] = ch_path

    return results


def export_json(conn: sqlite3.Connection, project_id: int, project_root: Path) -> dict[str, Any]:
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    memories = conn.execute(
        "SELECT * FROM memories WHERE project_id = ? AND status = 'approved'", (project_id,)
    ).fetchall()
    chapters = conn.execute(
        "SELECT * FROM chapters WHERE project_id = ?", (project_id,)
    ).fetchall()
    citations = conn.execute(
        "SELECT * FROM citations WHERE project_id = ?", (project_id,)
    ).fetchall()

    return {
        "project": dict(project) if project else None,
        "chapters": [dict(r) for r in chapters],
        "memories": [dict(r) for r in memories],
        "citations": [dict(r) for r in citations],
    }
