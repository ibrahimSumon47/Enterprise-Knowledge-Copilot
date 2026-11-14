"""FastAPI service: JWT auth, permission-aware RAG, audit trail and admin API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import audit, db, ingest, storage, uploads
from .auth import (
    AuthUser,
    current_identity,
    current_user,
    decode_token,
    require_admin,
    require_owner,
)
from .config import Settings, get_settings
from .embeddings import embed_documents, embed_query, rerank_state
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
    FirstDocumentRequest,
    GroupRequest,
    IngestResponse,
    InviteRequest,
    MemberUpdate,
    MeResponse,
    ReadyResponse,
    SignupRequest,
    WorkspaceNameRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ekc")

# Whole-log verification pages in ascending id order. The ceiling keeps a
# runaway table from pinning the free instance; hitting it reports
# complete=false rather than pretending the log was verified.
AUDIT_VERIFY_PAGE = 1000
AUDIT_VERIFY_MAX_ROWS = 50_000
UPLOAD_RATE_LIMIT = 10
UPLOAD_RATE_WINDOW = 3600

VISIBLE = {
    "guest": ["public"],
    "employee": ["public", "employee"],
    "engineering": ["public", "employee", "department:engineering"],
    "security": ["public", "employee", "department:security"],
    "hr": ["public", "employee", "department:people"],
    "finance": ["public", "employee", "department:finance"],
    "admin": ["public", "employee", "department", "confidential"],
    "owner": ["public", "employee", "department", "confidential"],
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
        # RENDER_GIT_COMMIT is injected by the host, so the deployed build can be
        # identified without logging into the dashboard.
        "commit": (os.environ.get("RENDER_GIT_COMMIT") or "unknown")[:12],
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


@app.post("/signup", status_code=201, tags=["auth"])
async def signup(
    payload: SignupRequest, settings: Settings = Depends(get_settings)
) -> dict[str, str]:
    """Create a confirmed account and an empty workspace owned by it.

    Supabase's admin endpoint is used so a new account can start working without
    an email round trip on the free tier. The workspace name is a placeholder;
    onboarding renames it before anything is asked.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="sign-up is not configured")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": payload.email,
                    "password": payload.password,
                    "email_confirm": True,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("signup request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="sign-up provider unavailable") from exc
    if response.status_code >= 400:
        logger.info("signup rejected: %s", response.status_code)
        raise HTTPException(
            status_code=409, detail="an account with that email already exists"
        )
    user_id = str(response.json().get("id", ""))
    if not user_id:
        raise HTTPException(status_code=502, detail="sign-up returned no user")
    if payload.invite_token:
        token_hash = hashlib.sha256(payload.invite_token.encode("utf-8")).hexdigest()
        joined = await db.redeem_invite_for(token_hash, user_id)
        if not joined:
            raise HTTPException(
                status_code=422, detail="invite is invalid, expired or already used"
            )
        return {"status": "joined", "email": payload.email}
    await db.create_workspace(user_id, payload.email, "My workspace")
    return {"status": "created", "email": payload.email}


@app.get("/onboarding", tags=["auth"])
async def onboarding_state(user: AuthUser = Depends(current_user)) -> dict[str, Any]:
    return {
        "workspace": await db.org_name(user.org_id) or "My workspace",
        "role": user.role,
        "email": user.email,
        "first_question": "What can this workspace answer?",
    }


@app.patch("/onboarding/workspace", tags=["auth"])
async def rename_workspace(
    payload: WorkspaceNameRequest, user: AuthUser = Depends(require_admin)
) -> dict[str, str]:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="owner role required")
    if not await db.rename_workspace(user.org_id, payload.name):
        raise HTTPException(status_code=404, detail="workspace not found")
    await audit.record(
        org_id=user.org_id,
        action="workspace.renamed",
        resource_type="organization",
        resource_id=user.org_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"name": payload.name},
    )
    return {"status": "updated", "name": payload.name}


