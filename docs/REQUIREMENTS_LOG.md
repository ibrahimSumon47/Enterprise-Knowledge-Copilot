# REQUIREMENTS LOG — Enterprise Knowledge Copilot

One line per requirement. **Source** = `owner` (stated by the owner) or `agent` (decided by the agent, approved by the owner).
**Status** = `open` (not built), `blocked` (needs owner input/key), `done`.

| ID | Date | Requirement | Source | Status / Notes |
| --- | --- | --- | --- | --- |
| R-01 | 2026-11-11 | Industry-level AI Engineer portfolio project: chat copilot over a company handbook. | owner | open |
| R-02 | 2026-11-11 | Role-based document access (RBAC) — each role sees only allowed documents. | owner | open |
| R-03 | 2026-11-11 | Every answer must show citations (document + section). | owner | open |
| R-04 | 2026-11-11 | Refuse to answer when retrieval confidence is low (no guessing). | owner | open |
| R-05 | 2026-11-11 | Audit log of questions, answers, role, sources. | owner | open |
| R-06 | 2026-11-11 | Evaluation dashboard (retrieval quality, refusal correctness). | owner | open |
| R-07 | 2026-11-11 | Stack: Next.js 16 on Vercel; FastAPI on a free Hugging Face Space; Supabase (Postgres + pgvector + Auth + RLS). | owner | open |
| R-08 | 2026-11-11 | LLM: free API main + open-model backup. Both Groq and Gemini keys will be supplied. | owner | done — `GROQ_API_KEY` + `GEMINI_API_KEY` set as repo secrets |
| R-09 | 2026-11-11 | Corpus: public GitLab Handbook (CC BY-SA 4.0), slice of ~800 pages. | owner | open |
| R-10 | 2026-11-11 | Everything free forever, cloud only (no local Docker, no paid services). | owner | constraint |
| R-11 | 2026-11-11 | Display name: **Enterprise Knowledge Copilot**. Tagline: "Ask the handbook. Get answers with proof." | owner | decided |
| R-12 | 2026-11-11 | Accent colour Teal `#0F766E`; logo = simple icon mark + wordmark. | agent (owner said "you choose") | decided |
| R-13 | 2026-11-11 | UI in English with a Bangla UI toggle; Bangla questions over English documents must work. | owner | open |
| R-14 | 2026-11-11 | Confidence badge on every answer (High / Medium / Refused). | agent, approved | open |
| R-15 | 2026-11-11 | Starter question chips in the chat, tailored per role. | agent, approved | open |
| R-16 | 2026-11-11 | Per-role refusal test cases on the evaluation dashboard. | agent, approved | open |
| R-17 | 2026-11-11 | Audit log fields: role, document id, latency, token count. | agent, approved | open |
| R-18 | 2026-11-11 | README with architecture diagram + "why this design" section. | agent, approved | open |
| R-19 | 2026-11-11 | Demo-video script and LinkedIn post are **out of scope for now**. | owner | deferred |
| R-20 | 2026-11-11 | Give all suggestions up front; do not repeatedly suggest during the build. | owner | working rule |
| R-21 | 2026-11-11 | No deadline, but do not drag the work out. | owner | working rule |
| R-22 | 2026-11-11 | Owner works irregular hours per day; model not specified. | owner | info |
| R-23 | 2026-11-11 | Secrets only via `gh secret set NAME` / GitHub Settings; never pasted into chat. | agent | working rule |
| R-24 | 2026-11-11 | Supabase project to be created by the agent via Supabase CLI if possible, else give detailed steps. | owner | done — project `enterprise-knowledge-copilot`, ref `ctfatevadhojxycuplsh`, ap-south-1, ACTIVE_HEALTHY |
| R-25 | 2026-11-11 | Vercel account is not linked to GitHub yet; CLI is logged in as `ibrahimsumon47`. | owner | open — not blocking; project created at deploy time |
| R-26 | 2026-11-11 | Hugging Face: no account and no write token yet. | owner | done — account `NoobMaster005`; local token is OAuth type, expires 2026-11-26 |
| R-27 | 2026-11-11 | `SUPABASE_DB_URL` repo secret added (7/7 secrets now set). | agent check | done — added 11:22 UTC; value pending live connection test |
| R-28 | 2026-11-11 | GitHub repo is public but completely empty (no commits, no branches); local folder is not a git repo. | agent check | open — first commit after START |
| R-29 | 2026-11-11 | `HF_TOKEN` must be a Write token; the local OAuth CLI token expires 2026-11-26. | agent check | done — owner's `ekc-space` is a WRITE token with no expiry; local OAuth token is only the CLI login |
| R-30 | 2026-11-11 | `SUPABASE_URL` re-set 11:23 UTC; Vercel still unlinked and no Vercel project for this repo. | agent check | open — non-blocking, project created at deploy time |
| R-31 | 2026-11-11 | Deploy skeleton pushed: Next.js 16.4.6 + React 19.3.1, `pnpm build` passes locally, commit `feb624c` on `main`. | agent | done |
| R-32 | 2026-11-11 | `SUPABASE_DB_URL` must use the **Session pooler** host; direct `db.<ref>.supabase.co` is IPv6-only and unreachable here (DNS `gaierror`), pooler `aws-0/aws-1-ap-south-1.pooler.supabase.com:5432` is reachable over IPv4. | agent check | working rule for the FastAPI service |
| R-33 | 2026-11-11 | Vercel project `enterprise-knowledge-copilot` created, linked, GitHub-connected; production alias `https://enterprise-knowledge-copilot-wine.vercel.app` returns 200; a push to `main` produced an automatic Production deployment. | agent | done |
| R-34 | 2026-11-11 | Supabase live key test: legacy `anon`/`service_role` + new `default/publishable`/`default/secret` exist; `service_role` REST `/rest/v1/` → 200, `/auth/v1/health` → 200, `anon` auth health → 200. | agent check | done |

## Timeline

- **2026-11-11** — Interview held. Environment checked (read-only). Requirements R-01…R-26 logged. No code, no installs, no git init.
- **2026-11-11** — Setup verified read-only: repo empty but public, 6/7 secrets present (`SUPABASE_DB_URL` missing), Supabase project healthy (`ctfatevadhojxycuplsh`), HF logged in as `NoobMaster005` (OAuth token expiring 2026-11-26), Vercel not linked to GitHub. Requirements R-27…R-29 logged.
- **2026-11-11** — Re-check after owner setup: 7/7 secrets present, Supabase `ACTIVE_HEALTHY`, HF has no Spaces yet and `ekc-space` is a WRITE token without expiry, repo still empty (no commits). Requirements R-30 logged. Build not started.
- **2026-11-11** — Connection checks passed: Supabase REST live (401 without key), session pooler reachable over IPv4, Groq/Gemini endpoints reachable, HF logged in, 7/7 secrets. Minimal Next.js 16.4.6 scaffold built (`pnpm build` ✓), committed and pushed to `main` (commit `feb624c`). Requirements R-31, R-32 logged. Feature build not started.
- **2026-11-11** — Vercel set up end to end: project created with a lowercase name (the folder name broke project creation), linked, `vercel.json` pinned the Next.js framework (the CLI-created project defaulted to a static `public` preset and failed the first build), production deploy ready, GitHub repo connected so pushes to `main` auto-deploy. Supabase keys proven working against the live project. Requirements R-33, R-34 logged.
