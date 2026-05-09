# LongMemEval Benchmark

OpenBook's first standard benchmark target is LongMemEval.

LongMemEval is a long-term memory benchmark for chat assistants. It contains
500 questions across memory types such as single-session recall, multi-session
reasoning, knowledge updates, temporal reasoning, and abstention.

This harness implements the **retrieval track**:

1. Ingest each item's haystack sessions into a fresh OpenBook database.
2. Search OpenBook with the item's question.
3. Compare retrieved session IDs against `answer_session_ids`.
4. Report Recall@K, Hit@K, Precision@K, NDCG@K, MRR, latency, and citation presence.

This is not the full end-to-end QA judge yet. The QA track should be added after
OpenBook has answer generation and an LLM judge/evaluator interface.

## Run The Sample

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset benchmarks/longmemeval/sample_longmemeval.json \
  --k 1,3,5 \
  --report-dir benchmarks/longmemeval/results/sample
```

## Retrieval Modes

The benchmark follows the same pattern used by tools such as Chroma, LangChain,
LlamaIndex, and Mem0: choose an embedding provider/model and choose the retrieval
mode.

FTS-only, no model:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode fts \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-fts
```

Local Ollama embeddings:

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

Local sentence-transformers embeddings:

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

OpenAI-compatible embeddings:

```bash
set OPENAI_API_KEY=your_key
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider openai-compatible \
  --embedding-model text-embedding-3-small \
  --embedding-base-url https://api.openai.com \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-openai-hybrid
```

Gemini embeddings with one Google AI Studio key:

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

## Run Official LongMemEval

Download the official cleaned LongMemEval data automatically:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s
```

Or download the official LongMemEval data manually from:

- https://github.com/xiaowu0162/LongMemEval

Then run:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset path/to/longmemeval_s.json \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s
```

Available official cleaned datasets:

- `--download oracle`: oracle/evidence-only LongMemEval
- `--download s`: LongMemEval_S, roughly 40 history sessions per question
- `--download m`: LongMemEval_M, roughly 500 history sessions per question

For a quick smoke run:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset path/to/longmemeval_s.json \
  --limit 25 \
  --k 1,3,5 \
  --report-dir benchmarks/longmemeval/results/smoke
```

## Report Files

`--report-dir` writes:

- `summary.md`: human-readable benchmark report
- `results.json`: full machine-readable results
- `records.jsonl`: one scored record per question
- `metrics.csv`: overall and per-category metrics
- `charts/recall_at_k.svg`: headline Recall@K chart
- `charts/recall_at_<k>_by_type.svg`: category breakdown chart
- `charts/latency_ms.svg`: ingestion/search latency chart
- `charts/scorecard.svg`: public benchmark scorecard chart

## Full QA Mode

Retrieval mode needs no API key.

Full retrieval-augmented QA mode needs a reader model and optionally a judge
model. This mirrors the official LongMemEval evaluation flow, where hypotheses
are judged against reference answers.

OpenAI-compatible example:

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

Gemini-only example:

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

Local Ollama reader example:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset path/to/longmemeval_s_cleaned.json \
  --k 1,3,5 \
  --qa \
  --reader-provider ollama \
  --reader-model llama3.1 \
  --reader-base-url http://localhost:11434 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-ollama
```

## Metrics

- `hit@k`: at least one gold evidence session appears in top K
- `recall@k`: fraction of gold evidence sessions retrieved in top K
- `precision@k`: fraction of top K retrieved sessions that are gold evidence
- `ndcg@k`: rank-aware retrieval quality for one or more gold sessions
- `mrr`: reciprocal rank of the first gold evidence session
- `abstention_accuracy@k`: for no-answer items, top K should be empty
- `mean_ingest_ms`: average haystack ingestion time per benchmark item
- `mean_search_ms`: average query time per benchmark item
- `citation_presence_rate`: whether retrieved cards include citations

## Why Retrieval First?

LongMemEval can be evaluated end-to-end with generated answers and an LLM judge,
but OpenBook's current MVP is a memory and retrieval layer. Retrieval scoring is
the honest first benchmark: it measures whether OpenBook can find the evidence
before asking a model to reason over it.
