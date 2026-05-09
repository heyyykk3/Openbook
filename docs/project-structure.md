# Project Structure

OpenBook keeps the repository small and release-focused.

```text
Openbook/
├── src/openbook/                 # Python package
│   ├── cli/                      # Click CLI entrypoint
│   ├── core/                     # SQLite, memory, search, context packs
│   ├── mcp/                      # MCP stdio server
│   ├── providers/                # Embedding and LLM providers
│   └── server/                   # Reserved for future runtime/server work
├── tests/                        # Unit and benchmark-harness tests
├── docs/                         # User and release documentation
├── benchmarks/longmemeval/       # Reproducible benchmark harness
├── .github/                      # CI and contribution templates
├── pyproject.toml                # Package metadata and dependencies
└── README.md                     # Project overview and quickstart
```

Ignored local state:

- `.openbook/`
- `.venv/`
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `benchmarks/**/data/`
- `benchmarks/**/results/`
- `.env`

## Public Repo Pattern

OpenBook follows the structure common in successful memory/RAG projects:

- clear README and quickstart
- package metadata in `pyproject.toml`
- docs in a dedicated `docs/` directory
- reproducible benchmarks in `benchmarks/`
- tests in `tests/`
- CI under `.github/workflows/`
- explicit `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and `CHANGELOG.md`

The main difference is intentional: OpenBook's source of truth is SQLite, while
Markdown/JSON are exports rather than the primary memory store.
