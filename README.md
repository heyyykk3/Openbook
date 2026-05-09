# OpenBook

**One folder, one shared memory book, every coding agent.**

OpenBook is a local-first, provider-agnostic, database-backed memory and RAG system for coding agents. It gives Codex, Claude Code, Cursor, OpenCode, Gemini CLI, Windsurf, and other MCP-compatible tools a shared project memory without forcing agents to read large Markdown or JSON files.

Status: **v0.1.0-alpha candidate**. The core no-key SQLite/FTS workflow is usable now. Vector retrieval and provider-backed QA are available in the benchmark/provider layer first; normal `remember` and `search` commands currently use SQLite FTS.

## Why OpenBook?

Most coding agents today either:
- Re-read entire READMEs and codebases on every turn
- Store memories in opaque, cloud-only services
- Require external vector databases or Docker daemons

OpenBook solves this by turning a repo into a **living, searchable, citation-backed project book** that agents can read, update, search, and cite directly from a lightweight local SQLite database.

## Core Principles

- **Local-first**: Everything lives in `.openbook/openbook.sqlite`
- **SQLite-first**: Source of truth is SQLite + FTS5; Markdown/JSON are optional exports
- **Token-efficient**: Retrieval returns small, budgeted context packs, not wall-of-text dumps
- **Citation-backed**: Every memory can cite file paths, commits, terminal sessions, and URLs
- **Provider-aware**: Works without embeddings; benchmark/provider hooks support Ollama, Gemini, OpenAI-compatible APIs, and sentence-transformers
- **Multi-agent safe**: Concurrent reads via WAL; serialized writes; tracked agent identity

## Quickstart

```bash
pipx install openbook-memory
cd my-repo
openbook setup --project . --yes --client codex
openbook smoke-test
openbook remember "Tests run with pytest -q" --approve
openbook search "how do tests run?"
```

## Installation

- `pip install openbook-memory`
- `pipx install openbook-memory`
- `uv tool install openbook-memory`

See [docs/installation.md](docs/installation.md) for details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `openbook init .` | Initialize `.openbook` in the project |
| `openbook setup --client codex` | Initialize and optionally install MCP |
| `openbook smoke-test` | Verify init/write/search with no API key |
| `openbook remember "..."` | Store a memory |
| `openbook search "..."` | Search memories |
| `openbook brief` | Get a project briefing |
| `openbook handoff` | Create a handoff context pack |
| `openbook review` | Show pending proposals |
| `openbook approve <id>` | Approve a memory |
| `openbook reject <id>` | Reject a memory |
| `openbook export` | Generate Markdown/JSON exports |
| `openbook doctor` | Check health of database, config, and providers |
| `openbook prune` | Archive stale memories |
| `openbook reindex` | Rebuild FTS/vector indexes |
| `openbook providers list` | List providers |
| `openbook providers test` | Test configured providers |

## MCP

OpenBook supports MCP stdio by default:

```bash
openbook mcp install --client codex --project .
openbook mcp install --client claude-code --project .
openbook mcp install --client cursor --project .
```

MCP tools: `openbook_remember`, `openbook_search`, `openbook_brief`, `openbook_handoff`, `openbook_cite`, `openbook_review`, `openbook_status`.

See [docs/mcp.md](docs/mcp.md).

## Slash Commands

Agents that support slash commands can use:

- `/openbook init`
- `/openbook remember <text>`
- `/openbook search <query>`
- `/openbook brief`
- `/openbook handoff`
- `/openbook review`
- `/openbook export`
- `/openbook doctor`

## Configuration

Edit `.openbook/config.toml`:

```toml
[storage]
database = ".openbook/openbook.sqlite"
vector_backend = "none"

[retrieval]
mode = "fts"
default_budget = "normal"

[embeddings]
provider = "none"
model = ""
base_url = ""
dimensions = 0
api_key_env = ""

[llm]
provider = "none"
model = ""
base_url = ""
api_key_env = ""
```

Provider keys are read from environment variables, not committed config files. For Gemini, set `GEMINI_API_KEY`; for OpenAI-compatible endpoints, set `OPENAI_API_KEY`.

See [docs/config.md](docs/config.md).
Troubleshooting is in [docs/troubleshooting.md](docs/troubleshooting.md).

## Repository Structure

See [docs/project-structure.md](docs/project-structure.md) for the source tree,
ignored local state, and release repo layout.

## Architecture

- **Database-first**: All real memory lives in SQLite
- **FTS5**: Keyword/full-text search by default
- **Optional vectors**: Schema supports `sqlite-vec` for vector search
- **Context packs**: Budgeted retrieval (`tiny`, `normal`, `deep`)
- **Trust scores**: High for user-approved notes and repo files; low for uncited claims
- **Temporal memory**: `valid_from`/`valid_to` with supersede relations

See [docs/architecture.md](docs/architecture.md).

## Benchmarks

OpenBook starts with LongMemEval, a standard long-term memory benchmark.

Run the installed no-key resource benchmark:

```bash
openbook benchmark resource --memories 100 --searches 20
```

Run the included sample:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset benchmarks/longmemeval/sample_longmemeval.json \
  --k 1,3,5 \
  --report-dir benchmarks/longmemeval/results/sample
```

Run the official cleaned LongMemEval_S retrieval benchmark:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode fts \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s
```

Run with local Ollama embeddings:

```bash
ollama pull nomic-embed-text
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider ollama \
  --embedding-model nomic-embed-text \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-ollama-hybrid
```

Run with Gemini embeddings:

```bash
set GEMINI_API_KEY=your_key
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider gemini \
  --embedding-model gemini-embedding-2 \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-gemini-hybrid
```

See [benchmarks/README.md](benchmarks/README.md) for runnable entry points,
[docs/benchmarks.md](docs/benchmarks.md) for details, and
[docs/benchmarking-policy.md](docs/benchmarking-policy.md) for what counts as a
publishable score.
See [docs/resource-benchmarks.md](docs/resource-benchmarks.md) for local
footprint measurements.
See [docs/competitive-benchmark-landscape.md](docs/competitive-benchmark-landscape.md)
for the current head-to-head benchmark landscape and claim boundary.

## Release Plan

OpenBook is currently targeting a public `v0.1.0-alpha`. See
[docs/release-plan.md](docs/release-plan.md) for the setup, provider,
agent-integration, benchmark, and open-source launch checklist.
See [docs/comparison.md](docs/comparison.md) for the head-to-head positioning
and [docs/public-alpha-checklist.md](docs/public-alpha-checklist.md) for the
launch gate.
See [docs/releasing.md](docs/releasing.md) for tag and PyPI release steps.

## Security

- `.openbookignore` prevents indexing secrets and build artifacts
- Secret scanning redacts and quarantines suspected secrets before storage
- Redaction in search results and context packs
- Full local wipe supported

See [docs/security.md](docs/security.md).

## Shared Runtime

One `.openbook/openbook.sqlite` per repo, shared across all agents:
- WAL mode for concurrent readers
- Busy timeout and short transactions for safe writes
- Append-only event log
- Per-agent sessions

See [docs/shared-runtime.md](docs/shared-runtime.md).

## Contributing

OpenBook is open source. Contributions welcome!

## License

MIT
