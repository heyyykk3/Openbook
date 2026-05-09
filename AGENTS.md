# Agent Instructions for OpenBook

## Project
OpenBook is a local-first, provider-agnostic, database-backed memory and RAG system for coding agents.

## Stack
- Python 3.10+
- SQLite + FTS5
- Click for CLI
- Optional: sqlite-vec, sentence-transformers, httpx

## Commands
- Install dev: `pip install -e ".[dev]"`
- Run tests: `pytest`
- Lint: `ruff check src`
- Type check: `mypy src`

## Architecture
- Source of truth: SQLite at `.openbook/openbook.sqlite`
- Optional exports: `.openbook/exports/*.md`
- Agents must use database retrieval, not exported Markdown

## Testing
Add tests in `tests/`. Run `pytest` before committing.

## Conventions
- Prefer simple, maintainable code
- Avoid unnecessary frameworks
- Follow existing code style
- Use type hints
