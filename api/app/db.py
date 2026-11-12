"""Database access. All permission predicates live in SQL, never in Python filters."""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from .config import Settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# One statement per operation keeps the access predicate auditable in one place.
SEARCH_SQL = """
select chunk_id, document_id, title, heading, content, access_level, department,
       is_synthetic, source_url, license, attribution, rrf_score
from public.search_chunks($1::vector, $2::text, $3::text, $4::text, $5::int)
"""


async def init_pool(settings: Settings) -> asyncpg.Pool:
    """Create the connection pool once per process."""
    global _pool
    if _pool is None:
        dsn = settings.supabase_db_url
        if not dsn:
            raise RuntimeError("SUPABASE_DB_URL is not configured")
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=4,
            command_timeout=30,
            statement_cache_size=0,  # Supavisor transaction pooler is not compatible
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("database pool is not initialised")
    return _pool


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding) + "]"


async def search_chunks(
    embedding: list[float],
    query_text: str,
    role: str,
    department: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Hybrid search with the caller's access predicate inside the SQL function."""
    rows = await pool().fetch(
        SEARCH_SQL,
        _vector_literal(embedding),
        query_text,
        role,
        department or "",
        limit,
    )
    return [dict(row) for row in rows]


async def insert_document(document: dict[str, Any]) -> str:
    """Upsert a document by slug and return its id."""
    row = await pool().fetchrow(
        """
        insert into public.documents
          (slug, title, source_url, license, attribution, access_level, department,
           is_synthetic, content_hash, metadata)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
        on conflict (slug) do update set
          title = excluded.title,
          source_url = excluded.source_url,
          license = excluded.license,
          attribution = excluded.attribution,
          access_level = excluded.access_level,
          department = excluded.department,
          is_synthetic = excluded.is_synthetic,
          content_hash = excluded.content_hash,
          metadata = excluded.metadata,
          version = public.documents.version + 1,
          updated_at = now()
        returning id
        """,
        document["slug"],
        document["title"],
        document.get("source_url"),
        document.get("license", "CC BY-SA 4.0"),
        document.get("attribution", "GitLab Handbook"),
        document["access_level"],
        document.get("department"),
        bool(document.get("is_synthetic", False)),
        document["content_hash"],
        json.dumps(document.get("metadata", {})),
    )
    return str(row["id"])


async def replace_chunks(document_id: str, chunks: list[dict[str, Any]]) -> None:
    """Replace all chunks of a document inside one transaction."""
    async with pool().acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                "delete from public.chunks where document_id = $1", document_id
            )
            await connection.executemany(
                """
                insert into public.chunks
                  (document_id, ordinal, heading, content, token_count, embedding)
                values ($1,$2,$3,$4,$5,$6::vector)
                """,
                [
                    (
                        document_id,
                        chunk["ordinal"],
                        chunk.get("heading"),
                        chunk["content"],
                        chunk.get("token_count", 0),
                        _vector_literal(chunk["embedding"]),
                    )
                    for chunk in chunks
                ],
            )


async def create_conversation(user_id: str, title: str) -> str:
    row = await pool().fetchrow(
        """
        insert into public.conversations (user_id, title)
        values ($1, $2) returning id
        """,
        user_id,
        title[:120],
    )
    return str(row["id"])


async def conversation_owner(conversation_id: str) -> str | None:
    row = await pool().fetchrow(
        "select user_id from public.conversations where id = $1", conversation_id
    )
    return str(row["user_id"]) if row else None


async def insert_message(message: dict[str, Any]) -> str:
    row = await pool().fetchrow(
        """
        insert into public.messages
          (conversation_id, role, content, citations, confidence, refused,
           latency_ms, token_count, provider)
        values ($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9)
        returning id
        """,
        message["conversation_id"],
        message["role"],
        message["content"],
        json.dumps(message.get("citations", [])),
        message.get("confidence"),
        bool(message.get("refused", False)),
        message.get("latency_ms"),
        message.get("token_count"),
        message.get("provider"),
    )
    return str(row["id"])


async def list_messages(conversation_id: str, user_id: str) -> list[dict[str, Any]]:
    """Messages of a conversation, but only for its owner (IDOR guard)."""
    owner = await conversation_owner(conversation_id)
    if owner != user_id:
        return []
    rows = await pool().fetch(
        """
        select id, role, content, citations, confidence, refused, latency_ms,
               token_count, provider, created_at
        from public.messages
        where conversation_id = $1
        order by created_at asc
        """,
        conversation_id,
    )
    return [dict(row) for row in rows]


async def rate_limit_hit(user_id: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Sliding-window rate limit in Postgres. Returns (allowed, remaining)."""
    async with pool().acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                delete from public.rate_events
                where user_id = $1 and created_at < now() - ($2 || ' seconds')::interval
                """,
                user_id,
                str(window_seconds),
            )
            count = await connection.fetchval(
                "select count(*) from public.rate_events where user_id = $1", user_id
            )
            if count >= limit:
                return False, 0
            await connection.execute(
                "insert into public.rate_events (user_id) values ($1)", user_id
            )
            return True, max(0, limit - int(count) - 1)


