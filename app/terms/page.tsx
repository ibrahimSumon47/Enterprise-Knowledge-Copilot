import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms",
  description: "The terms for using this service.",
};

export default function TermsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">Terms</p>
      <h1 className="mt-3 text-3xl font-semibold">Using the service.</h1>
      <p className="mt-4 text-sm text-[var(--text-muted)]">Last updated 13 November 2026.</p>

      <div className="mt-10 space-y-7 text-sm leading-7">
        <section>
          <h2 className="text-base font-semibold">What this is</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Enterprise Knowledge Copilot answers questions over the documents available to your
            workspace. Answers are generated text and can be wrong; the cited passage is the
            authoritative source. Check it before you act on a policy decision.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Your responsibilities</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            Keep your sign-in details to yourself, do not upload material you have no right to use,
            and do not use the service to attempt to reach documents outside your permissions.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Availability</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            The service runs on free infrastructure and may be unavailable during maintenance or a
            provider outage. It is provided without a warranty and without a service-level
            commitment.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold">Ending access</h2>
          <p className="mt-2 text-[var(--text-muted)]">
            An administrator can deactivate an account at any time. You can ask for your account and
            conversations to be removed as described on the{" "}
            <a className="underline decoration-dotted" href="/privacy">
              privacy page
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
