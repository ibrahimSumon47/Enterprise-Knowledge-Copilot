"""Embedding and reranking on CPU with ONNX models.

The free hosting target gives a 512 MB instance, which torch plus two
transformer models cannot fit. fastembed and flashrank serve the same
multilingual MiniLM encoder and the ms-marco MiniLM cross-encoder from ONNX
Runtime instead, at roughly a tenth of the memory. Models still load
lazily, so unit tests never download weights.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence

import numpy as np

from .config import Settings

logger = logging.getLogger(__name__)

_encoder: Any = None
_reranker: Any = None
_rerank_error: str | None = None
_dims = 384


def rerank_state() -> dict[str, Any]:
    """Why reranking is or is not running, for /health and the runbook."""
    return {"loaded": _reranker is not None, "error": _rerank_error}


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
        from fastembed import TextEmbedding

        logger.info("loading embedding model %s", settings.embedding_model)
        _encoder = TextEmbedding(model_name=settings.embedding_model, threads=1)
        _dims = len(next(iter(_encoder.embed(["dimension probe"]))))
    return _encoder


def _load_reranker(settings: Settings) -> Any:
    global _reranker
    if _reranker is None:
        from flashrank import Ranker

        # flashrank ships the same cross-encoders under their short names.
        model_name = settings.reranker_model.rsplit("/", 1)[-1]
        logger.info("loading reranker %s", model_name)
        cache_dir = os.environ.get("FLASHRANK_CACHE_DIR", "/tmp/flashrank")
        _reranker = Ranker(model_name=model_name, cache_dir=cache_dir, max_length=256)
    return _reranker


def _normalize(vector: Any) -> list[float]:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array)) or 1.0
    return [float(value) for value in array / norm]


def embed_documents(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    """Embed indexed passages. The multilingual MiniLM needs no prefix."""
    encoder = _load_encoder(settings)
    if hasattr(encoder, "encode"):  # injected encoder in tests
        vectors = encoder.encode(
            list(texts),
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    else:  # fastembed
        vectors = encoder.embed(list(texts), batch_size=16)
    return [_normalize(vector) for vector in vectors]


def embed_query(text: str, settings: Settings) -> list[float]:
    encoder = _load_encoder(settings)
    if hasattr(encoder, "encode"):
        vector = encoder.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    else:
        vector = next(iter(encoder.embed([text])))
    return _normalize(vector)


def _rrf_fallback(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order by the hybrid score when the cross-encoder cannot run.

    A 512 MB instance can run out of memory while loading a second ONNX model.
    Losing precision is acceptable; losing the whole answer to a crash is not,
    and the response still carries citations either way.
    """
    ordered = sorted(candidates, key=lambda item: item.get("rrf_score", 0.0), reverse=True)
    return [
        {**candidate, "rerank_score": float(candidate.get("rrf_score", 0.0)), "reranked": False}
        for candidate in ordered
    ]


def rerank(question: str, candidates: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Score each candidate against the question with a cross-encoder."""
    if not candidates:
        return []
    global _rerank_error
    try:
        model = _load_reranker(settings)
    except Exception as exc:  # noqa: BLE001 - never fail a request over the reranker
        _rerank_error = f"load {type(exc).__name__}: {str(exc)[:160]}"
        logger.warning("reranker unavailable, keeping hybrid order: %s", exc)
        return _rrf_fallback(candidates)

    if hasattr(model, "predict"):  # injected encoder in tests
        scores = model.predict([(question, _rerank_text(candidate)) for candidate in candidates])
        scored = [
            {**candidate, "rerank_score": float(score), "reranked": True}
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        scored.sort(key=lambda item: item["rerank_score"], reverse=True)
        return scored

    passages = [
        {"id": index, "text": _rerank_text(candidate)}
        for index, candidate in enumerate(candidates)
    ]
    try:
        ranked = model.rerank(question, passages, top_n=len(passages))
    except Exception as exc:  # noqa: BLE001 - same reason as above
        _rerank_error = f"score {type(exc).__name__}: {str(exc)[:160]}"
        logger.warning("rerank failed, keeping hybrid order: %s", exc)
        return _rrf_fallback(candidates)
    _rerank_error = None
    by_index = {int(item["id"]): float(item["score"]) for item in ranked}
    scored = [
        {**candidate, "rerank_score": by_index.get(index, float("-inf")), "reranked": True}
        for index, candidate in enumerate(candidates)
    ]
    scored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return scored


def _rerank_text(candidate: dict[str, Any]) -> str:
    heading = candidate.get("heading") or ""
    content = candidate.get("content") or ""
    return f"{candidate.get('title', '')} — {heading}\n{content}"[:2000]


def embedding_dims() -> int:
    return _dims
