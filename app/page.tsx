const stack = [
  "Next.js 16 on Vercel",
  "FastAPI on Hugging Face Spaces",
  "Supabase · Postgres + pgvector",
  "Groq + Gemini free tiers",
];

export default function Home() {
  return (
    <main className="wrap">
      <div className="card">
        <span className="badge">Setup verified · build starts next</span>
        <h1>Enterprise Knowledge Copilot</h1>
        <p className="tagline">Ask the handbook. Get answers with proof.</p>
        <p className="body">
          A role-aware copilot over a public company handbook: cited answers,
          refusals when confidence is low, an audit trail, and an evaluation
          dashboard.
        </p>
        <ul className="stack">
          {stack.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="note">
          This page is only the deploy skeleton. The copilot, retrieval
          pipeline, and evaluation dashboard are built on top of it.
        </p>
      </div>
    </main>
  );
}
