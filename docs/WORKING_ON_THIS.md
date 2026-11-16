# Working on Enterprise Knowledge Copilot

This is the practical guide for changing the project without breaking the things
that make it trustworthy. It covers the local loop, the request path, the rules
that are not negotiable, the measured strengths, and the limits in enough detail
that nobody has to rediscover them from a failing run.

Read this with:

1. `AGENTS.md` — the contract and access model.
2. `docs/PROJECT_STATE.md` — what is done, what is measured, what is next.
3. `docs/HANDOFF.md` — how to resume from zero context.
4. `docs/DEPLOY.md` — every environment variable and where it belongs.

## 1. The mental model

The product has two separate surfaces:

- **Public site**: `/`, `/product`, `/security`, `/privacy`, `/terms`, `/contact`,
  `/licenses`. Customer-facing copy only. Evaluation numbers, repository links
  and engineering caveats belong in this repository, not there.
- **Application**: `/chat`, `/library`, `/admin`, `/admin/quality`, `/settings`
  and the invite/onboarding routes. This is where authentication, retrieval and
  administration live.

The web app never talks to Postgres directly. It sends the Supabase access token
to the FastAPI service, which verifies the JWT, derives the caller's organisation
and role from `org_members`, and runs retrieval with those values inside SQL. The
browser cannot choose its tenant or role.

## 2. Local setup

### Prerequisites

| Tool | Version used here | Why |
| --- | --- | --- |
| Node.js | 24 | Next.js 16 and the Playwright toolchain |
| pnpm | 12.15.0 | lockfile and workspace commands |
| Python | 3.12 | the API image and the local `.venv` |
| Git + GitHub CLI | current | pushes, workflow dispatch, run inspection |

Python 3.14 is installed on the owner machine, but the pinned API dependencies do
not all have wheels for it. Use the existing `.venv`, or recreate it with a 3.12
interpreter. Do not upgrade the API to 3.14 just to avoid the virtualenv.

### Install

```bash
pnpm install
python -m venv .venv
# Windows Git Bash:
.venv/Scripts/python.exe -m pip install -r api/requirements-dev.txt
# Linux/macOS:
# .venv/bin/python -m pip install -r api/requirements-dev.txt
```

`api/requirements-dev.txt` includes the runtime requirements plus `pytest`, `ruff`
and coverage. The Docker image installs only `api/requirements.txt`.

### Environment

Copy `.env.example` to `.env.local` for the web app and set the names documented
in `docs/DEPLOY.md`. Never commit values. The minimum local web variables are:

```text
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

For a local API process, set the server-side variables in its environment:
`SUPABASE_URL`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`,
`GEMINI_API_KEY`. The service-role key must never be placed in a `NEXT_PUBLIC_*`
variable or in the web deployment.

### Run

```bash
pnpm dev
# second terminal, from the repository root:
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --app-dir api --port 8000
```

The first API start downloads the ONNX embedding and reranker models into the
local cache. That is a one-time wait. If the models cannot load, `/health` reports
the reranker state instead of silently falling back to a different ranking path.

