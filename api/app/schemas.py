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
    quote: str | None = None


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
    # Admin-only debug fields: why the answer ended as it did.
    retrieval: list[RetrievalCandidate] | None = None
    reason: str | None = None
    provider_trace: list[str] | None = None
    raw_reply: str | None = None


class SignupRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=10, max_length=200)
    invite_token: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("a valid email is required")
        return cleaned


class WorkspaceNameRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("workspace name is too short")
        return cleaned


INVITE_ROLES = (
    "admin",
    "guest",
    "employee",
    "engineering",
    "security",
    "hr",
    "finance",
)


class InviteRequest(BaseModel):
    role: Literal[
        "admin", "guest", "employee", "engineering", "security", "hr", "finance"
    ] = "employee"
    group_id: str | None = None
    max_uses: int = Field(default=1, ge=1, le=100)
    expires_hours: int = Field(default=72, ge=1, le=720)


class GroupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class MemberUpdate(BaseModel):
    role: Literal[
        "admin", "guest", "employee", "engineering", "security", "hr", "finance"
    ] | None = None
    status: Literal["active", "deactivated"] | None = None
    group_id: str | None = None


class WorkspaceSettingsRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    logo_url: str | None = Field(default=None, max_length=500)
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    allowed_domains: list[str] | None = Field(default=None, max_length=20)

    @field_validator("allowed_domains")
    @classmethod
    def clean_domains(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for item in value:
            domain = item.strip().lower().lstrip("@")
            if not domain or "." not in domain or "/" in domain or " " in domain:
                raise ValueError(f"invalid email domain: {item}")
            if domain not in cleaned:
                cleaned.append(domain)
        return cleaned


class FirstDocumentRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    text: str = Field(min_length=40, max_length=50_000)


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
    org_id: str
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