@app.post("/onboarding/document", tags=["auth"])
async def first_document(
    payload: FirstDocumentRequest,
    user: AuthUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Add the workspace's first document from pasted text.

    This is the onboarding path; the full browser upload with files, progress and
    re-index arrives in the upload slice and reuses the same document/chunk shape.
    """
    text = payload.text.strip()
    embedding = await asyncio.to_thread(embed_documents, [text], settings)
    document_id = await db.insert_document(
        {
            "org_id": user.org_id,
            "slug": f"onboarding-{uuid.uuid4().hex[:10]}",
            "title": payload.title,
            "access_level": "employee",
            "content_hash": uuid.uuid4().hex,
            "metadata": {"onboarding": True},
        }
    )
    await db.replace_chunks(
        document_id,
        [
            {
                "ordinal": 1,
                "heading": "Overview",
                "content": text,
                "token_count": len(text.split()),
                "embedding": embedding[0],
            }
        ],
    )
    await audit.record(
        org_id=user.org_id,
        action="document.added",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"title": payload.title, "onboarding": True},
    )
    return {"status": "added", "document_id": document_id}


@app.delete("/workspace", tags=["auth"])
async def delete_workspace(user: AuthUser = Depends(require_owner)) -> dict[str, str]:
    """Delete the workspace and everything in it. Owners only.

    An admin can run the workspace but cannot destroy it; ownership is never
    transferred by this route.
    """
    if not await db.delete_workspace(user.org_id):
        raise HTTPException(status_code=404, detail="workspace not found")
    return {"status": "deleted"}


@app.get("/admin/groups", tags=["admin"])
async def groups(user: AuthUser = Depends(require_admin)) -> dict[str, Any]:
    return {"groups": await db.list_groups(user.org_id)}


@app.post("/admin/groups", status_code=201, tags=["admin"])
async def create_group(
    payload: GroupRequest, user: AuthUser = Depends(require_admin)
) -> dict[str, Any]:
    group = await db.create_group(user.org_id, payload.name)
    return {"id": str(group["id"]), "name": group["name"]}


@app.post("/admin/invites", status_code=201, tags=["admin"])
async def create_invite(
    payload: InviteRequest, request: Request, user: AuthUser = Depends(require_admin)
) -> dict[str, Any]:
    """Return a copyable, single-use invitation link. Only its hash is stored."""
    if payload.role == "admin" and user.role != "owner":
        raise HTTPException(status_code=403, detail="only an owner can invite an admin")
    if payload.group_id and not await db.group_in_org(payload.group_id, user.org_id):
        raise HTTPException(status_code=422, detail="group does not belong to this workspace")
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours)
    invite = await db.create_invite(
        org_id=user.org_id,
        token_hash=token_hash,
        role=payload.role,
        group_id=payload.group_id,
        created_by=user.id,
        expires_at=expires_at,
        max_uses=payload.max_uses,
    )
    await audit.record(
        org_id=user.org_id,
        action="invite.created",
        resource_type="invite",
        resource_id=str(invite["id"]),
        actor_id=user.id,
        actor_role=user.role,
        detail={"role": payload.role, "max_uses": payload.max_uses},
    )
    return {
        "id": str(invite["id"]),
        "token": token,
        "path": f"/invite/{token}",
        "role": payload.role,
        "group_id": payload.group_id,
        "expires_at": invite["expires_at"].isoformat(),
        "max_uses": payload.max_uses,
    }


@app.get("/admin/invites", tags=["admin"])
async def invites(user: AuthUser = Depends(require_admin)) -> dict[str, Any]:
    rows = await db.list_invites(user.org_id)
    return {
        "invites": [
            {
                **row,
                "id": str(row["id"]),
                "group_id": str(row["group_id"]) if row["group_id"] else None,
                "expires_at": row["expires_at"].isoformat(),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }


@app.delete("/admin/invites/{invite_id}", tags=["admin"])
async def revoke_invite(
    invite_id: str, user: AuthUser = Depends(require_admin)
) -> dict[str, str]:
    if not await db.revoke_invite(invite_id, user.org_id):
        raise HTTPException(status_code=404, detail="invite not found")
    await audit.record(
        org_id=user.org_id,
        action="invite.revoked",
        resource_type="invite",
        resource_id=invite_id,
        actor_id=user.id,
        actor_role=user.role,
    )
    return {"status": "revoked"}


@app.post("/invites/{token}/accept", tags=["auth"])
async def accept_invite(
    token: str, identity: Any = Depends(current_identity)
) -> dict[str, str]:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    org_id = await db.accept_invite(token_hash)
    if not org_id:
        raise HTTPException(status_code=404, detail="invite is invalid, expired or used")
    await audit.record(
        org_id=org_id,
        action="invite.accepted",
        resource_type="invite",
        actor_id=identity.id,
        actor_role="member",
    )
    return {"status": "joined"}


@app.get("/admin/members", tags=["admin"])
async def members(user: AuthUser = Depends(require_admin)) -> dict[str, Any]:
    rows = await db.list_members(user.org_id)
    return {
        "members": [
            {
                **row,
                "user_id": str(row["user_id"]),
                "group_id": str(row["group_id"]) if row["group_id"] else None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }


@app.patch("/admin/members/{user_id}", tags=["admin"])
async def update_member(
    user_id: str, payload: MemberUpdate, user: AuthUser = Depends(require_admin)
) -> dict[str, str]:
    target = await db.member_role(user.org_id, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="member not found")
    if target == "owner":
        raise HTTPException(status_code=403, detail="ownership cannot be changed here")
    if target == "admin" and user.role != "owner":
        raise HTTPException(status_code=403, detail="only an owner can change an admin")
    if payload.role == "admin" and user.role != "owner":
        raise HTTPException(status_code=403, detail="only an owner can grant admin")
    if payload.group_id and not await db.group_in_org(payload.group_id, user.org_id):
        raise HTTPException(status_code=422, detail="group does not belong to this workspace")
    if payload.status == "deactivated" and user_id == user.id:
        raise HTTPException(status_code=400, detail="you cannot deactivate yourself")
    updated = await db.update_member(
        user.org_id, user_id, payload.role, payload.status, payload.group_id
    )
    if not updated:
        raise HTTPException(status_code=404, detail="member not found")
    await audit.record(
        org_id=user.org_id,
        action="member.updated",
        resource_type="member",
        resource_id=user_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"role": payload.role, "status": payload.status},
    )
    return {"status": "updated"}


@app.get("/me", response_model=MeResponse, tags=["auth"])
async def me(user: AuthUser = Depends(current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        department=user.department,
        org_id=user.org_id,
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
        return await db.create_conversation(user.org_id, user.id, question[:80])
    owner = await db.conversation_owner(conversation_id, user.org_id)
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
            "org_id": user.org_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": payload.question,
        }
    )

    result = await answer_question(
        payload.question,
        user.org_id,
        user.role,
        user.department,
        user.group_id,
        settings,
        app.state.router,
        app.state.graph,
    )

    message_id = await db.insert_message(
        {
            "org_id": user.org_id,
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
        org_id=user.org_id,
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
            "provider_trace": result.provider_trace,
        },
    )

    outage = result.unavailable or bool(
        result.reason and result.reason.startswith("no language model available")
    )
    if result.refused and not outage:
        try:
            await db.record_unanswered(
                org_id=user.org_id,
                user_id=user.id,
                role=user.role,
                question=payload.question,
                reason=result.reason,
                closest=result.suggestions,
            )
        except Exception:  # noqa: BLE001 - the queue must not fail the answer
            logger.warning("could not record the unanswered question", exc_info=True)

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=message_id,
        answer=result.answer,
        confidence=result.confidence if not result.refused else "low",
        refused=result.refused,
        citations=[citation_payload_from_dict(item) for item in result.citations],
        suggestions=[citation_payload_from_dict(item) for item in result.suggestions],
        latency_ms=result.latency_ms,
        tokens=result.tokens,
        provider=result.provider,
        outage=outage,
        unavailable=result.unavailable,
        retrieval=result.retrieval if user.role == "admin" else None,
        reason=result.reason if user.role == "admin" else None,
        provider_trace=result.provider_trace if user.role == "admin" else None,
        raw_reply=result.raw_reply if user.role == "admin" else None,
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
                user.org_id,
                user.role,
                user.department,
                user.group_id,
                settings,
                app.state.router,
                app.state.graph,
            )
        except Exception:  # noqa: BLE001 - the stream must close cleanly
            logger.exception("chat failed")
            yield frame("error", {"detail": "answer failed"})
            return

        if result.refused and not result.reason.startswith("no language model available"):
            try:
                await db.record_unanswered(
                    org_id=user.org_id,
                    user_id=user.id,
                    role=user.role,
                    question=payload.question,
                    reason=result.reason,
                    closest=result.suggestions,
                )
            except Exception:  # noqa: BLE001 - the queue must not fail the stream
                logger.warning("could not record the unanswered question", exc_info=True)

        yield frame(
            "citations",
            {
                "citations": result.citations,
                "suggestions": result.suggestions,
                "confidence": result.confidence,
            },
        )
        async for chunk in stream_tokens(result.answer):
            yield frame("token", {"text": chunk})

        message_id = await db.insert_message(
            {
                "org_id": user.org_id,
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
            org_id=user.org_id,
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
    messages = await db.list_messages(conversation_id, user.org_id, user.id)
    if not messages:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation_id": conversation_id, "messages": messages}


@app.post("/feedback", tags=["chat"])
async def feedback(payload: FeedbackRequest, user: AuthUser = Depends(current_user)) -> dict[str, str]:
    recorded = await db.record_feedback(
        payload.message_id, user.org_id, user.id, payload.rating, payload.reason
    )
    if not recorded:
        # The message is not in this workspace (or not this user's): do not say
        # whether the id exists elsewhere.
        raise HTTPException(status_code=404, detail="message not found")
    await audit.record(
        org_id=user.org_id,
        action="feedback.recorded",
        resource_type="message",
        resource_id=payload.message_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"rating": payload.rating},
    )
    return {"status": "recorded"}


async def _index_upload(
    document_id: str, org_id: str, text: str, settings: Settings
) -> None:
    try:
        chunks = ingest.chunk_markdown(text)
        if not chunks:
            raise uploads.UploadError("no usable sections were found")
        await db.set_document_progress(document_id, org_id, 10)
        batch_size = 8
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            embeddings = await asyncio.to_thread(
                embed_documents, [chunk["content"] for chunk in batch], settings
            )
            for chunk, embedding in zip(batch, embeddings, strict=False):
                chunk["embedding"] = embedding
            await db.set_document_progress(
                document_id, org_id, 10 + int(80 * min(1, (start + batch_size) / len(chunks)))
            )
        await db.replace_chunks(document_id, chunks)
        await db.set_document_status(document_id, org_id, "active")
        await db.set_document_progress(document_id, org_id, 100)
    except asyncio.CancelledError:
        raise
    except uploads.UploadError as exc:
        await db.set_document_status(document_id, org_id, "failed", exc.reason)
    except Exception:  # noqa: BLE001 - a bad file must never crash the worker
        logger.exception("upload indexing failed")
        await db.set_document_status(
            document_id, org_id, "failed", "the document could not be indexed"
        )


@app.post("/documents/upload", status_code=202, tags=["documents"])
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    group_id: str | None = Form(default=None),
    user: AuthUser = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Upload one document. Type, size, rate and storage caps are server-side."""
    if not storage.configured(settings):
        raise HTTPException(status_code=503, detail="document storage is not configured")
    if not await db.upload_rate_allowed(
        user.id, user.org_id, UPLOAD_RATE_LIMIT, UPLOAD_RATE_WINDOW
    ):
        raise HTTPException(
            status_code=429,
            detail="upload limit reached: 10 documents per hour",
            headers={"Retry-After": str(UPLOAD_RATE_WINDOW)},
        )

    buffer = bytearray()
    while True:
        piece = await file.read(1024 * 1024)
        if not piece:
            break
        buffer.extend(piece)
        if len(buffer) > uploads.MAX_BYTES:
            raise HTTPException(status_code=413, detail="the file is larger than 10 MB")

    try:
        parsed = await asyncio.wait_for(
            asyncio.to_thread(uploads.extract, file.filename, bytes(buffer)),
            timeout=uploads.PARSE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=422, detail="the file took too long to read") from exc
    except uploads.UploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc

    if group_id and not await db.group_in_org(group_id, user.org_id):
        raise HTTPException(status_code=422, detail="group does not belong to this workspace")
    used = await db.org_storage_used(user.org_id)
    if used + len(buffer) > uploads.MAX_ORG_BYTES:
        raise HTTPException(
            status_code=413,
            detail="this workspace has reached its 200 MB storage limit",
        )

    document_id = str(uuid.uuid4())
    path = f"{user.org_id}/{document_id}/{parsed.safe_name}"
    mime = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "html": "text/html",
        "text": "text/plain",
    }[parsed.kind]
    display_title = (title or parsed.safe_name).strip()[:160] or parsed.safe_name
    try:
        await storage.put(settings, path, bytes(buffer), mime)
    except Exception as exc:  # noqa: BLE001
        logger.warning("storage upload failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="the file could not be stored") from exc

    document_id = await db.create_upload_document(
        org_id=user.org_id,
        user_id=user.id,
        title=display_title,
        slug=f"upload-{uuid.uuid4().hex[:12]}",
        file_size=len(buffer),
        storage_path=path,
        mime_type=mime,
        content_hash=hash_identifier(path),
        group_id=group_id,
    )
    await audit.record(
        org_id=user.org_id,
        action="document.uploaded",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"title": display_title, "bytes": len(buffer), "kind": parsed.kind},
    )
    asyncio.create_task(_index_upload(document_id, user.org_id, parsed.text, settings))
    return {"document_id": document_id, "status": "processing", "progress": 0}


