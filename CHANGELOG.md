# Changelog

All notable changes to OpenBook will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic
versioning while in alpha.

## Unreleased

### Added

- SQLite-first memory store with FTS search.
- CLI commands for initialization, memory capture, search, briefings, handoff,
  review, export, provider checks, and MCP.
- Provider support for no-key FTS, Ollama embeddings, Gemini embeddings and LLMs,
  OpenAI-compatible endpoints, and sentence-transformers.
- LongMemEval benchmark harness with retrieval, hybrid search, QA mode, judge
  scoring, checkpointing, and SVG/CSV/JSON reports.
- Release plan covering setup, provider support, agent integrations, memory
  footprint measurements, and benchmark readiness.

### Changed

- Gemini defaults now use `gemini-embedding-2`, `gemini-3-flash-preview`, and
  benchmark judge examples use `gemini-3.1-pro-preview`.

### Security

- Provider API keys are read from environment variables and `.env` files are
  ignored by git.
