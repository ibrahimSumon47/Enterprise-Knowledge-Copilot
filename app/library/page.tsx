"use client";

import { FileText, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

type DocumentRow = {
  id: string;
  title: string;
  access_level: string;
  department: string | null;
  source_url: string | null;
  license: string;
  attribution: string;
  is_synthetic?: boolean;
  status?: string;
  error?: string | null;
  progress?: number;
};

type Me = { email: string; role: string };

const API = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com").replace(/\/$/, "");

const LEVEL_LABEL: Record<string, string> = {
  public: "Public",
  employee: "Employees",
  department: "Department",
  confidential: "Confidential",
};

export default function LibraryPage() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [role, setRole] = useState<string>("employee");
  const [uploading, setUploading] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);

  useEffect(() => {
    const supabase = supabaseBrowser();
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) return;
      setToken(data.session.access_token);
      setEmail(data.session.user.email ?? null);
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([apiFetch<{ documents: DocumentRow[] }>("/documents", token), apiFetch<Me>("/me", token)])
      .then(([docs, me]) => {
        if (!active) return;
        setDocuments(docs.documents ?? []);
        setRole(me.role);
      })
      .catch((caught) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Could not load the library");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return documents;
    return documents.filter((document) =>
      `${document.title} ${document.access_level} ${document.department ?? ""}`
        .toLowerCase()
        .includes(needle),
    );
  }, [documents, query]);

  const sample = email === "guest@ekc.local";
  const canManage = !sample && ["owner", "admin"].includes(role);

  async function refresh() {
    if (!token) return;
    const data = await apiFetch<{ documents: DocumentRow[] }>("/documents", token);
    setDocuments(data.documents ?? []);
  }

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setUploadNote("Choose a file first.");
      return;
    }
    setUploading(true);
    setUploadNote("Uploading…");
    try {
      const response = await fetch(`${API}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? `Upload failed (${response.status})`);
      for (let attempt = 0; attempt < 60; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const status = await apiFetch<DocumentRow>(`/documents/${data.document_id}`, token);
        if (status.status === "failed") {
          setUploadNote(status.error ?? "Indexing failed");
          break;
        }
        if (status.status === "active") {
          setUploadNote("Indexed and ready to answer from.");
          break;
        }
        setUploadNote(`Indexing… ${status.progress ?? 0}%`);
      }
      formElement.reset();
      await refresh();
    } catch (caught) {
      setUploadNote(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function remove(document: DocumentRow) {
    if (!token || !window.confirm(`Delete ${document.title} and its stored original?`)) return;
    try {
      await apiFetch(`/documents/${document.id}`, token, { method: "DELETE" });
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Delete failed");
    }
  }

  async function reindex(document: DocumentRow) {
    if (!token) return;
    try {
      await apiFetch(`/documents/${document.id}/reindex`, token, { method: "POST" });
      setUploadNote("Re-index queued.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Re-index failed");
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-muted)]">
            {sample ? "Sample workspace" : "Workspace"}
          </p>
          <h1 className="mt-2 text-2xl font-semibold">Document library</h1>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-muted)]">
            {sample
              ? "A read-only set of public handbook documents. Ask about any of them in Chat; open a citation to read the passage."
              : "Everything the copilot can answer from, filtered to the permissions of your role and department."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sample ? <span className="chip text-[11px]">Read only</span> : null}
          <span className="text-xs text-[var(--text-muted)]">
            {documents.length} {documents.length === 1 ? "document" : "documents"}
          </span>
        </div>
      </header>

      <div className="relative mt-6">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          size={16}
        />
        <label className="sr-only" htmlFor="library-search">
          Search the library
        </label>
        <input
          className="input pl-9"
          id="library-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by title, department or access level"
          type="search"
          value={query}
        />
      </div>

      {error ? (
        <p className="mt-4 rounded-lg border border-[var(--warn)] px-3 py-2 text-xs text-[var(--warn)]">
          {error}
        </p>
      ) : null}

      {canManage ? (
        <form className="panel mt-4 flex flex-wrap items-end gap-3 p-4" onSubmit={upload}>
          <div className="min-w-56 flex-1">
            <label className="block text-xs text-[var(--text-muted)]" htmlFor="upload-file">
              Upload a document (PDF, DOCX, MD, HTML, TXT · 10 MB)
            </label>
            <input
              accept=".pdf,.docx,.md,.markdown,.html,.htm,.txt"
              className="input mt-1"
              id="upload-file"
              name="file"
              required
              type="file"
            />
          </div>
          <button className="btn btn-primary" disabled={uploading} type="submit">
            {uploading ? <Loader2 className="animate-spin" size={15} /> : null}
            Upload
          </button>
          {uploadNote ? (
            <p className="w-full text-xs text-[var(--text-muted)]" role="status">
              {uploadNote}
            </p>
          ) : null}
        </form>
      ) : null}

      <div className="panel mt-5 overflow-hidden">
        {loading ? (
          <div className="divide-y divide-[var(--border)]">
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="flex items-center gap-3 px-4 py-4">
                <div className="skeleton h-8 w-8 rounded-md" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3 w-1/3" />
                  <div className="skeleton h-3 w-1/5" />
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <FileText className="mx-auto text-[var(--text-muted)]" size={22} />
            <h2 className="mt-3 text-sm font-semibold">
              {documents.length === 0 ? "No documents yet" : "No document matches that search"}
            </h2>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-7 text-[var(--text-muted)]">
              {documents.length === 0
                ? "An administrator can upload PDF, Word, Markdown, HTML or text documents and index them for answers."
                : "Try a shorter phrase, or search for the department that owns the policy."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {filtered.map((document) => (
              <li key={document.id} className="flex flex-wrap items-start gap-3 px-4 py-4">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--panel-2)]">
                  <FileText size={15} className="text-[var(--text-muted)]" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{document.title}</p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    {document.attribution}
                    {document.department ? ` · ${document.department}` : ""}
                  </p>
                  {document.status === "failed" ? (
                    <p className="mt-1 text-xs text-[var(--danger)]">
                      Indexing failed: {document.error ?? "unknown reason"}
                    </p>
                  ) : null}
                  {document.status === "processing" ? (
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      Indexing… {document.progress ?? 0}%
                    </p>
                  ) : null}
                </div>
                <span className="chip text-[10px]">
                  {LEVEL_LABEL[document.access_level] ?? document.access_level}
                </span>
                {canManage && !document.is_synthetic ? (
                  <div className="flex gap-2">
                    <button
                      className="text-xs underline decoration-dotted"
                      onClick={() => reindex(document)}
                      type="button"
                    >
                      Re-index
                    </button>
                    <button
                      className="text-xs text-[var(--danger)] underline decoration-dotted"
                      onClick={() => remove(document)}
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {token && !loading ? null : (
        <p className="mt-4 flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <Loader2 className="animate-spin" size={12} /> Loading your permissions…
        </p>
      )}

      <p className="mt-6 text-xs leading-6 text-[var(--text-muted)]">
        A document you cannot see is not returned by the search at all. Titles and snippets outside
        your access level are never sent to the browser.
      </p>
    </div>
  );
}
