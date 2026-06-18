# OpenBook

OpenBook is a local-first, provider-agnostic memory and RAG system for coding
agents. It gives Codex, Claude Code, Cursor, OpenCode, Gemini CLI, Windsurf, and
other MCP-compatible tools one shared project memory per repo.

## Quickstart

```bash
pipx install openbook-memory
cd my-repo
openbook setup --project . --yes --client codex
openbook smoke-test
openbook remember "Tests run with pytest -q" --approve
openbook search "how do tests run?"
```

## Start Here

- [Installation](installation.md)
- [Configuration](config.md)
- [MCP setup](mcp.md)
- [Provider setup](providers.md)
- [Architecture](architecture.md)
- [Benchmarks](benchmarks.md)
- [Security](security.md)
- [Release plan](release-plan.md)

## Why It Exists

Most coding agents keep separate memories, re-read large files repeatedly, or
depend on cloud-only storage. OpenBook keeps memory local, searchable, and
citation-backed in SQLite, while still leaving room for provider-backed and
hybrid retrieval workflows.

## Project Links

- [GitHub repository](https://github.com/heyyykk3/Openbook)
- [PyPI package](https://pypi.org/project/openbook-memory/)
