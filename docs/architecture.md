# Architecture

OpenBook is built around a database-first design with optional exports.

## Storage

### Primary: SQLite

All real memory lives in `.openbook/openbook.sqlite`.

Tables:
- `projects`: Project identity
- `chapters`: Grouped memory domains
- `memories`: Core memory records
- `citations`: Source-backed references
- `sources`: External sources
- `chunks`: Token-sized text chunks
- `embeddings`: Vector embeddings
- `relations`: Memory-to-memory relations
- `review_queue`: Pending approvals
- `retrieval_logs`: Query history
- `agents`: Agent identities
- `sessions`: Agent sessions
- `events`: Append-only event log
- `locks`: Concurrency locks
- `handoffs`: Agent handoffs

### FTS5

Full-text search via SQLite FTS5 virtual table `memories_fts`.

Triggers keep the FTS index in sync with `memories`.

### Optional Vectors

The schema is designed for `sqlite-vec` to be added later:
- `embeddings.vector` stores BLOB vectors
- `chunks` enables per-chunk embedding
- `embeddings` tracks `provider`, `model`, and `dimensions`

## Retrieval

### Context Packs

The main agent-facing output is a **context pack**:
- Accepts a query and token budget
- Searches FTS5 (and optionally vectors)
- Filters by chapter, type, trust, recency, tags
- Returns compact memory cards with citations
- Deduplicates overlapping memories
- Prefers source-backed and user-approved memories

### Budget Levels

- `tiny`: ~500-800 tokens
- `normal`: ~1500-2500 tokens
- `deep`: ~4000-8000 tokens

### Ranking

Hybrid ranking considers:
- FTS score
- Vector score (if available)
- Trust score
- Importance
- Recency
- Chapter match
- Tag match
- Citation strength
- Approval status

MVP uses a simple weighted score.

## Memory Lifecycle

1. **Proposed**: Agent stores a memory
2. **Review**: Optionally queued for approval
3. **Approved**: Available for retrieval
4. **Archived**: Stale or low-value
5. **Quarantined**: Contains suspected secrets
6. **Rejected**: Discarded

## Temporal Memory

Memories have `valid_from` and `valid_to`.

If a new memory contradicts an old one:
- Old memory is marked superseded
- A relation links old and new
- Retrieval prefers currently valid memories

## Exports

Markdown/JSON exports are for humans only:
- `cover.md`
- `index.md`
- `chapters/*.md`

Agents must use database retrieval by default.

## Modules

```
openbook/
  core/
    db.py          # Schema and migrations
    config.py      # TOML configuration
    models.py      # Data models
    project.py     # Root detection
    search.py      # FTS retrieval
    context_pack.py # Budgeted packs
    memory.py      # CRUD operations
    security.py    # Secret scanning
    exports.py     # Markdown/JSON export
  providers/
    base.py        # Provider interfaces
    embeddings.py  # Embedding providers
    llm.py         # LLM providers
  cli/
    main.py        # Click CLI
  mcp/
    server.py      # MCP stdio server
```
