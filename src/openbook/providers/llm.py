"""LLM provider implementations."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

from openbook.providers.base import LLMProvider


_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class NoneLLMProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "none"

    @property
    def model(self) -> str:
        return ""

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        return ""

    def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "provider": "none", "message": "LLM disabled"}


class OllamaLLMProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("response", ""))

    def health_check(self) -> dict[str, Any]:
        try:
            result = self.complete("Say 'ok'", temperature=0.0)
            return {"status": "ok", "provider": "ollama", "model": self._model, "response_preview": result[:50]}
        except Exception as e:
            return {"status": "error", "provider": "ollama", "error": str(e)}


class OpenAICompatibleLLMProvider(LLMProvider):
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

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    def health_check(self) -> dict[str, Any]:
        try:
            result = self.complete("Say 'ok'", temperature=0.0)
            return {"status": "ok", "provider": "openai-compatible", "model": self._model, "response_preview": result[:50]}
        except Exception as e:
            return {"status": "error", "provider": "openai-compatible", "error": str(e)}


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        api_key: Optional[str] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self._model = model
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini generation")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 1024},
        }
        data = self._post_json_with_retries(
            f"{self._base_url}/models/{self._model}:generateContent",
            payload,
            timeout=240.0,
        )
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts)

    def _post_json_with_retries(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        timeout: float,
        attempts: int = 6,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(attempts):
                try:
                    resp = client.post(url, headers=headers, json=payload)
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt == attempts - 1:
                        raise
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

    def health_check(self) -> dict[str, Any]:
        try:
            result = self.complete("Say 'ok'", temperature=0.0)
            return {"status": "ok", "provider": "gemini", "model": self._model, "response_preview": result[:50]}
        except Exception as e:
            return {"status": "error", "provider": "gemini", "model": self._model, "error": str(e)}


def get_llm_provider(config: dict[str, Any]) -> LLMProvider:
    provider = config.get("provider", "none")
    if provider == "none" or not provider:
        return NoneLLMProvider()
    if provider == "ollama":
        return OllamaLLMProvider(
            model=config.get("model", "llama3.1"),
            base_url=config.get("base_url", "http://localhost:11434"),
        )
    if provider == "openai-compatible":
        return OpenAICompatibleLLMProvider(
            model=config.get("model", ""),
            base_url=config.get("base_url", ""),
            api_key=_resolve_api_key(config, "OPENAI_API_KEY"),
        )
    if provider == "gemini":
        return GeminiLLMProvider(
            model=config.get("model", "gemini-3-flash-preview"),
            base_url=config.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
            api_key=_resolve_api_key(config, "GEMINI_API_KEY"),
        )
    raise ValueError(f"Unknown LLM provider: {provider}")


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
