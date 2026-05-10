# Competitive Benchmark Landscape

Status: public-source notes reviewed 2026-05-09. Treat these numbers as each
project's own published claims unless OpenBook reproduces them with the same
data, model stack, prompts, and judge.

## What Serious Memory Tools Publish

| Project | Public benchmark posture | Setup posture OpenBook should learn from |
| --- | --- | --- |
| Mem0 | Publishes leaderboard-style memory numbers, including LoCoMo, LongMemEval, and BEAM, plus token/latency claims. Current site material shows LongMemEval 93.4, LoCoMo 91.8, BEAM 1M 64.1, and BEAM 10M 48.2 style scorecards. | `pip install mem0ai`, hosted/self-hosted options, Docker/self-host docs, `.env` provider setup, and a separate benchmark repo. |
| Zep / Graphiti | Publishes temporal-graph memory benchmarks and latency/context-size comparisons against full context and other memory approaches. | Clear split between managed Zep and OSS Graphiti, with SDK workflows around user/thread memory and graph context. |
| Letta / Letta Code | Publishes memory benchmark writing around LoCoMo and positions memory as context management inside a stateful coding agent. | `npm i -g @letta-ai/letta-code`, first-run agent setup, git-backed memory files, and a complete agent product. |
| Cognee | Publishes graph/vector memory evaluation blog posts and emphasizes configurable local/cloud memory infrastructure. | `pip install cognee`, async API, `.env` provider configuration, local defaults across SQLite/LanceDB/Kuzu, and many integration docs. |
| Basic Memory | Does not appear to lead with public LoCoMo/LongMemEval/BEAM scores. It leads with local-first Markdown, MCP, ownership, and transparent files. | Very strong MCP install docs for Codex and other clients using `uvx basic-memory mcp`. |
| Memento MCP projects | Do not appear to lead with major benchmark numbers. They lead with local SQLite memory, typed memories, installers, optional UI/dashboard, and cross-client MCP. | NPM-style install/init commands and client auto-configuration are the main setup lesson. |

## Benchmark Targets OpenBook Should Support

| Benchmark | Why it matters for OpenBook |
| --- | --- |
| LongMemEval | Directly relevant to long-term memory retrieval and QA; OpenBook already has a reproducible harness. |
| LoCoMo | Common long conversation memory benchmark used by memory vendors for QA-style accuracy claims. |
| BEAM | Large-scale conversational memory benchmark used in current marketing scorecards. Run later; it is heavier than an alpha needs. |
| OpenBook Repo Memory Benchmark | Needed because generic chat-memory benchmarks do not prove coding-agent usefulness. It should test project decisions, commands, conventions, failure recall, and cross-agent handoffs. |

## OpenBook Claim Boundary

OpenBook can honestly claim today:

- no-key local SQLite/FTS memory for a repo
- MCP and CLI access to one shared project memory book
- reproducible LongMemEval retrieval harness
- no-key resource benchmark via `openbook benchmark resource`
- optional provider-backed benchmark runs with Ollama, Gemini, OpenAI-compatible APIs, and sentence-transformers
- LongMemEval_S no-key FTS retrieval baseline: R@10 94.90%, MRR 0.9143
- LongMemEval_S Gemini hybrid QA run: R@10 99.43%, MRR 0.9311, judged QA accuracy 84.00%
- Repo Memory benchmark is now runnable as `openbook benchmark repo-memory`; it is an OpenBook-specific coding-agent workflow benchmark, not a LoCoMo/LongMemEval/BEAM replacement.
- Repo Memory local 11-task report: Hit@3 100.00%, MRR 1.0000, citation presence 100.00%, stale/secret exclusion 100.00%.

OpenBook should not claim yet:

- SOTA memory accuracy
- parity with Mem0, Zep, Cognee, or Letta on broad memory benchmarks
- production-grade vector search in normal CLI/MCP search
- validated support for every MCP client until each has an end-to-end smoke run

## Sources

- [Mem0 docs](https://docs.mem0.ai/)
- [Mem0 research page](https://mem0.ai/research)
- [Mem0 memory-benchmarks repo](https://github.com/mem0ai/memory-benchmarks)
- [Zep Graphiti repo](https://github.com/getzep/graphiti)
- [Zep memory docs](https://help.getzep.com/v2/memory)
- [Letta Code docs](https://docs.letta.com/letta-code)
- [Letta Code memory docs](https://docs.letta.com/letta-code/memory/)
- [Cognee docs](https://docs.cognee.ai/setup-configuration/overview)
- [Basic Memory Codex integration](https://docs.basicmemory.com/integrations/codex/)
- [Memento MCP docs](https://lfrmonteiro99.github.io/memento-mcp/)
