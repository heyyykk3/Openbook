# MCP Integration

OpenBook supports the Model Context Protocol (MCP) via stdio transport.

## Manual Config

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "openbook": {
      "command": "openbook",
      "args": ["mcp"]
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

- **Codex**: Add the MCP JSON to your Codex config
- **Claude Code**: Add via `claude config add mcpServer ...`
- **Cursor**: Add to Cursor MCP settings
- **Windsurf**: Add to Windsurf MCP settings
- **Gemini CLI**: Add to Gemini CLI MCP settings
- **OpenCode**: Use the MCP JSON above

## Testing MCP

```bash
openbook mcp print-config
```
