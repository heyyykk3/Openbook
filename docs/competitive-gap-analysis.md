# OpenBook Competitive Gap Analysis

This is a working product checklist for making OpenBook the best local/shared
memory layer for Codex, Claude Code, Cursor, Gemini CLI, OpenCode, and other MCP
coding agents.

## Current Position

OpenBook is no longer a generic vector-memory prototype. The intended core is:

- Qdrant-native vector search with TurboQuant.
- SQLite as the readable ledger for text, metadata, FTS, graph, and audit data.
- Provider-agnostic embeddings.
- MCP-first access for coding agents.
- Project, branch, app, and session scoped recall.

The vector-side target is to beat Claude Mem by using Qdrant's TurboQuant path,
not by depending on one embedding provider.

## Against Claude Mem

| Area | Current Winner | Notes |
|---|---|---|
| Vector speed at 10k synthetic vectors | OpenBook | Qdrant TurboQuant probe: about 4.8 ms mean vs Claude Mem pgvector about 16.7 ms mean. |
| Ingest at 10k synthetic vectors | OpenBook | Qdrant batch upsert was much faster in the vector-only probe. |
| Exact marker recall after FTS fix | OpenBook | Hybrid vector plus FTS returned 100% top-1 in the 1000-memory benchmark. |
| Disk at very small scale | Claude Mem | Postgres has lower fixed overhead for hundreds or low thousands of memories. |
| Already-running reliability | Claude Mem | It is currently live with existing data and fewer moving parts. |
| Multi-agent/shared architecture | OpenBook | Built around one MCP server for multiple coding agents. |
| Embedding provider flexibility | OpenBook | Supports hash, sentence-transformers, OpenAI, OpenAI-compatible, Ollama, Gemini, Cohere, and Voyage. |

What is still missing before OpenBook clearly replaces Claude Mem:

1. One-command native Qdrant installer/start/doctor flow.
2. Config writers that install Codex, Claude Code, Cursor, and OpenCode entries directly.
3. Background service supervision for both Qdrant and OpenBook MCP.
4. Real workload benchmark using imported Claude Mem memories, not only synthetic data.
5. Storage compaction guidance for Qdrant and Postgres after benchmarks/imports.
6. Better recall diagnostics showing vector, FTS, scope, recency, and final rank explanations.
7. Hook installation automation, especially for Codex and non-Claude agents.

## Against Hindsight

Hindsight's major strength is not raw vector search. It is the learning loop:

- Retain: extract and normalize facts, temporal details, entities, and relationships.
- Recall: combine semantic, keyword, graph, and temporal retrieval.
- Reflect: synthesize higher-level observations and mental models.
- Integrations: polished Claude Code/Codex/Gemini/Cursor skills and hooks.
- Deployment: Docker, embedded Python, API, UI, cloud/remote options.

OpenBook already has pieces of this: hybrid vector plus FTS, graph storage,
session handoffs, reflection notes, and MCP tools. It is not yet as complete as
Hindsight in automated learning.

What is still missing versus Hindsight:

1. A real `retain` pipeline that turns raw agent transcripts into structured facts, decisions, warnings, entities, and relations.
2. A real `reflect` pipeline that periodically creates higher-level project mental models.
3. Conversation ingestion hooks for Codex and non-Claude agents; Claude Code hook scripts exist but need installer polish.
4. Agent skills/prompts that make Codex proactively call `read_context`, `write_page`, and `close_session`.
5. Cross-encoder or LLM reranking option for hard queries.
6. Memory banks/templates for coding projects, user preferences, design decisions, incidents, and research.
7. UI or CLI browser for inspecting and editing memories safely.
8. Benchmarks beyond synthetic vector recall: LongMemEval-style, coding-agent continuation, stale-decision avoidance, and exact-ID recall.

## Embedding Provider Roadmap

Already supported:

- `hash`
- `sentence-transformers`
- `openai`
- `openai-compatible`
- `ollama`
- `gemini`
- `cohere`
- `voyage`

High-value provider gaps:

- Jina embeddings.
- Mistral embeddings.
- Mixedbread embeddings.
- AWS Bedrock embeddings.
- Azure OpenAI explicit configuration.
- Vertex AI explicit configuration.
- Local HTTP endpoint presets for llama.cpp or other embedding servers.

The product stance should be: any embedding provider can feed OpenBook, but
Qdrant TurboQuant is the vector engine advantage.

## Next Implementation Cuts

Priority order:

1. Add `openbook install-service` for native Qdrant plus OpenBook LaunchAgents on macOS.
2. Add config writers for Codex, Claude Code, Cursor, OpenCode, and generic MCP clients.
3. Add hook installers for Claude Code first, then Codex/non-Claude agents as their hook surfaces allow.
4. Add `openbook doctor --deep` to verify Qdrant TurboQuant config, embedding provider, MCP health, service status, and sample recall.
5. Add benchmark scripts for imported Claude Mem data and Hindsight-style multi-strategy recall.
6. Add a richer Hindsight-style `reflect` scheduler that writes project mental-model pages over time.
