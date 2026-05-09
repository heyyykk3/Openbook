# OpenBook Comparison Notes

Status: draft for public alpha positioning, last reviewed 2026-05-09.

OpenBook's current position is intentionally narrow: one repository, one local SQLite memory book, shared by all coding agents that work in that repo. It is not trying to be a general agent platform, a managed memory service, a personal knowledge base, or a full graph-RAG system.

That constraint is the product. The goal is to make durable project memory boring enough that Codex, Claude Code, Cursor, Aider, Cline, OpenCode, and other coding agents can reuse the same local facts without each assistant inventing its own private lore.

## Comparison Table

| Project | Setup | Provider support | Agent integration | Storage and memory model | Benchmark reproducibility | Current weakness for OpenBook's target |
| --- | --- | --- | --- | --- | --- | --- |
| OpenBook | Local repo tool with SQLite file in the project. No external service should be required for the core path. | Should stay model-agnostic. Provider support belongs at the agent/client layer where possible. | Built for many coding agents sharing one repo-scoped memory book. MCP and CLI paths should make the same store visible to all clients. | Local SQLite memory book with explicit records about project decisions, conventions, files, tasks, and lessons. Not a vector-first personal memory system. | No public benchmark wins should be claimed until the harness, fixtures, data, and reproduction commands are complete. | Early product. Needs hard proof that shared repo memory helps real coding sessions and does not pollute context, age badly, or create false confidence. |
| [Mem0](https://docs.mem0.ai/) | Strong quickstart and managed platform. Open source/self-hosted paths also exist. | Broad application-memory ecosystem, with hosted and self-hosted options, SDK/API use, and framework integrations. | Good for app developers adding memory to agents or products. Less directly focused on multiple coding agents sharing one repo-local memory file. | User, agent, and session-oriented memory layer; typically API/SDK mediated and can involve vector/database infrastructure depending on deployment. | Mem0 has public benchmark/material claims in its own ecosystem, but OpenBook should not compare itself on accuracy until it has reproducible data. | More productized and broader than OpenBook. For repo-local coding workflows, it may feel like adopting a memory platform rather than dropping a memory book into a codebase. |
| [Basic Memory](https://docs.basicmemory.com/start-here/what-is-basic-memory) | Local MCP server over Markdown files; friendly for users who already like plain files and note tools. | LLM-agnostic through MCP clients. Uses local-first Markdown and semantic search patterns. | Excellent fit for MCP-capable assistants and personal/project notes. | Markdown notes, observations, relations, semantic graph, and local knowledge-base workflows. | Not primarily positioned as a coding-agent benchmark project. Reproducibility depends on the user's notes and workflow. | Stronger as a human-readable knowledge base. OpenBook should be simpler for repo-scoped coding memory if it avoids note-garden sprawl and keeps writes structured. |
| [Cognee](https://docs.cognee.ai/core-concepts) | More configurable system. Defaults exist, but serious use can involve LLM, embedding, relational, vector, and graph backend choices. | Broad provider matrix across LLMs, embeddings, vector stores, and graph stores. | Useful when building memory/search/reasoning into larger AI systems. Less narrowly aimed at a shared local memory book for coding agents. | Vector plus graph memory over raw data; configurable graph stores such as Kuzu/Neo4j and vector stores such as LanceDB/Qdrant/Postgres options. | Better suited to data/RAG evaluations than a repo-memory alpha checklist. Any OpenBook comparison needs same tasks, same data, same commands. | More powerful and more complex. OpenBook should not compete on graph sophistication; it should compete on low-friction, inspectable repo memory for day-to-day coding. |
| [Zep / Graphiti](https://help.getzep.com/graphiti/getting-started/overview) | Graphiti has a developer quickstart; Zep also has productized context-layer offerings. | Graphiti/Zep ecosystem is designed around temporal knowledge graphs and agentic applications. | Strong for applications that need evolving relationships, temporal context, and graph search. MCP/local graph offerings also exist. | Temporal knowledge graph with entity/relation history, hybrid search, and time-aware facts. | Zep has published benchmark-oriented material. OpenBook should cite it only as external work and avoid accuracy comparisons until OpenBook can reproduce its own runs. | Much deeper graph model than OpenBook. OpenBook's opportunity is not "better graph memory"; it is a smaller local coding memory primitive that teams can understand and reset. |
| [Letta Code](https://docs.letta.com/letta-code/) | Installable coding agent with login/setup flow. Memory is part of the agent product. | Model-agnostic positioning with support for major model families through Letta. | It is itself a stateful coding agent, not just a shared memory substrate for existing agents. | Git-backed memory filesystem of Markdown files per agent, with self-edited durable memory. | Benchmarks should be compared only when task definitions and transcripts are public and repeatable. | Stronger if a user wants one stateful agent that learns them. OpenBook's counter-position is shared repo memory across many agents, without replacing the agent. |
| Memento MCP / Memento-like MCP servers | There are multiple projects using the Memento name. Some position around local-first MCP memory; others around fragment or activation-based memory. | Usually LLM-agnostic through MCP. Provider support varies by implementation. | Good conceptual overlap: MCP memory servers are natural companions for coding assistants. | Varies. One current Memento positioning describes a local MCP server over a single SQLite file; other "memento" projects use fragment-based or multi-layer memory designs. | OpenBook should not claim superiority without testing the exact implementation and version. | Potentially the closest conceptual neighbor. OpenBook must be sharper on repo ownership, schema, migration story, agent write discipline, and reproducible coding-session evaluation. |

## Honest Positioning

OpenBook is not "memory for all AI." It is repo memory for coding agents.

Use OpenBook when:

- The same codebase is touched by multiple agents or multiple sessions.
- The useful memory is project-local: decisions, conventions, architecture notes, recurring failure modes, test commands, and handoff context.
- The team wants a local, inspectable store instead of a hosted platform or private per-agent notebook.
- The default memory unit should be the repository, not the user, account, organization, or assistant persona.

Do not use OpenBook yet when:

- You need production-grade personalization memory for an end-user application.
- You need temporal knowledge graph reasoning over changing business entities.
- You want a personal note system that humans browse and edit as Markdown.
- You need hosted auth, multi-tenant APIs, dashboards, analytics, retention policies, or enterprise controls.
- You need proven benchmark leadership today.

## What OpenBook Should Say Publicly

Say:

- "OpenBook is a local SQLite memory book for a repository."
- "It is meant to be shared by coding agents rather than owned by one assistant."
- "The alpha is testing whether explicit repo memory improves handoffs, reduces repeated rediscovery, and stays trustworthy over time."
- "Benchmarks are in progress; we will publish commands, fixtures, raw outputs, and failures before making performance claims."

Do not say:

- "OpenBook beats Mem0/Cognee/Zep/Letta."
- "OpenBook is the best memory layer."
- "Drop-in memory for every AI app."
- "Graph memory without the complexity."
- "Production ready."

## Differentiation To Prove

OpenBook's differentiation is plausible but not proven until the alpha produces evidence:

- Setup time: fresh repo to first useful memory in minutes.
- Cross-agent reuse: one agent writes a memory that another agent correctly uses later.
- Retrieval discipline: agents can find relevant memories without stuffing stale context into every prompt.
- Local trust: users can inspect, edit, export, and delete the memory book.
- Low operational burden: no hosted service, graph database, vector store, or per-agent account required for the core workflow.
- Coding specificity: memory schema and prompts are tuned for repository work, not generic chat history.

## Comparison Source Notes

This document relies on public docs and project pages current as of 2026-05-09:

- Mem0 docs describe a universal memory layer with managed and open-source/self-hosted options.
- Basic Memory docs describe an MCP server that reads and writes local Markdown files and builds a semantic graph.
- Cognee docs describe configurable LLM, embedding, vector store, relational database, and graph store backends.
- Zep/Graphiti docs describe temporal knowledge graphs for agentic applications.
- Letta Code docs describe a stateful coding agent with git-backed Markdown memory.
- Memento naming is fragmented; evaluate the exact repository/version before making direct claims.

For benchmark-specific competitor numbers and claim boundaries, see
[competitive-benchmark-landscape.md](competitive-benchmark-landscape.md).
