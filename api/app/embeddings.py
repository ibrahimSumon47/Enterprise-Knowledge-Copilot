"""Embedding and reranking on CPU with ONNX models.

The free hosting target gives a 512 MB instance, which torch plus two
transformer models cannot fit. fastembed and flashrank serve the same
multilingual-e5-small encoder and the same ms-marco MiniLM cross-encoder from
ONNX Runtime instead, at roughly a tenth of the memory. Models still load
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
_dims = 384

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


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
        _encoder = TextEmbedding(model_name=settings.embedding_model)
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
        _reranker = Ranker(model_name=model_name, cache_dir=cache_dir)
    return _reranker


def _normalize(vector: Any) -> list[float]:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array)) or 1.0
    return [float(value) for value in array / norm]


def embed_documents(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    """e5 models expect the `passage:` prefix for indexed text."""
    encoder = _load_encoder(settings)
    if hasattr(encoder, "passage_embed"):  # fastembed applies the model prompt itself
        vectors = encoder.passage_embed(list(texts), batch_size=16)
    else:  # injected encoder in tests
        vectors = encoder.encode(
            [f"{PASSAGE_PREFIX}{text}" for text in texts],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    return [_normalize(vector) for vector in vectors]


def embed_query(text: str, settings: Settings) -> list[float]:
    encoder = _load_encoder(settings)
    if hasattr(encoder, "query_embed"):
        vector = next(iter(encoder.query_embed([text])))
    else:
        vector = encoder.encode(
            [f"{QUERY_PREFIX}{text}"], normalize_embeddings=True, show_progress_bar=False
        )[0]
    return _normalize(vector)


def rerank(question: str, candidates: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Score each candidate against the question with a cross-encoder."""
    if not candidates:
        return []
    model = _load_reranker(settings)

    if hasattr(model, "predict"):  # injected encoder in tests
        scores = model.predict([(question, _rerank_text(candidate)) for candidate in candidates])
        scored = [
            {**candidate, "rerank_score": float(score)}
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        scored.sort(key=lambda item: item["rerank_score"], reverse=True)
        return scored

    passages = [
        {"id": index, "text": _rerank_text(candidate)}
        for index, candidate in enumerate(candidates)
    ]
    ranked = model.rerank(question, passages, top_k=len(passages))
    by_index = {int(item["id"]): float(item["score"]) for item in ranked}
    scored = [
        {**candidate, "rerank_score": by_index.get(index, float("-inf"))}
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
