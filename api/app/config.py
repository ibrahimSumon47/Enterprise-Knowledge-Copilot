"""Application settings. Values come from the environment only — never the repo."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_db_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_aud: str = "authenticated"

    groq_api_key: str = ""
    gemini_api_key: str = ""

    allowed_origins: str = "http://localhost:3000"

    # ONNX Runtime through fastembed: the free host gives 512 MB and torch does
    # not fit. The multilingual MiniLM (118M params, 0.22 GB on disk) still
    # crossed the limit while loading, so the default is bge-small-en-v1.5:
    # 0.067 GB, 384 dims, same schema. Non-Latin questions are translated to
    # English before they are embedded (pipeline._retrieval_question).
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"

    # Retrieval knobs. Kept explicit so the evaluation report can cite them.
    # With bge-small the encoder peaks near 110 MB, so the TinyBERT cross-encoder
    # fits inside 512 MB again and precision matters more than the saving.
    rerank_enabled: bool = True

    # The cross-encoder scores every candidate on a 0.1 CPU instance, so the pool
    # is the main latency lever: 24 keeps the recall that mattered at 40 while
    # roughly halving the scoring work.
    candidate_limit: int = 24
    # Three citations keeps the answer tight; six was diluting citation precision.
    rerank_top_k: int = 3
    # 96 tokens cut too much of the passage and cost hit@k; 192 keeps the policy
    # sentence in view at 0.75 of the 256-token scoring cost.
    rerank_max_length: int = 192
    # Adaptive depth: score a shortlist first and only pay for the rest when the
    # shortlist has nothing quotable. The trigger is the cross-encoder's own score,
    # not RRF: fusion scores are 1/(60+rank) and nearly flat when one branch returns
    # nothing (measured: an RRF margin rule fired on 2 of 46 questions), and high
    # confidence escalated 14 of 15 questions, so the bar is the refusal threshold.
    rerank_adaptive: bool = True
    rerank_fast_depth: int = 8
    # flashrank returns a sigmoid score in 0..1, not raw logits, so the
    # thresholds live on that scale: anything above 0.15 is worth answering from.
    min_rerank_score: float = 0.0
    min_answer_score: float = 0.15
    high_confidence_score: float = 0.45
    # Reciprocal-rank fusion never exceeds 2/61, so the hybrid fallback needs its
    # own scale instead of comparing against cross-encoder logits.
    rrf_high_score: float = 0.032
    rrf_medium_score: float = 0.016

    # Rate limits (per user, sliding window in Postgres).
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    max_question_chars: int = 2000

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
