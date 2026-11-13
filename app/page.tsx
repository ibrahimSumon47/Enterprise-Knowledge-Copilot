import { ArrowRight, Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Answers your team can check",
  description:
    "Search company documents in one place. Every answer cites the passage it came from, and the copilot says so when the documents do not cover the question.",
};

const benefits = [
  {
    title: "Every answer shows its source",
    body: "Citations open the exact passage, with the document, section and licence. Reviewers can check a claim in seconds instead of searching for the paragraph themselves.",
  },
  {
    title: "Access follows the person asking",
    body: "Public, employee, department and confidential material is filtered in the database query. A finance question never surfaces a document the account may not read.",
  },
  {
    title: "Refusals point somewhere useful",
    body: "When the evidence is thin, the copilot says it could not answer and offers the closest documents, then records the gap for an administrator to close.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4">
      <section className="grid gap-12 py-16 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-24">
        <div>
          <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">
            Knowledge copilot
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-[1.08] sm:text-5xl">
            Answers your team can check.
          </h1>
          <p className="mt-5 max-w-xl text-[15px] leading-7 text-[var(--text-muted)]">
            Enterprise Knowledge Copilot searches your handbook, policies and internal documents,
            answers in plain language, and shows the passage behind every claim. If the documents do
            not answer the question, it says so.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <form action="/api/sample-workspace" method="post">
              <button className="btn btn-primary" type="submit">
                Open sample workspace <ArrowRight size={15} />
              </button>
            </form>
            <Link className="btn" href="/login">
              Sign in
            </Link>
          </div>
          <p className="mt-3 text-xs text-[var(--text-muted)]">
            The sample workspace is read-only and needs no setup.
          </p>
        </div>

        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
            <p className="text-xs font-medium text-[var(--text-muted)]">Sample workspace</p>
            <span className="chip text-[10px]">read only</span>
          </div>
          <div className="space-y-4 p-5">
            <p className="w-fit max-w-[90%] rounded-lg bg-[var(--accent-soft)] px-3 py-2 text-sm">
              How do I submit an expense receipt?
            </p>
            <div className="space-y-2 text-sm leading-7">
              <p>
                Submit receipts within 45 days of the purchase through the expense tool. Anything
                above 25 USD needs an itemised receipt [1].
              </p>
              <p className="text-sm leading-7">
                Managers approve expenses weekly; finance reviews anything flagged as out of policy
                [2].
              </p>
            </div>
            <div className="space-y-2 border-t border-[var(--border)] pt-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                Sources
              </p>
              {[
                ["Expense policy", "Receipts and deadlines"],
                ["Approval workflow", "Weekly review"],
              ].map(([title, heading], index) => (
                <div key={title} className="flex gap-2 text-xs">
                  <span className="mono text-[var(--accent)]">[{index + 1}]</span>
                  <span>
                    {title} <span className="text-[var(--text-muted)]">· {heading}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="why" className="border-t border-[var(--border)] py-16">
        <h2 id="why" className="max-w-2xl text-2xl font-semibold">
          Built for the questions people ask between meetings.
        </h2>
        <div className="mt-10 grid gap-10 md:grid-cols-3">
          {benefits.map((benefit, index) => (
            <article key={benefit.title}>
              <p className="mono text-xs text-[var(--text-muted)]">0{index + 1}</p>
              <h3 className="mt-3 text-base font-semibold">{benefit.title}</h3>
              <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">{benefit.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="control" className="border-t border-[var(--border)] py-16">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <h2 id="control" className="text-2xl font-semibold">
              The answer is only half of it.
            </h2>
            <p className="mt-4 text-sm leading-7 text-[var(--text-muted)]">
              Administrators see what people ask, where the documents fall short, and who has been
              reading what. Questions that end in “I could not find this” become a queue of
              knowledge gaps instead of a dead end.
            </p>
            <Link className="btn mt-6" href="/product">
              See the product <ArrowRight size={15} />
            </Link>
          </div>
          <ul className="space-y-3">
            {[
              "Usage by day and by workspace",
              "Unanswered questions, ready to assign",
              "Feedback on individual answers",
              "Activity log with CSV export",
            ].map((item) => (
              <li
                key={item}
                className="flex items-center gap-3 border-b border-[var(--border)] pb-3 text-sm last:border-0"
              >
                <Check size={15} className="text-[var(--accent)]" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="border-t border-[var(--border)] py-16">
        <div className="panel flex flex-col gap-6 p-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">Try it with the sample documents.</h2>
            <p className="mt-2 max-w-xl text-sm leading-7 text-[var(--text-muted)]">
              A read-only workspace over a public handbook slice. Ask a question, open a citation,
              then ask something the documents do not cover.
            </p>
          </div>
          <form action="/api/sample-workspace" method="post" className="shrink-0">
            <button className="btn btn-primary" type="submit">
              Open sample workspace <ArrowRight size={15} />
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}
