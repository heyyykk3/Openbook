# Contributing to OpenBook

Thanks for helping build OpenBook. This project is currently in alpha, so the
most useful contributions are focused fixes, provider integrations, benchmark
reproduction, and installation improvements.

## Development Setup

```bash
git clone https://github.com/heyyykk3/Openbook.git
cd openbook
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

For optional local embedding support:

```bash
pip install -e ".[local]"
```

For optional sqlite-vec support:

```bash
pip install -e ".[vector]"
```

## Checks

Run these before opening a pull request:

```bash
python -m ruff check .
python -m pytest -q
python -m mypy src
```

## Design Rules

- Keep SQLite + FTS as the no-key default.
- Do not require Docker or a cloud account for the base path.
- Keep provider credentials in environment variables, never in committed files.
- Prefer small, citation-backed context packs over long Markdown/JSON dumps.
- Treat benchmark claims as reproducible artifacts: publish the dataset, command,
  model names, judge model, and output files.

## Pull Requests

Good pull requests usually include:

- A short explanation of the behavior change.
- Tests for new behavior.
- Documentation updates for user-facing commands or providers.
- Before/after benchmark numbers if retrieval behavior changed.

## Release Notes

Add user-visible changes to `CHANGELOG.md` under `Unreleased`.
