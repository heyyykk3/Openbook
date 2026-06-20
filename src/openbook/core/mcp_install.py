"""MCP client installer helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import toml

ClientName = Literal["codex", "claude-code", "claude-desktop", "cursor", "generic"]
TransportName = Literal["stdio", "http"]
DEFAULT_HTTP_MCP_URL = "https://localhost:8457/mcp"


@dataclass(frozen=True)
class InstallResult:
    client: str
    mode: str
    target: str
    message: str


def mcp_server_config(
    project_root: Path,
    client: str,
    *,
    transport: str | None = "stdio",
    url: str | None = None,
) -> dict[str, Any]:
    """Return an MCP config for either stdio or streamable HTTP transport."""
    normalized_transport = normalize_transport(transport)
    if normalized_transport == "http":
        return {
            "url": url or DEFAULT_HTTP_MCP_URL,
            "startup_timeout_sec": 10,
            "tool_timeout_sec": 120,
        }
    return {
        "command": "openbook",
        "args": ["mcp"],
        "env": {
            "OPENBOOK_PROJECT": str(project_root.resolve()),
            "OPENBOOK_CLIENT": client,
            "OPENBOOK_AGENT": f"openbook-{client}",
        },
    }


def mcp_config_document(
    project_root: Path,
    client: str = "generic",
    *,
    transport: str | None = "stdio",
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "mcpServers": {
            "openbook": mcp_server_config(
                project_root,
                client,
                transport=transport,
                url=url,
            )
        }
    }


def install_mcp_client(
    client: str,
    project_root: Path,
    *,
    dry_run: bool = False,
    codex_bin: str = "codex",
    config_path: Path | None = None,
    transport: str | None = "stdio",
    url: str | None = None,
) -> InstallResult:
    normalized = normalize_client(client)
    project_root = project_root.resolve()
    transport = normalize_transport(transport)
    if normalized == "cursor":
        return install_json_config(
            config_path or project_root / ".cursor" / "mcp.json",
            mcp_config_document(project_root, "cursor", transport=transport, url=url),
            client="cursor",
            dry_run=dry_run,
        )
    if normalized == "claude-code":
        return install_json_config(
            config_path or project_root / ".mcp.json",
            mcp_config_document(project_root, "claude-code", transport=transport, url=url),
            client="claude-code",
            dry_run=dry_run,
        )
    if normalized == "claude-desktop":
        return install_json_config(
            config_path or default_claude_desktop_config_path(),
            mcp_config_document(project_root, "claude-desktop", transport=transport, url=url),
            client="claude-desktop",
            dry_run=dry_run,
        )
    if normalized == "codex":
        return install_codex(
            codex_bin,
            project_root,
            dry_run=dry_run,
            transport=transport,
            url=url,
        )
    return InstallResult(
        client="generic",
        mode="print",
        target="stdout",
        message=json.dumps(
            mcp_config_document(project_root, "generic", transport=transport, url=url),
            indent=2,
        ),
    )


def normalize_client(client: str | None) -> ClientName:
    value = (client or "generic").strip().lower().replace("_", "-")
    aliases = {
        "claude": "claude-code",
        "claude-code-cli": "claude-code",
        "claude-desktop-app": "claude-desktop",
        "cursor-editor": "cursor",
        "openai-codex": "codex",
        "manual": "generic",
        "json": "generic",
    }
    value = aliases.get(value, value)
    if value not in {"codex", "claude-code", "claude-desktop", "cursor", "generic"}:
        raise ValueError(
            "Unsupported MCP client. Use one of: codex, claude-code, claude-desktop, cursor, generic"
        )
    return value  # type: ignore[return-value]


def normalize_transport(transport: str | None) -> TransportName:
    value = (transport or "stdio").strip().lower().replace("_", "-")
    aliases = {
        "streamable-http": "http",
        "https": "http",
        "url": "http",
    }
    value = aliases.get(value, value)
    if value not in {"stdio", "http"}:
        raise ValueError("Unsupported MCP transport. Use one of: stdio, http")
    return value  # type: ignore[return-value]


def install_json_config(
    path: Path,
    update: dict[str, Any],
    *,
    client: str,
    dry_run: bool,
) -> InstallResult:
    existing: dict[str, Any] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8") or "{}")
    merged = merge_mcp_config(existing, update)
    rendered = json.dumps(merged, indent=2) + "\n"
    if dry_run:
        return InstallResult(client=client, mode="dry-run", target=str(path), message=rendered)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return InstallResult(client=client, mode="write", target=str(path), message="installed")


def merge_mcp_config(existing: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    servers = dict(merged.get("mcpServers", {}))
    servers.update(update.get("mcpServers", {}))
    merged["mcpServers"] = servers
    return merged


def install_codex(
    codex_bin: str,
    project_root: Path,
    *,
    dry_run: bool,
    transport: str | None = "stdio",
    url: str | None = None,
) -> InstallResult:
    normalized_transport = normalize_transport(transport)
    if normalized_transport == "http":
        command = [codex_bin, "mcp", "add", "openbook", "--url", url or DEFAULT_HTTP_MCP_URL]
    else:
        env_args = [
            "--env",
            f"OPENBOOK_PROJECT={project_root}",
            "--env",
            "OPENBOOK_CLIENT=codex",
            "--env",
            "OPENBOOK_AGENT=openbook-codex",
        ]
        command = [codex_bin, "mcp", "add", "openbook", *env_args, "--", "openbook", "mcp"]
    if dry_run:
        return InstallResult(
            client="codex",
            mode="dry-run",
            target=codex_bin,
            message=" ".join(_quote_arg(arg) for arg in command),
        )
    if shutil.which(codex_bin) is None:
        raise RuntimeError("Codex CLI was not found on PATH. Install Codex or use --dry-run.")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    message = (completed.stdout or completed.stderr or "installed").strip()
    return InstallResult(client="codex", mode="command", target=codex_bin, message=message)


def default_claude_desktop_config_path() -> Path:
    appdata = Path.home() / "AppData" / "Roaming"
    if appdata.exists():
        return appdata / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def write_codex_toml_fragment(project_root: Path) -> str:
    """Return a TOML fragment for users who want manual Codex config editing."""
    data = {
        "mcp_servers": {
            "openbook": {
                "command": "openbook",
                "args": ["mcp"],
                "env": {
                    "OPENBOOK_PROJECT": str(project_root.resolve()),
                    "OPENBOOK_CLIENT": "codex",
                    "OPENBOOK_AGENT": "openbook-codex",
                },
            }
        }
    }
    return cast(str, toml.dumps(data))


def _quote_arg(arg: str) -> str:
    if not arg or any(char.isspace() for char in arg):
        return '"' + arg.replace('"', '\\"') + '"'
    return arg
