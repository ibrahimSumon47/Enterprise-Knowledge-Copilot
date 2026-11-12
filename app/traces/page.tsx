"use client";

import { Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

type Entry = {
  id: number;
  action: string;
  actor_role: string | null;
  outcome: string | null;
  created_at: string;
  detail?: {
    reason?: string;
    provider?: string;
    latency_ms?: number;
    confidence?: string;
    citations?: number;
  } | null;
};

type Health = {
  rss_mb?: number;
  rerank_state?: { loaded: boolean; candidates: number; max_length: number };
  providers?: { calls: number; hedged: number; backup_won: number; failed_over: number };
};

export default function TracesPage() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const supabase = supabaseBrowser();
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setToken(data.session.access_token);
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<{ role: string }>("/me", token)
      .then((me) => setRole(me.role))
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load profile"));
  }, [token]);

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const audit = await apiFetch<{ entries: Entry[] }>("/audit?limit=100", token);
      setEntries((audit.entries ?? []).filter((entry) => entry.action === "chat.question"));
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/health`, {
        signal: AbortSignal.timeout(20000),
      });
      if (response.ok) setHealth((await response.json()) as Health);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    if (role !== "admin") return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [role, load]);

  if (role && role !== "admin") {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-16">
        <h1 className="text-2xl font-semibold">Administrators only</h1>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          This account has the <span className="mono">{role}</span> role; traces are admin-only.
        </p>
      </div>
    );
  }

  const refusals = entries.filter((entry) => entry.outcome === "refused");
  const reasons = refusals.reduce<Record<string, number>>((counts, entry) => {
    const reason = entry.detail?.reason || "no reason recorded";
    counts[reason] = (counts[reason] ?? 0) + 1;
    return counts;
  }, {});
  const latencies = entries
    .map((entry) => entry.detail?.latency_ms ?? 0)
    .filter((value) => value > 0)
    .sort((a, b) => a - b);
  const p95 = latencies.length ? latencies[Math.floor(latencies.length * 0.95) - 1] : 0;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-12">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Traces</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            The last 100 questions from the audit log: provider, latency per stage, refusal reasons.
          </p>
        </div>
        <button className="btn" disabled={!token || busy} onClick={() => void load()} type="button">
          {busy ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />} Refresh
        </button>
      </header>

      {error ? (
        <p className="flex items-center gap-2 rounded-lg border border-[var(--warn)] px-3 py-2 text-xs text-[var(--warn)]">
          <ShieldAlert size={14} /> {error}
        </p>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-4">
        {[
          { label: "questions", value: entries.length },
          { label: "refused", value: refusals.length },
          { label: "p95 latency", value: p95 ? `${p95} ms` : "—" },
          { label: "rss", value: health?.rss_mb ? `${health.rss_mb} MB` : "—" },
        ].map((card) => (
          <div key={card.label} className="panel p-4">
            <p className="mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">{card.label}</p>
            <p className="mt-1 text-xl font-semibold">{card.value}</p>
          </div>
        ))}
      </section>

      <section className="panel p-4">
        <h2 className="text-sm font-semibold">Provider path</h2>
        <p className="mono mt-2 text-xs text-[var(--text-muted)]">
          calls {health?.providers?.calls ?? 0} · hedged {health?.providers?.hedged ?? 0} · backup won{" "}
          {health?.providers?.backup_won ?? 0} · primary failed {health?.providers?.failed_over ?? 0}
        </p>
        <p className="mono mt-1 text-xs text-[var(--text-muted)]">
          reranker {health?.rerank_state?.loaded ? "loaded" : "cold"} ·{" "}
          {health?.rerank_state?.candidates ?? 0} candidates ·{" "}
          {health?.rerank_state?.max_length ?? 0} tokens
        </p>
      </section>

      <section className="panel overflow-hidden">
        <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">Refusal reasons</h2>
        <ul className="divide-y divide-[var(--border)]">
          {Object.keys(reasons).length === 0 ? (
            <li className="px-4 py-3 text-xs text-[var(--text-muted)]">No refusals in this window.</li>
          ) : (
            Object.entries(reasons)
              .sort((a, b) => b[1] - a[1])
              .map(([reason, count]) => (
                <li key={reason} className="flex items-center justify-between px-4 py-2 text-xs">
                  <span>{reason}</span>
                  <span className="mono text-[var(--text-muted)]">{count}</span>
                </li>
              ))
          )}
        </ul>
      </section>

      <section className="panel overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
            <tr>
              <th className="px-4 py-2">when</th>
              <th className="px-4 py-2">role</th>
              <th className="px-4 py-2">outcome</th>
              <th className="px-4 py-2">provider</th>
              <th className="px-4 py-2">latency</th>
              <th className="px-4 py-2">reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {entries.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-[var(--text-muted)]" colSpan={6}>
                  {token ? "No chat traces yet." : "Sign in as admin to load traces."}
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono px-4 py-2 text-[var(--text-muted)]">
                    {new Date(entry.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-4 py-2">{entry.actor_role ?? "—"}</td>
                  <td className="px-4 py-2">{entry.outcome ?? "—"}</td>
                  <td className="px-4 py-2">{entry.detail?.provider ?? "—"}</td>
                  <td className="mono px-4 py-2">{entry.detail?.latency_ms ?? "—"} ms</td>
                  <td className="px-4 py-2 text-[var(--text-muted)]">{entry.detail?.reason || "answered"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
