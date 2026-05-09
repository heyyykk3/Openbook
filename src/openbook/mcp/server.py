"""MCP stdio server for OpenBook."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, cast

from openbook.core.context_pack import build_context_pack
from openbook.core.db import get_connection
from openbook.core.memory import get_review_queue, remember
from openbook.core.project import detect_project_root
from openbook.core.search import get_project_brief


def _send(msg: dict[str, Any]) -> None:
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def _recv() -> Optional[dict[str, Any]]:
    line = sys.stdin.readline()
    if not line:
        return None
    if line.startswith("Content-Length: "):
        length = int(line[len("Content-Length: "):].strip())
        sys.stdin.readline()  # empty line
        data = sys.stdin.read(length)
        return cast(dict[str, Any], json.loads(data))
    return None


def _lastrowid(cur: Any) -> int:
    row_id = cur.lastrowid
    if row_id is None:
        raise RuntimeError("Insert did not return a row id")
    return int(row_id)


def _get_project_info() -> tuple[Path, Any, int]:
    root = detect_project_root()
    conn = get_connection(root)
    root_str = str(root.resolve())
    row = conn.execute("SELECT id FROM projects WHERE root_path = ?", (root_str,)).fetchone()
    if row:
        project_id = int(row["id"])
    else:
        cur = conn.execute(
            "INSERT INTO projects (root_path, name) VALUES (?, ?)",
            (root_str, root.name),
        )
        project_id = _lastrowid(cur)
    return root, conn, project_id


def _get_agent_id(conn: Any, project_id: int) -> int:
    client = os.environ.get("OPENBOOK_CLIENT", "mcp")
    agent_name = os.environ.get("OPENBOOK_AGENT", "openbook-mcp")
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


TOOLS = {
    "openbook_remember": {
        "description": "Store a memory in OpenBook.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "memory_type": {"type": "string", "default": "fact"},
                "chapter": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content"],
        },
    },
    "openbook_search": {
        "description": "Search OpenBook memories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "budget": {"type": "string", "enum": ["tiny", "normal", "deep"], "default": "normal"},
                "chapter": {"type": "string"},
                "memory_type": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    },
    "openbook_brief": {
        "description": "Get a project briefing from OpenBook.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "openbook_handoff": {
        "description": "Create a handoff context pack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to_agent_hint": {"type": "string"},
            },
        },
    },
    "openbook_cite": {
        "description": "Add a citation to a memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer"},
                "file_path": {"type": "string"},
                "line_start": {"type": "integer"},
                "line_end": {"type": "integer"},
                "commit_hash": {"type": "string"},
                "url": {"type": "string"},
                "quote": {"type": "string"},
            },
            "required": ["memory_id"],
        },
    },
    "openbook_review": {
        "description": "Show pending memory proposals.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "openbook_status": {
        "description": "Show OpenBook status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_mcp_server() -> None:
    # Send initialize response first
    msg = _recv()
    if msg and msg.get("method") == "initialize":
        _send({
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "openbook", "version": "0.1.0"},
            },
        })

    _send({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    })

    while True:
        msg = _recv()
        if msg is None:
            break

        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
            })
            continue

        if method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = _handle_tool(tool_name, arguments)
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result}],
                    "isError": False,
                },
            })
            continue

        if req_id is not None:
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


def _handle_tool(name: str, arguments: dict[str, Any]) -> str:
    root, conn, project_id = _get_project_info()
    agent_id = _get_agent_id(conn, project_id)

    if name == "openbook_remember":
        memory_id = remember(
            conn=conn,
            project_id=project_id,
            content=arguments["content"],
            memory_type=arguments.get("memory_type", "fact"),
            title=arguments.get("title"),
            summary=arguments.get("summary"),
            chapter=arguments.get("chapter"),
            tags=arguments.get("tags"),
            agent_id=agent_id,
        )
        return f"Stored memory {memory_id}"

    if name == "openbook_search":
        pack = build_context_pack(
            conn=conn,
            project_id=project_id,
            query=arguments["query"],
            budget=arguments.get("budget", "normal"),
            chapter=arguments.get("chapter"),
            memory_type=arguments.get("memory_type"),
            tags=arguments.get("tags"),
            agent_id=agent_id,
        )
        return pack.to_text()

    if name == "openbook_brief":
        brief = get_project_brief(conn, project_id)
        lines = [f"# {brief.get('project_name', 'Unknown')}"]
        for section in ["commands", "warnings", "decisions", "cover_memories"]:
            items = brief.get(section, [])
            if items:
                lines.append(f"\n## {section.replace('_', ' ').title()}")
                for item in items:
                    lines.append(f"- {item.get('summary', item.get('title', str(item)))}")
        return "\n".join(lines)

    if name == "openbook_handoff":
        pack = build_context_pack(
            conn=conn,
            project_id=project_id,
            query="handoff context",
            budget="tiny",
            agent_id=agent_id,
        )
        return pack.to_text()

    if name == "openbook_cite":
        memory_id = arguments["memory_id"]
        cur = conn.execute(
            """
            INSERT INTO citations (project_id, file_path, line_start, line_end, commit_hash, url, quote)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                arguments.get("file_path"),
                arguments.get("line_start"),
                arguments.get("line_end"),
                arguments.get("commit_hash"),
                arguments.get("url"),
                arguments.get("quote"),
            ),
        )
        citation_id = cur.lastrowid
        conn.execute(
            "UPDATE memories SET citation_id = ? WHERE id = ? AND project_id = ?",
            (citation_id, memory_id, project_id),
        )
        return f"Added citation {citation_id} to memory {memory_id}"

    if name == "openbook_review":
        queue = get_review_queue(conn, project_id)
        if not queue:
            return "No pending proposals."
        lines = ["Pending proposals:"]
        for item in queue:
            lines.append(f"- [{item['id']}] {item['type']}: {item['summary'] or item['content'][:80]}")
        return "\n".join(lines)

    if name == "openbook_status":
        counts = conn.execute(
            "SELECT COUNT(*) as c FROM memories WHERE project_id = ? AND status = 'approved'",
            (project_id,),
        ).fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) as c FROM review_queue WHERE project_id = ? AND status = 'pending'",
            (project_id,),
        ).fetchone()["c"]
        return f"Project: {root.name}\nApproved memories: {counts}\nPending reviews: {pending}"

    return f"Unknown tool: {name}"
