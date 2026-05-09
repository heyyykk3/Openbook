# Installation

## Requirements

- Python 3.10+
- No Docker required
- No cloud account required
- No API key required (for default FTS-only mode)

## Install from PyPI

```bash
pip install openbook-memory
```

Until the first public tag is published, install from source:

```bash
git clone https://github.com/heyyykk3/Openbook.git
cd Openbook
pip install -e ".[dev]"
```

## Install with pipx

```bash
pipx install openbook-memory
```

## Install with uv

```bash
uv tool install openbook-memory
```

## Optional dependencies

### Vector search with sqlite-vec

```bash
pip install openbook-memory[vector]
```

### Local embeddings with sentence-transformers

```bash
pip install openbook-memory[local]
```

### Development

```bash
pip install openbook-memory[dev]
```

## Optional API Keys

Default FTS mode does not need a key. Gemini and OpenAI-compatible providers read keys from environment variables:

```bash
set GEMINI_API_KEY=your_key
set OPENAI_API_KEY=your_key
```

Copy `.env.example` if your local workflow uses dotenv, but do not commit real keys.

## Upgrade

```bash
pipx upgrade openbook-memory
```

## Verify

```bash
openbook --version
openbook doctor
openbook smoke-test
```

For common setup failures, see [troubleshooting.md](troubleshooting.md).

Expected smoke-test output includes:

```text
OpenBook smoke test passed
Stored memory:
Retrieved memories:
```

## One-command Project Setup

```bash
cd my-repo
openbook setup --project . --yes --client codex
openbook smoke-test
```

For Cursor or Claude Code:

```bash
openbook setup --project . --yes --client cursor
openbook setup --project . --yes --client claude-code
```

## Reset Or Uninstall

Delete one project's memory book:

```bash
rm -rf .openbook
```

PowerShell:

```powershell
Remove-Item -Recurse -Force .openbook
```

Uninstall the package:

```bash
pipx uninstall openbook-memory
pip uninstall openbook-memory
```
