# Demo video script (3–5 minutes)

Recorded against the live deployment, 2026-11-12. Every number below is a measured
number from this repository; nothing is rounded up.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Landing page | "This is a role-aware copilot over the GitLab Handbook: 754 documents, 871k words, plus twelve clearly labelled synthetic confidential documents that exist only to prove the access model." |
| 0:20–0:40 | Scroll to the stat cards | "The interesting part is not that it answers. It is that it can prove what it answered from, and refuse when it cannot." |
| 0:40–1:00 | Sign-in page, pick Administrator | "Seven demo roles. The role is not a UI filter: it is a parameter of the SQL query that selects passages." |
| 1:00–1:40 | Chat: "How do I submit an expense receipt?" | "Every sentence carries a marker. The drawer shows the passage, the score and the licence of the source." |
| 1:40–2:05 | Open the source drawer | "Reranker score 0.88 for the top passage. When the top score falls under the threshold, the copilot refuses instead of guessing." |
| 2:05–2:30 | Ask something the corpus cannot answer | "It says it does not know. That refusal is logged with the role and the question, and it counts as a wrong refusal in the evaluation when the label says the question was answerable." |
| 2:30–3:05 | Sign in as Guest, ask "What are the engineering salary bands?" | "Same question, different role. The guest gets a refusal with zero citations; the administrator gets the confidential salary-band document. This is verified by the retrieval endpoint, not only by the wording of an answer." |
| 3:05–3:35 | Admin page: document access + audit trail | "Changing an access level writes an audit entry, and the chain verifies. Verification anchors on the page edge, because the log is larger than one page." |
| 3:35–4:00 | Evaluations page / `docs/reports/retrieval_eval.md` | "Ranking is measured without any LLM: hit@3 is 0.857 on the test split across three deterministic passes. The end-to-end hit@k is 0.406, and the gap is the refusal decision, not retrieval." |
| 4:00–4:30 | `docs/reports/security.md` | "Trivy, a CycloneDX SBOM, pip-audit, pnpm audit and OpenSSF Scorecard run in CI, with every action pinned to a commit SHA. The audit found a real bug: the chain verifier called the whole log tampered once it passed 500 rows." |
| 4:30–5:00 | `/health` JSON | "Memory under five concurrent requests: 386 to 402 megabytes with both ONNX models loaded, on a 512 MB free instance. No torch: fastembed and flashrank run on onnxruntime." |
| 5:00 | Close | "Everything is free tier: Vercel, Render, Supabase, Groq and Gemini. The limits are in the README — including the ones I have not solved." |

## Recording notes

- Start the API first and load `/health` once, so the recording does not contain a
  cold start; mention the cold start instead.
- Keep the browser at 1280×800 so the source drawer and the audit table fit.
- Do not read the numbers from memory; keep `docs/reports/retrieval_eval.md` and
  `docs/reports/security.md` open in another window.
