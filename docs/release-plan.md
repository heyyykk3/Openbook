# OpenBook Release Plan

This document tracks how close OpenBook is to open-sourcing and what setup polish
is still needed before a public alpha.

## Release Readiness

| Stage | Status | Notes |
| --- | ---: | --- |
| Internal prototype | 90% | Core SQLite memory, CLI, docs, tests, providers, and benchmarks exist. |
| Public alpha | 70% | Needs packaging polish, installer commands, CI, license/contribution files, and honest MVP docs. |
| Strong public launch | 45-55% | Needs completed benchmark reports, comparison page, npm/uvx install path, and more agent installers. |

## What Other Tools Do

| Tool | Install Pattern | Agent Connection | Storage / Memory Model | Provider Story |
| --- | --- | --- | --- | --- |
| Mem0 | `pip install mem0ai`, `npm install mem0ai`, hosted MCP via `npx mcp-add` | Claude, Claude Code, Codex, Cursor, Windsurf, VS Code, OpenCode through MCP | Qdrant + SQLite defaults for OSS library; hosted and self-hosted modes | OpenAI defaults; OSS docs list OpenAI, Anthropic, Gemini, vector stores, rerankers |
| Basic Memory | `uvx basic-memory mcp` via `codex mcp add` | Codex, Claude Code, Cursor, Claude Desktop, any MCP client | Markdown files as source of truth with MCP sync | Mostly local knowledge management, not provider-heavy |
| Memento MCP | `npm install -g ...`, then `memento-mcp install` | Claude Code, Codex, Cursor, stdio MCP clients | Local-first project memory | Installer is the strong point: npm + auto-client wiring |
| Cognee | `pip install cognee`, Docker MCP, `.env` provider config | MCP integrations for Claude Code, Cursor, Continue, Cline, Roo Code, Codex docs | SQLite/LanceDB/Kuzu local defaults; graph memory options | Broad: OpenAI, Azure, Gemini, Anthropic, Bedrock, Groq, Ollama, LM Studio, HuggingFace, llama.cpp, custom |
| Zep / Graphiti | Cloud SDKs plus local Graphiti MCP | SDK, graph API, MCP for graph memory | Temporal knowledge graph | Strong graph/temporal memory story; cloud-first Zep plus OSS Graphiti |
| Letta Code | Desktop app or `npm install -g @letta-ai/letta-code` | It is a full coding agent, not just memory MCP | Git-backed MemFS markdown memory, subagents, reflection | OpenAI, Anthropic, Gemini, zAI, Minimax, OpenRouter, Bedrock, Azure, Together |

## OpenBook Position

OpenBook should not try to be a full coding agent like Letta. The strongest
position is:

> One repo, one local SQLite memory book, shared by any coding agent.

OpenBook's advantage should be:

- SQLite-first, no Docker, no server required
- FTS search works with zero API keys
- Optional vector search through provider plugins
- Designed around coding-agent workflows and citations
- One runtime per folder shared safely by different coding agents
- Book metaphor: cover, index, chapters, citations, handoff
- Token efficiency: agents query the book instead of loading Markdown/JSON blobs

## Provider Matrix

Current support:

| Provider Type | Current OpenBook Support | Release Target |
| --- | --- | --- |
| FTS / no embedding | Yes | Keep default |
| Ollama embeddings | Yes | Add docs and smoke test |
| Gemini embeddings | Yes | Keep `gemini-embedding-2` default |
| Gemini reader/judge | Yes | Keep `gemini-3-flash-preview`, `gemini-3.1-pro-preview` examples |
| OpenAI-compatible embeddings | Yes | Document OpenAI, OpenRouter, vLLM, LM Studio |
| OpenAI-compatible LLM | Yes | Document OpenAI, OpenRouter, vLLM, LM Studio |
| sentence-transformers | Yes | Document local install extra |
| Anthropic | No direct provider | Add through LiteLLM/OpenAI-compatible if possible, or direct provider later |
| Bedrock / Vertex / Mistral / Cohere rerank | No | Post-alpha |

