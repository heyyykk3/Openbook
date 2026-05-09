# Security Policy

OpenBook is local-first software that stores project memory in a SQLite database.
Security reports are welcome, especially around secret handling, MCP exposure,
path traversal, prompt-injection persistence, and unsafe benchmark artifacts.

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| `0.1.x-alpha` | Yes |

## Reporting a Vulnerability

For private repositories, use GitHub private vulnerability reporting or open a
private issue with maintainers. Do not file public issues that include secrets,
exploit payloads, or private user data.

Please include:

- Affected command or API.
- Minimal reproduction steps.
- Expected impact.
- Whether any secrets or private files were exposed.

## Secret Handling

- Do not commit real `.env` files.
- Do not store provider keys in `.openbook/config.toml`.
- Use environment variables such as `GEMINI_API_KEY` and `OPENAI_API_KEY`.
- Rotate any key that appears in logs, screenshots, benchmark output, or chat.

## Benchmark Safety

Benchmark outputs under `benchmarks/**/results/` and downloaded datasets under
`benchmarks/**/data/` are ignored by git. Review all benchmark artifacts before
publishing them.
