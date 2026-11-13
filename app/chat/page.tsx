"use client";

import { AlertTriangle, CornerDownLeft, Loader2, LogOut, Quote, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { apiFetch, type Citation } from "@/lib/api";
import { WarmupBanner } from "@/components/warmup-banner";
import { supabaseBrowser } from "@/lib/supabase/client";

type Answer = {
  answer: string;
  confidence?: string;
  refused?: boolean;
  unavailable?: boolean;
  citations: Citation[];
  suggestions?: Citation[];
  provider?: string;
  latency_ms?: number;
  reason?: string;
};

type Turn = { question: string; result?: Answer; error?: string };

const CONFIGURED = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);

const SUGGESTIONS = [
  "How do I submit an expense receipt?",
  "What is the incident response process?",
  "How does parental leave work?",
];

export default function ChatPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!CONFIGURED) return;
    try {
      const supabase = supabaseBrowser();
      supabase.auth.getSession().then(({ data }) => {
        if (!data.session) {
          router.replace("/login");
          return;
        }
        setToken(data.session.access_token);
        setEmail(data.session.user.email ?? null);
      });
    } catch (caught) {
      // Surfaced in the banner below; no state writes inside an effect.
      console.error(caught);
    }
  }, [router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(nextQuestion: string) {
    const text = nextQuestion.trim();
    if (!text || !token || busy) return;
    setBusy(true);
    setQuestion("");
    try {
      const kept = JSON.parse(localStorage.getItem("ekc-recent-questions") ?? "[]") as unknown;
      const list = Array.isArray(kept) ? kept.filter((item): item is string => typeof item === "string") : [];
      localStorage.setItem(
        "ekc-recent-questions",
        JSON.stringify([text, ...list.filter((item) => item !== text)].slice(0, 8)),
      );
    } catch {
      /* storage can be blocked; the palette list is a convenience only */
    }
    setTurns((current) => [...current, { question: text }]);
    try {
      const result = await apiFetch<Answer>("/chat", token, {
        method: "POST",
        body: JSON.stringify({ question: text }),
      });
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1 ? { ...turn, result } : turn,
        ),
      );
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Request failed";
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1 ? { ...turn, error: message } : turn,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    const asked = new URLSearchParams(window.location.search).get("ask");
    if (!asked) return;
    window.history.replaceState({}, "", "/chat");
    const timer = window.setTimeout(() => void ask(asked), 0);
    return () => window.clearTimeout(timer);
    // one-shot deep link from the command palette
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function signOut() {
    await supabaseBrowser().auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-10 lg:grid-cols-[1.6fr_1fr]">
      <section className="flex min-h-[70vh] flex-col">
        <header className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Ask the handbook</h1>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {email ? `Signed in as ${email}` : "Checking your session…"}
            </p>
          </div>
          <button className="btn" onClick={signOut} type="button">
            <LogOut size={14} /> Sign out
          </button>
        </header>

        <WarmupBanner />

        {CONFIGURED ? null : (
          <p className="mt-4 rounded-lg border border-[var(--warn)] px-3 py-2 text-xs leading-6 text-[var(--warn)]">
            <AlertTriangle className="mr-1 inline" size={13} />
            Supabase is not configured on this deployment. Add NEXT_PUBLIC_SUPABASE_URL and
            NEXT_PUBLIC_SUPABASE_ANON_KEY in Vercel, then redeploy.
          </p>
        )}

        <div className="panel mt-5 flex-1 space-y-5 overflow-y-auto p-5">
          {turns.length === 0 ? (
            <div>
              <p className="text-sm text-[var(--text-muted)]">
                Answers cite the passage they came from, and the copilot refuses when the evidence
                is weak. Try one of these:
              </p>
              <div className="mt-4 flex flex-col gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="panel-2 px-3 py-2 text-left text-sm transition-colors hover:border-[var(--border-strong)]"
                    onClick={() => ask(suggestion)}
                    type="button"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((turn, index) => (
            <article key={`${turn.question}-${index}`} className="space-y-3">
              <p className="ml-auto w-fit max-w-[85%] rounded-xl bg-[var(--accent-soft)] px-3 py-2 text-sm">
                {turn.question}
              </p>

              {turn.error ? (
                <div className="rounded-xl border border-[var(--warn)] px-3 py-2 text-xs leading-6">
                  <p className="flex items-center gap-2 font-medium text-[var(--warn)]">
                    <AlertTriangle size={14} /> The copilot could not answer
                  </p>
                  <p className="mt-1 text-[var(--text-muted)]">
                    {turn.error}. The free instance sleeps after 15 idle minutes and can be
                    restarting; wait a moment and ask again.
                  </p>
                </div>
              ) : null}

              {turn.result ? (
                <div className="space-y-3">
                  {turn.result.refused ? (
                    <div className="rounded-xl border border-[var(--border-strong)] px-3 py-3">
                      <p className="flex items-start gap-2 text-sm text-[var(--text-muted)]">
                        {turn.result.unavailable ? (
                          <AlertTriangle className="mt-0.5 shrink-0 text-[var(--accent)]" size={15} />
                        ) : (
                          <ShieldAlert className="mt-0.5 shrink-0" size={15} />
                        )}
                        <span>
                          {turn.result.unavailable ? (
                            <span className="mb-1 block text-xs font-medium text-[var(--accent)]">
                              Temporary service issue
                            </span>
                          ) : null}
                          {turn.result.answer}
                        </span>
                      </p>
                      {turn.result.suggestions && turn.result.suggestions.length > 0 ? (
                        <div className="mt-3 border-t border-[var(--border)] pt-3">
                          <p className="text-xs text-[var(--text-muted)]">
                            These documents may help:
                          </p>
                          <ul className="mt-2 space-y-1">
                            {turn.result.suggestions.map((suggestion) => (
                              <li key={suggestion.chunk_id} className="flex gap-2 text-sm">
                                <Quote className="mt-1 shrink-0 text-[var(--accent)]" size={12} />
                                <span>
                                  {suggestion.title}
                                  {suggestion.heading ? (
                                    <span className="text-[var(--text-muted)]"> · {suggestion.heading}</span>
                                  ) : null}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="text-sm leading-7 whitespace-pre-wrap">{turn.result.answer}</div>
                  )}
                  {turn.result.citations.length > 0 ? (
                    <ul className="space-y-2">
                      {turn.result.citations.map((citation) => (
                        <li key={citation.chunk_id} className="panel-2 p-3">
                          <p className="flex items-center gap-2 text-xs font-medium">
                            <Quote size={13} className="text-[var(--accent)]" />
                            {citation.title}
                            {citation.heading ? (
                              <span className="text-[var(--text-muted)]">· {citation.heading}</span>
                            ) : null}
                          </p>
                          <p className="mt-1 text-[12px] leading-6 text-[var(--text-muted)]">
                            {citation.quote ? (
                              <span className="mb-1 block font-medium text-[var(--text)]">
                                “{citation.quote}”
                              </span>
                            ) : null}
                            {citation.snippet}
                          </p>
                          <p className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--text-muted)]">
                            <span className="capitalize">{citation.access_level}</span>
                            <span>{citation.license}</span>
                            {citation.source_url ? (
                              <a
                                className="underline decoration-dotted"
                                href={citation.source_url}
                                rel="noreferrer noopener"
                                target="_blank"
                              >
                                source
                              </a>
                            ) : null}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}
          <div ref={endRef} />
        </div>

        <form
          className="mt-4 flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
        >
          <label className="sr-only" htmlFor="question">
            Your question
          </label>
          <textarea
            className="input min-h-[64px] flex-1 resize-y"
            id="question"
            maxLength={2000}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void ask(question);
              }
            }}
            placeholder="Ask about policy, leave, security or expenses…"
            value={question}
          />
          <button className="btn btn-primary h-[64px]" disabled={busy || !token} type="submit">
            {busy ? <Loader2 className="animate-spin" size={15} /> : <CornerDownLeft size={15} />}
            Ask
          </button>
        </form>
      </section>

      <aside className="space-y-4">
        <div className="panel p-5">
          <h2 className="text-sm font-semibold">How to read an answer</h2>
          <ul className="mt-3 space-y-3 text-[12px] leading-6 text-[var(--text-muted)]">
            <li>Every claim carries a marker that maps to one retrieved passage.</li>
            <li>A refusal means the documents did not support an answer, not that the app broke.</li>
            <li>Department and confidential documents only appear for roles that may read them.</li>
            <li>Open a source to read the passage and its licence.</li>
          </ul>
        </div>
        <div className="panel-2 p-4">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
            Response times
          </p>
          <p className="mt-2 text-[12px] leading-6 text-[var(--text-muted)]">
            After a quiet period the first answer can take a moment while the service warms up.
            Answers usually arrive in a few seconds.
          </p>
        </div>
      </aside>
    </div>
  );
}
