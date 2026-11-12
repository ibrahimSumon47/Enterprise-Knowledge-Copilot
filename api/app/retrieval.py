"""Permission-aware retrieval: query embedding, hybrid SQL search, rerank, grade."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from . import db
from .config import Settings
from .embeddings import embed_query, note_rerank_depth, rerank

logger = logging.getLogger(__name__)


@dataclass
class Retrieved:
    """A chunk that survived retrieval and reranking."""

    chunk_id: str
    document_id: str
    title: str
    heading: str | None
    content: str
    access_level: str
    department: str | None
    is_synthetic: bool
    source_url: str | None
    license: str
    attribution: str
    rrf_score: float
    rerank_score: float = 0.0
    reranked: bool = True
    citation_id: int = 0

    @property
    def label(self) -> str:
        parts = [self.title]
        if self.heading:
            parts.append(self.heading)
        if self.is_synthetic:
            parts.append("synthetic")
        return " · ".join(parts)


@dataclass
class RetrievalResult:
    candidates: list[Retrieved] = field(default_factory=list)
    top_score: float | None = None
    confidence: str = "low"

    @property
    def usable(self) -> bool:
        return bool(self.candidates)


def _shortlist_depth(candidates: list[Retrieved], settings: Settings) -> int:
    """How many passages the cross-encoder should read.

    A leader that RRF already ranks first in some branch, with fourth place clearly
    behind it, is the signal that the hybrid order is trustworthy: the reranker
    then only has to confirm the top few instead of re-scoring the whole pool.
    """
    if not settings.rerank_adaptive or len(candidates) <= settings.rerank_fast_depth:
        return len(candidates)
    top = candidates[0].rrf_score
    if top < settings.rerank_agree_score:
        return len(candidates)
    fourth = candidates[min(3, len(candidates) - 1)].rrf_score
    if fourth > top * settings.rerank_margin_ratio:
        return len(candidates)
    return settings.rerank_fast_depth


async def retrieve(question: str, role: str, department: str | None, settings: Settings) -> RetrievalResult:
    """Run the full retrieval path. The access predicate is applied by SQL."""
    # ONNX inference is CPU-bound; keep the event loop free for health checks.
    embedding = await asyncio.to_thread(embed_query, question, settings)
    rows = await db.search_chunks(
        embedding=embedding,
        query_text=question,
        role=role,
        department=department,
        limit=settings.candidate_limit,
    )

    candidates = [
        Retrieved(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            title=str(row["title"]),
            heading=row["heading"],
            content=str(row["content"]),
            access_level=str(row["access_level"]),
            department=row["department"],
            is_synthetic=bool(row["is_synthetic"]),
            source_url=row["source_url"],
            license=str(row["license"]),
            attribution=str(row["attribution"]),
            rrf_score=float(row["rrf_score"]),
        )
        for row in rows
    ]

    if not candidates:
        return RetrievalResult()

    if settings.rerank_enabled:
        depth = _shortlist_depth(candidates, settings)
        reranked = await asyncio.to_thread(
            rerank,
            question,
            [candidate.__dict__ for candidate in candidates[:depth]],
            settings,
        )
        best = max((item.get("rerank_score", 0.0) for item in reranked), default=0.0)
        if depth < len(candidates) and best < settings.min_answer_score:
            # Nothing quotable in the shortlist: the evidence may sit deeper in the
            # pool, so pay for the full pass before refusing.
            reranked = await asyncio.to_thread(
                rerank, question, [candidate.__dict__ for candidate in candidates], settings
            )
            note_rerank_depth("escalated")
        else:
            note_rerank_depth("short" if depth < len(candidates) else "full")
    else:
        # Hybrid order only. Used where the host cannot fit a second model.
        reranked = [
            {**candidate.__dict__, "rerank_score": candidate.rrf_score}
            for candidate in candidates
        ]
    # One passage per document: a second chunk of the same page wastes a citation
    # slot and lowers precision without adding evidence.
    seen_documents: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in reranked:
        document_id = str(item["document_id"])
        if document_id in seen_documents:
            continue
        seen_documents.add(document_id)
        deduped.append(item)

    kept = [
        item
        for item in deduped
        if item["rerank_score"] >= settings.min_rerank_score
    ][: settings.rerank_top_k]
    if not kept:
        return RetrievalResult()

    retrieved: list[Retrieved] = []
    for index, item in enumerate(kept, start=1):
        retrieved.append(
            Retrieved(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                title=item["title"],
                heading=item.get("heading"),
                content=item["content"],
                access_level=item["access_level"],
                department=item.get("department"),
                is_synthetic=bool(item.get("is_synthetic")),
                source_url=item.get("source_url"),
                license=item["license"],
                attribution=item["attribution"],
                rrf_score=float(item.get("rrf_score", 0.0)),
                rerank_score=float(item.get("rerank_score", 0.0)),
                reranked=bool(item.get("reranked", True)),
                citation_id=index,
            )
        )

    top = retrieved[0].rerank_score
    if retrieved[0].reranked:
        if top >= settings.high_confidence_score:
            confidence = "high"
        elif top >= settings.min_answer_score:
            confidence = "medium"
        else:
            confidence = "low"
    elif top >= settings.rrf_high_score:
        confidence = "high"
    elif top >= settings.rrf_medium_score:
        confidence = "medium"
    else:
        confidence = "low"

    return RetrievalResult(candidates=retrieved, top_score=top, confidence=confidence)


def build_context(candidates: list[Retrieved], max_chars: int = 5200) -> str:
    """Number the passages so the model can cite them as [n]."""
    lines: list[str] = []
    used = 0
    for candidate in candidates:
        block = (
            f"[{candidate.citation_id}] {candidate.label}\n"
            f"{(candidate.content or '').strip()[:1600]}\n"
        )
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


def citation_payload(candidate: Retrieved) -> dict[str, Any]:
    """Shape returned to the web app and stored on the message."""
    return {
        "id": candidate.citation_id,
        "title": candidate.title,
        "heading": candidate.heading,
        "document_id": candidate.document_id,
        "chunk_id": candidate.chunk_id,
        "snippet": (candidate.content or "")[:400],
        "source_url": candidate.source_url,
        "license": candidate.license,
        "attribution": candidate.attribution,
        "access_level": candidate.access_level,
        "is_synthetic": candidate.is_synthetic,
        "score": round(candidate.rerank_score, 3),
    }
