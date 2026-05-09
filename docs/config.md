# Configuration

OpenBook uses TOML configuration at `.openbook/config.toml`.

## Default Config

```toml
[storage]
database = ".openbook/openbook.sqlite"
vector_backend = "none"

[retrieval]
mode = "fts"
default_budget = "normal"

[embeddings]
provider = "none"
model = ""
base_url = ""
dimensions = 0
api_key_env = ""

[llm]
provider = "none"
model = ""
base_url = ""
api_key_env = ""
```

## Sections

### [storage]

- `database`: Path to SQLite database
- `vector_backend`: `none` or `sqlite-vec`

### [retrieval]

- `mode`: `fts`, `vector`, or `hybrid`
- `default_budget`: `tiny`, `normal`, or `deep`

### [embeddings]

- `provider`: `none`, `ollama`, `gemini`, `openai-compatible`, `sentence-transformers`
- `model`: Model name
- `base_url`: Server URL
- `dimensions`: Vector dimensions
- `api_key_env`: Optional environment variable name for provider API keys

### [llm]

- `provider`: `none`, `ollama`, `gemini`, `openai-compatible`
- `model`: Model name
- `base_url`: Server URL
- `api_key_env`: Optional environment variable name for provider API keys

## Example: Local Semantic

```toml
[storage]
database = ".openbook/openbook.sqlite"
vector_backend = "sqlite-vec"

[retrieval]
mode = "hybrid"
default_budget = "normal"

[embeddings]
provider = "ollama"
model = "nomic-embed-text"
base_url = "http://localhost:11434"
dimensions = 768

[llm]
provider = "ollama"
model = "llama3.1"
base_url = "http://localhost:11434"
```

## Example: Gemini Semantic Search

Set the key in your shell:

```bash
set GEMINI_API_KEY=your_key
```

Then configure OpenBook:

```toml
[storage]
database = ".openbook/openbook.sqlite"
vector_backend = "sqlite-vec"

[retrieval]
mode = "hybrid"
default_budget = "normal"

[embeddings]
provider = "gemini"
model = "gemini-embedding-2"
dimensions = 768
api_key_env = "GEMINI_API_KEY"

[llm]
provider = "gemini"
model = "gemini-3-flash-preview"
api_key_env = "GEMINI_API_KEY"
```

## Environment Variables

- `OPENBOOK_CLIENT`: Client name (e.g., `codex`, `cursor`)
- `OPENBOOK_AGENT`: Agent name
- `GEMINI_API_KEY`: Default key for Gemini embeddings and generation
- `OPENAI_API_KEY`: Default key for OpenAI-compatible embeddings and generation

## Auto-Detection

The setup wizard auto-detects:
- Git repo root
- Project name from README
- Stack from config files
- Available Ollama server
- Existing MCP clients
- sqlite-vec availability
