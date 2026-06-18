"""Embedding provider implementations."""

from __future__ import annotations

import os
import time
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import httpx

from openbook.providers.base import EmbeddingProvider


_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class NoneEmbeddingProvider(EmbeddingProvider):
    """No-op embedding provider."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def model(self) -> str:
        return ""

    @property
    def dimensions(self) -> int:
        return 0

    def embed_text(self, text: str) -> list[float]:
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]

    def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "provider": "none", "message": "Vector search disabled"}


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._dims: Optional[int] = None

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        if self._dims is None:
            try:
                vec = self.embed_text("test")
                self._dims = len(vec)
            except Exception:
                self._dims = 0
        return self._dims

    def embed_text(self, text: str) -> list[float]:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0] if isinstance(embeddings[0], list) else embeddings
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            return [e if isinstance(e, list) else [e] for e in embeddings]

    def health_check(self) -> dict[str, Any]:
        try:
            vec = self.embed_text("health check")
            return {"status": "ok", "provider": "ollama", "model": self._model, "dimensions": len(vec)}
        except Exception as e:
            return {"status": "error", "provider": "ollama", "error": str(e)}


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str, base_url: str, api_key: Optional[str] = None) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""

    @property
    def name(self) -> str:
        return "openai-compatible"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return 0  # Will be inferred on first use

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        return results[0] if results else []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/v1/embeddings",
                headers=headers,
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data.get("data", [])]

    def health_check(self) -> dict[str, Any]:
        try:
            vec = self.embed_text("health check")
            return {"status": "ok", "provider": "openai-compatible", "model": self._model, "dimensions": len(vec)}
        except Exception as e:
            return {"status": "error", "provider": "openai-compatible", "error": str(e)}


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model: str = "gemini-embedding-2",
        api_key: Optional[str] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        output_dimensionality: Optional[int] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._output_dimensionality = output_dimensionality
        self._dims: Optional[int] = output_dimensionality

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        if self._dims is None:
            try:
                self._dims = len(self.embed_text("dimension check"))
            except Exception:
                self._dims = 0
        return self._dims

    def embed_text(self, text: str) -> list[float]:
        return self._embed_one(text, task_type="SEMANTIC_SIMILARITY")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._embed_batch(texts, task_type="SEMANTIC_SIMILARITY")

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text, task_type="RETRIEVAL_QUERY")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")

    def _embed_one(self, text: str, task_type: str) -> list[float]:
        self._require_key()
        payload = self._embed_request(text, task_type)
        data = self._post_json_with_retries(
            f"{self._base_url}/models/{self._model}:embedContent",
            payload,
            timeout=120.0,
        )
        values = data.get("embedding", {}).get("values", [])
        return [float(x) for x in values]

    def _embed_batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        self._require_key()
        if not texts:
            return []
        payload = {
            "requests": [self._embed_request(text, task_type) for text in texts],
        }
        data = self._post_json_with_retries(
            f"{self._base_url}/models/{self._model}:batchEmbedContents",
            payload,
            timeout=240.0,
        )
        embeddings = data.get("embeddings", [])
        return [[float(x) for x in item.get("values", [])] for item in embeddings]

    def _post_json_with_retries(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        timeout: float,
        attempts: int = 6,
    ) -> dict[str, Any]:
        self._validate_post_url(url)
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(attempts):
                try:
                    resp = client.post(url, headers=self._headers(), json=payload)
                except httpx.TimeoutException as exc:
                    if attempt == attempts - 1:
                        raise RuntimeError(
                            "Gemini embedding request timed out while connecting to "
                            f"{self._safe_url_origin(url)}: {exc}. Check the embedding "
                            "endpoint/base URL and DNS/network access."
                        ) from exc
                    time.sleep(_retry_delay(None, attempt))
                    continue
                except httpx.TransportError as exc:
                    if attempt == attempts - 1:
                        raise RuntimeError(
                            "Gemini embedding request failed while connecting to "
                            f"{self._safe_url_origin(url)}: {exc}. Check the embedding "
                            "endpoint/base URL and DNS/network access."
                        ) from exc
                    time.sleep(_retry_delay(None, attempt))
                    continue
                if resp.status_code not in _RETRY_STATUS_CODES:
                    resp.raise_for_status()
                    data = resp.json()
                    return data if isinstance(data, dict) else {}
                if attempt == attempts - 1:
                    resp.raise_for_status()
                time.sleep(_retry_delay(resp, attempt))
        return {}

    def _validate_post_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                f"Gemini embedding request has invalid URL {url!r}. Set the Gemini "
                "embedding base_url to an absolute http(s) URL."
            )

    def _safe_url_origin(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return "<invalid embedding URL>"
        return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    def _embed_request(self, text: str, task_type: str) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": f"models/{self._model}",
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
        }
        if self._output_dimensionality:
            request["outputDimensionality"] = self._output_dimensionality
        return request

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    def _require_key(self) -> None:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini embeddings")

    def health_check(self) -> dict[str, Any]:
        try:
            vec = self.embed_text("health check")
            return {"status": "ok", "provider": "gemini", "model": self._model, "dimensions": len(vec)}
        except Exception as e:
            return {"status": "error", "provider": "gemini", "model": self._model, "error": str(e)}


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str) -> None:
        self._model_name = model
        self._model: Any = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model)
        except ImportError as e:
            raise RuntimeError("sentence-transformers is not installed. Install with: pip install sentence-transformers") from e

    @property
    def name(self) -> str:
        return "sentence-transformers"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        if self._model is None:
            return 0
        return int(self._model.get_sentence_embedding_dimension())

    def embed_text(self, text: str) -> list[float]:
        if self._model is None:
            return []
        return [float(x) for x in self._model.encode(text).tolist()]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            return [[] for _ in texts]
        embeddings = self._model.encode(texts)
        return [[float(x) for x in e.tolist()] for e in embeddings]

    def health_check(self) -> dict[str, Any]:
        try:
            dim = self.dimensions
            return {"status": "ok", "provider": "sentence-transformers", "model": self._model_name, "dimensions": dim}
        except Exception as e:
            return {"status": "error", "provider": "sentence-transformers", "error": str(e)}


def get_embedding_provider(config: dict[str, Any]) -> EmbeddingProvider:
    provider = config.get("provider", "none")
    if provider == "none" or not provider:
        return NoneEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            model=config.get("model", "nomic-embed-text"),
            base_url=config.get("base_url", "http://localhost:11434"),
        )
    if provider == "openai-compatible":
        return OpenAICompatibleEmbeddingProvider(
            model=config.get("model", ""),
            base_url=config.get("base_url", ""),
            api_key=_resolve_api_key(config, "OPENAI_API_KEY"),
        )
    if provider == "gemini":
        dimensions = config.get("dimensions") or config.get("output_dimensionality")
        return GeminiEmbeddingProvider(
            model=config.get("model", "gemini-embedding-2"),
            base_url=config.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
            api_key=_resolve_api_key(config, "GEMINI_API_KEY"),
            output_dimensionality=int(dimensions) if dimensions else None,
        )
    if provider == "sentence-transformers":
        return SentenceTransformersEmbeddingProvider(
            model=config.get("model", "all-MiniLM-L6-v2"),
        )
    raise ValueError(f"Unknown embedding provider: {provider}")


def _resolve_api_key(config: dict[str, Any], default_env: str) -> Optional[str]:
    explicit = config.get("api_key")
    if explicit:
        return str(explicit)
    env_name = str(config.get("api_key_env") or default_env)
    return os.environ.get(env_name)


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    retry_after = response.headers.get("retry-after") if response is not None else None
    if retry_after is not None:
        try:
            return min(120.0, max(1.0, float(retry_after)))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))
