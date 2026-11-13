import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What this service stores, why, and how to have it removed.",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">Privacy</p>
      <h1 className="mt-3 text-3xl font-semibold">What we keep.</h1>
      <p className="mt-4 text-sm text-[var(--text-muted)]">Last updated 13 November 2026.</p>

      <div className="mt-10 space-y-7 text-sm leading-7">
        <section>
          <h2 className="text-base font-semibold">Account data</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            An account has an email address, a display name, a role and, for department roles, a
            department. Passwords are stored as hashes by the authentication provider; this
            application never sees them.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Questions and answers</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Questions you ask are stored with the answer, the cited passages and the role you asked
            as. They are visible to you in the conversation and to workspace administrators in the
            activity record. Questions the copilot could not answer are kept in the unanswered queue
            so an administrator can improve the documents.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Documents</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Documents uploaded to a workspace are used only to answer questions inside that
            workspace. Access levels and departments determine who can retrieve them.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Service providers</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            The application runs on Vercel, the API on Render and the database and authentication on
            Supabase. These providers process data on our behalf. Language models are called with
            the retrieved passages needed to answer the question; prompts are not used to train a
            model by this application.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Deletion</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Ask an administrator to remove a conversation, a document or the account. Activity-log
            entries are retained to keep the record verifiable; the email used in a request is
            enough for us to locate it.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Contact</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Privacy questions go to the address on the{" "}
            <a className="underline decoration-dotted" href="/contact">
              contact page
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
