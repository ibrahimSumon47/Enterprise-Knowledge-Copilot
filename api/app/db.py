"""Database access. All permission predicates live in SQL, never in Python filters."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

import asyncpg

from .config import Settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# One statement per operation keeps the access predicate auditable in one place.
SEARCH_SQL = """
select chunk_id, document_id, title, heading, content, access_level, department,
       is_synthetic, source_url, license, attribution, rrf_score
from public.search_chunks_org($1::vector, $2::text, $3::uuid, $4::text, $5::text, $6::int)
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
    org_id: str,
    role: str,
    department: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Hybrid search with the organisation and access predicates in SQL."""
    rows = await pool().fetch(
        SEARCH_SQL,
        _vector_literal(embedding),
        query_text,
        org_id,
        role,
        department or "",
        limit,
    )
    return [dict(row) for row in rows]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


async def insert_document(document: dict[str, Any]) -> str:
    """Upsert a document by slug and return its id."""
    row = await pool().fetchrow(
        """
        insert into public.documents
          (org_id, slug, title, source_url, license, attribution, access_level,
           department, is_synthetic, content_hash, metadata)
        values (coalesce($1::uuid, (select id from public.organizations where is_sample limit 1)),
                $2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
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
        document.get("org_id"),
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
                  (org_id, document_id, ordinal, heading, content, token_count, embedding)
                select d.org_id, $1, $2, $3, $4, $5, $6::vector
                from public.documents d where d.id = $1
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


async def create_conversation(org_id: str, user_id: str, title: str) -> str:
    row = await pool().fetchrow(
        """
        insert into public.conversations (org_id, user_id, title)
        values ($1, $2, $3) returning id
        """,
        org_id,
        user_id,
        title[:120],
    )
    return str(row["id"])


async def conversation_owner(conversation_id: str, org_id: str) -> str | None:
    row = await pool().fetchrow(
        "select user_id from public.conversations where id = $1 and org_id = $2",
        conversation_id,
        org_id,
    )
    return str(row["user_id"]) if row else None


async def insert_message(message: dict[str, Any]) -> str:
    row = await pool().fetchrow(
        """
        insert into public.messages
          (org_id, conversation_id, role, content, citations, confidence, refused,
           latency_ms, token_count, provider)
        values ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10)
        returning id
        """,
        message["org_id"],
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


async def list_messages(
    conversation_id: str, org_id: str, user_id: str
) -> list[dict[str, Any]]:
    """Messages of a conversation, scoped to the tenant and its owner."""
    owner = await conversation_owner(conversation_id, org_id)
    if owner != user_id:
        return []
    rows = await pool().fetch(
        """
        select id, role, content, citations, confidence, refused, latency_ms,
               token_count, provider, created_at
        from public.messages
        where conversation_id = $1 and org_id = $2
        order by created_at asc
        """,
        conversation_id,
        org_id,
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


async def create_workspace(user_id: str, email: str, name: str) -> str:
    """Create an empty workspace and make the signer-up its owner."""
    async with pool().acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                insert into public.profiles (id, email, role)
                values ($1::uuid, $2, 'employee')
                on conflict (id) do nothing
                """,
                user_id,
                email,
            )
            row = await connection.fetchrow(
                """
                insert into public.organizations (name, slug, created_by)
                values ($1, $2, $3::uuid)
                returning id
                """,
                name[:80],
                f"{_slug(name)[:40] or 'workspace'}-{uuid.uuid4().hex[:8]}",
                user_id,
            )
            await connection.execute(
                """
                insert into public.org_members (org_id, user_id, role)
                values ($1, $2::uuid, 'owner')
                on conflict (org_id, user_id) do update set role = 'owner'
                """,
                row["id"],
                user_id,
            )
            return str(row["id"])


async def rename_workspace(org_id: str, name: str) -> bool:
    row = await pool().fetchrow(
        "update public.organizations set name = $2 where id = $1 returning id",
        org_id,
        name[:80],
    )
    return row is not None


async def profile_for(user_id: str) -> dict[str, Any] | None:
    row = await pool().fetchrow(
        """
        select p.id, p.email, p.role, p.department,
               m.org_id, m.role as org_role
        from public.profiles p
        left join public.org_members m
          on m.user_id = p.id and m.status = 'active'
        where p.id = $1
        """,
        user_id,
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
          (org_id, prev_hash, entry_hash, actor_id, actor_role, action,
           resource_type, resource_id, outcome, ip_hash, detail, created_at)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::timestamptz)
        """,
        entry["org_id"],
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
        # value and made every entry fail its own hash check. asyncpg wants a
        # datetime here, not the ISO string the hash is computed over.
        datetime.fromisoformat(entry["created_at"]),
    )


async def audit_rows(after_id: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
    """One ascending page of the audit log, for whole-log verification.

    `audit_page` returns the newest N rows for the UI; verification has to walk
    from the genesis row upward or a break before the window stays invisible.
    """
    rows = await pool().fetch(
        """
        -- Every column the hash covers must be selected, or verification
        -- compares a payload the row never had.
        select id, prev_hash, entry_hash, actor_id, actor_role, action,
               resource_type, resource_id, outcome, ip_hash, created_at, detail
        from public.audit_log
        where id > $1
        order by id asc
        limit $2
        """,
        after_id,
        limit,
    )
    return [dict(row) for row in rows]


_checkpoint_ready = False

_CHECKPOINT_DDL = """
create table if not exists public.audit_verify_checkpoint (
  id boolean primary key default true check (id),
  last_id bigint not null,
  head text not null,
  entries bigint not null,
  anchored_at_genesis boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.audit_verify_checkpoint enable row level security;
"""


async def ensure_audit_checkpoint() -> None:
    """Create the single-row checkpoint table on first use.

    Migrations are applied by hand here, and verification must not fail just
    because the newest one has not run yet; `create table if not exists` is
    idempotent, so it costs one round trip per process.
    """
    global _checkpoint_ready
    if _checkpoint_ready:
        return
    await pool().execute(_CHECKPOINT_DDL)
    _checkpoint_ready = True


async def audit_checkpoint() -> dict[str, Any] | None:
    await ensure_audit_checkpoint()
    row = await pool().fetchrow(
        """
        select last_id, head, entries, anchored_at_genesis, updated_at
        from public.audit_verify_checkpoint
        where id
        """
    )
    return dict(row) if row else None


async def audit_row(row_id: int) -> dict[str, Any] | None:
    """The checkpoint anchor row, used to detect a stale or rewritten checkpoint."""
    row = await pool().fetchrow(
        "select id, entry_hash from public.audit_log where id = $1", row_id
    )
    return dict(row) if row else None


async def save_audit_checkpoint(
    last_id: int, head: str, entries: int, anchored_at_genesis: bool
) -> None:
    """Advance the checkpoint. It never moves backwards.

    A concurrent run that verified a shorter prefix cannot roll the pointer back,
    and a failed verification never reaches this function at all.
    """
    await ensure_audit_checkpoint()
    await pool().execute(
        """
        insert into public.audit_verify_checkpoint
          (id, last_id, head, entries, anchored_at_genesis, updated_at)
        values (true, $1, $2, $3, $4, now())
        on conflict (id) do update
          set last_id = excluded.last_id,
              head = excluded.head,
              entries = excluded.entries,
              anchored_at_genesis = excluded.anchored_at_genesis,
              updated_at = now()
          where excluded.last_id >= public.audit_verify_checkpoint.last_id
        """,
        last_id,
        head,
        entries,
        anchored_at_genesis,
    )


async def audit_page(org_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = await pool().fetch(
        """
        -- Every column the hash covers must be selected, or verification
        -- compares a payload the row never had.
        select id, prev_hash, entry_hash, actor_id, actor_role, action,
               resource_type, resource_id, outcome, ip_hash, created_at, detail
        from public.audit_log
        where org_id = $1
        order by id desc
        limit $2
        """,
        org_id,
        limit,
    )
    return [dict(row) for row in rows]


async def list_documents(
    org_id: str, role: str, department: str | None
) -> list[dict[str, Any]]:
    """Admin/inventory listing that still applies the access predicate."""
    rows = await pool().fetch(
        """
        select id, slug, title, access_level, department, is_synthetic, status,
               source_url, version, updated_at,
               (select count(*) from public.chunks c where c.document_id = d.id) as chunk_count
        from public.documents d
        where status = 'active'
          and org_id = $3
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
        org_id,
    )
    return [dict(row) for row in rows]


async def set_document_access(
    document_id: str, org_id: str, access_level: str, department: str | None
) -> bool:
    row = await pool().fetchrow(
        """
        update public.documents
        set access_level = $3, department = $4, updated_at = now()
        where id = $1 and org_id = $2
        returning id
        """,
        document_id,
        org_id,
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


async def record_unanswered(
    *,
    org_id: str,
    user_id: str,
    role: str,
    question: str,
    reason: str,
    closest: list[dict[str, Any]],
) -> None:
    """Queue a refused question so an admin can close the knowledge gap."""
    await pool().execute(
        """
        insert into public.unanswered_questions
          (org_id, user_id, role, question, reason, closest)
        values ($1, $2::uuid, $3, $4, $5, $6::jsonb)
        """,
        org_id,
        user_id,
        role,
        question[:2000],
        reason[:240],
        json.dumps(closest),
    )


async def record_feedback(
    message_id: str, org_id: str, user_id: str, rating: int, reason: str | None
) -> bool:
    """Record feedback only when the message belongs to this user and tenant."""
    row = await pool().fetchrow(
        """
        insert into public.feedback (message_id, user_id, rating, reason, org_id)
        select m.id, $2::uuid, $3, $4, c.org_id
        from public.messages m
        join public.conversations c on c.id = m.conversation_id
        where m.id = $1::uuid and c.org_id = $5 and c.user_id = $2::uuid
        on conflict (message_id, user_id) do update set
          rating = excluded.rating, reason = excluded.reason
        returning id
        """,
        message_id,
        user_id,
        rating,
        reason,
        org_id,
    )
    return row is not None


async def org_name(org_id: str) -> str | None:
    row = await pool().fetchrow(
        "select name from public.organizations where id = $1", org_id
    )
    return str(row["name"]) if row else None


async def list_unanswered(org_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = await pool().fetch(
        """
        select id, role, question, reason, closest, created_at
        from public.unanswered_questions
        where org_id = $1 and resolved_at is null
        order by created_at desc
        limit $2
        """,
        org_id,
        limit,
    )
    return [dict(row) for row in rows]


async def resolve_unanswered(question_id: str, org_id: str, actor_id: str) -> bool:
    row = await pool().fetchrow(
        """
        update public.unanswered_questions
        set resolved_at = now(), resolved_by = $3::uuid
        where id = $1::uuid and org_id = $2 and resolved_at is null
        returning id
        """,
        question_id,
        org_id,
        actor_id,
    )
    return bool(row)


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
