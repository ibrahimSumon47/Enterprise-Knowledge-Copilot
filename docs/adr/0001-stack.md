# ADR 0001 — Next.js on Vercel, FastAPI on Render, Supabase for data

Status: accepted (2026-11-11).

## Context

The brief requires a role-aware RAG copilot that runs entirely on free tiers,
proves access control in the database, and stays portable. Hugging Face Docker
Spaces, the original API host, now require a PRO plan, so the API needed a new
home without changing the architecture.

## Decision

- **Web:** Next.js 16 App Router on Vercel Hobby. Server components for pages,
  client components only where a session or a stream is involved.
- **API:** FastAPI in a Docker image on Render's free web service. Render injects
  `PORT`; the image builds from the repository root so `api/` and `data/` resolve
  with default settings.
- **Data:** Supabase Postgres with pgvector, Auth and RLS. Row Level Security is
  the access boundary; the API's service role is used for writes only.
- **Retrieval:** SQL function `search_chunks` performs hybrid pgvector plus
  full-text search, fuses with reciprocal rank fusion, and applies the access
  predicate inside the query.
- **Inference:** ONNX Runtime through `fastembed` and `flashrank`, not PyTorch.
  The free host gives 512 MB and 0.1 CPU; torch alone would not fit.

## Consequences

- The API sleeps after 15 idle minutes and wakes in about a minute.
- Ingestion must run on a build runner (`ingest.yml`), not on the API host.
- The cross-encoder is opt-in (`EKC_RERANK_ENABLED`) because the encoder and the
  reranker together exceed the free instance. Hybrid retrieval still returns
  citations; the evaluation harness can measure the difference.
- Anything that needs more memory or CPU is a paid upgrade, which the project
  rules currently forbid. The constraint is documented rather than hidden.
