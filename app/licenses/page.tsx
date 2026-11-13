import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Licenses and sources",
  description: "Where the sample documents come from and what they may be used for.",
};

const models = [
  { name: "bge-small-en-v1.5", role: "passage and question embeddings", licence: "MIT" },
  { name: "ms-marco-TinyBERT cross-encoder", role: "ranking the retrieved passages", licence: "Apache-2.0" },
  { name: "ONNX Runtime", role: "CPU inference", licence: "MIT" },
];

export default function LicensesPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16">
      <p className="mono text-xs uppercase tracking-[0.18em] text-[var(--accent)]">
        Licenses and sources
      </p>
      <h1 className="mt-3 text-3xl font-semibold">Attribution.</h1>

      <section className="mt-10">
        <h2 className="text-base font-semibold">Sample documents</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
          The sample workspace uses documents from the{" "}
          <a className="underline decoration-dotted" href={site.handbook.url}>
            {site.handbook.title}
          </a>
          , licensed{" "}
          <a className="underline decoration-dotted" href={site.handbook.licenseUrl}>
            {site.handbook.license}
          </a>
          . Attribution, licence and a link to the source are stored with every document and shown
          in the source panel next to a citation. The documents remain under their original licence;
          this product does not relicense them.
        </p>
        <p className="mt-3 text-sm leading-7 text-[var(--text-muted)]">
          Workspaces may also contain internal documents uploaded by their administrators. Those
          documents stay with the workspace that uploaded them.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--border)] pt-6">
        <h2 className="text-base font-semibold">Models</h2>
        <ul className="mt-3 space-y-3">
          {models.map((model) => (
            <li key={model.name} className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
              <span className="text-sm">
                {model.name} <span className="text-[var(--text-muted)]">· {model.role}</span>
              </span>
              <span className="mono text-xs text-[var(--text-muted)]">{model.licence}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10 border-t border-[var(--border)] pt-6">
        <h2 className="text-base font-semibold">Software</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
          Next.js, FastAPI, LangGraph, Supabase (Postgres, pgvector, Auth, Row Level Security) and
          Tailwind CSS, under their respective open-source licences.
        </p>
      </section>
    </div>
  );
}
