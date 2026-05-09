# Benchmarking Policy

OpenBook should make benchmarks easy for users to run and hard for us to
misrepresent.

## What Other Projects Publish

Memory projects commonly publish both benchmark scores and reproduction paths:

- Mem0 documents LoCoMo, LongMemEval, and BEAM results, including token usage,
  and links to an open-source evaluation framework.
- Cognee publishes research/evaluation results and documents a built-in
  evaluation framework for retrieval quality.
- Letta publishes memory benchmark writing and leaderboard-style comparisons.
- Zep/Graphiti publishes temporal knowledge graph memory results and papers.

The lesson: serious memory tools do not only show a chart. They give users a way
to reproduce or audit the number.

## OpenBook Benchmark Standards

Every published OpenBook score must include:

- benchmark name and dataset version
- exact command used
- git commit SHA
- retrieval mode: `fts`, `vector`, or `hybrid`
- embedding provider and model, or `none`
- reader provider and model, if QA mode is enabled
- judge provider and model, if judged accuracy is enabled
- `top_k` / context budget
- whether abstention questions are included
- latency metrics
- context size or token metrics when available
- raw outputs or a downloadable artifact bundle

## Result Tiers

| Tier | Meaning | Publishable? |
| --- | --- | --- |
| Smoke | Small sample to verify install/auth | No, except as setup proof |
| Retrieval baseline | Full dataset, retrieval-only | Yes, if clearly labeled |
| Full QA | Full dataset, reader + judge | Yes |
| Comparison | OpenBook vs another system | Only if exact method is shared |

## Required Report Files

For a public result, include:

- `summary.md`
- `results.json`
- `records.jsonl`
- `metrics.csv`
- charts from `charts/`

Never publish raw logs that contain API keys, local paths with private names, or
provider error messages containing account information.

## Benchmarks To Support

Alpha:

- LongMemEval retrieval baseline
- LongMemEval full QA

Next:

- LoCoMo
- BEAM or another large-context production-scale memory benchmark
- HotPotQA-style multi-hop retrieval
- OpenBook Repo Memory Benchmark for coding agents

## OpenBook Repo Memory Benchmark

OpenBook should add its own coding-agent benchmark because generic memory
benchmarks do not fully test project memory. The benchmark should test:

- remembering project commands
- remembering architecture decisions
- recalling prior bug fixes
- avoiding stale superseded facts
- returning citations to files, commits, or terminal sessions
- using small context packs instead of dumping the whole memory store

This benchmark should run with no API key in FTS mode, then optionally with
local/cloud embedding providers.