### The fast local loop

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
.venv/Scripts/python.exe -m ruff check api/app api/tests
PYTHONPATH=api .venv/Scripts/python.exe -m pytest api/tests -q
node scripts/check-done.mjs
```

Run the checks that cover the code you touched. A UI-only change needs lint,
typecheck and build. An API or retrieval change also needs Ruff and the API tests.
A migration change needs the DB migrate workflow and the isolation workflow.

## 3. Repository map

| Path | What lives there |
| --- | --- |
| `app/` | Next.js App Router pages, client components and route handlers |
| `components/` | shared UI components |
| `lib/` | Supabase clients, API helpers, formatting and client-side logic |
| `api/app/` | FastAPI app, auth, retrieval, pipeline, uploads, storage, DB access |
| `api/tests/` | API unit and integration tests; no network or live database required |
| `supabase/migrations/` | forward-only schema, RLS, functions and grants |
| `supabase/tests/` | SQL checks run by the DB migrate workflow |
| `scripts/` | operational and verification scripts, including `check-done` |
| `eval/` | golden questions, splits and the live evaluation harness |
| `e2e/` | Playwright tests against the deployed product |
| `docs/` | state, handoff, runbooks, threat model, reports and this guide |

## 4. The request path

1. The browser signs in through Supabase and sends `Authorization: Bearer <jwt>`.
2. FastAPI verifies the JWT against Supabase JWKS and loads the active
   `org_members` row. Missing or deactivated membership returns 403.
3. The question is routed (short/unclear, compensation, security, policy,
   handbook) and, for Bengali, translated to English for retrieval.
4. Hybrid retrieval runs pgvector plus full-text inside SQL, with the organisation,
   role, department and group predicate applied in the query. RRF fuses the lists;
   the TinyBERT cross-encoder reranks the candidate pool.
5. The grounded call receives numbered passages and must return JSON with an
   answer and verbatim evidence quotes.
6. Every quote is checked against its cited retrieved passage. The relevance guard
   requires shared question terms. Only verified quotes become citations.
7. A failed verification becomes an honest refusal with the closest sources. A
   provider outage becomes `temporarily_unavailable`, not a fake refusal.
8. The question, answer, citations, provider, reason and latency are audited. A
   refusal is also queued for an administrator.

## 5. Access rules you must preserve

| Principal | May read |
| --- | --- |
| `guest` | public documents |
| `employee` | public + employee |
| `engineering`, `security`, `hr`, `finance` | public + employee + their department |
| `admin` | everything their group scope allows in the organisation, including synthetic confidential documents |
| owner | every document in the workspace, including every group, plus workspace deletion and owner/admin management |

Tenant and permission predicates belong **inside the SQL that selects chunks**,
not in Python after retrieval. `supabase/tests/cross_tenant.sql` and the
Cross-tenant isolation workflow are the gate. A post-filter is a bug even if the
visible result happens to look right.

Groups add a second dimension: a document with a `group_id` is visible only to
members of that group and to owners, who bypass the group predicate. Admins and
members do not bypass it. Invites carry a role and optional group. Invite tokens are returned once, stored
as SHA-256 hashes, expire, can be revoked, and are single-use or limited-use.

## 6. Verification ladder

Use the smallest gate that actually covers the change, then stop.

| Change | Required evidence |
| --- | --- |
| Copy, styling, a single component | lint, typecheck, build; visual check if the user asked for one |
| Client logic | lint, typecheck, unit tests, build |
| API route or schema | Ruff, API tests, typecheck/build if shared types changed |
| Retrieval, prompts, citations | API tests plus a fresh evaluation run with a new cache tag |
| Migration or RLS | DB migrate workflow and Cross-tenant isolation workflow |
| Auth, onboarding, upload | Sign-in e2e or upload e2e against the deployed build |
| Security workflow | The Security run must be green; do not leave a known red check |

`node scripts/check-done.mjs` is the repository-level acceptance gate. It reads
`docs/PHASES.json` and verifies the artefacts each phase promises. A phase is not
done because the code exists; it is done when the named command or artefact can be
read and passes.

### Evaluation runs

The live harness is `eval/run_eval.py`. It needs the deployed API, Supabase URL,
anon key and the demo password. Because those credentials are repository secrets,
the reproducible path is the **Nightly eval** workflow:

```bash
gh workflow run nightly-eval.yml \
  -f split=dev -f subset=false -f cache_tag=<new-tag> \
  -f throttle=5 -f retry_outage=3
