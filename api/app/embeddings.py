"""Embedding and reranking. Models load lazily so tests never download weights."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from .config import Settings

logger = logging.getLogger(__name__)

_encoder: Any = None
_reranker: Any = None
_dims = 384


def set_encoder(encoder: Any) -> None:
    """Test hook: inject a fake encoder."""
    global _encoder
    _encoder = encoder


def set_reranker(reranker: Any) -> None:
    """Test hook: inject a fake reranker."""
    global _reranker
    _reranker = reranker


def _load_encoder(settings: Settings) -> Any:
    global _encoder, _dims
    if _encoder is None:
        from sentence_transformers import SentenceTransformer

        logger.info("loading embedding model %s", settings.embedding_model)
        _encoder = SentenceTransformer(settings.embedding_model, device="cpu")
        _dims = int(_encoder.get_sentence_embedding_dimension())
    return _encoder


def _load_reranker(settings: Settings) -> Any:
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        logger.info("loading reranker %s", settings.reranker_model)
        _reranker = CrossEncoder(settings.reranker_model, device="cpu")
    return _reranker


def embed_documents(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    """e5 models expect the `passage:` prefix for indexed text."""
    encoder = _load_encoder(settings)
    vectors = encoder.encode(
        [f"passage: {text}" for text in texts],
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [list(map(float, vector)) for vector in vectors]


def embed_query(text: str, settings: Settings) -> list[float]:
    encoder = _load_encoder(settings)
    vector = encoder.encode(
        [f"query: {text}"], normalize_embeddings=True, show_progress_bar=False
    )[0]
    return list(map(float, vector))


def rerank(question: str, candidates: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Score each candidate against the question and sort by the cross-encoder."""
    if not candidates:
        return []
    model = _load_reranker(settings)
    pairs = [(question, _rerank_text(candidate)) for candidate in candidates]
    scores = model.predict(pairs)
    scored = [
        {**candidate, "rerank_score": float(score)}
        for candidate, score in zip(candidates, scores, strict=True)
    ]
    scored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return scored


def _rerank_text(candidate: dict[str, Any]) -> str:
    heading = candidate.get("heading") or ""
    content = candidate.get("content") or ""
    return f"{candidate.get('title', '')} — {heading}\n{content}"[:2000]


def embedding_dims() -> int:
    return _dims
