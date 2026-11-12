"""LLM providers behind one interface, with a breaker and a deterministic mock."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class ProviderError(RuntimeError):
    """Raised when a provider cannot answer; the router falls through."""


@dataclass
class Completion:
    text: str
    provider: str
    tokens: int


class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion: ...


class GroqProvider:
    name = "groq"

    # Groq retired llama-3.3-70b-versatile for free and developer tiers on
    # 2026-08-16, so the free replacement is the default here.
    def __init__(self, settings: Settings, model: str = "openai/gpt-oss-120b") -> None:
        self._key = settings.groq_api_key
        self._model = model

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        if not self._key:
            raise ProviderError("groq key missing")
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                GROQ_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
            )
        if response.status_code >= 400:
            raise ProviderError(f"groq http {response.status_code}")
        body = response.json()
        text = body["choices"][0]["message"]["content"].strip()
        tokens = int(body.get("usage", {}).get("total_tokens", 0))
        return Completion(text=text, provider=self.name, tokens=tokens)


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self._key = settings.gemini_api_key
        # The model id is configuration, not a constant: the v1beta catalogue
        # retires ids, and a retired id answers 404 for every request.
        self._model = model or settings.gemini_model

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        if not self._key:
            raise ProviderError("gemini key missing")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                GEMINI_URL.format(model=self._model),
                params={"key": self._key},
                json=payload,
            )
        if response.status_code >= 400:
            raise ProviderError(f"gemini http {response.status_code}")
        body = response.json()
        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as exc:
            raise ProviderError("gemini returned no text") from exc
        tokens = int(body.get("usageMetadata", {}).get("totalTokenCount", 0))
        return Completion(text=text, provider=self.name, tokens=tokens)


async def list_gemini_models(api_key: str) -> dict[str, Any]:
    """Model ids this key can actually call, so a 404 is diagnosable."""
    if not api_key:
        return {"models": [], "error": "gemini key missing"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(GEMINI_MODELS_URL, params={"key": api_key})
    if response.status_code >= 400:
        return {"models": [], "error": f"http {response.status_code}"}
    body = response.json()
    names = [
        str(model.get("name", "")).removeprefix("models/")
        for model in body.get("models", [])
        if "generateContent" in (model.get("supportedGenerationMethods") or [])
    ]
    return {"models": names, "error": None}


async def probe_gemini(api_key: str, models: list[str]) -> list[dict[str, Any]]:
    """One tiny generation per model, so a 404 is attributable to a model id."""
    if not api_key:
        return [{"model": model, "status": "no key"} for model in models]
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for model in models:
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 8},
            }
            try:
                response = await client.post(
                    GEMINI_URL.format(model=model), params={"key": api_key}, json=payload
                )
                detail = None if response.status_code < 400 else response.text[:160]
                results.append({"model": model, "status": response.status_code, "detail": detail})
            except Exception as exc:  # noqa: BLE001 - diagnostic must not raise
                results.append({"model": model, "status": "error", "detail": type(exc).__name__})
    return results


class MockProvider:
    """Deterministic provider for tests and the offline evaluation subset."""

    name = "mock"

    def __init__(self, answer: str | None = None) -> None:
        self._answer = answer

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        if self._answer is not None:
            return Completion(text=self._answer, provider=self.name, tokens=len(prompt.split()))
        # Echo the first cited passage so citation verification has something real
        # to check. The evaluation subset asserts this behaviour.
        marker = "[1]"
        if marker in prompt:
            start = prompt.index(marker) + len(marker)
            passage = prompt[start : start + 320].strip()
            return Completion(
                text=f"According to the handbook [1], {passage}",
                provider=self.name,
                tokens=len(prompt.split()),
            )
        return Completion(text="I don't know based on the documents I can access.", provider=self.name, tokens=10)


class ProviderRouter:
    """Tries providers in order and opens a circuit after repeated failures."""

    def __init__(self, providers: list[LLMProvider], cooldown_seconds: int = 60) -> None:
        self._providers = providers
        self._cooldown = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def _available(self, provider: LLMProvider) -> bool:
        return time.monotonic() >= self._open_until.get(provider.name, 0)

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        errors: list[str] = []
        for provider in self._providers:
            if not self._available(provider):
                errors.append(f"{provider.name}: circuit open")
                continue
            try:
                completion = await provider.complete(system, prompt, max_tokens)
                self._failures[provider.name] = 0
                return completion
            except Exception as exc:  # noqa: BLE001 - any provider failure must fall through
                logger.warning("provider %s failed: %s", provider.name, type(exc).__name__)
                self._failures[provider.name] = self._failures.get(provider.name, 0) + 1
                if self._failures[provider.name] >= 2:
                    self._open_until[provider.name] = time.monotonic() + self._cooldown
                errors.append(f"{provider.name}: {type(exc).__name__} {str(exc)[:80]}")
        raise ProviderError("; ".join(errors) or "no provider configured")

    def health(self) -> dict[str, str]:
        return {
            provider.name: "open" if not self._available(provider) else "closed"
            for provider in self._providers
        }


def build_router(settings: Settings) -> ProviderRouter:
    providers: list[LLMProvider] = []
    if settings.groq_api_key:
        providers.append(GroqProvider(settings))
    if settings.gemini_api_key:
        providers.append(GeminiProvider(settings))
    if not providers:
        providers.append(MockProvider())
    return ProviderRouter(providers)
