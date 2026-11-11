# Security report

Date: 2026-11-11. Scope: this repository and the two deployed origins.

## Verified in this build

| Control | Evidence |
| --- | --- |
| Authorisation inside SQL | `search_chunks` takes `role` and `department` and applies `can_read` in the query; a post-filter would be a bug. `supabase/migrations/20261111000100_init.sql`. |
| Row Level Security | Policies on `documents`, `chunks`, `profiles`, `audit_log`, `eval_runs`; verified by querying as a role account through PostgREST. |
| Identity from token | The API verifies the Supabase JWT against the project JWKS, then loads the role from `profiles`; `require_admin` rejects employees. |
| Audit chain | Each row stores the previous hash; `/audit/verify` recomputes the chain and reports the first break. |
| Secret separation | Only the anon key is in the browser bundle; the service-role key exists on the API host only. `.env.example` lists names, no values. |
| Secret scanning | CI installs the pinned gitleaks CLI and scans full history; the job is green. |
| Dependency audit | `pnpm audit --audit-level high` is clean (one moderate advisory remains, below the gate); `pip-audit` runs for the API. |
| Commit hygiene | CI fails on attribution trailers; the four commits that predated the rule were rewritten and force-pushed once. |
| Transport | HTTPS everywhere; CORS restricted to the Vercel origin plus localhost. |
| Injection resistance | Answers are plain text, no HTML rendering, no tool execution from model output. |

## Open findings

1. **Availability, not confidentiality.** The free API instance exceeds 512 MB
   when both ONNX models load, so chat can return 502 while the service
   restarts. Retrieval reranks with the TinyBERT cross-encoder (`EKC_RERANK_ENABLED=1`);
   turning the reranker back on requires an instance with more memory.
2. **Demo accounts share a password.** Stored as a GitHub secret and used only
   for review. Rotate with `gh workflow run seed-users.yml` before any real use.
3. **No published evaluation report yet.** `docs/reports/eval.json` is absent,
   so `node scripts/check-done.mjs --phase P8` fails by design. The harness and
   the 84-question golden set are committed.
4. **No third-party penetration test.**

## Reproduction

```bash
node scripts/check-done.mjs --phase P0
node scripts/check-done.mjs --phase P1
gh run list --workflow=ci.yml --limit 1
curl -s https://enterprise-knowledge-copilot-2u57.onrender.com/health
```
