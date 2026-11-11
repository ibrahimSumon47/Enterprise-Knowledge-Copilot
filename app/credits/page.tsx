import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Credits and licences" };

const models = [
  {
    name: "paraphrase-multilingual-MiniLM-L12-v2",
    role: "passage and query embeddings (384 dimensions)",
    licence: "Apache-2.0",
    href: "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  },
  {
    name: "ms-marco MiniLM cross-encoders",
    role: "candidate reranking",
    licence: "Apache-2.0",
    href: "https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-12-v2",
  },
  {
    name: "fastembed · flashrank · ONNX Runtime",
    role: "CPU inference without PyTorch",
    licence: "Apache-2.0 / MIT",
    href: "https://onnxruntime.ai/",
  },
];

export default function CreditsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-14">
      <span className="chip chip-accent mono">attribution</span>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">Credits and licences</h1>

      <section className="mt-8 space-y-3">
        <h2 className="text-sm font-semibold">Corpus</h2>
        <p className="text-sm leading-7 text-[var(--text-muted)]">
          Most documents come from the{" "}
          <a className="underline decoration-dotted" href={site.handbook.url}>
            {site.handbook.title}
          </a>
          , used under{" "}
          <a className="underline decoration-dotted" href={site.handbook.licenseUrl}>
            {site.handbook.license}
          </a>
          . Each chunk stores its source URL, licence and attribution string, so the UI can always
          show where a passage came from. Documents from the handbook remain under the same licence;
          this project does not relicense them.
        </p>
        <p className="text-sm leading-7 text-[var(--text-muted)]">
          A small set of confidential documents is synthetic: it exists to prove that the access
          model works, is marked <span className="mono">synthetic</span> in metadata, and describes
          no real person, customer or system.
        </p>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="text-sm font-semibold">Models</h2>
        <ul className="space-y-3">
          {models.map((model) => (
            <li key={model.name} className="panel-2 p-4">
              <p className="text-sm">{model.name}</p>
              <p className="mt-1 text-[12px] text-[var(--text-muted)]">{model.role}</p>
              <p className="mono mt-2 text-[10px] text-[var(--text-muted)]">
                {model.licence} ·{" "}
                <a className="underline decoration-dotted" href={model.href}>
                  model card
                </a>
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="text-sm font-semibold">Software</h2>
        <p className="text-sm leading-7 text-[var(--text-muted)]">
          Next.js, FastAPI, LangGraph, Supabase (Postgres, pgvector, Auth, Row Level Security),
          Tailwind CSS. The language models are reached through a provider interface: Groq first,
          Gemini as the fallback, and a deterministic mock for tests so CI never spends a token.
        </p>
      </section>
    </div>
  );
}
