"use client";

import { Database, Loader2, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { isStaleCheckpoint } from "@/lib/audit";
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

type ChainCheck = {
  entries: number;
  intact: boolean;
  broken_ids: number[];
  head: string;
  anchor_id?: number | null;
  anchored_at_genesis?: boolean;
  complete?: boolean;
  first_id?: number | null;
  last_id?: number | null;
  mode?: "full" | "incremental";
  checkpoint_id?: number | null;
  verified_now?: number;
  verified_at?: string | null;
  checkpoint_at?: string | null;
};

type DocumentRow = {
  id: string;
  title: string;
  access_level: string;
  department: string | null;
  is_synthetic?: boolean;
};

function isoClock(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function isoAge(value?: string | null) {
  if (!value) return null;
  const elapsed = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(elapsed)) return null;
  const minutes = Math.max(0, Math.floor(elapsed / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.floor(hours / 24)} d ago`;
}

const LEVELS = ["public", "employee", "department", "confidential"];
const DEPARTMENTS = ["engineering", "security", "people", "finance"];

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [chain, setChain] = useState<ChainCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [saving, setSaving] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [fullPass, setFullPass] = useState(false);
  const checkpointStale = chain ? isStaleCheckpoint(chain.checkpoint_at) : false;

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
      setChain(await apiFetch<ChainCheck>("/audit/verify", token, { method: "POST" }));
      const docs = await apiFetch<{ documents: DocumentRow[] }>("/documents", token);
      setDocuments(docs.documents ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function verifyChain(full: boolean) {
    if (!token) return;
    setVerifying(true);
    setError(null);
    try {
      setChain(
        await apiFetch<ChainCheck>(`/audit/verify${full ? "?full=true" : ""}`, token, {
          method: "POST",
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  }

  async function saveDocument(row: DocumentRow, accessLevel: string, department: string | null) {
    if (!token) return;
    setSaving(row.id);
    setError(null);
    try {
      await apiFetch(`/documents/${row.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({ access_level: accessLevel, department }),
      });
      setDocuments((current) =>
        current.map((item) =>
          item.id === row.id ? { ...item, access_level: accessLevel, department } : item,
        ),
      );
      const audit = await apiFetch<AuditPage>("/audit?limit=25", token);
      setEntries(audit.entries ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update the document");
    } finally {
      setSaving(null);
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
        <div className="border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">Document access</h2>
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
            Changing a level writes an audit entry and applies on the next retrieval query.
          </p>
        </div>
        <div className="max-h-80 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2">document</th>
                <th className="px-4 py-2">level</th>
                <th className="px-4 py-2">department</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {documents.slice(0, 60).map((row) => (
                <DocumentRowEditor
                  busy={saving === row.id}
                  key={row.id}
                  onSave={(level, department) => void saveDocument(row, level, department)}
                  row={row}
                />
              ))}
              {documents.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-[var(--text-muted)]" colSpan={4}>
                    Press Refresh to load documents.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold">Audit trail</h2>
            {chain ? (
              <span
                title={
                  (chain.mode === "incremental"
                    ? `Resumed from checkpoint #${chain.checkpoint_id ?? "?"}; ${chain.verified_now ?? 0} new rows hashed this run.`
                    : `Re-hashed the whole log from genesis; ${chain.verified_now ?? chain.entries} rows hashed this run.`) +
                  (checkpointStale
                    ? " The checkpoint has not advanced in over six hours; a full pass re-checks the whole log."
                    : "")
                }
                className={`mono flex items-center gap-1 text-[11px] ${
                  chain.intact ? "text-[var(--ok)]" : "text-[var(--danger)]"
                }`}
              >
                <ShieldCheck size={13} />
                {chain.intact ? (
                  <>
                    {`chain ok · ${chain.entries} entries · ${
                      chain.mode === "incremental"
                        ? `checkpoint #${chain.checkpoint_id ?? "?"} (+${chain.verified_now ?? 0})`
                        : "full pass"
                    }${chain.complete === false ? " · partial log" : ""}${
                      chain.anchored_at_genesis === false ? " · prefix missing" : ""
                    }`}
                    {checkpointStale ? (
                      <>
                        <span className="text-[var(--warn)]"> · </span>
                        <button
                          className="text-[var(--warn)] underline decoration-dotted underline-offset-2 disabled:opacity-60"
                          disabled={verifying || !token}
                          onClick={() => void verifyChain(true)}
                          title="Re-hash the whole log from genesis now"
                          type="button"
                        >
                          checkpoint stale
                        </button>
                      </>
                    ) : null}
                  </>
                ) : (
                  `chain broken · ${chain.broken_ids.length} entries`
                )}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <label
              className="mono flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]"
              title="Re-hash the whole log from genesis instead of resuming from the checkpoint"
            >
              <input
                checked={fullPass}
                className="accent-[var(--accent)]"
                onChange={(event) => setFullPass(event.target.checked)}
                type="checkbox"
              />
              full pass
            </label>
            <button
              className="btn"
              disabled={verifying || !token}
              onClick={() => void verifyChain(fullPass)}
              type="button"
            >
              {verifying ? (
                <Loader2 className="animate-spin" size={14} />
              ) : (
                <ShieldCheck size={14} />
              )}
              {verifying ? "Verifying…" : "Re-verify"}
            </button>
          </div>
        </div>
        {chain ? (
          <p className="mono border-b border-[var(--border)] px-4 py-2 text-[10px] text-[var(--text-muted)]">
            last verified {isoClock(chain.verified_at) ?? "—"} · checkpoint{" "}
            {chain.checkpoint_id
              ? `#${chain.checkpoint_id} advanced ${isoAge(chain.checkpoint_at) ?? "—"}`
              : "not created yet"}
          </p>
        ) : null}
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

function DocumentRowEditor({
  row,
  busy,
  onSave,
}: {
  row: DocumentRow;
  busy: boolean;
  onSave: (level: string, department: string | null) => void;
}) {
  const [level, setLevel] = useState(row.access_level);
  const [department, setDepartment] = useState(row.department ?? "");
  const dirty =
    level !== row.access_level || (level === "department" && department !== (row.department ?? ""));

  return (
    <tr>
      <td className="max-w-[22rem] truncate px-4 py-2" title={row.title}>
        {row.title}
        {row.is_synthetic ? (
          <span className="mono ml-2 text-[10px] text-[var(--text-muted)]">synthetic</span>
        ) : null}
      </td>
      <td className="px-4 py-2">
        <select
          aria-label={`Access level for ${row.title}`}
          className="mono rounded border border-[var(--border)] bg-transparent px-2 py-1 text-[11px]"
          onChange={(event) => setLevel(event.target.value)}
          value={level}
        >
          {LEVELS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2">
        <select
          aria-label={`Department for ${row.title}`}
          className="mono rounded border border-[var(--border)] bg-transparent px-2 py-1 text-[11px]"
          disabled={level !== "department"}
          onChange={(event) => setDepartment(event.target.value)}
          value={department}
        >
          <option value="">—</option>
          {DEPARTMENTS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2 text-right">
        <button
          className="btn"
          disabled={!dirty || busy || (level === "department" && !department)}
          onClick={() => onSave(level, level === "department" ? department : null)}
          type="button"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </td>
    </tr>
  );
}
