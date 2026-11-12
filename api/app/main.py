"""FastAPI service: JWT auth, permission-aware RAG, audit trail and admin API."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from . import audit, db, ingest
from .auth import AuthUser, current_user, decode_token, require_admin
from .config import Settings, get_settings
from .embeddings import rerank_state
from .pipeline import answer_question, build_graph, stream_tokens
from .providers import GeminiProvider, build_router, list_gemini_models, probe_gemini
from .redact import hash_identifier
from .retrieval import retrieve
from .schemas import (
    AuditVerifyResponse,
    ChatRequest,
    ChatResponse,
    DocumentUpdate,
    EvalRun,
    FeedbackRequest,
    IngestResponse,
    MeResponse,
    ReadyResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ekc")

VISIBLE = {
    "guest": ["public"],
    "employee": ["public", "employee"],
    "engineering": ["public", "employee", "department:engineering"],
    "security": ["public", "employee", "department:security"],
    "hr": ["public", "employee", "department:people"],
    "finance": ["public", "employee", "department:finance"],
    "admin": ["public", "employee", "department", "confidential"],
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.router = build_router(settings)
    app.state.graph = build_graph(app.state.router, settings)
    try:
        if settings.supabase_db_url:
            await db.init_pool(settings)
            logger.info("database pool ready")
    except Exception as exc:  # noqa: BLE001 - the Space must boot even if the DB is down
        logger.error("database pool failed: %s", type(exc).__name__)
    yield
    await db.close_pool()


def _rss_mb() -> int:
    """Peak RSS in MB. The free host allows 512 MB, so this is worth seeing."""
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    except Exception:  # pragma: no cover - not Linux
        return 0


app = FastAPI(
    title="Enterprise Knowledge Copilot API",
    version="1.0.0",
    description="Role-aware retrieval with citations, refusals and a hash-chained audit log.",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def hardening(request: Request, call_next):
    """Request size cap, security headers and a coarse per-IP guard."""
    length = request.headers.get("content-length")
    if length and int(length) > 200_000:
        return JSONResponse({"detail": "payload too large"}, status_code=413)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", tags=["ops"])
async def health(request: Request) -> dict[str, Any]:
    settings = get_settings()
    router = getattr(request.app.state, "router", None)
    return {
        "status": "ok",
        "service": "ekc-api",
        "rss_mb": _rss_mb(),
        "model": settings.embedding_model,
        "rerank": settings.rerank_enabled,
        "rerank_state": rerank_state(),
        "providers": router.stats() if router is not None else {},
    }


@app.get("/ready", response_model=ReadyResponse, tags=["ops"])
async def ready(settings: Settings = Depends(get_settings)) -> ReadyResponse:
    try:
        counts = await db.ready_checks()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database not ready")
    return ReadyResponse(
        status="ready",
        documents=int(counts["documents"]),
        chunks=int(counts["chunks"]),
        profiles=int(counts["profiles"]),
        providers=app.state.router.health(),
    )


@app.get("/me", response_model=MeResponse, tags=["auth"])
async def me(user: AuthUser = Depends(current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        department=user.department,
        visible_levels=VISIBLE.get(user.role, ["public"]),
    )


async def _rate_limit(user: AuthUser, settings: Settings) -> None:
    allowed, remaining = await db.rate_limit_hit(
        user.id, settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(settings.rate_limit_window_seconds)},
        )
    return None


async def _ensure_conversation(user: AuthUser, conversation_id: str | None, question: str) -> str:
    if not conversation_id:
        return await db.create_conversation(user.id, question[:80])
    owner = await db.conversation_owner(conversation_id)
    if owner is None or owner != user.id:
        # Do not reveal whether the id exists.
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation_id


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    payload: ChatRequest,
    request: Request,
    user: AuthUser = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    await _rate_limit(user, settings)
    conversation_id = await _ensure_conversation(user, payload.conversation_id, payload.question)

    await db.insert_message(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": payload.question,
        }
    )

    result = await answer_question(
        payload.question,
        user.role,
        user.department,
        settings,
        app.state.router,
        app.state.graph,
    )

    message_id = await db.insert_message(
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": result.answer,
            "citations": result.citations,
            "confidence": result.confidence if not result.refused else "refused",
            "refused": result.refused,
            "latency_ms": result.latency_ms,
            "token_count": result.tokens,
            "provider": result.provider,
        }
    )

    await audit.record(
        action="chat.question",
        resource_type="conversation",
        resource_id=conversation_id,
        actor_id=user.id,
        actor_role=user.role,
        outcome="refused" if result.refused else "ok",
        ip_hash=hash_identifier(request.client.host if request.client else "unknown"),
        detail={
            "confidence": result.confidence,
            "citations": len(result.citations),
            "provider": result.provider,
            "latency_ms": result.latency_ms,
            "reason": result.reason,
        },
    )

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=message_id,
        answer=result.answer,
        confidence=result.confidence if not result.refused else "low",
        refused=result.refused,
        citations=[citation_payload_from_dict(item) for item in result.citations],
        latency_ms=result.latency_ms,
        tokens=result.tokens,
        provider=result.provider,
        outage=bool(result.reason and result.reason.startswith("no language model available")),
    )


def citation_payload_from_dict(item: dict[str, Any]):
    from .schemas import Citation

    return Citation(**item)


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: AuthUser = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Server-sent events: status, citations, token chunks, then done."""
    await _rate_limit(user, settings)
    conversation_id = await _ensure_conversation(user, payload.conversation_id, payload.question)

    async def events() -> AsyncIterator[str]:
        def frame(event: str, data: dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield frame("status", {"stage": "retrieving"})
        try:
            result = await answer_question(
                payload.question,
                user.role,
                user.department,
                settings,
                app.state.router,
                app.state.graph,
            )
        except Exception:  # noqa: BLE001 - the stream must close cleanly
            logger.exception("chat failed")
            yield frame("error", {"detail": "answer failed"})
            return

        yield frame("citations", {"citations": result.citations, "confidence": result.confidence})
        async for chunk in stream_tokens(result.answer):
            yield frame("token", {"text": chunk})

        message_id = await db.insert_message(
            {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": result.answer,
                "citations": result.citations,
                "confidence": result.confidence if not result.refused else "refused",
                "refused": result.refused,
                "latency_ms": result.latency_ms,
                "token_count": result.tokens,
                "provider": result.provider,
            }
        )
        await audit.record(
            action="chat.question",
            resource_type="conversation",
            resource_id=conversation_id,
            actor_id=user.id,
            actor_role=user.role,
            outcome="refused" if result.refused else "ok",
            ip_hash=hash_identifier(request.client.host if request.client else "unknown"),
            detail={
                "confidence": result.confidence,
                "citations": len(result.citations),
                "provider": result.provider,
                "latency_ms": result.latency_ms,
            },
        )
        yield frame(
            "done",
            {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "refused": result.refused,
                "confidence": result.confidence,
                "latency_ms": result.latency_ms,
                "tokens": result.tokens,
                "provider": result.provider,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/conversations/{conversation_id}/messages", tags=["chat"])
async def conversation_messages(
    conversation_id: str, user: AuthUser = Depends(current_user)
) -> dict[str, Any]:
    messages = await db.list_messages(conversation_id, user.id)
    if not messages:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation_id": conversation_id, "messages": messages}


@app.post("/feedback", tags=["chat"])
async def feedback(payload: FeedbackRequest, user: AuthUser = Depends(current_user)) -> dict[str, str]:
    await db.pool().execute(
        """
        insert into public.feedback (message_id, user_id, rating, reason)
        values ($1,$2,$3,$4)
        on conflict (message_id, user_id) do update set
          rating = excluded.rating, reason = excluded.reason
        """,
        payload.message_id,
        user.id,
        payload.rating,
        payload.reason,
    )
    await audit.record(
        action="feedback.recorded",
        resource_type="message",
        resource_id=payload.message_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"rating": payload.rating},
    )
    return {"status": "recorded"}


@app.get("/documents", tags=["documents"])
async def documents(user: AuthUser = Depends(current_user)) -> dict[str, Any]:
    rows = await db.list_documents(user.role, user.department)
    return {"documents": rows, "role": user.role}


@app.patch("/documents/{document_id}", tags=["documents"])
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    user: AuthUser = Depends(require_admin),
) -> dict[str, str]:
    if payload.access_level == "department" and not payload.department:
        raise HTTPException(status_code=422, detail="department is required for that level")
    updated = await db.set_document_access(document_id, payload.access_level, payload.department)
    if not updated:
        raise HTTPException(status_code=404, detail="document not found")
    await audit.record(
        action="document.access_changed",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"access_level": payload.access_level, "department": payload.department},
    )
    return {"status": "updated"}


