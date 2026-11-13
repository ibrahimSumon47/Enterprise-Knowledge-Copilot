"""Request and response models. Pydantic validates every input at the edge."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION = 2000


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=MAX_QUESTION)
    conversation_id: str | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question is empty")
        return cleaned


class Citation(BaseModel):
    id: int
    title: str
    heading: str | None = None
    document_id: str
    chunk_id: str
    snippet: str
    source_url: str | None = None
    license: str
    attribution: str
    access_level: str
    is_synthetic: bool = False
    score: float


class RetrievalCandidate(BaseModel):
    id: int
    document_id: str
    chunk_id: str
    title: str
    heading: str | None = None
    rerank_score: float
    rrf_score: float
    reranked: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str | None = None
    answer: str
    confidence: Literal["high", "medium", "low"]
    refused: bool
    citations: list[Citation]
    # Offered on a refusal: the closest passages, so the reader has somewhere
    # to go instead of a dead end.
    suggestions: list[Citation] = []
    latency_ms: int
    tokens: int
    provider: str
    # True when no language model answered at all (outage or quota). Clients can
    # say "try again shortly" instead of implying the handbook has no answer.
    outage: bool = False
    unavailable: bool = False
    cached: bool = False
    # Admin-only debug field: retrieval order and scores for this question.
    retrieval: list[RetrievalCandidate] | None = None


class FeedbackRequest(BaseModel):
    message_id: str
    rating: Literal[-1, 1]
    reason: str | None = Field(default=None, max_length=600)


class DocumentUpdate(BaseModel):
    access_level: Literal["public", "employee", "department", "confidential"]
    department: Literal["engineering", "security", "people", "finance"] | None = None


class IngestResponse(BaseModel):
    job_id: str
    status: str


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    department: str | None
    visible_levels: list[str]


class AuditEntry(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: str | None
    actor_role: str | None
    outcome: str
    entry_hash: str
    created_at: str


class AuditVerifyResponse(BaseModel):
    entries: int
    intact: bool
    broken_ids: list[int]
    head: str
    # Orders verify from a stored checkpoint; `mode` says whether this run
    # re-hashed the whole log or only the rows after `checkpoint_id`.
    mode: str = "full"
    checkpoint_id: int | None = None
    verified_now: int = 0
    # `verified_at` is when this run finished; `checkpoint_at` is when the
    # resume point last advanced, so the panel can show how stale it is.
    verified_at: str | None = None
    checkpoint_at: str | None = None
    anchor_id: int | None = None
    anchored_at_genesis: bool = False
    complete: bool = True
    first_id: int | None = None
    last_id: int | None = None


class EvalRun(BaseModel):
    id: str
    mode: str
    commit_sha: str | None
    metrics: dict[str, Any]
    passed: bool
    created_at: str


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    documents: int
    chunks: int
    profiles: int
    providers: dict[str, str]