@app.get("/documents/{document_id}", tags=["documents"])
async def document_status(
    document_id: str, user: AuthUser = Depends(current_user)
) -> dict[str, Any]:
    detail = await db.document_detail(document_id, user.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {
        **detail,
        "id": str(detail["id"]),
        "updated_at": detail["updated_at"].isoformat()
        if hasattr(detail["updated_at"], "isoformat")
        else str(detail["updated_at"]),
    }


@app.get("/documents/{document_id}/download", tags=["documents"])
async def download_document(
    document_id: str,
    user: AuthUser = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Download an original as an attachment: HTML is never served inline."""
    detail = await db.document_detail(document_id, user.org_id)
    if detail is None or not detail["storage_path"]:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        body = await storage.get(settings, str(detail["storage_path"]))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="stored file not found") from exc
    name = uploads.safe_filename(str(detail["storage_path"]).rsplit("/", 1)[-1])
    media = "application/pdf" if detail["mime_type"] == "application/pdf" else "text/plain"
    return Response(
        content=body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/documents/{document_id}/reindex", status_code=202, tags=["documents"])
async def reindex_document(
    document_id: str,
    user: AuthUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    detail = await db.document_detail(document_id, user.org_id)
    if detail is None or not detail["storage_path"]:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        body = await storage.get(settings, str(detail["storage_path"]))
        parsed = await asyncio.wait_for(
            asyncio.to_thread(
                uploads.extract, str(detail["storage_path"]).rsplit("/", 1)[-1], body
            ),
            timeout=uploads.PARSE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        await db.set_document_status(document_id, user.org_id, "failed", "re-index timed out")
        raise HTTPException(status_code=422, detail="re-index timed out") from exc
    except uploads.UploadError as exc:
        await db.set_document_status(document_id, user.org_id, "failed", exc.reason)
        raise HTTPException(status_code=422, detail=exc.reason) from exc
    await db.set_document_status(document_id, user.org_id, "processing")
    await db.set_document_progress(document_id, user.org_id, 0)
    asyncio.create_task(_index_upload(document_id, user.org_id, parsed.text, settings))
    return {"status": "processing", "document_id": document_id}


@app.get("/documents", tags=["documents"])
async def documents(user: AuthUser = Depends(current_user)) -> dict[str, Any]:
    rows = await db.list_documents(
        user.org_id, user.role, user.department, user.group_id
    )
    return {"documents": rows, "role": user.role}


@app.patch("/documents/{document_id}", tags=["documents"])
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    user: AuthUser = Depends(require_admin),
) -> dict[str, str]:
    if payload.access_level == "department" and not payload.department:
        raise HTTPException(status_code=422, detail="department is required for that level")
    updated = await db.set_document_access(
        document_id, user.org_id, payload.access_level, payload.department
    )
    if not updated:
        raise HTTPException(status_code=404, detail="document not found")
    await audit.record(
        org_id=user.org_id,
        action="document.access_changed",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"access_level": payload.access_level, "department": payload.department},
    )
    return {"status": "updated"}


@app.delete("/documents/{document_id}", tags=["documents"])
async def remove_document(
    document_id: str,
    user: AuthUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Delete an uploaded document, its chunks and its stored original.

    Sample-workspace corpus documents stay immutable so a shared reviewer cannot
    destroy evidence; only uploaded documents in a real workspace can be removed.
    """
    detail = await db.document_detail(document_id, user.org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="document not found")
    path = await db.delete_upload_document(document_id, user.org_id)
    if path is None and detail["storage_path"] is None:
        raise HTTPException(
            status_code=403,
            detail="sample workspace documents cannot be deleted",
        )
    if path:
        try:
            await storage.delete(settings, path)
        except Exception:  # noqa: BLE001 - the row is the source of truth
            logger.warning("stored original could not be removed", exc_info=True)
    await audit.record(
        org_id=user.org_id,
        action="document.deleted",
        resource_type="document",
        resource_id=document_id,
        actor_id=user.id,
        actor_role=user.role,
        detail={"title": detail["title"]},
    )
    return {"status": "deleted"}


@app.get("/admin/unanswered", tags=["admin"])
async def unanswered_queue(
    limit: int = 50, user: AuthUser = Depends(require_admin)
) -> dict[str, Any]:
    """Questions the copilot could not answer, newest first."""
    return {"questions": await db.list_unanswered(user.org_id, max(1, min(limit, 200)))}


@app.post("/admin/unanswered/{question_id}/resolve", tags=["admin"])
async def resolve_unanswered(
    question_id: str, user: AuthUser = Depends(require_admin)
) -> dict[str, str]:
    resolved = await db.resolve_unanswered(question_id, user.org_id, user.id)
    if not resolved:
        raise HTTPException(status_code=404, detail="question not found or already resolved")
    await audit.record(
        org_id=user.org_id,
        action="knowledge.gap_resolved",
        resource_type="unanswered_question",
        resource_id=question_id,
        actor_id=user.id,
        actor_role=user.role,
    )
    return {"status": "resolved"}


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
        org_id=user.org_id,
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
    all_candidates: bool = False,
    settings: Settings = Depends(get_settings),
    _: AuthUser = Depends(require_admin),
) -> dict[str, Any]:
    """Ranking and scores for one question, without calling a language model.

    Refusal is decided by a single number, the top rerank score. This returns it so
    a threshold can be tuned against the corpus instead of guessed at. With
    `all_candidates=true` every scored passage is returned, which is what the
    model-free evaluation needs to compare fused order, rerank order and blends.
    """
    result = await retrieve(
        question,
        _.org_id,
        role if _.role in ("admin", "owner") else _.role,
        department,
        _.group_id,
        settings,
        all_candidates,
    )
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
                "snippet": (candidate.content or "")[:240],
            }
            for candidate in result.candidates
        ],
    }


