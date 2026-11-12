# Security report

Date: 2026-11-11. Scope: this repository and the two deployed origins.

## Verified in this build

| Control | Evidence |
| --- | --- |
| Authorisation inside SQL | `search_chunks` takes `role` and `department` and applies `can_read` in the query; a post-filter would be a bug. `supabase/migrations/20261111000100_init.sql`. |
| Row Level Security | Policies on `documents`, `chunks`, `profiles`, `audit_log`, `eval_runs`; verified by querying as a role account through PostgREST. |
| Identity from token | The API verifies the Supabase JWT against the project JWKS, then loads the role from `profiles`; `require_admin` rejects employees. |
| Audit chain | Each row stores the previous hash; `/audit/verify` pages the **whole log** from the genesis row (1000-row pages, 50 000-row ceiling reported as `complete: false`) and reports the first break. `.github/workflows/audit-integrity.yml` runs `scripts/check_audit_chain.py` every six hours and fails the run when the deployed chain does not verify, when the endpoint is unreachable, or when the response is malformed. |
| Secret separation | Only the anon key is in the browser bundle; the service-role key exists on the API host only. `.env.example` lists names, no values. |
| Secret scanning | CI installs the pinned gitleaks CLI and scans full history; the job is green. |
| Dependency audit | `pnpm audit --audit-level high`: one moderate advisory, below the gate. `pip-audit` against `api/requirements.txt`: see the finding below. Both run in `.github/workflows/security.yml` and attach their reports as the `dependency-audit` artifact. |
| Container scan | Trivy 0.57.1 scans the built image and the repository in `.github/workflows/security.yml`; SARIF goes to code scanning. |
| SBOM | CycloneDX `sbom.cdx.json` is produced from the built image and kept as the `sbom-cyclonedx` artifact. |
| Supply-chain posture | OpenSSF Scorecard runs weekly and on `main` (`.github/workflows/security.yml`, job `scorecard`) and publishes SARIF. |
| Action pinning | Every `uses:` in `.github/workflows/` is a commit SHA, including the third-party actions (`aquasecurity`, `ossf`, `pnpm`). |
| Least privilege | Workflows default to `contents: read`; only the SARIF upload steps get `security-events: write`, and Scorecard adds `id-token: write` for its results. |
| Commit hygiene | CI fails on attribution trailers; the four commits that predated the rule were rewritten and force-pushed once. |
| Transport | HTTPS everywhere; CORS restricted to the Vercel origin plus localhost. |
| Injection resistance | Answers are plain text, no HTML rendering, no tool execution from model output. |

## Findings from the 2026-11-12 security run

1. **Fixed — vulnerable direct pins.** `pip-audit` reported 63 advisories across 7
   packages. The direct pins were updated (`PyJWT` 2.10.1 → 2.15.1,
   `python-multipart` 0.0.20 → 0.0.33, `fastapi` 0.115.6 → 0.116.1, which also
   moves `starlette` off 0.41.3). The remaining advisories are all in the
   `langgraph` 0.2 family; fixing them means a 1.x migration of the graph code,
   which is not a dependency-only change and is recorded as accepted risk below.
2. **Fixed — the audit chain could never verify.** Three faults stacked up:
   (a) verification only read the newest 500 rows and treated the first row of
   that window as a chain break, so anything older was invisible;
   (b) `asyncpg` returns `jsonb` as text, so the verifier hashed a string where the
   writer hashed a dict; (c) the insert never stored `created_at`, so the column
   defaulted to `now()` with microseconds while the hash covered the app's
   second-precision timestamp. The verifier was right to fail; the rows were never
   edited. Fixed in `api/app/audit.py` (window anchor, jsonb decode) and
   `api/app/db.py` (persist `created_at`), with unit tests for each. Existing rows
   were re-hashed in id order by `scripts/repair_audit_chain.py`, which backs up
   the old hashes first and rewrites only `prev_hash`/`entry_hash`. Verification
   now walks the whole log (`db.audit_rows`), so the window anchor is gone and a
   deleted prefix is reported as `anchored_at_genesis: false`.
3. **Recorded — base image CVEs.** Trivy reports HIGH/CRITICAL advisories in
   `python:3.12-slim` OS packages. They are uploaded as SARIF and printed in the
   job log, and the gate is advisory because only a newer base image can fix
   them; the repository's own dependency gates are pip-audit and pnpm audit.
4. **Recorded — no OSV-Scanner or Dependabot.** Not added; the two audits above
   are the dependency gates.

## Accepted risk

- **`langgraph` 0.2.x advisories.** The graph runs in-process with a compiled
  `StateGraph` and no checkpoint loading from untrusted input, which is the
  surface those advisories describe. Upgrading to 1.x is scheduled, not silently
  skipped: the pin in `api/requirements.txt` carries this note.
- **Shared demo password.** Stored as a GitHub secret and used only for review.

## Earlier open findings

1. **Availability, not confidentiality.** The free API instance sleeps after 15
   idle minutes and a cold start can take about a minute. Measured under load:
   386–402 MB RSS with both ONNX models and five concurrent retrieval requests,
   below the 512 MB limit.
2. **Demo accounts share a password.** Stored as a GitHub secret and used only
   for review. Rotate with `gh workflow run seed-users.yml` before any real use.
3. **No third-party penetration test.**

## Reproduction

```bash
node scripts/check-done.mjs --phase P0
node scripts/check-done.mjs --phase P1
gh run list --workflow=ci.yml --limit 1
curl -s https://enterprise-knowledge-copilot-2u57.onrender.com/health
```

## Shared accounts

The seven seeded accounts exist for reviewers and are shared, so three controls
bound them:

- `DELETE /documents/{id}` is refused with 403 and audited as
  `document.delete_denied`; test: `test_shared_admin_cannot_delete_documents`.
- Document access-level changes are audited and reverted nightly by
  `.github/workflows/reset-admin-edits.yml` against `data/access_baseline.json`.
- Changing an access level requires `require_admin`; test:
  `test_document_update_is_admin_only`.
