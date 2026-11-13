"use client";

import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { ROLES, ROLE_LABEL } from "@/lib/site";
import { supabaseBrowser } from "@/lib/supabase/client";

/** Hydration marker: false in SSR HTML, true once React is running. */
const subscribeToHydration = () => () => {};
const hydrated = () => true;
const serverSnapshot = () => false;

/** Only same-site paths are accepted so `next` cannot become an open redirect. */
function safeNext(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/chat";
  return value;
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("employee@ekc.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The form is inert until React has hydrated. Without this, a browser that
  // autofills and submits before the bundle runs performs a native GET submit,
  // which reloads /login and puts the password in the URL. That was the
  // "sign-in keeps bouncing back to /login" report.
  const ready = useSyncExternalStore(subscribeToHydration, hydrated, serverSnapshot);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const { data, error: authError } = await supabaseBrowser().auth.signInWithPassword({
        email,
        password,
      });
      if (authError) {
        setError(authError.message);
        return;
      }
      if (!data.session) {
        setError("This account is not confirmed yet. Ask an administrator to confirm it.");
        return;
      }
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-14">
      <div className="grid gap-6 lg:grid-cols-[1fr_1.05fr]">
        <section>
          <span className="chip chip-accent mono">demo access</span>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">Sign in as a role</h1>
          <p className="mt-3 max-w-md text-sm leading-7 text-[var(--text-muted)]">
            Every role sees a different slice of the corpus. Sign in as an employee, ask a question,
            then sign in as an administrator and ask it again — the answers should diverge, and the
            documents behind them should too.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {ROLES.map((role) => (
              <button
                key={role}
                className="chip mono"
                onClick={() => setEmail(`${role}@ekc.local`)}
                type="button"
              >
                {ROLE_LABEL[role]}
              </button>
            ))}
          </div>
          <p className="mt-4 text-xs leading-6 text-[var(--text-muted)]">
            The password for the seven demo accounts is held by the project owner and is not stored
            in this repository.
          </p>
        </section>

        <form
          className="panel p-6"
          data-auth-version="2"
          method="post"
          onSubmit={signIn}
        >
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <KeyRound size={15} className="text-[var(--accent)]" /> Email and password
          </h2>
          <label className="mt-5 block text-xs text-[var(--text-muted)]" htmlFor="email">
            Email
          </label>
          <input
            autoComplete="username"
            className="input mt-1"
            id="email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
          <label className="mt-4 block text-xs text-[var(--text-muted)]" htmlFor="password">
            Password
          </label>
          <input
            autoComplete="current-password"
            className="input mt-1"
            id="password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {error ? (
            <p className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]">
              {error}
            </p>
          ) : null}
          <button
            className="btn btn-primary mt-5 w-full justify-center"
            disabled={busy || !ready}
            type="submit"
          >
            {busy ? <Loader2 className="animate-spin" size={15} /> : <ShieldCheck size={15} />}
            {busy ? "Signing in" : "Sign in"}
          </button>
          <noscript>
            <p className="mt-4 text-xs leading-5 text-[var(--danger)]">
              Sign-in needs JavaScript. Enable it and reload this page.
            </p>
          </noscript>
          <p className="mt-4 text-[11px] leading-5 text-[var(--text-muted)]">
            Sessions are issued by Supabase Auth. The browser only ever holds the anon key; the
            service-role key stays on the API.
          </p>
        </form>
      </div>
    </div>
  );
}
