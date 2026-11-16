# PROJECT STATE

**Last updated:** 2026-11-14 (working guide and Scorecard registry fix)

How to set up, verify, change and operate the project — including the detailed
strengths, limitations and non-limitations — is in `docs/WORKING_ON_THIS.md`.

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

- Answer generation is the weak point: 21/32 dev and 13/21 test answerable
  questions are wrong refusals, while retrieval hit@5 is 0.885/1.0.
- Citation precision is 0.240 dev and 0.265 test.
- The 512 MB free instance cannot hold a larger cross-encoder; the free instance
  sleeps, so a cold start can take about a minute.
- Free LLM quotas throttle, retire model ids and can return empty or truncated
  content; provider outages are explicit, not counted as document refusals.
- The answer cache in `eval/run_eval.py` is keyed by `--cache-tag`; forgetting to
  change it re-scores old answers.
- Uploads are parsed and embedded synchronously and accept only Markdown, text,
  HTML, PDF and DOCX; there is no connector sync, OCR or background queue.
- Password reset and Google sign-in need the console steps in `docs/DEPLOY.md`
  before those flows work on a fresh deployment.
- The golden set is 84 questions (50 dev, 34 test), so small score differences are
  noisy; both splits have been inspected during diagnosis.

The full impact, mitigation and removal condition for each limit is in
`docs/WORKING_ON_THIS.md`.

## Next steps

1. Retain the refusal reason and raw reply for every wrong refusal, then fix the
   largest cause and re-measure dev once before touching test.
2. Improve citation precision without weakening quote verification, the relevance
   guard or the unanswerable-refusal rate.
3. Enable password reset and Google sign-in in Supabase/Google using the
   identity section of `docs/DEPLOY.md`; the code paths already exist.
4. Keep the SQL permission predicate and the two-workspace isolation gate at zero
   leakage on every schema or retrieval change.
