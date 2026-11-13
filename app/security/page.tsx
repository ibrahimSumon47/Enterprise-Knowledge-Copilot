import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Security",
  description:
    "How Enterprise Knowledge Copilot keeps documents inside their permissions and keeps a record of who asked what.",
};

const controls = [
  {
    title: "Sign-in",
    body: "Accounts are issued through Supabase Auth. Sessions are short-lived JWTs signed by the identity provider; the API verifies the signature against the published keys on every request.",
  },
  {
    title: "Access control",
    body: "Every document carries an access level and, where relevant, a department. The rule is part of the database query, mirrored by row-level security policies, so a document outside your permissions is never selected.",
  },
  {
    title: "Document handling",
    body: "Uploads are parsed and split into passages for search. Retrieved text is treated as data: instructions inside a document are not executed, and citations are checked against the passages that were retrieved.",
  },
  {
    title: "Activity record",
    body: "Questions, refusals, document changes and administrative actions are written to an append-only log with a hash chain, so a removed or altered entry is detectable. Administrators can export the log as CSV.",
  },
  {
    title: "Data in transit",
    body: "The app, the API and the database talk over TLS. The browser never receives a database credential: it holds a user session and calls the API with a bearer token.",
  },
  {
    title: "Retention",
    body: "Questions and answers stay with the workspace until an administrator removes them. The activity log is retained for the life of the workspace unless a retention period is configured.",
  },
];

export default function SecurityPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">Security</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">Documents stay where they belong.</h1>
      <p className="mt-4 max-w-2xl text-[15px] leading-7 text-[var(--text-muted)]">
        This page describes the controls in the product. It is written for the person evaluating it,
        not for a compliance binder.
      </p>

      <div className="mt-10 space-y-8">
        {controls.map((control) => (
          <section key={control.title} className="border-t border-[var(--border)] pt-6">
            <h2 className="text-base font-semibold">{control.title}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-muted)]">
              {control.body}
            </p>
          </section>
        ))}
      </div>

      <section className="panel mt-12 p-6">
        <h2 className="text-base font-semibold">Report a concern</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
          If you find a security issue, send the details to the address on the{" "}
          <Link className="underline decoration-dotted" href="/contact">
            contact page
          </Link>
          . Please do not open a public issue with a working exploit.
        </p>
      </section>
    </div>
  );
}
