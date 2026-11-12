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


def test_graph_compiles() -> None:
    """LangGraph rejects a node whose name is also a state key, so build it here."""
    from app.pipeline import build_graph

    class DummyRouter:
        async def complete(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("the graph must not call the model while compiling")

    graph = build_graph(DummyRouter(), Settings(supabase_url="https://example.test"))  # type: ignore[arg-type]
    assert graph is not None


def _retrieval_row(index: int) -> dict:
    return {
        "chunk_id": f"chunk-{index}",
        "document_id": f"doc-{index}",
        "title": f"Doc {index}",
        "heading": "Policy",
        "content": "Text about the policy.",
        "access_level": "employee",
        "department": None,
        "is_synthetic": False,
        "source_url": None,
        "license": "CC BY-SA 4.0",
        "attribution": "GitLab Handbook",
        "rrf_score": 0.016 - index * 0.0001,
    }


def _run_adaptive(monkeypatch, first_pass_score: float) -> list[int]:
    """Run retrieve with 24 candidates and record how many each rerank call got."""
    from app.retrieval import retrieve

    calls: list[int] = []

    async def fake_search(**kwargs):
        return [_retrieval_row(index) for index in range(24)]

    def fake_rerank(question, candidates, settings):
        calls.append(len(candidates))
        scored = []
        for index, candidate in enumerate(candidates):
            score = first_pass_score if (not calls[1:] and index == 0) else 0.01
            scored.append({**candidate, "rerank_score": score})
        return sorted(scored, key=lambda item: item["rerank_score"], reverse=True)

    monkeypatch.setattr(db, "search_chunks", fake_search)
    monkeypatch.setattr("app.retrieval.embed_query", lambda text, settings: [0.1] * 384)
    monkeypatch.setattr("app.retrieval.rerank", fake_rerank)

    settings = Settings(supabase_url="https://example.supabase.co")
    asyncio.run(retrieve("a question?", "employee", None, settings))
    return calls


def test_adaptive_rerank_stops_when_shortlist_is_confident(monkeypatch) -> None:
    assert _run_adaptive(monkeypatch, 0.9) == [8]


def test_adaptive_rerank_scores_the_rest_when_shortlist_is_weak(monkeypatch) -> None:
    assert _run_adaptive(monkeypatch, 0.2) == [8, 16]
