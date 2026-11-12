import { FileCheck2, Fingerprint, KeyRound, Lock, ScrollText, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Trust centre" };

const controls = [
  {
    icon: Lock,
    title: "Authorisation inside the query",
    body: "search_chunks takes the caller's role and department and applies the access predicate in SQL. Row Level Security enforces the same rule for anything that talks to Postgres directly.",
    evidence: "supabase/migrations/20261111000100_init.sql · can_read(), search_chunks()",
  },
  {
    icon: Fingerprint,
    title: "Identity from the token, never the body",
    body: "The API verifies the Supabase JWT against the project's JWKS, then loads the role from profiles. A request cannot claim a role the account does not have.",
    evidence: "api/app/auth.py · require_user(), require_admin()",
  },
  {
    icon: ScrollText,
    title: "Tamper-evident audit trail",
    body: "Each entry stores the hash of the previous entry. Recomputing the chain surfaces any edit or deletion, and the audit page runs that check on demand.",
    evidence: "api/app/audit.py · /audit/verify",
  },
  {
    icon: ShieldCheck,
    title: "Untrusted retrieved text",
    body: "Retrieved passages are data, not instructions: the prompt says so, the answer is verified against the cited chunks, and prompt-injection probes are part of the evaluation set.",
    evidence: "api/app/pipeline.py · verify_answer() · eval/golden_set.jsonl",
  },
  {
    icon: KeyRound,
    title: "Least-privilege secrets",
    body: "Only the anon key reaches the browser. The service-role key and the model API keys live on the API host, and the repository contains names, never values.",
    evidence: ".env.example · docs/DEPLOY.md",
  },
  {
    icon: FileCheck2,
    title: "Supply chain checks",
    body: "CI runs a dependency audit, a secret scan over full history, CodeQL for the web and the API, a Trivy image scan, a CycloneDX SBOM, OpenSSF Scorecard and a failure on any commit that carries an attribution trailer. Every action is pinned to a commit SHA.",
    evidence: ".github/workflows/ci.yml · codeql.yml · SECURITY.md",
  },
];

export default function TrustPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-14">
      <span className="chip chip-accent mono">security</span>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">What this system can prove</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--text-muted)]">
        Each control below points at the code that implements it. A control without a test is a
        claim, so the evaluation suite treats cross-role leakage as a hard failure.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {controls.map((control) => (
          <article key={control.title} className="panel p-5">
            <control.icon size={16} className="text-[var(--accent)]" />
            <h2 className="mt-3 text-sm font-semibold">{control.title}</h2>
            <p className="mt-2 text-[13px] leading-6 text-[var(--text-muted)]">{control.body}</p>
            <p className="mono mt-3 text-[10px] leading-5 text-[var(--text-muted)]">
              {control.evidence}
            </p>
          </article>
        ))}
      </div>
      <div className="panel-2 mt-6 p-5 text-sm leading-7 text-[var(--text-muted)]">
        <p>
          Found something? The disclosure policy and contact address are in{" "}
          <span className="mono text-[var(--text)]">SECURITY.md</span> and{" "}
          <a className="underline decoration-dotted" href="/.well-known/security.txt">
            /.well-known/security.txt
          </a>
          .
        </p>
        <p className="mt-2">
          The corpus is public GitLab Handbook content under CC BY-SA 4.0, plus synthetic
          confidential documents that exist only to demonstrate access control. See{" "}
          <a className="underline decoration-dotted" href="/credits">
            credits
          </a>{" "}
          and{" "}
          <a className="underline decoration-dotted" href={site.handbook.licenseUrl}>
            the licence
          </a>
          .
        </p>
      </div>
    </div>
  );
}
