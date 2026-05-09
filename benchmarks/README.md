# OpenBook Benchmarks

This directory contains reproducible benchmark harnesses for OpenBook.

OpenBook treats benchmarks as source artifacts, not marketing screenshots. Every
published score should include:

- dataset name and version
- exact command
- retrieval mode
- embedding provider and model
- reader model, if QA mode is enabled
- judge model, if judged QA accuracy is reported
- context budget or `top_k`
- latency and token/context-size metrics when available
- raw machine-readable output files

## Available Benchmarks

| Benchmark | Path | Status | What It Measures |
| --- | --- | --- | --- |
| LongMemEval | `benchmarks/longmemeval/` | Active | Long-term memory retrieval and optional QA |

## Quick Smoke Test

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --dataset benchmarks/longmemeval/sample_longmemeval.json \
  --k 1,3,5 \
  --report-dir benchmarks/longmemeval/results/sample
```

## Official LongMemEval Retrieval

No API key required:

```bash
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode fts \
  --include-abstention \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-fts
```

## Full LongMemEval QA

Requires a reader model and a judge model. This example uses one Gemini API key:

```bash
set GEMINI_API_KEY=your_key
python benchmarks/longmemeval/openbook_longmemeval.py \
  --download s \
  --retrieval-mode hybrid \
  --embedding-provider gemini \
  --embedding-model gemini-embedding-2 \
  --embedding-batch-size 32 \
  --qa \
  --qa-top-k 10 \
  --reader-provider gemini \
  --reader-model gemini-3-flash-preview \
  --judge-provider gemini \
  --judge-model gemini-3.1-pro-preview \
  --include-abstention \
  --k 1,3,5,10 \
  --report-dir benchmarks/longmemeval/results/openbook-longmemeval-s-gemini-full
```

The full run writes a checkpoint file after every completed item:

```text
benchmarks/longmemeval/results/<run>/checkpoint.records.jsonl
```

If the run is interrupted, rerun the same command with the same `--report-dir`
and completed records will be skipped.

## Output Files

Each report directory contains:

- `summary.md`: human-readable report
- `results.json`: full structured result object
- `records.jsonl`: per-question scored records
- `metrics.csv`: flattened metrics for spreadsheets
- `charts/*.svg`: dependency-free charts
- `checkpoint.records.jsonl`: resumable progress for long QA runs

## What Not To Claim

Do not claim OpenBook is better than another memory system unless the comparison
uses the same dataset split, same evaluator, same model stack, and same scoring
script. Memory benchmarks are sensitive to prompt wording, judge choice, and
context budget.