@app.get("/admin/recall", tags=["admin"])
async def recall_debug(
    question: str,
    role: str = "admin",
    department: str | None = None,
    k: int = 50,
    settings: Settings = Depends(get_settings),
    _: AuthUser = Depends(require_admin),
) -> dict[str, Any]:
    """The hybrid candidates before dedup, reranking or any threshold.

    Recall is a property of this list: if the answer is not in it, no reranker or
    threshold downstream can recover it.
    """
    embedding = await asyncio.to_thread(embed_query, question, settings)
    rows = await db.search_chunks(
        embedding=embedding,
        query_text=question,
        org_id=_.org_id,
        role=role if _.role in ("admin", "owner") else _.role,
        department=department,
        group_id=_.group_id,
        limit=max(1, min(k, 100)),
    )
    return {
        "k": k,
        "candidates": [
            {
                "document_id": str(row["document_id"]),
                "title": row["title"],
                "heading": row["heading"],
                "rrf_score": round(float(row["rrf_score"]), 5),
                "snippet": (row["content"] or "")[:240],
            }
            for row in rows
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
    rows = await db.audit_page(_.org_id, min(limit, 200))
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
async def audit_verify(
    full: bool = False, user: AuthUser = Depends(require_admin)
) -> AuditVerifyResponse:
    """Verify the audit chain from the last checkpoint, or from genesis.

    Re-hashing 1 600 rows on every run is wasted work once a prefix has been
    verified, so a successful run stores the head it reached and the next run
    starts there. That is only safe because the checkpoint is not trusted
    blindly: the row it names must still exist and hash to the stored head, and
    the first new row is checked against it, so a stale or rewritten checkpoint
    falls back to a full pass. `?full=true` forces that pass and is what the
    weekly schedule uses, so a forged checkpoint cannot hide an edit for long.
    The row ceiling keeps a runaway table from pinning the free instance; it
    reports `complete: false` rather than pretending the log was verified.
    """
    checkpoint = None if full else await db.audit_checkpoint()
    checkpoint_at = checkpoint["updated_at"] if checkpoint else None
    start = 0
    if checkpoint is not None:
        anchor = await db.audit_row(int(checkpoint["last_id"]))
        if anchor is not None and anchor["entry_hash"] == checkpoint["head"]:
            start = int(checkpoint["last_id"])
        else:
            logger.warning("audit checkpoint %s no longer matches; full re-verify", checkpoint["last_id"])
            checkpoint = None
            checkpoint_at = None

    rows: list[dict[str, Any]] = []
    after = start
    reached_end = False
    while len(rows) < AUDIT_VERIFY_MAX_ROWS:
        batch = await db.audit_rows(after, AUDIT_VERIFY_PAGE)
        rows.extend(batch)
        if len(batch) < AUDIT_VERIFY_PAGE:
            reached_end = True
            break
        after = batch[-1]["id"]

    initial_prev = str(checkpoint["head"]) if checkpoint else audit.GENESIS
    result = audit.verify_chain(rows, initial_prev=initial_prev)
    checked_at = datetime.now(timezone.utc)
    verified_now = len(rows)
    entries = int(checkpoint["entries"]) + verified_now if checkpoint else verified_now
    anchored = (
        bool(checkpoint["anchored_at_genesis"]) if checkpoint else result["anchored_at_genesis"]
    )
    result.update(
        {
            "complete": reached_end,
            "entries": entries,
            "verified_now": verified_now,
            "mode": "incremental" if checkpoint else "full",
            "checkpoint_id": int(checkpoint["last_id"]) if checkpoint else None,
            "first_id": rows[0]["id"] if rows else start or None,
            "last_id": rows[-1]["id"] if rows else start or None,
            "anchored_at_genesis": anchored,
            "verified_at": checked_at.isoformat(timespec="seconds"),
            "checkpoint_at": checkpoint_at.isoformat(timespec="seconds")
            if hasattr(checkpoint_at, "isoformat")
            else checkpoint_at,
        }
    )
    # A resume point that has not moved in a day and a run that hashed nothing
    # new means verification is stuck, not that the log is quiet. Re-check the
    # whole log instead of trusting the same checkpoint again.
    if (
        not full
        and checkpoint is not None
        and verified_now == 0
        and isinstance(checkpoint_at, datetime)
        and (datetime.now(timezone.utc) - checkpoint_at).total_seconds() > 24 * 3600
    ):
        logger.warning("checkpoint is over 24 h old with nothing new; escalating to a full pass")
        return await audit_verify(full=True, user=user)
    if checkpoint is not None:
        result["anchor_id"] = int(checkpoint["last_id"])
    if result["intact"] and reached_end and rows:
        await db.save_audit_checkpoint(
            int(rows[-1]["id"]), str(rows[-1]["entry_hash"]), entries, anchored
        )
        result["checkpoint_at"] = checked_at.isoformat(timespec="seconds")
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
