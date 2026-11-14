"""LLM providers behind one interface, with a breaker and a deterministic mock."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
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
    # Why the providers that were not used did not win: quota, timeout, error.
    trace: list[str] = field(default_factory=list)


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
        self._timeout = settings.groq_timeout_seconds

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        if not self._key:
            raise ProviderError("groq key missing")
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            # gpt-oss spends completion tokens on hidden reasoning. Left at the
            # default effort it truncated the grounded JSON on simple questions,
            # which the pipeline could only score as an empty-evidence refusal.
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
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
        # The model id is configuration, not a constant: the catalogue retires ids
        # and a retired id answers 404 for every request. The first id that answers
        # is remembered, so a dead alias costs one failed call, not one per question.
        self._timeout = settings.gemini_timeout_seconds
        primary = model or settings.gemini_model
        extra = [name.strip() for name in (settings.gemini_fallbacks or "").split(",") if name.strip()]
        self._models = list(dict.fromkeys([primary, *extra]))

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        if not self._key:
            raise ProviderError("gemini key missing")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
        }
        failures: list[str] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for model in self._models:
                response = await client.post(
                    GEMINI_URL.format(model=model),
                    params={"key": self._key},
                    json=payload,
                )
                if response.status_code >= 400:
                    failures.append(f"{model} http {response.status_code}")
                    continue
                body = response.json()
                try:
                    text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
                except (KeyError, IndexError):
                    failures.append(f"{model} no text")
                    continue
                tokens = int(body.get("usageMetadata", {}).get("totalTokenCount", 0))
                self._models.remove(model)
                self._models.insert(0, model)
                return Completion(text=text, provider=self.name, tokens=tokens)
        raise ProviderError("gemini " + "; ".join(failures))


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
    """Hedged provider calls: the backup starts on a timer, not on failure.

    A quota-limited provider can hang instead of returning 429, and waiting for it
    to time out cost the evaluation a 24 s p95. Each provider is started after a
    short stagger, the first success wins, and a fast failure starts the rest
    immediately instead of waiting out the timer.
    """

    def __init__(
        self,
        providers: list[LLMProvider],
        cooldown_seconds: int = 60,
        hedge_seconds: float = 3.0,
    ) -> None:
        self._providers = providers
        self._cooldown = cooldown_seconds
        self._hedge = hedge_seconds
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        # Counts so the hedge cost can be read from /health instead of guessed.
        self._stats = {"calls": 0, "hedged": 0, "backup_won": 0, "failed_over": 0}

    def _available(self, provider: LLMProvider) -> bool:
        return time.monotonic() >= self._open_until.get(provider.name, 0)

    async def _call(
        self,
        provider: LLMProvider,
        delay: float,
        start_now: asyncio.Event,
        system: str,
        prompt: str,
        max_tokens: int,
    ) -> Completion:
        if delay:
            try:
                await asyncio.wait_for(start_now.wait(), timeout=delay)
            except asyncio.TimeoutError:
                # The primary was still running when the timer expired: this is the
                # double-spend case, paid in exchange for the latency bound.
                self._stats["hedged"] += 1
        return await provider.complete(system, prompt, max_tokens)

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> Completion:
        usable = [provider for provider in self._providers if self._available(provider)]
        skipped = [
            f"{provider.name}: circuit open after repeated failures"
            for provider in self._providers
            if not self._available(provider)
        ]
        if not usable:
            raise ProviderError("; ".join(skipped) or "every provider circuit is open")

        self._stats["calls"] += 1
        errors: list[str] = list(skipped)
        start_now = asyncio.Event()
        tasks = {
            asyncio.create_task(
                self._call(
                    provider,
                    self._hedge * index,
                    start_now,
                    system,
                    prompt,
                    max_tokens,
                )
            ): provider
            for index, provider in enumerate(usable)
        }
        try:
            pending = set(tasks)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    provider = tasks[task]
                    try:
                        completion = task.result()
                    except asyncio.CancelledError:
                        continue
                    except Exception as exc:  # noqa: BLE001 - fall through to the rest
                        logger.warning("provider %s failed: %s", provider.name, type(exc).__name__)
                        self._failures[provider.name] = self._failures.get(provider.name, 0) + 1
                        if self._failures[provider.name] >= 2:
                            self._open_until[provider.name] = time.monotonic() + self._cooldown
                        errors.append(f"{provider.name}: {type(exc).__name__} {str(exc)[:80]}")
                        # A fast failure should not wait out the hedge timer.
                        start_now.set()
                        if provider is usable[0]:
                            self._stats["failed_over"] += 1
                        continue
                    self._failures[provider.name] = 0
                    if provider is not usable[0]:
                        self._stats["backup_won"] += 1
                    completion.trace = list(errors)
                    return completion
            raise ProviderError("; ".join(errors) or "no provider answered")
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    def stats(self) -> dict[str, int]:
        return dict(self._stats)

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
    return ProviderRouter(providers, hedge_seconds=settings.provider_hedge_seconds)
