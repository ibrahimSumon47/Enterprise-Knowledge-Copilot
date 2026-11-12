"""Unit tests for the parts of the API that must never regress."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app import audit, db
from app.config import Settings
from app.ingest import chunk_markdown
from app.pipeline import REFUSAL, classify, verify_answer
from app.redact import redact
from app.retrieval import Retrieved, retrieve


def make_candidate(citation_id: int = 1, content: str | None = None) -> Retrieved:
    return Retrieved(
        chunk_id=f"chunk-{citation_id}",
        document_id=f"doc-{citation_id}",
        title="Expense policy",
        heading="Receipts",
        content=content
        or "Employees must submit receipts for expenses above 25 USD within 45 days.",
        access_level="employee",
        department=None,
        is_synthetic=False,
        source_url="https://example.test/doc",
        license="CC BY-SA 4.0",
        attribution="GitLab Handbook",
        rrf_score=0.03,
        rerank_score=2.5,
        citation_id=citation_id,
    )


def test_chunking_keeps_headings() -> None:
    text = "# Policy\n\nIntro paragraph. " * 3 + "\n\n## Receipts\n\nSubmit receipts within 45 days for anything above 25 USD. " * 4
    chunks = chunk_markdown(text)
    assert chunks
    assert any(chunk["heading"] == "Receipts" for chunk in chunks)
    assert all(len(chunk["content"]) <= 1200 for chunk in chunks)


def test_refusal_on_empty_evidence() -> None:
    ok, reason = verify_answer(REFUSAL, [])
    assert ok is True
    assert reason == "explicit refusal"


def test_answer_without_citation_fails_verification() -> None:
    ok, reason = verify_answer("Employees must submit receipts within 45 days.", [make_candidate()])
    assert ok is False
    assert "citation" in reason


def test_answer_with_unknown_marker_fails() -> None:
    ok, reason = verify_answer("Receipts are required [7].", [make_candidate(1)])
    assert ok is False
    assert "does not exist" in reason


def test_answer_with_real_citation_passes() -> None:
    ok, reason = verify_answer(
        "Employees submit receipts for expenses above 25 USD within 45 days [1].",
        [make_candidate(1)],
    )
    assert ok is True, reason


def test_router_classifies_compensation() -> None:
    assert classify("What is the salary band for staff engineers?") == "compensation"


def test_redaction_strips_email_and_token() -> None:
    cleaned = redact("mail a.b@example.com and Bearer abc.def.ghi")
    assert "a.b@example.com" not in cleaned
    assert "abc.def.ghi" not in cleaned


def test_audit_chain_detects_tampering() -> None:
    payload = {
        "action": "chat.question",
        "resource_type": "conversation",
        "resource_id": "c1",
        "actor_id": "u1",
        "actor_role": "employee",
        "outcome": "ok",
        "ip_hash": "h",
        "detail": {},
        "created_at": "2026-11-11T10:00:00+00:00",
    }
    first = audit.compute_hash(audit.GENESIS, payload)
    second_payload = {**payload, "action": "chat.refused"}
    second = audit.compute_hash(first, second_payload)
    rows = [
        {"id": 1, "prev_hash": audit.GENESIS, "entry_hash": first, **payload},
        {"id": 2, "prev_hash": first, "entry_hash": second, **second_payload},
    ]
    assert audit.verify_chain(rows)["intact"] is True
    rows[0]["entry_hash"] = "tampered"
    assert audit.verify_chain(rows)["intact"] is False


def test_retrieval_uses_sql_permission_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_search(**kwargs: Any):
        captured.update(kwargs)
        return [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "title": "Expense policy",
                "heading": "Receipts",
                "content": "Receipts are required above 25 USD.",
                "access_level": "employee",
                "department": None,
                "is_synthetic": False,
                "source_url": "https://example.test",
                "license": "CC BY-SA 4.0",
                "attribution": "GitLab Handbook",
                "rrf_score": 0.03,
            }
        ]

    monkeypatch.setattr(db, "search_chunks", fake_search)
    monkeypatch.setattr("app.retrieval.embed_query", lambda text, settings: [0.1] * 384)
    monkeypatch.setattr(
        "app.retrieval.rerank",
        lambda question, candidates, settings: [
            {**candidates[0], "rerank_score": 3.0}
        ],
    )

    settings = Settings(supabase_url="https://example.supabase.co")
    result = asyncio.run(retrieve("receipts?", "employee", None, settings))
    assert captured["role"] == "employee"
    assert captured["department"] is None
    assert captured["limit"] == settings.candidate_limit
    assert result.candidates
    assert result.confidence == "high"


def test_long_chunk_is_scored_head_and_tail() -> None:
    """A sentence at the bottom of a long page must reach the cross-encoder."""
    from app.embeddings import _rerank_windows

    long_chunk = {
        "title": "Expense policy",
        "heading": "Receipts",
        "content": ("filler " * 900) + "Submit receipts within 45 days.",
    }
    windows = _rerank_windows(long_chunk, 900)
    assert len(windows) == 2
    assert windows[1].endswith("Submit receipts within 45 days.")
    assert windows[0].startswith("Expense policy — Receipts")

    short_chunk = {"title": "T", "heading": "H", "content": "short"}
    assert len(_rerank_windows(short_chunk, 900)) == 1


def test_graph_compiles() -> None:
    """LangGraph rejects a node whose name is also a state key, so build it here."""
    from app.pipeline import build_graph

    class DummyRouter:
        async def complete(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("the graph must not call the model while compiling")

    graph = build_graph(DummyRouter(), Settings(supabase_url="https://example.test"))  # type: ignore[arg-type]
    assert graph is not None


def test_router_hedges_slow_primary() -> None:
    """A hanging primary must not own the latency budget."""
    import time

    from app.providers import Completion, ProviderRouter

    class Slow:
        name = "slow"

        async def complete(self, system, prompt, max_tokens=700):
            await asyncio.sleep(5)
            return Completion(text="slow", provider="slow", tokens=1)

    class Fast:
        name = "fast"

        async def complete(self, system, prompt, max_tokens=700):
            return Completion(text="fast", provider="fast", tokens=1)

    router = ProviderRouter([Slow(), Fast()], hedge_seconds=0.05)
    started = time.monotonic()
    completion = asyncio.run(router.complete("system", "prompt"))
    assert completion.provider == "fast"
    assert time.monotonic() - started < 1.0


def test_router_fails_over_without_waiting_for_the_timer() -> None:
    """A fast 429 should start the backup immediately, not after the hedge delay."""
    import time

    from app.providers import Completion, ProviderError, ProviderRouter

    class Broken:
        name = "broken"

        async def complete(self, system, prompt, max_tokens=700):
            raise ProviderError("429")

    class Fast:
        name = "fast"

        async def complete(self, system, prompt, max_tokens=700):
            return Completion(text="fast", provider="fast", tokens=1)

    router = ProviderRouter([Broken(), Fast()], hedge_seconds=3.0)
    started = time.monotonic()
    completion = asyncio.run(router.complete("system", "prompt"))
    assert completion.provider == "fast"
    assert time.monotonic() - started < 1.0


def test_router_reports_when_every_provider_fails() -> None:
    import pytest

    from app.providers import ProviderError, ProviderRouter

    class Broken:
        name = "broken"

        async def complete(self, system, prompt, max_tokens=700):
            raise ProviderError("429")

    router = ProviderRouter([Broken()], hedge_seconds=0.0)
    with pytest.raises(ProviderError):
        asyncio.run(router.complete("system", "prompt"))
