import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Product",
  description:
    "Ask a question, follow the citations, see what your account is allowed to read, and give administrators a queue of the gaps.",
};

const flow = [
  {
    title: "Ask in your own words",
    body: "Type a question the way you would ask a colleague. Bangla and English both work; the search runs over the English documents either way.",
  },
  {
    title: "Read an answer with its sources",
    body: "Each sentence carries a numbered marker. Open a marker to see the passage, the document title, the section and the licence.",
  },
  {
    title: "Only see what you may read",
    body: "The access rule is applied while the documents are selected, not after. Department material stays inside that department.",
  },
  {
    title: "Close the gap when there is one",
    body: "A question the documents cannot answer comes back with the closest sources, and lands in the admin queue labelled Unanswered.",
  },
];

export default function ProductPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">Product</p>
      <h1 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">
        One place to ask, one click to check.
      </h1>
      <p className="mt-4 max-w-2xl text-[15px] leading-7 text-[var(--text-muted)]">
        Enterprise Knowledge Copilot connects a question to the passage that answers it, and gives
        administrators the evidence they need to keep the documents current.
      </p>

      <ol className="mt-12 space-y-8">
        {flow.map((step, index) => (
          <li key={step.title} className="grid gap-3 border-t border-[var(--border)] pt-8 sm:grid-cols-[64px_1fr]">
            <span className="mono text-sm text-[var(--text-muted)]">0{index + 1}</span>
            <div>
              <h2 className="text-lg font-semibold">{step.title}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-muted)]">
                {step.body}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <section className="mt-14 grid gap-6 sm:grid-cols-2">
        <div className="panel p-6">
          <h2 className="text-base font-semibold">For the people asking</h2>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-[var(--text-muted)]">
            <li>Keyboard-first: open the palette with ⌘K or Ctrl+K.</li>
            <li>Recent questions are one click away.</li>
            <li>Scope a question to a folder when a library grows.</li>
            <li>Answers copy with their citations attached.</li>
          </ul>
        </div>
        <div className="panel p-6">
          <h2 className="text-base font-semibold">For the people maintaining it</h2>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-[var(--text-muted)]">
            <li>Upload policies and re-index them from the admin area.</li>
            <li>See unanswered questions instead of relying on complaints.</li>
            <li>Review thumbs-down feedback with the reason attached.</li>
            <li>Export the activity log for a review or an audit.</li>
          </ul>
        </div>
      </section>

      <section className="mt-14 border-t border-[var(--border)] pt-10">
        <h2 className="text-xl font-semibold">Try the sample workspace</h2>
        <p className="mt-2 max-w-xl text-sm leading-7 text-[var(--text-muted)]">
          It uses a public handbook slice and is read-only, so you can open citations and test a
          refusal without changing anything.
        </p>
        <form action="/api/sample-workspace" className="mt-5" method="post">
          <button className="btn btn-primary" type="submit">
            Open sample workspace
          </button>
        </form>
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          Already have an account? <Link className="underline decoration-dotted" href="/login">Sign in</Link>.
        </p>
      </section>
    </div>
  );
}
