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

    # Both run on ONNX Runtime through fastembed and flashrank: the free host
    # gives 512 MB, which torch cannot fit. Dims stay at 384 for the schema.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    reranker_model: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"

    # Retrieval knobs. Kept explicit so the evaluation report can cite them.
    candidate_limit: int = 30
    rerank_top_k: int = 6
    min_rerank_score: float = -6.0
    min_answer_score: float = -4.0

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
