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

Test split, `--cache-tag product-v2`: hit@k 0.036, citation precision 0.029,
refusal accuracy 0.412, p50/p95 3 435/4 793 ms, leakage 0. The targets (at most 3
wrong refusals of 21; 90% of unanswerable refused) were missed. The measured cause
is the score floor refusing before a model call, plus single-citation answers.
The floor is now 0.0; that re-run scored 0.441 refusal accuracy and 0.071 hit@k, so the floor was not the whole cause. `docs/reports/answer_diagnosis.md` records that hit@k now measures answer citations rather than retrieval ranks.

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
2. Multi-tenant workspaces (organisation, members, invites) are not built; the
   access model is the seven-role shared workspace. This is the largest gap
   against the reframe brief and is recorded, not hidden.
3. Document upload from the browser (PDF/DOCX/HTML) is still the CLI ingestion
   workflow; `/library` lists and searches what is indexed.
4. Google OAuth and password reset are not wired.
