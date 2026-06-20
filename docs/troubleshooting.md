# Troubleshooting

This page covers the failures most likely to happen during the public alpha.

## `openbook` Command Not Found

Install with one of:

```bash
pipx install openbook-memory
pip install openbook-memory
uv tool install openbook-memory
```

For local development:

```bash
pip install -e ".[dev]"
```

## MCP Client Opens The Wrong Project

Run the installer with an explicit project path:

```bash
openbook mcp install --client codex --project .
openbook mcp install --client cursor --project .
openbook mcp install --client claude-code --project .
```

The generated MCP config should include `OPENBOOK_PROJECT` with an absolute path
to the repository.

## Codex CLI Is Not Found

`openbook mcp install --client codex` shells out to `codex mcp add`. If Codex is
not on `PATH`, preview the command instead:

```bash
openbook mcp install --client codex --project . --dry-run
```

Then run the printed `codex mcp add ...` command in an environment where Codex is
installed.

## Cursor Or Claude Code Does Not See The Server

Check that the generated config exists:

```text
.cursor/mcp.json
.mcp.json
```

Restart the client after writing MCP config. Many MCP clients load stdio server
config only at startup.

## HTTP MCP Returns 406

Streamable HTTP MCP endpoints require an event-stream capable client. A bare
`curl https://localhost:8457/mcp` may return `406 Not Acceptable`; verify with:

```bash
curl -k -H 'Accept: application/json, text/event-stream' https://localhost:8457/mcp
```

## Database Does Not Exist

Initialize the project:

```bash
openbook setup --project . --yes
openbook doctor
```

## SQLite Is Locked

OpenBook uses SQLite WAL and short transactions. If a process crashes mid-write:

1. Stop active agents using the repository.
2. Run `openbook doctor`.
3. Retry the command.

If the lock persists, copy `.openbook/` as a backup before deleting sidecar
SQLite files such as `openbook.sqlite-wal` or `openbook.sqlite-shm`.

## Provider Key Missing

Default FTS mode needs no API key. Gemini and OpenAI-compatible providers read
keys from environment variables:

```bash
set GEMINI_API_KEY=your_key
set OPENAI_API_KEY=your_key
```

Do not store real keys in `.openbook/config.toml`.

## Vector Search Returns Poor Results

First check the no-key baseline:

```bash
openbook search "your query"
```

Then verify provider health:

```bash
openbook providers test
```

If you changed embedding model or dimensions, run `openbook reindex`. Vector
reindexing is still alpha; FTS remains the reliable fallback.

## Reset Everything

The memory book is local:

```bash
rm -rf .openbook
```

On Windows PowerShell:

```powershell
Remove-Item -Recurse -Force .openbook
```

Back up `.openbook/openbook.sqlite` first if you may need the memories later.
