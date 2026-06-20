# OpenBook Private Launch Plan

OpenBook should launch as a private repo first. The initial promise should be
specific:

> A local-first shared memory server for Codex, Claude Code, Cursor, Gemini CLI,
> and other MCP coding agents, powered by Qdrant TurboQuant and pluggable
> embeddings.

Do not position the first private launch as a full Hindsight replacement. The
strongest initial wedge is fast, shared, coding-agent memory with clear local
ownership and strong provider flexibility.

## Private Launch MVP

Required before inviting users:

1. Native macOS installer for Qdrant and OpenBook service.
2. `openbook doctor --deep` that verifies:
   - Qdrant is reachable.
   - Collection uses TurboQuant.
   - Search uses quantization and rescoring settings.
   - Embedding provider works.
   - MCP server is reachable.
   - A write/read smoke test succeeds.
3. `openbook config codex --write` and `openbook config claude --write`.
4. Claude Mem import:
   - read existing Claude Mem Postgres config,
   - import projects and memories,
   - preserve metadata,
   - regenerate or reuse embeddings safely,
   - report imported/skipped/failed counts.
5. Memory browser CLI:
   - list books,
   - list pages,
   - inspect one page,
   - mark stale,
   - delete page.
6. Benchmark command:
   - vector-only TurboQuant benchmark,
   - imported-data benchmark,
   - hybrid recall benchmark,
   - JSON output.
7. Private launch docs:
   - what OpenBook stores,
   - what stays local,
   - how to rotate/delete memories,
   - how to swap embedding providers,
   - how to reset/rebuild Qdrant collections.

## Feature Set To Ship

Core:

- Qdrant TurboQuant vector index.
- SQLite readable ledger.
- MCP tools for write/read/context/handoff.
- Lite MCP profile for normal agent sessions and full profile for admin/curation.
- Codex and Claude Code config helpers.
- Claude Code hook scripts for recent-context injection and explicit `<remember>` capture.
- Multi-provider embeddings.
- Project, branch, session, app, global scopes.
- Hybrid vector + FTS recall.
- Secret redaction and private-tag exclusion.

Coding-agent features:

- Book cover per repo.
- Decision, bugfix, warning, command, convention, task, handoff page types.
- Session close/handoff command.
- Repo mining with ignore rules.
- Recall explanations with vector/text/scope/recency scores.
- Stale memory controls.

Provider features:

- OpenAI.
- OpenAI-compatible endpoints.
- Ollama.
- Gemini.
- Cohere.
- Voyage.
- Sentence Transformers.
- Hash fallback.
- Add next: Jina, Mistral, Mixedbread, Azure OpenAI preset, Bedrock preset,
  Vertex AI preset.

## TurboQuant Claims

Only make claims that match Qdrant's current behavior:

- TurboQuant compresses the stored vector representation.
- Query vectors remain full precision.
- Qdrant stores quantized vectors alongside original vectors.
- Collection disk footprint includes WAL, segments, payload indexes, HNSW, and
  original vectors, so full collection size is not the same as theoretical
  vector compression.

Compression envelope:

| TurboQuant mode | Theoretical vector compression vs float32 |
|---|---:|
| `bits4` | 8x |
| `bits2` | 16x |
| `bits1_5` | 24x |
| `bits1` | 32x |

Launch default:

- `bits4`
- `float16` original vectors
- quantized search enabled
- rescore disabled
- cosine distance
- indexing threshold 1000

Why default to `bits4`: it is the safest private-launch balance between speed,
recall, and compression. Lower-bit modes should be exposed as advanced tuning
after real recall benchmarks pass.

## Real Benchmarks To Run Before Public Launch

Run these on at least 10k, 50k, and 100k memories:

1. Vector-only benchmark:
   - compare Qdrant none/bits4/bits2/bits1_5/bits1,
   - measure disk, ingest, p50/p95 latency, top1/hit10.
2. Imported Claude Mem benchmark:
   - import real Claude Mem memories,
   - compare OpenBook recall against Claude Mem for marker, semantic, and
     continuation queries.
3. Coding continuation benchmark:
   - ask an agent to resume old tasks,
   - measure whether it loads the right project decisions and avoids stale ones.
4. Hindsight-style benchmark:
   - raw session retain,
   - reflection generation,
   - temporal/entity recall,
   - multi-hop project reasoning.
5. Provider benchmark:
   - same memory/query set across local Ollama, Gemini, OpenAI-compatible, Cohere,
     Voyage, and sentence-transformers.

## What Makes OpenBook Different

Against Claude Mem:

- Faster vector path at scale with Qdrant TurboQuant.
- Multi-agent shared MCP daemon.
- Better scoping model for repos, branches, sessions, and apps.
- More embedding provider flexibility.
- More transparent local ledger.

Against Hindsight:

- Smaller local-first coding-agent focus.
- Easier to inspect and edit memories.
- Qdrant/TurboQuant as the performance wedge.
- Less cloud/platform surface.

Hindsight still leads on automated learning, reflection, polished integrations,
and memory benchmarks. OpenBook should close that gap after the private MVP.
