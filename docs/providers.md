# Providers

OpenBook is provider-agnostic for both embeddings and LLMs.

## Embedding Providers

### none (default)
Disables vector search. Uses SQLite FTS5 only.

```toml
[embeddings]
provider = "none"
```

### ollama
Uses local Ollama embeddings.

```toml
[embeddings]
provider = "ollama"
model = "nomic-embed-text"
base_url = "http://localhost:11434"
dimensions = 768
```

Recommended models:
- `nomic-embed-text`
- `all-minilm`
- `embeddinggemma`
- `qwen3-embedding`

### openai-compatible
Supports any OpenAI-compatible `/v1/embeddings` endpoint.

```toml
[embeddings]
provider = "openai-compatible"
model = "text-embedding-3-small"
base_url = "https://api.openai.com"
```

### gemini
Uses Google Gemini embeddings through one `GEMINI_API_KEY`.

```toml
[embeddings]
provider = "gemini"
model = "gemini-embedding-2"
api_key_env = "GEMINI_API_KEY"
dimensions = 768
```

### sentence-transformers
Local Hugging Face models.

```toml
[embeddings]
provider = "sentence-transformers"
model = "all-MiniLM-L6-v2"
```

Requires: `pip install openbook-memory[local]`

## LLM Providers

### none (default)
Disables LLM use. OpenBook works fully without an LLM.

### ollama

```toml
[llm]
provider = "ollama"
model = "llama3.1"
base_url = "http://localhost:11434"
```

### openai-compatible

```toml
[llm]
provider = "openai-compatible"
model = "gpt-4o-mini"
base_url = "https://api.openai.com"
```

### gemini

```toml
[llm]
provider = "gemini"
model = "gemini-3-flash-preview"
api_key_env = "GEMINI_API_KEY"
```

For benchmark judging, use an explicit judge model such as
`gemini-3.1-pro-preview`.

## Testing Providers

```bash
openbook providers list
openbook providers test
```

## Changing Embedding Models

If you change the embedding model or dimensions, OpenBook will detect incompatible vectors. You can:
- Reindex existing memories
- Keep the old index
- Create a new embedding profile