Alpha target: support 5 practical routes clearly:

1. No-key local FTS
2. Ollama local embeddings
3. Gemini one-key embeddings + QA benchmark
4. OpenAI-compatible cloud/local endpoints
5. sentence-transformers local embeddings

## Agent Connection Matrix

Current:

| Agent / Client | Current OpenBook Path | Needed Before Alpha |
| --- | --- | --- |
| Codex | Manual MCP config / CLI docs | `openbook mcp install --client codex` writes config |
| Claude Code | MCP stdio possible | `openbook mcp install --client claude-code` |
| Cursor | MCP config possible | Write `.cursor/mcp.json` |
| Windsurf | MCP config possible | Add installer snippet |
| OpenCode | MCP config possible | Add installer snippet |
| Gemini CLI | Not documented enough | Add MCP snippet if supported |
| VS Code / Continue / Cline / Roo | Not central for alpha | Add after core coding agents |

## Setup We Should Ship

Minimum alpha install:

```bash
pipx install openbook-memory
cd my-repo
openbook init .
openbook mcp install --client codex
openbook doctor
```

Modern quick install:

```bash
uvx openbook-memory init --mcp codex
```

NPM wrapper, matching what MCP users expect:

```bash
npm install -g @openbook/memory
openbook init
openbook install codex
```

The npm package can be a thin wrapper that:

- checks Python/uv availability
- installs/runs `openbook-memory`
- writes MCP config for selected clients
- prints exact next steps

## Memory / Resource Story

OpenBook should publish these numbers:

| Metric | Need |
| --- | --- |
| Idle RAM | Measure CLI and MCP server idle memory |
| SQLite DB size | Measure after 100, 1k, 10k memories |
| Search latency | Already reported in LongMemEval |
| Token savings | Compare context pack tokens vs raw Markdown/JSON export |
| Startup time | CLI cold start and MCP startup |
| Concurrent access | WAL read/write test with multiple agents |

Expected alpha claim, after measuring:

> OpenBook stores memory in one local SQLite database. Default FTS mode needs no
> embedding model, no API key, no Docker, and no external vector database.

## Benchmark Plan

Public benchmark tiers:

1. LongMemEval retrieval baseline: FTS-only, no API key
2. LongMemEval full QA: Gemini embeddings + Gemini reader + Gemini judge
3. LoCoMo or other conversational memory benchmark
4. Coding-agent memory benchmark: project decision recall, command recall, bug-fix recall

OpenBook should expose benchmarks the way serious memory projects do: runnable
commands, raw outputs, exact model names, charts, and a clear policy for what is
or is not comparable. See `docs/benchmarking-policy.md`.

Do not compare to Mem0/Zep/Signet unless:

- dataset split is identical
- metric is identical
- evaluator model is disclosed
- prompts/config are published

## Alpha Blockers

- Initialize git repo.
- Add `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md`.
- Add GitHub Actions for ruff, pytest, mypy.
- Implement real `openbook mcp install --client ...` config writers.
- Add `openbook setup` wizard path for FTS, Ollama, Gemini, OpenAI-compatible.
- Add npm wrapper or at least document `uvx` install.
- Remove local caches and benchmark datasets from publish artifacts.
- Publish clean benchmark reports without secrets or temporary logs.
- Rotate any temporary benchmark API key before release.

## Release Recommendation

Release `v0.1.0-alpha` when:

- CI passes on GitHub.
- Codex and Claude Code install commands work end to end.
- No-key FTS quickstart works in under 60 seconds.
- Gemini or Ollama provider smoke test is documented.
- One real benchmark report is published.
- Benchmark reproduction docs and raw output format are published.

Then release `v0.2.0` when:

- npm wrapper exists.
- Cursor/Windsurf/OpenCode installers work.
- vector search is persistent and reindexable.
- LongMemEval full QA benchmark is complete and reproducible.
