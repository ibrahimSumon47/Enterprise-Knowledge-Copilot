"use client";

import { Check, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import { site } from "@/lib/site";

const api = site.apiBaseUrl.replace(/\/$/, "");

async function token(): Promise<string> {
  const { data } = await supabaseBrowser().auth.getSession();
  const value = data.session?.access_token;
  if (!value) throw new Error("Your session expired. Sign in again.");
  return value;
}

async function call(path: string, init: RequestInit = {}) {
  const response = await fetch(`${api}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${await token()}`,
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${(await response.text()).slice(0, 160)}`);
  }
  return response.json();
}

export default function OnboardingPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [named, setNamed] = useState(false);
  const [added, setAdded] = useState(false);
  const [busy, setBusy] = useState<"name" | "document" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    call("/onboarding")
      .then((data) => {
        setWorkspace(data.workspace);
        setName(data.workspace);
        setEmail(data.email);
        if (data.workspace && data.workspace !== "My workspace") setNamed(true);
      })
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Could not load onboarding"),
      );
  }, []);

  async function saveName(event: React.FormEvent) {
    event.preventDefault();
    setBusy("name");
    setError(null);
    try {
      const data = await call("/onboarding/workspace", {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      setWorkspace(data.name);
      setNamed(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not rename the workspace");
    } finally {
      setBusy(null);
    }
  }

  async function addDocument(event: React.FormEvent) {
    event.preventDefault();
    setBusy("document");
    setError(null);
    try {
      await call("/onboarding/document", {
        method: "POST",
        body: JSON.stringify({ title, text }),
      });
      setAdded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add the document");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-16">
      <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Set up</p>
      <h1 className="mt-2 text-2xl font-semibold">{workspace || "Your workspace"}</h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        Three steps, then you can ask questions with citations. Signed in as {email || "…"}.
      </p>

      <section className="panel mt-8 p-6" aria-labelledby="step-name">
        <h2 className="flex items-center gap-2 text-sm font-semibold" id="step-name">
          {named ? <Check size={15} className="text-[var(--accent)]" /> : "1."} Name the
          workspace
        </h2>
        <form className="mt-4 flex gap-2" onSubmit={saveName}>
          <input
            aria-label="Workspace name"
            className="input"
            maxLength={80}
            minLength={2}
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
          <button className="btn btn-primary" disabled={busy !== null} type="submit">
            {busy === "name" ? <Loader2 className="animate-spin" size={15} /> : null}
            Save
          </button>
        </form>
      </section>

      <section className="panel mt-4 p-6" aria-labelledby="step-document">
        <h2 className="flex items-center gap-2 text-sm font-semibold" id="step-document">
          {added ? <Check size={15} className="text-[var(--accent)]" /> : "2."} Add the
          first document
        </h2>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Paste a policy or handbook section. Browser file upload arrives in the next slice.
        </p>
        <form className="mt-4 space-y-3" onSubmit={addDocument}>
          <input
            aria-label="Document title"
            className="input"
            maxLength={160}
            minLength={2}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Expense policy"
            required
            value={title}
          />
          <textarea
            aria-label="Document text"
            className="input min-h-40"
            minLength={40}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste at least a paragraph of the document…"
            required
            value={text}
          />
          <button className="btn btn-primary" disabled={busy !== null} type="submit">
            {busy === "document" ? <Loader2 className="animate-spin" size={15} /> : null}
            Add document
          </button>
        </form>
      </section>

      <section className="panel mt-4 p-6" aria-labelledby="step-question">
        <h2 className="text-sm font-semibold" id="step-question">
          3. Ask the first question
        </h2>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Answers cite the passages they used and refuse when the workspace has no evidence.
        </p>
        <button
          className="btn btn-primary mt-4"
          disabled={!added}
          onClick={() => router.push("/chat")}
          type="button"
        >
          Ask a question
        </button>
      </section>

      {error ? (
        <p
          className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]"
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}
