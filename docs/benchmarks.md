# Benchmarks

OpenBook uses real memory/RAG benchmarks, starting with LongMemEval.

For benchmark publication rules and comparison standards, see
[benchmarking-policy.md](benchmarking-policy.md). For runnable benchmark entry
points, see [../benchmarks/README.md](../benchmarks/README.md).

## Installed No-Key Benchmark

Every installed OpenBook package includes two no-key benchmarks:

```bash
openbook benchmark repo-memory
openbook benchmark resource --memories 100 --searches 20
```

They write `summary.md`, `results.json`, raw records, CSV metrics, and charts.
They do not require API keys, model downloads, Docker, or benchmark datasets.

`repo-memory` is the OpenBook-specific benchmark. It checks project command
recall, architecture decision recall, setup gotchas, coding conventions,
failure recovery, cross-agent handoff recall, citation presence, and exclusion
of stale/quarantined memory.

## Published Results

- [LongMemEval_S FTS full 500 report](../benchmarks/published/longmemeval-s-fts-full-500/summary.md):
  no-key SQLite FTS retrieval baseline with summary, raw records, metrics CSV,
  and SVG charts.
- [LongMemEval_S Gemini hybrid QA full 500 report](../benchmarks/published/longmemeval-s-gemini-hybrid-qa-full-500/summary.md):
  Gemini embeddings plus Gemini reader/judge, including retrieval and judged QA
  metrics.
- [Repo Memory local 11-task report](../benchmarks/published/repo-memory-local-11-task/summary.md):
  no-key coding-agent memory workflow benchmark with command, decision,
  convention, failure, handoff, provider, release, setup, and security tasks.

## LongMemEval

LongMemEval is the first benchmark target because it is a widely used long-term
memory benchmark for agent memory tools.

OpenBook currently supports the LongMemEval retrieval track:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset benchmarks/longmemeval/sample_longmemeval.json \
  --k 1,3,5 \
  --report-dir benchmarks/longmemeval/results/sample
```

With official data:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s
```

This benchmark reports:

- Recall@K
- Hit@K
- Precision@K
- NDCG@K
- MRR
- abstention accuracy
- ingestion latency
- search latency
- citation presence

When `--report-dir` is set, the benchmark writes:

- `summary.md`
- `results.json`
- `records.jsonl`
- `metrics.csv`
- SVG charts for public scorecard, Recall@K, category Recall@K, and latency
- run metadata including OpenBook version, git commit when available, Python,
  platform, dataset SHA256, and the command used

## Local Embeddings

The LongMemEval harness supports the same provider-style setup used by common
RAG tools:

- `--retrieval-mode fts`: SQLite FTS5 only, no embeddings
- `--retrieval-mode vector`: local/cloud embeddings only
- `--retrieval-mode hybrid`: combines FTS and vector scores

Local Ollama example:

```bash
ollama pull nomic-embed-text
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider ollama \
  --embedding-model nomic-embed-text \
  --embedding-base-url http://localhost:11434 \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-ollama-hybrid
```

Local sentence-transformers example:

```bash
pip install ".[local]"
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider sentence-transformers \
  --embedding-model all-MiniLM-L6-v2 \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-minilm-hybrid
```

Gemini embeddings example:

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

## Full QA Mode

Retrieval mode does not need an API key.

Full QA mode needs a reader model. To produce judged QA accuracy, it also needs
a judge model. Both support `openai-compatible` and `ollama` providers.

Example:

```bash
set OPENAI_API_KEY=your_key
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --k 1,3,5,10 \
  --qa \
  --qa-top-k 10 \
  --reader-provider openai-compatible \
  --reader-model gpt-4o-mini \
  --reader-base-url https://api.openai.com \
  --judge-provider openai-compatible \
  --judge-model gpt-4o \
  --judge-base-url https://api.openai.com \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-qa
```

Gemini-only QA:

```bash
set GEMINI_API_KEY=your_key
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider gemini \
  --embedding-model gemini-embedding-2 \
  --qa \
  --qa-top-k 10 \
  --reader-provider gemini \
  --reader-model gemini-3-flash-preview \
  --judge-provider gemini \
  --judge-model gemini-3.1-pro-preview \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-gemini-qa
```

## Current Scope

The harness measures retrieval quality and optional end-to-end QA. Retrieval
results are useful for memory-layer development. QA results are better for
public comparisons, but they must disclose the reader and judge model.

Normal OpenBook `remember` and `search` commands currently use SQLite FTS. The
vector and hybrid retrieval paths live in the benchmark harness while the
product vector index is hardened.

Future benchmark tracks should add:

- LoCoMo long-term conversational memory
- BEIR/MTEB-style retrieval comparisons for embedding providers
- OpenBook Repo Memory Benchmark for coding-agent project memory