```

Then repeat with `split=test`. The harness:

- caches answers per split, question and cache tag; always use a new tag after a
  retrieval or prompt change, or you will re-score old answers;
- refuses to publish a run with more than 5% provider errors;
- records per-question provider, retrieval rank, refusal outcome and latency;
- writes `docs/reports/eval_dev.json` and `docs/reports/eval_test.json`, which the
  workflow uploads as the `nightly-eval` artifact.

Current numbers and their history are in `README.md` and
`docs/PROJECT_STATE.md`. Do not copy a number from an old report into a new claim.

### Browser tests

```bash
EKC_DEMO_PASSWORD=... pnpm exec playwright test
```

The upload spec needs a fresh signup and can take several minutes on the free
host; it waits for the document to reach `ready`, asks a question, then deletes
the document. The sign-in spec covers all seven roles, session reload, the admin
gate and sign-out.

## 7. Changing the project safely

### Adding a migration

Migrations are forward-only and are applied by `.github/workflows/db-migrate.yml`
on push to `main`. Add a new timestamped file; never edit an applied migration.
Include the RLS policy or `security definer` function in the same migration. Add a
SQL assertion under `supabase/tests/` when the change affects isolation, and run
the isolation workflow before claiming it works.

### Changing retrieval

Keep the permission predicate in SQL. If you add a retrieval function, grant it
to `authenticated` only, set a safe `search_path`, and prove a non-member gets zero
rows. Update the API tests and run a full dev evaluation. Retrieval changes are
not accepted on a single anecdotal question.

### Changing the answer prompt or provider routing

Use a new `--cache-tag`. Read the wrong-refusal table, not only the aggregate.
Distinguish four causes before changing anything:

1. quote verification failed;
2. empty evidence from the model;
3. provider error or truncation;
4. relevance guard rejected a verified quote.

Do not relax the citation verifier or the permission predicate to improve a
score. Fix the cause and re-run dev once; only then run test.

### Adding an upload type

Add the extension **and** magic-byte check in `api/app/uploads.py`, a bounded
parser, a size/rate test, and a clear failure state in the library UI. Original
files go to the private Storage bucket; downloads are always attachments. Do not
parse an unbounded archive or follow external links from a document.

### Adding a UI page

Use the existing design tokens in `app/globals.css`. Keep the public site free of
engineering evidence. Fetch only with `apiFetch`/the existing Supabase helpers so
the bearer token and error handling stay consistent. Add an empty, loading and
error state; a spinner with no recovery path is not a finished screen.

## 8. Deploying and operating

| Piece | Trigger | Check |
| --- | --- | --- |
| Web | push to `main` (Vercel) | open the deployed URL; Playwright sign-in |
| API | push to `main` touching `api/**`, `Dockerfile`, `render.yaml` or corpus | `/health.commit` matches the pushed SHA |
| Database | push to `main` touching `supabase/**` | DB migrate run is green |
| Isolation | push to `main` | Cross-tenant isolation run is green |
| Keep-warm | every ten minutes | `/health` responds |

If a deploy looks stale, read `/health.commit` before debugging the code. Render
builds are queued and the free instance may be asleep; a cold start is not a code
failure.

## 9. Strong points, in detail

### 9.1 Permissions are part of the query, not a UI convention

The organisation, role, department and group predicate is in the SQL function that
returns chunks, mirrored by RLS on the tables. A forgotten Python filter cannot
leak a document, and a crafted API request cannot ask for another tenant. The
two-workspace red-team suite has repeatedly reported zero violations across
uploads, invites, groups, deactivation and retrieval. This is the strongest
security property in the project.

### 9.2 Answers are grounded in verified quotes

The model does not get to invent a citation. It returns evidence quotes, and the
backend checks each quote against the exact retrieved passage, then checks that the
quote shares question terms. Unverified answers become refusals with the closest
real sources. The verifier has regression tests for whitespace, case, ellipses,
light paraphrase, fabricated quotes and unrelated quotes.

### 9.3 Refusal is honest, including provider failure

A missing document and a throttled model are different outcomes. The API reports
`unavailable`/`outage` for the latter; the admin detail includes the provider
trace and reason. The evaluation harness excludes no-model rows and refuses to
publish a run above 5% provider errors. This makes quality numbers interpretable
instead of rewarding a provider outage as a successful refusal.

### 9.4 The audit log is tamper-evident

Every important action is hash-chained. A scheduled check verifies the chain from
a checkpoint every six hours, and a weekly pass verifies from genesis. A break
opens an issue rather than silently resetting. Workspace deletion detaches audit
entries instead of deleting them, so the chain remains verifiable; that retention
trade-off is documented below.

### 9.5 Upload handling is defensive

Uploads are checked by extension and magic bytes, streamed with a hard size cap,
limited per user and per workspace, parsed with bounded libraries, stored privately,
and served as attachments. Original bytes never become a public URL. Failed
parsing, empty text, re-index and delete are explicit states in the library UI.

### 9.6 Provider routing degrades instead of locking in

Groq is primary and Gemini is a backup behind one interface. The router hedges a
slow primary, records which providers were tried, and exposes failures. Switching
providers or model ids does not require rewriting the pipeline, and the free-tier
constraint is visible in configuration rather than hidden in code.

### 9.7 The evaluation is reproducible

The harness is code, not a spreadsheet: deterministic splits, answer caching,
throttling, provider-error exclusion, per-question data and a hard leakage gate.
The reports in `docs/reports/` can be regenerated with the commands above. That is
why the project can publish an unflattering number and still be credible.

### 9.8 The free-tier choices are deliberate

ONNX `bge-small-en-v1.5` and TinyBERT keep the API inside 512 MB; the database and
auth are managed by Supabase; the web is static/server-rendered on Vercel; CI uses
GitHub-hosted runners and pinned actions. There is no credit card dependency and
no paid service hiding in the critical path.

### 9.9 The operational surface exists

Health reports build identity and reranker state. Keep-warm, DB migrate, isolation,
audit integrity, dependency audit, Trivy, CodeQL, secret scanning, sign-in e2e and
the evaluation are separate workflows with visible results. An operator can tell
whether the deployed build is the one in `main`.

## 10. Limitations, in detail

These are real constraints, not disclaimers. Each one names the impact and the
mitigation that exists today.

### 10.1 Answer refusal quality is the main product limit

**What:** the latest full runs have 21 wrong refusals out of 32 answerable dev
questions and 13 of 21 test questions. Retrieval hit@5 is 0.885 dev and 1.0 test,
so the gold passage is usually present; the failure is after retrieval.

**Impact:** a user can ask an answerable question and receive the honest refusal
screen. This is the largest gap between the demo and a dependable assistant.

**Mitigation:** refusal accuracy, wrong refusals, citation precision and the
per-question JSON are published. The failed 2600-token/low-reasoning experiment is
recorded rather than hidden. The next change must first retain the refusal reason
and raw reply for each wrong refusal; guessing at the prompt again is not accepted.

**What would remove it:** a provider/prompt path that returns usable evidence on
the gold passages without weakening quote verification or the unanswerable-refusal
rate, demonstrated on dev and then test.

### 10.2 Citation precision is low

**What:** citation precision is 0.240 dev and 0.265 test. An answer may cite a
passage that contains some query terms but is not the single best passage.

**Impact:** the reader may have to open more than one source, and the citation
hit@k metric understates retrieval quality.

**Mitigation:** retrieval rank is measured separately with `all_candidates=true`,
and the UI shows document, heading, passage and licence. Multiple citations are
allowed only when each quote verifies.

**What would remove it:** better answer-time passage selection or a stricter
relevance guard, measured against both citation precision and wrong refusals.

### 10.3 The golden set is small

**What:** 84 questions total, split into 50 dev and 34 test. A few questions move
the percentage by several points.

**Impact:** differences below roughly five points are not strong evidence of a
real improvement, and the test split has been read during diagnosis.

**Mitigation:** dev is the iteration split; test is run once after a dev decision.
Both splits and per-question rows are retained. The harness reports counts, not
just percentages.

**What would remove it:** a larger, independently labelled set with a held-out
portion that is never inspected during development.

### 10.4 Free model providers are variable

**What:** Groq and Gemini free tiers throttle, time out, retire model ids and
sometimes return truncated or empty content. The router gives each provider a
short leash and hedges, but it cannot manufacture capacity.

**Impact:** latency varies, an answer can be `temporarily_unavailable`, and a
provider change can alter quality without any repository change.

**Mitigation:** provider errors are counted; runs above 5% are invalid. Outages
are shown as unavailable, not as document refusals. The provider and trace are
recorded in the admin audit detail. Model ids are configuration.

**What would remove it:** a paid or self-hosted model with an SLA, which conflicts
with the free-only rule.

### 10.5 The free API host is small and sleeps

**What:** Render free gives 512 MB and sleeps after 15 idle minutes. The process
uses ONNX instead of torch to fit; a larger cross-encoder was measured at 402 MB
RSS and caused a restart. The first request after sleep can take about a minute.

**Impact:** cold-start latency, no persistent local disk, and a hard ceiling on
model size. A larger reranker is not a configuration flip.

**Mitigation:** keep-warm every ten minutes, a compact embedding model, bounded
candidate pool and rerank length, `/health` reporting RSS and reranker state, and
all state in Supabase.

**What would remove it:** a larger always-on host, which is outside the free-only
constraint.

### 10.6 Corpus and connectors are limited

**What:** the corpus is the public GitLab Handbook plus a small synthetic
confidential set. There is no Google Drive, Confluence, Slack, SharePoint or
email connector, no scheduled source sync, and no OCR for scanned PDFs.

**Impact:** this is a working reference implementation over a known corpus, not a
drop-in enterprise search product. Uploaded documents are the only way to add
private knowledge.

**Mitigation:** Markdown, text, HTML, PDF and DOCX upload with parsing, re-index
and delete; source and licence are shown with each citation; synthetic documents
are labelled and used for access-control tests.

**What would remove it:** connector workers, incremental sync, OCR and a document
lifecycle model, each with its own permission mapping.

### 10.7 Uploads are synchronous and bounded

**What:** parsing and embedding happen during the upload request. Large files and
many chunks take time, and the free instance may time out. The accepted formats
and size, per-user and per-workspace limits are deliberately narrow.

**Impact:** a very large document can fail or need a retry; images, spreadsheets,
archives and scanned PDFs are rejected rather than half-ingested.

**Mitigation:** streaming size cap, bounded parsers, clear failed state, re-index
action, private original storage, and a 10 MB per-file / 200 MB per-workspace /
10-per-hour cap. Failures are visible rather than silently dropped.

**What would remove it:** a background ingestion queue with progress and retries,
which adds infrastructure the free plan does not provide.

### 10.8 Answer latency has no SLA

**What:** p95 was 6.5 s dev and 5.7 s test in the latest runs, before cold starts.
A cold Render instance plus a provider retry can exceed ten seconds.

**Impact:** the product is usable but not suitable for strict real-time support
workflows.

**Mitigation:** retrieval and reranking are bounded, streaming exists for the chat
path, provider hedging limits a hung primary, and `/health` exposes warm state.

**What would remove it:** a warm paid instance or a smaller local model with
consistent capacity.

### 10.9 Identity setup has console-only steps

**What:** password reset needs Supabase redirect/template configuration and an
email sender for volume; Google sign-in needs a Google OAuth client and Supabase
provider configuration. The code paths exist, but the owner must enable them.

**Impact:** a fresh deployment cannot use those flows until the console steps in
`docs/OWNER_TODO.md` are completed.

**Mitigation:** the steps are written down, the app shows the normal Supabase
error instead of pretending success, and invite links work without an email
provider.

**What would remove it:** a fully automated identity deployment, which the free
consoles do not expose.

### 10.10 Audit retention survives workspace deletion

**What:** deleting a workspace detaches its audit rows (`org_id` becomes null)
rather than deleting them, so the hash chain stays verifiable.

**Impact:** audit content outlives the workspace for compliance and integrity
purposes. This is a deliberate retention choice, not an accidental orphan.

**Mitigation:** the API only exposes audit rows to authorised administrators, and
the behaviour is documented in the threat model and project state.

**What would remove it:** a documented retention and crypto-shredding policy,
which would be a product/compliance decision rather than a code tweak.

### 10.11 One region and no availability guarantee

**What:** Vercel, Render and Supabase free tiers are single-provider dependencies.
There is no multi-region failover, no backup restoration drill in CI, and no
uptime commitment.

**Impact:** a provider incident can take the demo down. It is a portfolio-grade
deployment, not a service with an SLA.

**Mitigation:** all state is in managed Postgres, deployment is reproducible from
`main`, `/health` identifies the build and the runbooks name the recovery steps.

**What would remove it:** paid redundancy and tested disaster recovery.

### 10.12 Browser and accessibility coverage is not exhaustive

**What:** Playwright covers sign-in, onboarding, upload, chat and the critical
admin gates. It is not a full cross-browser or WCAG audit.

**Impact:** a visual or keyboard issue can survive CI.

**Mitigation:** semantic HTML, visible focus styles, labels on form controls and a
responsive layout are used; screenshots are kept in `docs/screenshots/`.

**What would remove it:** automated accessibility checks and a real browser matrix
as required gates.

## 11. Non-limitations: things that are deliberately handled

These are often assumed to be weaknesses in a free project. They are not.

### 11.1 It is not a mock

The deployment uses real Supabase Auth, Postgres, pgvector and RLS, real private
Storage, real model providers and real browser tests. The synthetic documents are
labelled test fixtures, but the access-control behaviour they exercise is the same
code path as uploaded documents.

### 11.2 Permissions are not client-side

Hiding a button is not access control. The role and tenant are derived from the
verified token and membership row, and the predicate runs in SQL. A crafted
request gets zero rows, not a filtered response.

### 11.3 Tenant isolation is not just a claim in the README

The isolation workflow creates two real workspaces and attacks uploads, invites,
groups and retrieval. It fails on any leak. The SQL test independently checks the
database boundary. The evaluation's permission-leakage gate is always zero.

### 11.4 Citations are not decorative

An answer without verified quotes is refused. A true quote from an unrelated
passage is rejected by the relevance guard. The citation shown in the UI contains
the passage and its provenance, not just a document title.

### 11.5 A provider outage is not called a refusal

The API distinguishes an unavailable model from missing evidence and says so.
The evaluation excludes those rows and marks a run invalid above 5% provider
errors. This is better than a clean-looking score built on outages.

### 11.6 Free does not mean fake data or paid hidden services

The corpus is the public GitLab Handbook under CC BY-SA 4.0, attributed in the app
and on `/licenses`. The confidential set is explicitly synthetic and labelled.
The stack uses free tiers and open models; there is no trial, watermark or paid
API in the critical path.

### 11.7 The audit trail is not a plain log table

Entries are hash-chained, checkpointed and verified on a schedule; tampering is
detected and escalated. That is stronger than an append-only table with no
integrity check.

### 11.8 The system is not locked to one model vendor

The provider interface, router and configuration allow Groq or Gemini to be
replaced or reordered. Retrieval and verification do not depend on a provider SDK.
A model id change is configuration plus a new evaluation run, not a rewrite.

### 11.9 The evaluation is not a demo script

It runs the deployed API, throttles live calls, caches by configuration, records
per-question outcomes and enforces a leakage gate. The reports include the
unflattering numbers. That is what makes a positive number meaningful.

### 11.10 The free-tier limits are measured, not guessed

The 512 MB reranker limit came from an observed RSS/restart, the sleep behaviour
from Render's documented free plan, the provider timeout from latency runs, and
the corpus size from the ingested documents. The limits section links to the
evidence instead of hand-waving.

## 12. Common tasks

| I want to... | Do this |
| --- | --- |
| Add a page | add it under `app/`, use `apiFetch`/Supabase helpers, add loading/empty/error states, run lint/typecheck/build |
| Add an API route | add schema + route + `db` function, derive org/role server-side, add tests, run Ruff/pytest |
| Change a prompt | new `--cache-tag`, full dev run, inspect wrong refusals, then one test run |
| Add a role or group rule | migration with RLS/function, SQL isolation test, API test, isolation workflow |
| Add an upload format | magic-byte check, bounded parser, caps, tests, library failure state |
| Debug a stale deployment | read `/health.commit`, then the Render build log |
| Debug an auth failure | check `org_members.active`, JWKS, `ALLOWED_ORIGINS`, then the audit detail |
| Rotate a secret | update the owning dashboard, redeploy, never paste it into an issue or chat |

## 13. Definition of done for a change

A change is finished when all of these are true:

1. The smallest relevant local checks pass, and the failure output was read.
2. The deployed build identifies the pushed commit, if deployment is in scope.
3. The relevant CI workflow is green, including isolation for permission changes.
4. `docs/PROJECT_STATE.md` and `docs/features.json` reflect the new state.
5. The evidence is a file, a run id, a URL or a screenshot that another person can
   open — not a sentence saying it works.

If a check cannot run, say which one and why. A known red check is a bug, not a
documentation problem.
