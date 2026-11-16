# Deploying the two halves

The web app runs on Vercel, the FastAPI service runs on Render's free Docker
plan, and everything stateful lives in Supabase. No step here needs a paid plan.

## Which value goes where

GitHub secrets are write-only: GitHub never shows a stored value again. That is
why they cannot be copied out of the repository settings. The real values live
in the dashboard that issued them, and each one has exactly one home:

| Variable | Where it is set | Where to copy it from | Looks like |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel (Production + Preview) | Supabase → Project Settings → API → Project URL | `https://<ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel (Production + Preview) | Supabase → Project Settings → API → **anon / publishable** key | `eyJhbG…` or `sb_pub…` |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel (Production + Preview) | The Render service URL, once it exists | `https://ekc-api-xxxx.onrender.com` |
| `SUPABASE_URL` | Render | same Project URL as above | `https://<ref>.supabase.co` |
| `SUPABASE_DB_URL` | Render | Supabase → Connect → **Session pooler** URI | `postgresql://postgres.<ref>:…@aws-0-….pooler.supabase.com:5432/postgres` |
| `SUPABASE_SERVICE_ROLE_KEY` | Render **only** | Supabase → API → **service_role** / secret key | `eyJhbG…` or `sb_sec…` |
| `GROQ_API_KEY` | Render | console.groq.com → API Keys | `gsk_…` |
| `GEMINI_API_KEY` | Render | aistudio.google.com → API key | `AIza…` |

Two rules that matter more than the table:

1. `SUPABASE_SERVICE_ROLE_KEY` must never be set on Vercel. It bypasses row-level
   security, so it only ever belongs to the server-side API.
2. `NEXT_PUBLIC_*` values are compiled into the browser bundle. They are allowed
   to be public; anything without that prefix is not.

## Render

1. Push to `main` (the blueprint below is already committed).
2. Render → **New → Blueprint** → pick this repository. Render reads
   `render.yaml` and creates the `ekc-api` web service.
3. When it asks for the `sync: false` variables, paste the five values from the
   table above.
4. Wait for the first build, then check `https://<service>.onrender.com/health`
   returns `{"status":"ok"}`.
5. Put that origin into `NEXT_PUBLIC_API_BASE_URL` on Vercel and redeploy.

### What the free plan actually does

- The instance sleeps after **15 minutes without traffic** and wakes on the next
  request in about **a minute**. Nothing is deleted and the URL never expires;
  the first question after a quiet period is simply slow.
- Each workspace gets **750 instance hours per month**. A service that is asleep
  consumes none, so normal use stays far below the limit. Keeping it awake 24/7
  burns about 720 of them, which still fits, but a short nap is cheaper.
- Free services can be restarted by Render at any time and cannot use persistent
  disks. That is fine here: all state is in Supabase.
- Do **not** create a Render Postgres: free Render databases expire after 30
  days. Supabase is the database.
- 512 MB of RAM is the real constraint. The API therefore uses ONNX
  (`fastembed`, `flashrank`) instead of torch; the torch build needed more than
  a gigabyte just to import.

## Vercel

Environment variables → add the three `NEXT_PUBLIC_*` names for Production and
Preview, then redeploy. `vercel.json` pins the framework, and `.vercelignore`
keeps `api/`, `data/`, `eval/`, `docs/`, `supabase/` and the corpus clone out of
the build.

## Identity providers and storage

The application code is present; these console settings enable the flows.

### Password reset

1. Supabase → Authentication → URL Configuration: add
   `https://enterprise-knowledge-copilot-wine.vercel.app/reset-password` to the
   redirect allow list (and `http://localhost:3000/reset-password` for local).
2. Authentication → Email Templates → Reset password: confirm the template uses
   `{{ .ConfirmationURL }}`.
3. Supabase's built-in sender is rate-limited. For more than a few resets per
   hour, connect a free SMTP sender under Authentication → SMTP.

### Demo account passwords

`@ekc.local` addresses cannot receive recovery email. Set
`EKC_DEMO_PASSWORD` in GitHub → Settings → Secrets and variables → Actions, then
run **Actions → Reset demo passwords**. The workflow uses the Supabase Admin API
to write that password to the six login demo users and never prints the value.
Changing the secret without running the workflow does not reset an existing
account.

The sample workspace uses the separate `EKC_GUEST_PASSWORD` secret and the same
name in Vercel Production. Keep the two values equal, then run the same workflow;
it updates `guest@ekc.local` from that secret instead of the demo password. This
keeps the one-click sample working after a demo reset.

### Google sign-in

1. Google Cloud Console → APIs & Services → OAuth consent screen: external,
   testing or published, scopes `email` and `profile`.
2. Credentials → Create credentials → OAuth client ID → Web application.
3. Authorised JavaScript origin:
   `https://enterprise-knowledge-copilot-wine.vercel.app`.
4. Authorised redirect URI:
   `https://ctfatevadhojxycuplsh.supabase.co/auth/v1/callback`.
5. Supabase → Authentication → Providers → Google: enable and paste the client
   ID and secret.
6. Supabase → Authentication → URL Configuration: keep the site URL and add
   `/chat` to the redirect allow list.

Google users arrive without a workspace. Send them an invite link; the invite
page sends them to registration with the token. A workspace is created for a
normal sign-up, never for an invited account.

### Storage

`supabase/migrations/20261114180000_uploads.sql` creates the private `documents`
bucket. If the project has no Storage schema, create a private bucket named
`documents` before applying migrations.
