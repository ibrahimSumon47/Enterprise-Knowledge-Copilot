# PROJECT STATE

**Last updated:** 2026-11-14 (answer-quality evaluation)

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

Final full runs with `--cache-tag quality-v6`, five seconds between questions:
43575136979 (dev) and 43576319480 (test). Reports: `docs/reports/eval_dev.json`
and `docs/reports/eval_test.json`.

| Metric | Dev (50) | Test (34) |
| --- | --- | --- |
| retrieval hit@5 | 0.885 | 1.0 |
| retrieval recall@50 | 1.0 | 1.0 |
| retrieval MRR | 0.845 | 0.907 |
| citation hit@k | 0.375 | 0.429 |
| citation precision | 0.240 | 0.265 |
| refusal accuracy | 0.560 | 0.588 |
| wrong refusals | 21 of 32 | 13 of 21 |
| unanswerable refused | 17 of 18 | 12 of 13 |
| p50 / p95 latency | 4185 / 6502 ms | 4331 / 5672 ms |
| permission leakage | 0 | 0 |

Provider errors were 0 in both final runs. Initial runs with `quality-v5` had 16
and 12 wrong refusals. The attempted fix gave the grounded call 2600 tokens and
low reasoning effort; it made both splits worse, so it is recorded as a failed
experiment, not a success. Retrieval is unchanged and the remaining refusals are
model-side after retrieval. The next step is to retain the refusal reason and raw
reply for each wrong refusal before changing the prompt again.

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
3. Browser upload is built with type/magic checks, size and rate caps, private
   Storage originals, progress, re-index and delete; the remaining gap is
   group-scoped documents, which arrives with invites in 2c.
4. Google OAuth and password reset are not wired.
