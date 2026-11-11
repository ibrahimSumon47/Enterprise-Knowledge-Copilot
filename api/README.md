---
title: Enterprise Knowledge Copilot API
emoji: 📚
colorFrom: teal
colorTo: gray
sdk: docker
pinned: false
---

# Enterprise Knowledge Copilot — API

FastAPI service behind https://enterprise-knowledge-copilot-wine.vercel.app.

It verifies Supabase JWTs, runs permission-aware hybrid retrieval (pgvector +
Postgres full-text, reciprocal rank fusion, cross-encoder reranking), and answers
through a small LangGraph pipeline that can refuse. Documents are treated as
untrusted data.

Configuration is by Space secrets only: `SUPABASE_URL`, `SUPABASE_DB_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`.
No secret is ever written to the repository.

Source and full documentation: https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot
