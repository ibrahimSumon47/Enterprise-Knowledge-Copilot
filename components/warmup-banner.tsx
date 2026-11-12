"use client";

import { Loader2, Snowflake } from "lucide-react";
import { useEffect, useState } from "react";
import { site } from "@/lib/site";

type State = "checking" | "warming" | "ready" | "unreachable";

/**
 * The free API instance sleeps. This probes /health before the first question and
 * says so, instead of letting the first answer look like a failure.
 */
export function WarmupBanner() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => setState((value) => (value === "checking" ? "warming" : value)), 2500);

    fetch(`${site.apiBaseUrl}/health`, { signal: controller.signal })
      .then((response) => {
        if (cancelled) return;
        setState(response.ok ? "ready" : "unreachable");
      })
      .catch(() => {
        if (!cancelled) setState("warming");
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, []);

  if (state === "ready" || state === "checking") return null;

  const unreachable = state === "unreachable";
  return (
    <p
      aria-live="polite"
      className="mt-4 flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-muted)]"
    >
      {unreachable ? <Snowflake size={14} /> : <Loader2 className="animate-spin" size={14} />}
      {unreachable
        ? "The API did not answer the health check yet. It may still be waking up; a question will retry it."
        : "Waking the free API instance. The first answer can take up to a minute while models load."}
    </p>
  );
}
