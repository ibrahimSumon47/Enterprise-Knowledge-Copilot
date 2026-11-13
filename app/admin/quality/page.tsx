"use client";

import { Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import Link from "next/link";
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
    latency_ms?: number;
    confidence?: string;
    citations?: number;
  } | null;
};

type EvalRun = {
  id: string;
  mode: string;
  created_at: string;
  passed: boolean;
  metrics: Record<string, unknown>;
};

const METRIC_LABEL: Record<string, string> = {
  hit_at_k: "Right passage in the retrieved set",
  "hit@k": "Right passage in the retrieved set",
  mrr: "Position of the first correct passage",
  citation_precision: "Citations that support the sentence",
  refusal_accuracy: "Unanswerable questions refused",
  p95_latency_ms: "95th percentile response time",
  p95: "95th percentile response time",
};

const REASON_LABEL: Record<string, string> = {
  "model judged the sources insufficient": "Documents did not cover it",
  "model answered without declaring citations": "Answer could not be checked",
  "model reply was not the required JSON": "Answer could not be read",
  "citation markers do not match the declared sources": "Citation check failed",
  "answer has no citations": "Answer had no sources",
  "answer does not overlap its sources": "Answer drifted from its sources",
  "too many uncited sentences": "Parts of the answer had no source",
};

function prettyReason(reason: string | undefined) {
  if (!reason) return "Answered";
  return REASON_LABEL[reason] ?? "Not answered";
}

export default function QualityPage() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
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
      setRuns(await apiFetch<EvalRun[]>("/eval-runs", token));
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
          Answer quality and performance are available to workspace administrators.
        </p>
      </div>
    );
  }

  const refusals = entries.filter((entry) => entry.outcome === "refused");
  const reasons = refusals.reduce<Record<string, number>>((counts, entry) => {
    const reason = entry.detail?.reason || "not answered";
    counts[reason] = (counts[reason] ?? 0) + 1;
    return counts;
  }, {});
  const latencies = entries
    .map((entry) => entry.detail?.latency_ms ?? 0)
    .filter((value) => value > 0)
    .sort((a, b) => a - b);
  const p95 = latencies.length ? latencies[Math.floor(latencies.length * 0.95) - 1] : 0;
  const latest = runs[0];

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 px-4 py-10">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-muted)]">
            <Link className="hover:text-[var(--text)]" href="/admin">
              Administration
            </Link>{" "}
            / Quality
          </p>
          <h1 className="mt-2 text-2xl font-semibold">Answer quality</h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-muted)]">
            How often answers are grounded in the documents, and how quickly they arrive.
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

      <section aria-labelledby="quality" className="panel p-6">
        <h2 className="text-base font-semibold" id="quality">
          Answer quality
        </h2>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Last measured run{latest ? ` · ${new Date(latest.created_at).toLocaleDateString()}` : ""}
        </p>
        {latest ? (
          <dl className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(latest.metrics).map(([key, value]) => (
              <div key={key}>
                <dt className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                  {METRIC_LABEL[key] ?? key.replaceAll("_", " ")}
                </dt>
                <dd className="mono mt-1 text-lg">{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-4 text-sm text-[var(--text-muted)]">
            No measured run is recorded for this workspace yet. The next scheduled run writes its
            results here.
          </p>
        )}
      </section>

      <section aria-labelledby="performance" className="space-y-4">
        <h2 className="text-base font-semibold" id="performance">
          Performance
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: "Questions, last 100", value: entries.length },
            { label: "Not answered", value: refusals.length },
            { label: "95th percentile", value: p95 ? `${(p95 / 1000).toFixed(1)} s` : "—" },
          ].map((card) => (
            <div key={card.label} className="panel p-4">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                {card.label}
              </p>
              <p className="mono mt-1 text-xl font-semibold">{card.value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="panel overflow-hidden">
          <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">
            Why answers were withheld
          </h2>
          <ul className="divide-y divide-[var(--border)]">
            {Object.keys(reasons).length === 0 ? (
              <li className="px-4 py-3 text-xs text-[var(--text-muted)]">
                No withheld answers in this window.
              </li>
            ) : (
              Object.entries(reasons)
                .sort((a, b) => b[1] - a[1])
                .map(([reason, count]) => (
                  <li key={reason} className="flex items-center justify-between gap-3 px-4 py-2 text-xs">
                    <span>{prettyReason(reason)}</span>
                    <span className="mono text-[var(--text-muted)]">{count}</span>
                  </li>
                ))
            )}
          </ul>
        </div>

        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Recent questions and their response times</caption>
            <thead className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Outcome</th>
                <th className="px-4 py-2">Response</th>
                <th className="px-4 py-2">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {entries.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-[var(--text-muted)]" colSpan={5}>
                    {token ? "No questions yet." : "Sign in as an administrator to load this view."}
                  </td>
                </tr>
              ) : (
                entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono px-4 py-2 text-[var(--text-muted)]">
                      {new Date(entry.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2">{entry.actor_role ?? "—"}</td>
                    <td className="px-4 py-2">{entry.outcome === "refused" ? "Not answered" : "Answered"}</td>
                    <td className="mono px-4 py-2">{entry.detail?.latency_ms ?? "—"} ms</td>
                    <td className="px-4 py-2 text-[var(--text-muted)]">
                      {entry.outcome === "refused" ? prettyReason(entry.detail?.reason) : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
