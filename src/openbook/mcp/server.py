"""MCP stdio server for OpenBook."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional, cast

from openbook.server.service import OpenBookService


def _send(msg: dict[str, Any]) -> None:
    data = json.dumps(msg).encode("utf-8")
    stdout = cast(Any, sys.stdout).buffer
    stdout.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
    stdout.flush()


def _recv() -> Optional[dict[str, Any]]:
    stdin = cast(Any, sys.stdin).buffer
    line = stdin.readline()
    if not line:
        return None
    if line.startswith(b"Content-Length: "):
        length = int(line[len(b"Content-Length: "):].strip())
        stdin.readline()  # empty line
        data = stdin.read(length).decode("utf-8")
        return cast(dict[str, Any], json.loads(data))
    return None


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
    while True:
        msg = _recv()
        if msg is None:
            break

        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "openbook", "version": "0.1.0"},
                },
            })
            continue

        if method == "notifications/initialized":
            continue

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
            is_error = False
            try:
                result = _handle_tool(tool_name, arguments)
            except Exception as e:
                is_error = True
                result = str(e)
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result}],
                    "isError": is_error,
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
    service = OpenBookService(client="mcp", agent_name="openbook-mcp")

    if name == "openbook_remember":
        stored = service.remember(
            content=arguments["content"],
            memory_type=arguments.get("memory_type", "fact"),
            title=arguments.get("title"),
            summary=arguments.get("summary"),
            chapter=arguments.get("chapter"),
            tags=arguments.get("tags") or [],
        )
        return f"Stored memory {stored['memory_id']}"

    if name == "openbook_search":
        pack = service.search(
            arguments["query"],
            budget=arguments.get("budget", "normal"),
            chapter=arguments.get("chapter"),
            memory_type=arguments.get("memory_type"),
            tags=arguments.get("tags") or [],
        )
        return pack.to_text()

    if name == "openbook_brief":
        brief = service.brief()
        lines = [f"# {brief.get('project_name', 'Unknown')}"]
        for section in ["commands", "warnings", "decisions", "cover_memories"]:
            items = brief.get(section, [])
            if items:
                lines.append(f"\n## {section.replace('_', ' ').title()}")
                for item in items:
                    lines.append(f"- {item.get('summary', item.get('title', str(item)))}")
        return "\n".join(lines)

    if name == "openbook_handoff":
        return service.handoff(to_agent_hint=arguments.get("to_agent_hint")).to_text()

    if name == "openbook_cite":
        citation_id = service.cite(
            memory_id=arguments["memory_id"],
            file_path=arguments.get("file_path"),
            line_start=arguments.get("line_start"),
            line_end=arguments.get("line_end"),
            commit_hash=arguments.get("commit_hash"),
            url=arguments.get("url"),
            quote=arguments.get("quote"),
        )
        return f"Added citation {citation_id} to memory {arguments['memory_id']}"

    if name == "openbook_review":
        queue = service.review_queue()
        if not queue:
            return "No pending proposals."
        lines = ["Pending proposals:"]
        for item in queue:
            lines.append(f"- [{item['id']}] {item['type']}: {item['summary'] or item['content'][:80]}")
        return "\n".join(lines)

    if name == "openbook_status":
        status = service.status()
        return (
            f"Project: {status['project']}\n"
            f"Approved memories: {status['approved_memories']}\n"
            f"Pending reviews: {status['pending_reviews']}"
        )

    raise ValueError(f"Unknown tool: {name}")
