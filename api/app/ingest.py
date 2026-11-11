"""Corpus ingestion. Markdown -> headings-aware chunks -> embeddings -> Postgres.

The job is a single background task on the Space; progress is written to
`ingest_jobs` so the admin page can poll it. Re-running is safe: documents are
upserted by slug and chunks are replaced.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from . import db
from .config import Settings
from .embeddings import embed_documents

logger = logging.getLogger(__name__)

CORPUS_ENV = "EKC_CORPUS_PATH"


def corpus_path() -> Path:
    """Find the committed corpus in both layouts: the repo and the container.

    In the repo the file sits at the checkout root; in the image the package is
    /app/app, so the same parents[2] arithmetic would point at /data.
    """
    candidates = [
        Path(os.environ[CORPUS_ENV]) if os.environ.get(CORPUS_ENV) else None,
        Path.cwd() / "data" / "corpus.jsonl",
        Path(__file__).resolve().parents[2] / "data" / "corpus.jsonl",
        Path("/app/data/corpus.jsonl"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return candidates[1]


CORPUS_PATH = corpus_path()
MAX_CHUNK_CHARS = 1100
MIN_CHUNK_CHARS = 160


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "section"


def chunk_markdown(text: str) -> list[dict[str, Any]]:
    """Split on headings, then on paragraphs, keeping the heading path attached."""
    chunks: list[dict[str, Any]] = []
    current_heading = ""
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        buffer = []
        if not body:
            return
        for piece in _split_long(body):
            previous = chunks[-1] if chunks else None
            same_section = previous is not None and previous["heading"] == (
                current_heading or None
            )
            fits = (
                previous is not None
                and len(previous["content"]) + len(piece) + 2 <= MAX_CHUNK_CHARS
            )
            if len(piece) < MIN_CHUNK_CHARS and same_section and fits:
                # Attach short trailing fragments to the previous chunk, but never
                # across a heading: that would file evidence under the wrong section.
                chunks[-1]["content"] = f"{chunks[-1]['content']}\n\n{piece}".strip()
                chunks[-1]["token_count"] = len(chunks[-1]["content"].split())
                continue
            chunks.append(
                {
                    "ordinal": len(chunks),
                    "heading": current_heading or None,
                    "content": piece,
                    "token_count": len(piece.split()),
                }
            )

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            current_heading = line.lstrip("#").strip()[:160]
            continue
        buffer.append(line)
        if sum(len(item) for item in buffer) > MAX_CHUNK_CHARS:
            flush()
    flush()
    return chunks


def _split_long(body: str) -> list[str]:
    """Paragraph split with a hard cap so no chunk blows the context budget."""
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", body) if paragraph.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHUNK_CHARS:
            if current:
                pieces.append(current)
                current = ""
            for start in range(0, len(paragraph), MAX_CHUNK_CHARS):
                pieces.append(paragraph[start : start + MAX_CHUNK_CHARS])
            continue
        if len(current) + len(paragraph) + 2 > MAX_CHUNK_CHARS and current:
            pieces.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        pieces.append(current)
    return pieces


async def _set_job(job_id: str, **fields: Any) -> None:
    assignments = ", ".join(f"{key} = ${index + 2}" for index, key in enumerate(fields))
    # asyncpg hands parameters straight to Postgres; json/jsonb columns want text.
    values = [
        json.dumps(value) if key == "stats" and isinstance(value, dict) else value
        for key, value in fields.items()
    ]
    await db.pool().execute(
        f"update public.ingest_jobs set {assignments}, updated_at = now() where id = $1",
        job_id,
        *values,
    )


async def run_ingest(job_id: str, settings: Settings) -> None:
    """Index the committed corpus file. Errors are recorded on the job row."""
    try:
        await _set_job(job_id, status="running", progress=2)
        documents = _read_corpus()
        total = len(documents)
        await _set_job(job_id, progress=5, stats={"documents": total})

        indexed_docs = 0
        indexed_chunks = 0
        skipped = 0

        for index, document in enumerate(documents):
            chunks = chunk_markdown(document["text"])
            if not chunks:
                skipped += 1
                continue
            document_id = await db.insert_document(
                {
                    **document,
                    "metadata": {
                        "synthetic": document.get("is_synthetic", False),
                        "words": len(document["text"].split()),
                    },
                }
            )
            vectors = await asyncio.to_thread(
                embed_documents, [chunk["content"] for chunk in chunks], settings
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk["embedding"] = vector
            await db.replace_chunks(document_id, chunks)
            indexed_docs += 1
            indexed_chunks += len(chunks)

            if index % 10 == 0:
                progress = 5 + int((index + 1) / total * 90)
                await _set_job(
                    job_id,
                    progress=progress,
                    stats={
                        "documents_total": total,
                        "documents_indexed": indexed_docs,
                        "chunks_indexed": indexed_chunks,
                        "skipped": skipped,
                    },
                )
            await asyncio.sleep(0)  # yield so health checks stay responsive

        await _set_job(
            job_id,
            status="done",
            progress=100,
            stats={
                "documents_total": total,
                "documents_indexed": indexed_docs,
                "chunks_indexed": indexed_chunks,
                "skipped": skipped,
            },
        )
        logger.info("ingest done: %s docs, %s chunks", indexed_docs, indexed_chunks)
    except Exception as exc:  # noqa: BLE001 - job state must record any failure
        logger.exception("ingest failed")
        await _set_job(job_id, status="failed", error=str(exc)[:500], progress=100)


def _read_corpus() -> list[dict[str, Any]]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"corpus file missing at {CORPUS_PATH}")
    documents: list[dict[str, Any]] = []
    with CORPUS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record.setdefault(
                "content_hash",
                hashlib.sha256(record["text"].encode("utf-8")).hexdigest(),
            )
            documents.append(record)
    return documents


def corpus_fingerprint() -> dict[str, Any]:
    """Cheap summary for the admin page."""
    if not CORPUS_PATH.exists():
        return {"exists": False}
    documents = _read_corpus()
    return {
        "exists": True,
        "documents": len(documents),
        "synthetic": sum(1 for doc in documents if doc.get("is_synthetic")),
        "size_bytes": CORPUS_PATH.stat().st_size,
        "slug_sample": _slug(documents[0]["title"]) if documents else "",
    }
