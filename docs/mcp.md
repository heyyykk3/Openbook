# MCP Integration

OpenBook supports the Model Context Protocol (MCP) via stdio transport.

Status: Codex/Cursor/Claude config generation is implemented and covered by
tests. Full end-to-end validation inside every client is still an alpha launch
task; use `--dry-run` first if you want to inspect the exact config.

## Install For A Client

Project-pinned MCP installs are the recommended path. They set
`OPENBOOK_PROJECT` so each agent opens the correct repo memory book even when
the MCP client launches from another working directory.

Codex:

```bash
openbook mcp install --client codex --project .
```

Claude Code project config:

```bash
openbook mcp install --client claude-code --project .
```

Cursor project config:

```bash
openbook mcp install --client cursor --project .
```

Initialize and install in one command:

```bash
openbook setup --project . --yes --client codex
```

Claude Desktop user config:

```bash
openbook mcp install --client claude-desktop --project .
```

Preview without writing:

```bash
openbook mcp install --client cursor --project . --dry-run
```

## Manual Config

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "openbook": {
      "command": "openbook",
      "args": ["mcp"],
      "env": {
        "OPENBOOK_PROJECT": "/absolute/path/to/your/repo",
        "OPENBOOK_CLIENT": "generic",
        "OPENBOOK_AGENT": "openbook-generic"
      }
    }
  }
}
```

## MCP Tools

### openbook_remember
Store a memory.

```json
{
  "content": "Tests run with pytest -q",
  "memory_type": "command",
  "chapter": "commands",
  "tags": ["testing", "pytest"]
}
```

### openbook_search
Search memories and return a context pack.

```json
{
  "query": "how do tests run?",
  "budget": "normal",
  "chapter": "commands"
}
```

### openbook_brief
Get a project briefing.

### openbook_handoff
Create a handoff context pack for the next agent.

### openbook_cite
Add a citation to a memory.

### openbook_review
Show pending memory proposals.

### openbook_status
Show OpenBook status.

## Clients

- **Codex**: `openbook mcp install --client codex --project .`
- **Claude Code**: `openbook mcp install --client claude-code --project .`
- **Claude Desktop**: `openbook mcp install --client claude-desktop --project .`
- **Cursor**: `openbook mcp install --client cursor --project .`
- **Windsurf**: Add to Windsurf MCP settings
- **Gemini CLI**: Add to Gemini CLI MCP settings
- **OpenCode**: Use the MCP JSON above

## Testing MCP

```bash
openbook mcp print-config
```
