# Tutorial: using Enterprise Knowledge Copilot

This is the short, practical walkthrough for someone opening the product for the
first time. It does not require a local development setup.

**Live app:** https://enterprise-knowledge-copilot-wine.vercel.app

---

## 1. Try the sample workspace (about two minutes)

1. Open the live app.
2. Click **Open sample workspace**.
3. You land in **Chat** as a read-only guest.
4. Ask one of the starter questions, for example:
   - `How do I submit an expense claim?`
   - `What is the deadline for submitting receipts?`
   - `How do I report a suspected security vulnerability?`
5. Open the numbered citation under a sentence. The drawer shows the document,
   heading, passage and licence.
6. Ask something the handbook does not cover. The answer is a refusal with the
   closest sources. That is intentional: the product does not invent an answer.

The sample workspace contains a public slice of the GitLab Handbook. It is
shared, read-only and separate from every customer workspace.

> If you are already signed in as an owner or admin, use a private/incognito
> window for the sample. The button starts a guest session in the same browser,
> so it would replace your current session.

## 2. Create your own workspace

1. Open **/register**.
2. Use your own email and choose a password. This account becomes the workspace
   **owner**.
3. Onboarding asks you to:
   - name the workspace;
   - paste a first policy or handbook section;
   - open Chat and ask about it.
4. After onboarding, open **Library**. You can upload real files or load the
   demo library.

There is one owner per workspace. Ownership transfer is not implemented; create
a new workspace with `/register` if you need a separate one.

## 3. Load the demo library (optional)

A new workspace starts empty. To explore the product with realistic content:

1. Sign in as the owner.
2. Open **Library**.
3. Click **Load demo library** and confirm.
4. Wait about 30–40 seconds while the sample documents and search chunks are
   copied. Keep the tab open.
5. The library now contains the public handbook, department documents and the
   labelled synthetic confidential documents.

The copy belongs to your workspace. The shared sample workspace is not changed,
and every later owner can use the same button. Loading it twice does not create
duplicates.

## 4. Upload your own documents

1. Open **Library**.
2. Choose a **PDF, DOCX, HTML, Markdown or TXT** file (up to 10 MB).
3. Click **Upload** and wait for indexing to finish. The status changes from
   processing to ready.
4. Ask about the document in **Chat**.

Workspace limits are 10 MB per file, 200 MB per workspace and 10 uploads per
hour. Scanned PDFs need OCR and are not supported. Re-index or delete uploaded
documents from the Library.

## 5. Ask questions

Chat answers only from documents the signed-in account may read in that
workspace. It does not browse the web, use general knowledge, run code or read
another workspace.

Useful question shapes:

- `What does the policy say about ...?`
- `What are the steps for ...?`
- `Who approves ...?`
- `What is the deadline for ...?`

Bangla and English questions both work; retrieval uses the English documents.
Every accepted answer has citations. If the evidence is missing or weak, the
product refuses and queues the question for an administrator.

## 6. Invite your team

Open **Settings**.

1. Choose a role and, optionally, a group.
2. Click **Create link** and copy the single-use invitation.
3. Send it to the person. They create an account and join this workspace.

Roles decide what a person can read:

| Role | Can read |
| --- | --- |
| guest | public |
| employee | public + employee |
| engineering / security / hr / finance | public + employee + their department |
| admin | every access level in the workspace, within its groups |
| owner | every document in every group |

Only an owner can invite another admin or change an admin. Admins manage the
workspace day to day but cannot change workspace settings, delete the workspace
or grant ownership.

## 7. Admin and owner basics

- **Admin → Operations** shows analytics, unanswered questions and audit tools.
- **Admin → Quality** shows answer quality and latency.
- **Settings** manages members, groups, invitations, workspace settings and audit
  export.
- **Library** manages documents.
- An owner can also load the demo library and delete the whole workspace.

Only owners can change the workspace name, logo, accent colour and allowed email
domains. Only owners can delete the workspace.

## 8. Troubleshooting

**The sample button does nothing.**
Hard-refresh the page (`Ctrl+Shift+R`) and try again. If you are signed in, open a
private window first. If it still fails, the guest credential needs to be
re-synchronised using the demo-reset workflow in `docs/DEPLOY.md`.

**Chat refuses every question.**
Check that the workspace has documents in Library and that indexing has finished.
A new workspace is empty until you load the demo library or upload files.

**A question is refused even though the document exists.**
The refusal may be the evidence guard rejecting a weak passage. Re-index the
document, ask with more specific wording, and check the unanswered queue as an
administrator.

**I forgot a demo password.**
The `@ekc.local` demo accounts cannot receive email. An owner or maintainer runs
the **Reset demo passwords** workflow in GitHub Actions; the password comes from
the `EKC_DEMO_PASSWORD` repository secret. The guest sample account uses its own
`EKC_GUEST_PASSWORD` and is not overwritten by a demo reset.

**I need to run the project locally.**
Follow `docs/WORKING_ON_THIS.md` for the local setup and `docs/DEPLOY.md` for
environment variables, Supabase, Vercel and Render.

---

## Where to go next

- `README.md` — what the product does and the current measured results.
- `docs/WORKING_ON_THIS.md` — developer setup, access rules and verification.
- `docs/DEPLOY.md` — deployment and identity configuration.
- `docs/reports/` — evaluation evidence and security reports.
