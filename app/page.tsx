import {
  ArrowRight,
  FileCheck2,
  GitBranch,
  Lock,
  ScanSearch,
  ShieldCheck,
  SquareTerminal,
  Waypoints,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { ACCESS_LEVELS, ROLE_LABEL, ROLES, site } from "@/lib/site";

export const metadata: Metadata = { title: "Role-aware answers with proof" };

const pipeline = [
  {
    icon: Waypoints,
    title: "Route",
    body: "The question is classified: policy lookup, people question, security question or out of scope.",
  },
  {
    icon: ScanSearch,
    title: "Retrieve",
    body: "Hybrid search over pgvector and Postgres full-text, fused with reciprocal rank fusion, filtered by the caller's role inside the query.",
  },
  {
    icon: FileCheck2,
    title: "Grade & answer",
    body: "A cross-encoder reranks the candidates; the model may only use what survived the grade.",
  },
  {
    icon: ShieldCheck,
    title: "Verify or refuse",
    body: "Every sentence is checked against the cited chunks. Weak evidence produces an honest “I don't know”.",
  },
];

const features = [
  {
    title: "Answers with citations",
    body: "Each claim links to the exact passage. Citation chips open the source drawer with the passage highlighted.",
  },
  {
    title: "Honest refusals",
    body: "Below the confidence threshold, or when a citation fails verification, the copilot refuses instead of guessing.",
  },
  {
    title: "Access enforced in SQL",
    body: "Role and department predicates live in the retrieval query and in Row Level Security policies — never applied after the fact.",
  },
  {
    title: "Tamper-evident audit log",
    body: "Every question, refusal, role and document id is hash-chained, so removing a row breaks the chain and the verify button says so.",
  },
  {
    title: "Measured quality",
    body: "A golden set of 80+ questions runs in CI: hit@k, MRR, citation precision, faithfulness, refusal accuracy, latency — with zero permission leakage as a hard gate.",
  },
  {
    title: "Traceable cost",
    body: "Latency, tokens and an estimated cost per answer, per provider, on a traces page.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4">
      <section className="pt-16 pb-12 sm:pt-24">
        <span className="chip chip-accent mono">role-aware retrieval · citations · refusals</span>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          {site.tagline}
        </h1>
        <p className="mt-5 max-w-2xl text-[15px] leading-7 text-[var(--text-muted)]">
          {site.description} Built on the public GitLab Handbook, plus a small set of clearly
          labelled synthetic confidential documents that exist only to prove the access model.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link className="btn btn-primary" href="/chat">
            Open the copilot <ArrowRight size={15} />
          </Link>
          <Link className="btn" href="/trust">
            <Lock size={15} /> Security controls
          </Link>
          <a className="btn" href={site.repo} rel="noreferrer noopener" target="_blank">
            <GitBranch size={15} /> Source
          </a>
        </div>
        <dl className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { k: "Documents", v: "handbook slice" },
            { k: "Embeddings", v: "multilingual e5" },
            { k: "Reranker", v: "cross-encoder" },
            { k: "Leakage gate", v: "0 allowed" },
          ].map((item) => (
            <div key={item.k} className="panel-2 px-4 py-3">
              <dt className="mono text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                {item.k}
              </dt>
              <dd className="mt-1 text-sm">{item.v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="pipeline" className="border-t border-[var(--border)] py-14">
        <h2 id="pipeline" className="text-2xl font-semibold tracking-tight">
          How an answer is produced
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-muted)]">
          Five nodes, one graph. Refusing is a successful outcome, not an error.
        </p>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {pipeline.map((step, index) => (
            <li key={step.title} className="panel p-5">
              <div className="flex items-center gap-2">
                <step.icon size={16} className="text-[var(--accent)]" />
                <span className="mono text-[11px] text-[var(--text-muted)]">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="mt-3 text-sm font-semibold">{step.title}</h3>
              <p className="mt-2 text-[13px] leading-6 text-[var(--text-muted)]">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="access" className="border-t border-[var(--border)] py-14">
        <h2 id="access" className="text-2xl font-semibold tracking-tight">
          How access control works
        </h2>
        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <div className="panel overflow-hidden">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Access levels visible to each role</caption>
              <thead className="bg-[var(--panel-2)] text-[var(--text-muted)]">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Role</th>
                  {ACCESS_LEVELS.map((level) => (
                    <th scope="col" key={level} className="px-4 py-3 font-medium capitalize">
                      {level}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROLES.map((role) => (
                  <tr key={role} className="border-t border-[var(--border)]">
                    <th scope="row" className="px-4 py-3 font-normal">
                      {ROLE_LABEL[role]}
                    </th>
                    {ACCESS_LEVELS.map((level) => {
                      const allowed =
                        role === "admin"
                          ? true
                          : role === "guest"
                            ? level === "public"
                            : level === "department"
                              ? false
                              : level !== "confidential";
                      return (
                        <td key={level} className="px-4 py-3">
                          <span
                            className={
                              allowed
                                ? "mono text-xs text-[var(--ok)]"
                                : "mono text-xs text-[var(--text-muted)]"
                            }
                          >
                            {allowed ? "allow" : "deny"}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[var(--text-muted)]">
              The predicate is part of the SQL that selects chunks, and the same rule is enforced by
              Row Level Security for anything that talks to Postgres directly. A denied request
              explains why it was denied without revealing the title of the document.
            </p>
            <p className="text-sm leading-7 text-[var(--text-muted)]">
              Department-scoped documents are visible to the matching department role and to
              administrators. Confidential documents in this project are synthetic and labelled as
              such in metadata and in the UI.
            </p>
            <div className="panel-2 p-4">
              <p className="mono text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                CI gate
              </p>
              <p className="mt-2 text-sm">
                Cross-role leakage attempts — including paraphrases and prompt injection — must
                return exactly <span className="mono text-[var(--accent)]">0</span> leaked passages,
                or the build fails.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="features" className="border-t border-[var(--border)] py-14">
        <h2 id="features" className="text-2xl font-semibold tracking-tight">
          What is in the product
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <article key={feature.title} className="panel p-5">
              <h3 className="text-sm font-semibold">{feature.title}</h3>
              <p className="mt-2 text-[13px] leading-6 text-[var(--text-muted)]">{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="reviewer" className="border-t border-[var(--border)] py-14">
        <div className="panel flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 id="reviewer" className="text-lg font-semibold">
              Reviewing this project?
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--text-muted)]">
              Sign in with one of the role accounts from the sign-in page, ask the same question as
              two different roles, and watch the answers diverge. The security page links every
              control to the test that proves it.
            </p>
          </div>
          <div className="flex shrink-0 gap-3">
            <Link className="btn btn-primary" href="/login">
              <SquareTerminal size={15} /> Sign in
            </Link>
            <Link className="btn" href="/evals">
              Evaluation results
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
