import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact",
  description: "Questions about the product, access or security.",
};

export default function ContactPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">Contact</p>
      <h1 className="mt-3 text-3xl font-semibold">Talk to the team behind it.</h1>
      <p className="mt-4 max-w-xl text-[15px] leading-7 text-[var(--text-muted)]">
        For access, a walkthrough, or a security question, send an email. It reaches a person, not a
        ticket queue.
      </p>
      <a
        className="btn btn-primary mt-8"
        href="mailto:ibrahimsumon005@gmail.com?subject=Enterprise%20Knowledge%20Copilot"
      >
        ibrahimsumon005@gmail.com
      </a>
      <p className="mt-6 max-w-xl text-sm leading-7 text-[var(--text-muted)]">
        We usually reply within two working days. For a security report, include the page or
        endpoint and the steps to reproduce it.
      </p>
    </div>
  );
}
