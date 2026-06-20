# TurboQuant Compression Notes

This note separates three different numbers that are easy to confuse:

1. **Theoretical stored-vector compression** from TurboQuant bit depth.
2. **Measured Qdrant collection disk footprint**, which includes original vectors,
   WAL, segments, HNSW/index data, payload indexes, and metadata.
3. **End-to-end OpenBook footprint**, which also includes SQLite ledger data.

For launch, only claim the first number as TurboQuant vector compression. Use the
second and third numbers only when backed by a benchmark output from the target
machine and dataset.

## Documented TurboQuant Envelope

Qdrant documents TurboQuant as supporting the following encoding options:

| Mode | Compression vs float32 vector representation |
|---|---:|
| `bits4` | 8x |
| `bits2` | 16x |
| `bits1_5` | 24x |
| `bits1` | 32x |

Qdrant also documents two operational details that matter for OpenBook:

- TurboQuant uses asymmetric quantization: stored vectors are compressed, while
  query vectors are scored in full precision.
- Quantized vectors are stored alongside original vectors, so measured collection
  size is not equal to just the compressed vector bytes.

## Local Synthetic Sweep

Command:

```bash
.venv/bin/python scripts/benchmark_turboquant_compression.py \
  --docs 10000 \
  --queries 200 \
  --bits none bits4 bits2 bits1_5 bits1 \
  --index-timeout 20
```

Environment:

- Qdrant native `1.18.2`
- 10,000 synthetic vectors
- 768 dimensions
- cosine distance
- original vector datatype `float16`
- original vectors on disk
- payload on disk
- 1 MB WAL
- indexing threshold `1000`
- HNSW `ef=64`
- quantized search, rescoring off

Result:

| Mode | Theoretical vector compression | Measured collection disk | Mean latency | p95 latency | Top1 |
|---|---:|---:|---:|---:|---:|
| none | 1x | 23.9 MB | 4.650 ms | 7.058 ms | 100% |
| `bits4` | 8x | 65.7 MB | 3.313 ms | 4.938 ms | 100% |
| `bits2` | 16x | 64.9 MB | 3.838 ms | 4.924 ms | 100% |
| `bits1_5` | 24x | 26.5 MB | 3.475 ms | 5.495 ms | 100% |
| `bits1` | 32x | 26.0 MB | 3.721 ms | 4.942 ms | 100% |

Interpretation:

- At 10k vectors, collection overhead and original-vector storage still dominate
  disk footprint.
- `bits4` and `bits2` were faster than no quantization but used more measured
  disk in this small synthetic run because Qdrant stores quantized data alongside
  originals.
- `bits1_5` and `bits1` had the best measured disk in this run while preserving
  exact-vector top1, but exact-vector synthetic recall is not enough to choose a
  product default.
- The private-launch default should remain `bits4` until semantic recall on real
  coding-memory data proves lower-bit modes are safe.

## What To Benchmark Next

Before making public claims:

1. Run this script at 50k and 100k vectors.
2. Run imported Claude Mem memories, not only synthetic vectors.
3. Compare `bits4`, `bits2`, `bits1_5`, and `bits1` on semantic recall,
   exact-marker recall, continuation tasks, and stale-decision avoidance.
4. Test both `rescore=false` and `rescore=true --oversampling 2.0`.
5. Repeat with at least two embedding distributions, for example Gemini or Voyage
   and local Ollama/sentence-transformers.