@app.delete("/documents/{document_id}", tags=["documents"])
async def remove_document(document_id: str, user: AuthUser = Depends(require_admin)) -> dict[str, str]:
    deleted = await db.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="document not found")
    await audit.record(
        action="document.deleted",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
    )
    return {"status": "deleted"}


@app.post("/admin/ingest", response_model=IngestResponse, tags=["admin"])
async def start_ingest(user: AuthUser = Depends(require_admin)) -> IngestResponse:
    job_id = str(uuid.uuid4())
    await db.pool().execute(
        "insert into public.ingest_jobs (id, status, created_by) values ($1, 'queued', $2)",
        job_id,
        user.id,
    )
    asyncio.create_task(ingest.run_ingest(job_id, get_settings()))
    await audit.record(
        action="ingest.started",
        resource_type="ingest_job",
        resource_id=job_id,
        actor_id=user.id,
        actor_role=user.role,
    )
    return IngestResponse(job_id=job_id, status="queued")


@app.get("/admin/providers/models", tags=["admin"])
async def provider_models(
    probe: bool = False,
    answer: bool = False,
    models: str = "",
    settings: Settings = Depends(get_settings),
    _: AuthUser = Depends(require_admin),
) -> dict[str, Any]:
    """Which Gemini model ids the configured key can call.

    Exists because a retired id answers 404 and the fallback provider turns into a
    silent outage; this answers the question without putting the key anywhere.
    With `probe=true` it also runs a one-word generation per candidate.
    """
    if answer:
        # Exercises the real provider, including the model chain, without needing
        # Groq to fail first.
        try:
            completion = await GeminiProvider(settings).complete(
                "You are a health check.", "Reply with the single word OK.", max_tokens=8
            )
            return {
                "provider": completion.provider,
                "tokens": completion.tokens,
                "chars": len(completion.text),
            }
        except Exception as exc:  # noqa: BLE001 - the answer is the diagnostic
            return {"provider": "none", "error": str(exc)[:240]}
    if probe:
        requested = [name.strip() for name in models.split(",") if name.strip()]
        candidates = requested or [
            settings.gemini_model,
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
        ]
        return {"probe": await probe_gemini(settings.gemini_api_key, candidates[:6])}
    return await list_gemini_models(settings.gemini_api_key)


