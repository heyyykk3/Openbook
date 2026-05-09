# Releasing OpenBook

OpenBook is not ready for a broad public launch until the alpha checklist passes,
but the release path should be boring before launch day.

## Pre-release Checklist

Before tagging:

```bash
python -m ruff check .
python -m pytest -q
python -m openbook.cli.main smoke-test
python benchmarks/resource_benchmark.py --memories 25 --searches 5 --report-dir benchmarks/resource/results/ci
python -m pip wheel . -w dist --no-deps
python -m mypy src
```

Also verify:

- LongMemEval report is complete or explicitly marked pending.
- `docs/comparison.md` does not claim wins without data.
- `docs/public-alpha-checklist.md` is updated.
- Temporary API keys used for benchmarks are revoked.
- Benchmark logs are not committed.
- The GitHub repository visibility decision is intentional.

## Versioning

Use alpha tags until installation, MCP integrations, and benchmark publication
are stable:

```bash
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

The tag triggers `.github/workflows/release.yml`, which builds the wheel/sdist
and publishes to PyPI using trusted publishing.

## PyPI Trusted Publishing

Before the first PyPI release:

1. Create the `openbook-memory` project on PyPI.
2. Configure trusted publishing for `heyyykk3/Openbook`.
3. Use the `pypi` environment name from the GitHub Actions workflow.
4. Do not add long-lived PyPI API tokens to the repository.

## Public Alpha Gate

The repo can become public alpha when:

- CI is green.
- `openbook setup --project . --yes --client codex` works.
- At least one second client path works (`claude-code` or `cursor`).
- `openbook smoke-test` works from a clean install.
- Benchmark docs include exact reproduction commands.
- LongMemEval result is published or clearly labeled in progress.

## Do Not Publish

Do not publish if:

- benchmark output contains API keys or account identifiers
- generated datasets/results are accidentally staged
- setup requires undocumented local state
- docs imply production readiness
- temporary benchmark keys have not been revoked
