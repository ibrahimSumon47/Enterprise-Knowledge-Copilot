# Owner console steps

These are the only actions that need the Supabase or Google console; the app code
is already in place.

## Password reset

1. Supabase → Authentication → URL Configuration: add
   `https://enterprise-knowledge-copilot-wine.vercel.app/reset-password` to the
   redirect allow list (and `http://localhost:3000/reset-password` for local).
2. Authentication → Email Templates → Reset password: confirm the template uses
   `{{ .ConfirmationURL }}`.
3. Supabase's built-in email sender is rate-limited; for more than a few resets
   per hour, connect a free SMTP sender (for example Resend's free tier) under
   Authentication → SMTP.

## Google sign-in

1. Google Cloud Console → APIs & Services → OAuth consent screen: external,
   publishing status testing or published, scopes `email` and `profile`.
2. Credentials → Create credentials → OAuth client ID → Web application.
3. Authorised JavaScript origin: `https://enterprise-knowledge-copilot-wine.vercel.app`.
4. Authorised redirect URI:
   `https://ctfatevadhojxycuplsh.supabase.co/auth/v1/callback`.
5. Supabase → Authentication → Providers → Google: enable, paste the client ID
   and client secret, save.
6. Supabase → Authentication → URL Configuration: keep the site URL and add
   `/chat` to the redirect allow list.

Google users arrive without a workspace. Send them an invite link; the invite
page sends them to registration with the token, and the workspace is created only
for a normal sign-up, never for an invited account.

## Storage

`supabase/migrations/20261114180000_uploads.sql` creates the private `documents`
bucket. If the project has no Storage schema yet, create a private bucket named
`documents` in Storage → New bucket before applying migrations.