@app.get("/admin/retrieval", tags=["admin"])
async def retrieval_debug(
    question: str,
    role: str = "admin",
    department: str | None = None,
    settings: Settings = Depends(get_settings),
    _: AuthUser = Depends(require_admin),
) -> dict[str, Any]:
    """Ranking and scores for one question, without calling a language model.

    Refusal is decided by a single number, the top rerank score. This returns it so
    a threshold can be tuned against the corpus instead of guessed at.
    """
    result = await retrieve(question, role, department, settings)
    return {
        "confidence": result.confidence,
        "top_score": result.top_score,
        "refused": not result.usable or result.confidence == "low",
        "min_answer_score": settings.min_answer_score,
        "high_confidence_score": settings.high_confidence_score,
        "candidates": [
            {
                "id": candidate.citation_id,
                "title": candidate.title,
                "heading": candidate.heading,
                "rerank_score": round(candidate.rerank_score, 4),
                "rrf_score": round(candidate.rrf_score, 4),
                "is_synthetic": candidate.is_synthetic,
            }
            for candidate in result.candidates
        ],
    }


@app.get("/admin/ingest/{job_id}", tags=["admin"])
async def ingest_status(job_id: str, _: AuthUser = Depends(require_admin)) -> dict[str, Any]:
    row = await db.pool().fetchrow(
        "select id, status, progress, stats, error, updated_at from public.ingest_jobs where id = $1",
        job_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return dict(row)


@app.get("/audit", tags=["admin"])
async def audit_log(limit: int = 100, _: AuthUser = Depends(require_admin)) -> dict[str, Any]:
    rows = await db.audit_page(min(limit, 200))
    return {
        "entries": [
            {
                **row,
                "created_at": row["created_at"].isoformat()
                if hasattr(row["created_at"], "isoformat")
                else str(row["created_at"]),
            }
            for row in rows
        ]
    }


@app.post("/audit/verify", response_model=AuditVerifyResponse, tags=["admin"])
async def audit_verify(_: AuthUser = Depends(require_admin)) -> AuditVerifyResponse:
    rows = await db.audit_page(500)
    result = audit.verify_chain(rows)
    return AuditVerifyResponse(**result)


@app.get("/eval-runs", response_model=list[EvalRun], tags=["evaluation"])
async def eval_runs(user: AuthUser = Depends(current_user)) -> list[EvalRun]:
    rows = await db.eval_runs(20)
    return [
        EvalRun(
            id=str(row["id"]),
            mode=str(row["mode"]),
            commit_sha=row["commit_sha"],
            metrics=row["metrics"],
            passed=bool(row["passed"]),
            created_at=row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"]),
        )
        for row in rows
    ]


@app.get("/auth-check", tags=["ops"])
async def auth_check(request: Request, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Diagnostic: verifies a JWT without touching the database."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    claims = decode_token(header.split(" ", 1)[1], settings)
    return {"sub": str(claims.get("sub")), "role": str(claims.get("role", ""))}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "Enterprise Knowledge Copilot API", "docs": "/docs"}
