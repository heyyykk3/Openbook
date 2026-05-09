# Shared Runtime

OpenBook is designed for multi-agent use: one repo, one shared memory book.

## One Folder, One Book

```
my-app/
  .openbook/
    openbook.sqlite
```

Codex, Claude Code, Cursor, Gemini CLI, OpenCode, and other agents can all use this same memory.

## Concurrency Model

### Reads
- SQLite WAL mode enables many concurrent readers
- No locks needed for search or brief

### Writes
- `busy_timeout = 5000ms`
- Short transactions
- Serialized writes via SQLite's WAL locking

## Schema Migration Locks

Only one process runs schema migrations at a time:
- Uses `locks` table with expiration
- If a lock holder crashes, another process can steal the lock after expiration

## Reindex Locks

Only one process runs embedding reindexing at a time.

## Agent Tracking

OpenBook tracks:
- Agent identity (`client_name`, `agent_name`, `version`)
- Session ID
- Process ID
- Hostname
- Current working directory

This helps debug multi-agent interactions.

## Event Log

Append-only `events` table records:
- Memory creation
- Approvals and rejections
- Searches
- Handoffs

## Optional Daemon

For heavier multi-agent use, an optional runtime daemon can be started:

```bash
openbook runtime start
openbook runtime stop
openbook runtime status
```

In the MVP, direct SQLite access is the default and daemon mode is not yet implemented.
