# Security policy

## Reporting a vulnerability

Open a private advisory at
<https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot/security/advisories/new>.
Please do not open a public issue for a suspected vulnerability.

Include what you did, what happened, and the impact you believe it has. A
reproduction (request, role, question) is worth more than a scanner screenshot.

## Scope

- The web app: https://enterprise-knowledge-copilot-wine.vercel.app
- The API service in `api/` (self-hosted in this deployment)
- The database schema and RLS policies in `supabase/migrations`

## Out of scope

- Denial of service through volume
- Findings that need a compromised owner account
- Synthetic documents: their contents are invented for this portfolio project

## What this project already does

- Access decisions are made inside the SQL that retrieves chunks, and mirrored
  by Row Level Security policies.
- The service-role key never reaches the browser or the repository.
- Documents are treated as untrusted data; instructions inside them are ignored
  and every citation is verified before an answer is returned.
- The audit log is hash-chained so tampering is detectable.
- Secrets are provided by environment variables only; `.env.example` lists names.

## Response

Best effort, within seven days for a first reply. This is a portfolio project,
not a commercial service.
