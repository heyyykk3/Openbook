# OpenBook Ecosystem Coverage

OpenBook is not a Claude Mem clone. Claude Mem is one useful baseline for MCP
memory tools, but the product target is broader: a local-first shared memory
layer for coding agents that combines fast vector recall, project continuity,
structured learning, temporal evidence, and operational safety.

## Systems We Track

| System | Strong pattern | OpenBook response |
|---|---|---|
| Claude Mem | Simple MCP memory tools, tags, recent context, Claude hooks, lite/full server split. | Keep compact compatibility aliases, add lite/full MCP profiles, Claude Code hooks, import path, and quality checks. |
| Hindsight | Retain, recall, reflect, and agent-learning loop. | Keep `retain-session`, `recall/read-context`, `reflect`, context contracts, and future scheduler for periodic reflections. |
| OpenMemory / Mem0 | Local portable memory across multiple AI apps. | Keep one shared MCP daemon for Codex, Claude Code, Cursor, Gemini CLI, OpenCode, and custom MCP clients. |
| Zep / Graphiti | Temporal knowledge graph and governed low-latency context assembly. | Keep SQLite graph entities/relations, evidence packs, branch lanes, and future temporal reconciliation. |
| LangMem | Semantic, episodic, and procedural memory updates. | Store memory-layer metadata: semantic, episodic, procedural, operational, reflective, and temporal-graph. |
| Coding-agent practice | Avoid wrong-context edits, stale decisions, and prompt interference. | Use context contracts, decision guard, verification, failure memory, project init, blackboard, and bounded context compilation. |

## Memory Layers

OpenBook stores a `memory_layer` in page metadata for new pages.

| Layer | Typical page kinds | Purpose |
|---|---|---|
| `semantic` | fact, reference, code, cover, bookmark | Stable project knowledge and documentation. |
| `episodic` | diary, transcript, observation, blackboard | What happened in recent sessions and what agents need to resume. |
| `procedural` | decision, preference, warning, command | Rules, habits, constraints, and working commands. |
| `operational` | bugfix | Failures, root causes, and fixes that prevent repeated mistakes. |
| `reflective` | summary, relationship | Higher-level patterns and project mental models. |
| `temporal-graph` | entities and relations | Explainable multi-hop links and evidence paths. |

## Product Decisions

- Normal agent sessions should use `OPENBOOK_MCP_PROFILE=lite` to avoid tool-schema bloat.
- Admin, import, graph, benchmark, and curation sessions should use `OPENBOOK_MCP_PROFILE=full`.
- Memory must be advisory. Current repository files and the user's current ask outrank stored context.
- OpenBook should store many pages, but retrieve only a bounded, task-relevant packet.
- TurboQuant is the vector-engine wedge; it is not a substitute for good retain/reflect/curation loops.

## Remaining High-Value Gaps

1. Native service installer for Qdrant plus OpenBook MCP.
2. Direct config writers for Codex, Claude Code, Cursor, OpenCode, Gemini CLI, and generic MCP clients.
3. Interactive curator with queue/status/execute workflow.
4. Reembed, rebuild, export, backup, and restore commands.
5. Deeper temporal graph extraction and relation reconciliation.
6. Benchmark suite for real coding-agent continuation, stale-decision avoidance, and imported memory data.
7. Hook installers for Codex and other agents as their hook surfaces allow.