async def profile_for(user_id: str) -> dict[str, Any] | None:
    row = await pool().fetchrow(
        "select id, email, role, department from public.profiles where id = $1", user_id
    )
    return dict(row) if row else None


async def last_audit_hash() -> str:
    row = await pool().fetchrow(
        "select entry_hash from public.audit_log order by id desc limit 1"
    )
    return str(row["entry_hash"]) if row else "genesis"


async def insert_audit(entry: dict[str, Any]) -> None:
    await pool().execute(
        """
        insert into public.audit_log
          (prev_hash, entry_hash, actor_id, actor_role, action, resource_type,
           resource_id, outcome, ip_hash, detail, created_at)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::timestamptz)
        """,
        entry["prev_hash"],
        entry["entry_hash"],
        entry.get("actor_id"),
        entry.get("actor_role"),
        entry["action"],
        entry["resource_type"],
        entry.get("resource_id"),
        entry.get("outcome", "ok"),
        entry.get("ip_hash"),
        json.dumps(entry.get("detail", {})),
        # The hash covers created_at, so the row must store the same instant.
        # Letting the column default to now() stored a later, microsecond-precise
        # value and made every entry fail its own hash check.
        entry["created_at"],
    )


async def audit_page(limit: int = 100) -> list[dict[str, Any]]:
    rows = await pool().fetch(
        """
        -- Every column the hash covers must be selected, or verification
        -- compares a payload the row never had.
        select id, prev_hash, entry_hash, actor_id, actor_role, action,
               resource_type, resource_id, outcome, ip_hash, created_at, detail
        from public.audit_log
        order by id desc
        limit $1
        """,
        limit,
    )
    return [dict(row) for row in rows]


async def list_documents(role: str, department: str | None) -> list[dict[str, Any]]:
    """Admin/inventory listing that still applies the access predicate."""
    rows = await pool().fetch(
        """
        select id, slug, title, access_level, department, is_synthetic, status,
               source_url, version, updated_at,
               (select count(*) from public.chunks c where c.document_id = d.id) as chunk_count
        from public.documents d
        where status = 'active'
          and (
            $1 = 'admin'
            or ($1 = 'guest' and access_level = 'public')
            or ($1 <> 'guest' and (
                 access_level in ('public','employee')
                 or (access_level = 'department' and department = $2)))
          )
        order by access_level, title
        limit 500
        """,
        role,
        department or "",
    )
    return [dict(row) for row in rows]


async def set_document_access(document_id: str, access_level: str, department: str | None) -> bool:
    row = await pool().fetchrow(
        """
        update public.documents
        set access_level = $2, department = $3, updated_at = now()
        where id = $1
        returning id
        """,
        document_id,
        access_level,
        department,
    )
    return row is not None


async def delete_document(document_id: str) -> bool:
    row = await pool().fetchrow(
        "delete from public.documents where id = $1 returning id", document_id
    )
    return row is not None


async def eval_runs(limit: int = 20) -> list[dict[str, Any]]:
    rows = await pool().fetch(
        """
        select id, mode, commit_sha, metrics, passed, created_at
        from public.eval_runs
        order by created_at desc
        limit $1
        """,
        limit,
    )
    return [dict(row) for row in rows]


async def record_eval_run(
    mode: str, commit_sha: str | None, metrics: dict[str, Any], passed: bool
) -> None:
    await pool().execute(
        """
        insert into public.eval_runs (mode, commit_sha, metrics, passed)
        values ($1,$2,$3::jsonb,$4)
        """,
        mode,
        commit_sha,
        json.dumps(metrics),
        passed,
    )


async def cache_get(cache_key: str, access_scope: str) -> dict[str, Any] | None:
    row = await pool().fetchrow(
        """
        select answer from public.answer_cache
        where cache_key = $1 and access_scope = $2
          and created_at > now() - interval '1 day'
        """,
        cache_key,
        access_scope,
    )
    return json.loads(row["answer"]) if row else None


async def cache_put(cache_key: str, access_scope: str, answer: dict[str, Any]) -> None:
    await pool().execute(
        """
        insert into public.answer_cache (cache_key, access_scope, answer)
        values ($1,$2,$3::jsonb)
        on conflict (cache_key) do update set
          access_scope = excluded.access_scope,
          answer = excluded.answer,
          created_at = now()
        """,
        cache_key,
        access_scope,
        json.dumps(answer),
    )


async def ready_checks() -> dict[str, Any]:
    """Readiness probe used by the Space and the check-done script."""
    row = await pool().fetchrow(
        """
        select
          (select count(*) from public.documents where status = 'active') as documents,
          (select count(*) from public.chunks) as chunks,
          (select count(*) from public.profiles) as profiles
        """
    )
    return dict(row)
