# OWNER ANSWERS — Enterprise Knowledge Copilot

- **Interview date:** 2026-11-11
- **Interviewer:** Buffy (Freebuff)
- **Owner:** Md Ibrahim Hossain Sumon (ibrahimsumon005@gmail.com / GitHub: ibrahimSumon47)
- **Local folder:** `E:\AI Engineering Projects\Enterprise-Knowledge-Copilot`
- **GitHub repo (exists):** https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot
- **Status:** interview only — no build, no install, no `git init` done in this session

---

## 1. Environment check (read-only)

| Item | Result |
| --- | --- |
| Folder contents | almost empty — only `.freebuff` |
| Git repo | **No** (`fatal: not a git repository`) — deliberately not initialized |
| `git config user.name` | `Md Ibrahim Hossain Sumon` |
| `git config user.email` | `ibrahimsumon005@gmail.com` |
| `gh auth status` | ✓ logged in as **ibrahimSumon47** (scopes: gist, read:org, repo, user, workflow) |
| node | v24.22.1 |
| pnpm | 12.15.0 |
| python | 3.14.7 |
| pip | 26.2.1 |
| docker | **NOT installed** |
| gh | 2.103.3 |
| vercel CLI | 65.4.0 — logged in as `ibrahimsumon47` |
| supabase CLI | 2.118.0 |
| huggingface-cli | deprecated (`hf` CLI present instead) |
| winget | v1.29.380 |

No secret values were printed or stored.

---

## 2. Accounts & keys

### Q1. Supabase project already created?
**Answer (owner, verbatim):** "তোমার কাছে তো Supabase এর CLI আছে তাহলে তুমি বানিয়ে নাও আর না পারলে আমাকে ডিটেলস এ বলে দাঁও কি করতে হবে।"
**Meaning:** not created yet. Owner wants the agent to create it with the Supabase CLI if possible; otherwise give step-by-step instructions. Creating it needs an interactive `supabase login` (browser) and a database password that **the owner types himself**.

### Q2. Hugging Face account + WRITE token ready?
**Answer:** "কিছুই নেই, সাহায্য দরকার"
**Meaning:** no account, no token → **needs help** (account + write token).

### Q3. Which free LLM API key?
**Answer:** "দুটোই ব্যবহার করবো। ডিটেলস এ বলো কিভাবে দিবো তোমাকে এই Key গুলো"
**Meaning:** both **Groq and Gemini** will be used (Groq = main, Gemini = backup). Owner asked for the exact way to hand over keys → keys must go in as GitHub secrets / platform env vars, never in chat.

### Q4. Vercel CLI logged in + Vercel linked to GitHub?
**Answer:** "না" (not linked to GitHub)
**Meaning:** CLI is logged in (`ibrahimsumon47`) but the Vercel account is **not linked to GitHub** → linking is a setup step.

---

## 3. Product

### Q5. Display name & tagline
**Answer:** keep **Enterprise Knowledge Copilot**
**Tagline (accepted):** "Ask the handbook. Get answers with proof."
Other names offered and rejected: PolicyKosh, CiteDesk, Handbok.

### Q6. Look and feel
**Answer (owner, verbatim):** "You choose"
**Agent decision (recorded as approved):**
- Accent colour: **Teal `#0F766E`**
- Logo: **simple icon mark + wordmark** (small geometric mark next to the name)

### Q7. Interface language
**Answer:** **English + বাংলা UI toggle**
Bangla questions over English documents will be supported either way.

### Q8. Handbook slice size
**Answer:** "~800 pages" (richer)
**Note:** owner first asked whether a GitLab account is needed — it is **not**. The GitLab Handbook is public and CC BY-SA 4.0, so the slice can be cloned/downloaded without an account.

---

## 4. Working style

### Q9. Freebuff hours per day + selected model
**Answer:** "অনিয়মিত" (irregular); model not specified.

### Q10. Demo-video script + LinkedIn post at the end?
**Answer:** "এটা আপাদত বাদ" → **out of scope for now** (can be added later on request).

