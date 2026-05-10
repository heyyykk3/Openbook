# OpenBook Repo Memory Benchmark

Track: coding-agent repo memory
OpenBook version: `0.1.0`
Tasks: **11**

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Hit@1 | 100.00% |
| Hit@3 | 100.00% |
| MRR | 1.0000 |
| Citation presence | 100.00% |
| Stale/secret excluded | 100.00% |
| Mean context tokens | 741.00 |
| Search latency mean/p95 | 0.544 ms / 0.723 ms |

## By Category

| Category | Tasks | Hit@3 | MRR | Citation | Exclusion |
| --- | ---: | ---: | ---: | ---: | ---: |
| benchmark | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| command | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| convention | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| decision | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| failure | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| handoff | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| provider | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| release | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| security | 1 | 100.00% | 1.0000 | 100.00% | 100.00% |
| setup | 2 | 100.00% | 1.0000 | 100.00% | 100.00% |

## Notes

This is a no-key local benchmark. It measures whether OpenBook retrieves repo-scoped coding memories across simulated agents, includes citations, and excludes archived or quarantined memory. It is not comparable to LoCoMo, LongMemEval, or BEAM scores.

## Artifacts

- `results.json`
- `records.jsonl`
- `metrics.csv`
- `charts/scorecard.svg`
