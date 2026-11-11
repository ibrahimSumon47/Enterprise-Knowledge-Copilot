"use client";

import { Database, Loader2, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

type Job = {
  id: string;
  status: string;
  progress: number;
  stats?: Record<string, number>;
  error?: string | null;
  updated_at?: string;
};

type Entry = {
  id: string;
  action: string;
  actor_role: string | null;
  outcome: string | null;
  created_at: string;
};

type AuditPage = { entries: Entry[] };

type ChainCheck = { ok: boolean; checked?: number; broken_at?: string | null };

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [chain, setChain] = useState<ChainCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const supabase = supabaseBrowser();
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) return;
      setToken(data.session.access_token);
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<{ role: string }>("/me", token)
      .then((me) => setRole(me.role))
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load profile"));
  }, [token]);

  async function refresh() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const audit = await apiFetch<AuditPage>("/audit?limit=25", token);
      setEntries(audit.entries ?? []);
      setChain(await apiFetch<ChainCheck>("/audit/verify", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function startIngest() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const started = await apiFetch<{ job_id: string; status: string }>("/admin/ingest", token, {
        method: "POST",
      });
      setJob({ id: started.job_id, status: started.status, progress: 0 });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start ingestion");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!job || !token || job.status === "done" || job.status === "failed") return;
    const timer = setInterval(() => {
      apiFetch<Job>(`/admin/ingest/${job.id}`, token)
        .then(setJob)
        .catch(() => undefined);
    }, 4000);
    return () => clearInterval(timer);
  }, [job, token]);

  if (role && role !== "admin") {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-16">
        <h1 className="text-2xl font-semibold">Administrators only</h1>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          This account has the <span className="mono">{role}</span> role. Sign in as{" "}
          <span className="mono">admin@ekc.local</span> to manage ingestion and read the audit log.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-12">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Operations</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Corpus ingestion, audit trail and chain verification.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={refresh} type="button">
            {busy ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />} Refresh
          </button>
          <button className="btn btn-primary" onClick={startIngest} type="button">
            <Database size={14} /> Run ingestion
          </button>
        </div>
      </header>

      {error ? (
        <p className="flex items-center gap-2 rounded-lg border border-[var(--warn)] px-3 py-2 text-xs text-[var(--warn)]">
          <TriangleAlert size={14} /> {error}
        </p>
      ) : null}

      {job ? (
        <section className="panel p-5">
          <h2 className="text-sm font-semibold">Ingestion job</h2>
          <p className="mono mt-2 text-[11px] text-[var(--text-muted)]">{job.id}</p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--panel-2)]">
            <div
              className="h-full bg-[var(--accent)] transition-all"
              style={{ width: `${Math.min(100, Math.max(0, job.progress))}%` }}
            />
          </div>
          <p className="mono mt-2 text-[11px] text-[var(--text-muted)]">
            {job.status} · {job.progress}%{" "}
            {job.stats?.documents_indexed ? `· ${job.stats.documents_indexed} docs` : ""}{" "}
            {job.stats?.chunks_indexed ? `· ${job.stats.chunks_indexed} chunks` : ""}
          </p>
          {job.error ? (
            <p className="mt-2 text-[11px] text-[var(--danger)]">{job.error}</p>
          ) : null}
        </section>
      ) : null}

      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">Audit trail</h2>
          {chain ? (
            <span
              className={`mono flex items-center gap-1 text-[11px] ${
                chain.ok ? "text-[var(--ok)]" : "text-[var(--danger)]"
              }`}
            >
              <ShieldCheck size={13} />
              {chain.ok ? `chain ok · ${chain.checked ?? 0} entries` : "chain broken"}
            </span>
          ) : null}
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-[var(--panel-2)] text-[var(--text-muted)]">
            <tr>
              <th className="px-4 py-2 font-medium" scope="col">
                Action
              </th>
              <th className="px-4 py-2 font-medium" scope="col">
                Role
              </th>
              <th className="px-4 py-2 font-medium" scope="col">
                Outcome
              </th>
              <th className="px-4 py-2 font-medium" scope="col">
                When
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td className="px-4 py-4 text-xs text-[var(--text-muted)]" colSpan={4}>
                  Press refresh to load the latest entries.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr className="border-t border-[var(--border)]" key={entry.id}>
                  <td className="mono px-4 py-2 text-[11px]">{entry.action}</td>
                  <td className="px-4 py-2 text-[11px]">{entry.actor_role ?? "—"}</td>
                  <td className="px-4 py-2 text-[11px]">{entry.outcome ?? "—"}</td>
                  <td className="mono px-4 py-2 text-[10px] text-[var(--text-muted)]">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
