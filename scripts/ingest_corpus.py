"""Index data/corpus.jsonl into Supabase from a CI runner or a laptop.

The Render instance is intentionally tiny (0.1 CPU), so embedding 754 documents
there would take hours. This script reuses the API's own ingestion code on a
normal build runner, and records progress in the same ingest_jobs table.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import db, ingest  # noqa: E402
from app.config import get_settings  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if not settings.supabase_db_url:
        print("SUPABASE_DB_URL is not set", file=sys.stderr)
        return 2

    await db.init_pool(settings)
    job_id = str(uuid.uuid4())
    await db.pool().execute(
        "insert into public.ingest_jobs (id, status) values ($1, 'queued')", job_id
    )
    try:
        await ingest.run_ingest(job_id, settings)
        row = await db.pool().fetchrow(
            "select status, stats, error from public.ingest_jobs where id = $1", job_id
        )
        print("job", job_id, dict(row) if row else {})
        return 0 if row is not None and row["status"] == "done" else 1
    finally:
        await db.close_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
