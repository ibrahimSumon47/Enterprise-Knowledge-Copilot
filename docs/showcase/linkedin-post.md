# LinkedIn post draft

I built a role-aware RAG copilot over the GitLab Handbook, and the interesting part
is not the answer — it is the refusal.

**What it does**
754 handbook documents, 871k words, plus 12 synthetic confidential documents.
You ask in English or Bengali; the answer carries `[n]` citations you can open, and
when the evidence is weak it says "I don't know" instead of guessing.

**Access control is in the query, not after it**
The role/department predicate lives inside the SQL function that selects chunks,
mirrored by Row Level Security. Permission leakage is measured at exactly 0 on
every evaluation run — it is the hard gate that can fail the build.

**Free tier, end to end**
Vercel (web) + Render (FastAPI, 512 MB) + Supabase (Postgres, pgvector, Auth, RLS).
No paid service, no trial. Groq primary, Gemini backup, hedged at 1.5 s and capped
at 12 s — measured: p95 6.7 s, down from 24 s before the fallback was fixed.

**What the evaluation honestly says**
84 questions: hit@k 0.406, citation precision 0.333, refusal accuracy 0.679, p95
6.7 s, leakage 0.
Then I measured retrieval without any LLM (free quota was the bottleneck): on the
34-question test split the right document is in the top three **85.7%** of the
time, in three deterministic passes. So ranking is not what loses the answers —
the refusal decision is. The top reranker score overlaps between answerable and
unanswerable questions (AUC 0.69), and no single threshold both refuses 90% of the
unanswerable ones and keeps the answerable ones: at 0.28 it refuses 19 of 32
answerable dev questions. That is now a documented, measured limit instead of a
guess.
Weak spot, stated in the README: 14 answerable questions are refused because the
4 MB cross-encoder scores the correct passage near zero. I tried a 34 MB
cross-encoder — it hit 402 MB RSS and killed the free instance. Tried lowering the
threshold, head-and-tail scoring, and an LLM evidence grader; each is measured in
`docs/reports/` and each failed to beat run-to-run noise.

**What I learned**
Most of the work was not adding a feature, it was measuring whether the last
"improvement" was real. Three of them were not.

Live: https://enterprise-knowledge-copilot-wine.vercel.app
Code: https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot

#RAG #LLM #FastAPI #Nextjs #Supabase #FreeTier #Evaluation
