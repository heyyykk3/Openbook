# Resource Benchmarks

OpenBook's resource benchmark measures the practical footprint of a local
memory workflow without requiring API keys or network access. It is designed to
run quickly in CI with small defaults while still supporting larger local runs.

## Quick Start

```bash
openbook benchmark resource --memories 100 --report-dir benchmarks/resource/results/smoke
```

From a source checkout, `python benchmarks/resource_benchmark.py ...` remains a
compatibility wrapper around the same packaged benchmark code.

The command writes:

- `summary.md`: a short Markdown report for humans.
- `results.json`: structured benchmark data for CI, comparisons, or dashboards.

## What It Measures

- SQLite database size and bytes per memory.
- Insert latency, including min, mean, p50, p95, and max.
- Full-text search latency, including min, mean, p50, p95, and max.
- Context pack size in bytes, characters, and approximate tokens.
- Peak process RSS when the current platform exposes it through Python.

The benchmark uses deterministic synthetic memories and SQLite FTS5. That keeps
it portable and no-key while providing a useful baseline for comparing OpenBook's
resource profile against other memory tools or future implementation changes.

## CLI Options

```bash
openbook benchmark resource \
  --memories 1000 \
  --searches 100 \
  --context-limit 50 \
  --report-dir benchmarks/resource/results/local \
  --work-dir benchmarks/resource/work/local
```

- `--memories`: number of synthetic memories to insert. Default: `100`.
- `--searches`: number of full-text searches to run. Default: `20`.
- `--context-limit`: number of recent memories to pack into context. Default:
  `20`.
- `--seed`: deterministic data generation seed. Default: `1337`.
- `--report-dir`: output directory for `summary.md` and `results.json`.
- `--work-dir`: optional scratch directory for the SQLite database. If omitted,
  a temporary directory is used.

## CI Usage

Keep CI runs small so they catch regressions without adding meaningful wall time:

```bash
openbook benchmark resource --memories 25 --searches 5 --report-dir benchmarks/resource/results/ci
```

For local comparisons, use a stable `--work-dir` and save each `--report-dir`
under a named subdirectory. Do not compare absolute latency numbers across very
different machines; use them to spot large changes on the same machine or runner.
