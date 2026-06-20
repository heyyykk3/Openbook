# Shared Runtime

OpenBook is designed for multi-agent use: one repo, one shared memory book.

## One Folder, One Book

```
my-app/
  .openbook/
    openbook.sqlite
```

Codex, Claude Code, Cursor, Gemini CLI, OpenCode, and other agents should use
the OpenBook service surface for this same memory. The service owns project
setup, agent identity, sessions, database connections, and retrieval behavior.

Run the no-key cross-agent smoke test:

```bash
openbook smoke-test --multi-agent
```

This writes a memory as a simulated writer client and retrieves it as a simulated
reader client through the same OpenBook service boundary.

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

## Service Boundary

The canonical runtime boundary is `OpenBookService`. MCP and CLI commands call
that service instead of independently opening and managing the memory database.
SQLite remains the local ledger behind the service; future HTTP or background
daemon transports should route to the same service object.

Daemon commands are reserved for process supervision:

```bash
openbook runtime start
openbook runtime stop
openbook runtime status
```

In the MVP, `runtime` process supervision is not yet implemented, but agent-facing
behavior is already routed through the service boundary.