### Q11. Anything to add / remove / avoid?
**Answer (owner, verbatim):** "You can suggest Now. তবে কাজ শুরু পর আবার বার বার সাজেস্ট দেওয়ার জন্য বন্ধ হইও না। সাজেশন থাকলে এখনই দাঁও"
**Meaning:** give all suggestions now, and do not keep suggesting during the work.
**Suggestions given now and approved:**
1. Confidence badge on every answer (High / Medium / Refused).
2. Starter question chips in the chat, per role.
3. Per-role refusal test cases on the evaluation dashboard (allowed vs blocked).
4. Richer audit log: role, document id, latency, token count.
5. README with architecture diagram + "why this design" section.

### Q12. Deadline
**Answer:** "কোনো ডেডলাইন নাই তবে বেশি দেরিও করা যাবে না"
**Meaning:** no fixed date; keep a steady pace, do not drag.

---

## 5. Fixed stack (from the project brief)

- Frontend: **Next.js 16** on **Vercel**
- Backend: **FastAPI** on a free **Hugging Face Space**
- Data: **Supabase** — Postgres, pgvector, Auth, RLS
- LLM: **Groq** free API as main + **Gemini** free API as backup
- Corpus: public **GitLab Handbook** (CC BY-SA 4.0)
- Hard constraint: **everything free forever, cloud only** (no Docker locally, no paid tiers)

---

## 6. Open items (blocking build start)

Secrets are added by the owner only: `gh secret set NAME` in a terminal (value typed there) or GitHub Settings → Secrets and variables → Actions. Never in chat.

---

## 7. Verified setup state (checked 2026-11-11, read-only)

### GitHub

| Check | Result |
| --- | --- |
| Repo `ibrahimSumon47/Enterprise-Knowledge-Copilot` | exists, **public**, created 2026-11-11 |
| Commits / branches | **empty** — `Git Repository is empty` (409), branches `[]` |
| Local folder | still **not** a git repo |
| Repo secrets present | **7/7** — `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`, `SUPABASE_DB_URL` (`SUPABASE_DB_URL` added 11:22 UTC, `SUPABASE_URL` re-set 11:23 UTC) |
| Repo secret missing | none — values are write-only, so exact values get a live connection test at build time |

### Supabase (created by owner)

| Field | Value |
| --- | --- |
| Project name | `enterprise-knowledge-copilot` |
| Project ref | `ctfatevadhojxycuplsh` |
| Region | `ap-south-1` (South Asia / Mumbai) |
| Postgres | 17.11.0.018 |
| Status | `ACTIVE_HEALTHY` |
| DB host | `db.ctfatevadhojxycuplsh.supabase.co` |
| REST probe | `401` without an API key → project is live and serving |
| Expected `SUPABASE_URL` | `https://ctfatevadhojxycuplsh.supabase.co` (no trailing slash) |
| Local CLI link | not linked — not needed for the build |

### Hugging Face

| Check | Result |
| --- | --- |
| Account | `NoobMaster005` (logged in) |
| Access token `ekc-space` | type **Write**, permission **WRITE**, **no expiry field** — classic Write tokens do not expire (valid until revoked/regenerated). Correct for `HF_TOKEN`. |
| Local CLI login | separate **OAuth** session token `oauth-NoobMaster005`, expires **2026-11-26** — this is only this machine's `hf` CLI login, it is not the `HF_TOKEN` secret |
| Existing Spaces | none (`[]`) — the Space name is free |

### Vercel

| Check | Result |
| --- | --- |
| CLI login | `ibrahimsumon47` ✓ |
| Project for this repo | none yet |
| Vercel ↔ GitHub | **not linked** (owner confirmed) |
| Impact | not blocking — project can be created and deployed by CLI at deploy time |

## 8. Remaining owner actions before START

**None blocking.** Verified 2026-11-11 11:25 UTC: 7/7 secrets set, Supabase `ACTIVE_HEALTHY`, HF `ekc-space` is a WRITE token with no expiry, GitHub repo public (still empty, as expected before the build).

**Done since:** repo initialized and pushed (`main`), Vercel project `enterprise-knowledge-copilot` created + linked + GitHub-connected, production alias **https://enterprise-knowledge-copilot-wine.vercel.app** live (HTTP 200), and a push-triggered auto-deploy confirmed.

Still open, all agent work after START: Hugging Face Space creation, schema/RLS/pgvector index, corpus ingestion, smoke + auth tests, Vercel env vars for Supabase (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) and the Space URL.

Note: GitHub secret values are write-only. They are validated by a live connection test as the first build step; if one is wrong, only that secret is re-set by the owner.
