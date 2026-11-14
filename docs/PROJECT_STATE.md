# PROJECT STATE

**Last updated:** 2026-11-13 (product reframe)

## Where it runs

| Thing | Where | State |
| --- | --- | --- |
| Web | https://enterprise-knowledge-copilot-wine.vercel.app | live, Vercel, auto-deploy on `main` |
| API | https://enterprise-knowledge-copilot-2u57.onrender.com | live, Render free Docker, 512 MB |
| Data | Supabase `ctfatevadhojxycuplsh` | Postgres 17, pgvector, RLS, 754 documents |
| Corpus | `data/corpus.jsonl` | GitLab Handbook (CC BY-SA 4.0) + 12 labelled synthetic documents |

## Product surface (2026-11-13)

- Public: `/`, `/product`, `/security`, `/privacy`, `/terms`, `/contact`, `/licenses`.
  No evaluation numbers, repository links or project language.
- App: `/chat`, `/library`, `/admin`, `/admin/quality`. Quality is admin-only and
  labelled Answer quality / Performance.
- Sample workspace: `POST /api/sample-workspace` reads `EKC_GUEST_PASSWORD` on the
  server, signs in `guest@ekc.local`, and redirects to `/chat`; read-only.
- Unanswered questions: refusals are queued and the admin Operations page lists
  them with a resolve action.

## Verification

| What | Evidence |
| --- | --- |
| Sign-in on production, all seven roles | `.github/workflows/e2e-auth.yml` green on `48f4c22`; 9 Playwright tests, form sign-in, session reload, admin gate, sign out |
| Sign-in bug cause | pre-hydration native GET submit put the password in the URL; inputs are uncontrolled and the submit is inert until hydration |
| Cross-tenant / cross-role leakage | 0 in the evaluation and in `api/tests/test_retrieval_access.py` |
| Activity log | checkpoint verification every six hours, weekly full pass, 24 h stale escalation, issue on failure |
| API build identity | `/health.commit` (Render's `RENDER_GIT_COMMIT`) |

## Answer quality

Test split, `--cache-tag product-v5`: retrieval hit@5 1.0,
recall@50 1.0, MRR 0.907; citation
precision 0.294; wrong refusals 13 of
21; unanswerable refused 13 of
13; p50/p95 4278/7353 ms;
leakage 0. All wrong refusals are Gemini replies that judge present evidence
insufficient; Groq answers pass. Retrieval is perfect on the split, so the next
change is provider routing and answerability prompting, not search.

## Known limits

- The 512 MB free instance cannot hold a larger cross-encoder.
- The free instance sleeps; keep-warm runs every ten minutes.
- Free LLM quotas throttle and provider outages surface as honest refusals.
- The answer cache in `eval/run_eval.py` is keyed by `--cache-tag`; forgetting to
  change it re-scores old answers.
- Local `pytest` cannot run on this machine (Python 3.14 has no asyncpg wheel for
  0.30.0); API tests run in CI.

## Next steps

1. Re-measure the test split with the 0.0 floor and publish whether the refusal
   target is met.
2. Multi-tenant workspaces are built: owner > admin > member, signup creates an
   empty workspace, onboarding adds the first document, and the real two-workspace
   red-team suite reports zero leakage (`docs/ISOLATION.md`). Invites, deactivation,
   analytics and workspace settings remain.
3. Document upload from the browser (PDF/DOCX/HTML) is still the CLI ingestion
   workflow; onboarding accepts pasted text.
4. Google OAuth and password reset are not wired.
