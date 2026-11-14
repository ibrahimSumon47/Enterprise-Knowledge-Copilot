"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The form is inert until React has hydrated. Without this, a browser that
  // autofills and submits before the bundle runs performs a native GET submit,
  // which reloads /login and puts the password in the URL.
  const ready = useSyncExternalStore(subscribeToHydration, hydrated, serverSnapshot);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    // Uncontrolled inputs: a browser that autofills before React hydrates keeps
    // its values instead of having them replaced by empty state.
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    setBusy(true);
    setError(null);
    try {
      const { data, error: authError } = await supabaseBrowser().auth.signInWithPassword({
        email,
        password,
      });
      if (authError) {
        setError(
          authError.message === "Invalid login credentials"
            ? "That email and password do not match an account."
            : authError.message,
        );
        return;
      }
      if (!data.session) {
        setError("This account has not been confirmed yet. Ask an administrator to confirm it.");
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
    <div className="mx-auto w-full max-w-md px-4 py-20">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
        Use the email address your workspace administrator issued.
      </p>

      <form
        className="panel mt-6 p-6"
        data-auth-version="3"
        data-ready={ready ? "true" : "false"}
        method="post"
        onSubmit={signIn}
      >
        <label className="block text-xs text-[var(--text-muted)]" htmlFor="email">
          Email
        </label>
        <input
          autoComplete="username"
          className="input mt-1"
          id="email"
          name="email"
          placeholder="you@company.com"
          required
          type="email"
        />
        <label className="mt-4 block text-xs text-[var(--text-muted)]" htmlFor="password">
          Password
        </label>
        <input
          autoComplete="current-password"
          className="input mt-1"
          id="password"
          name="password"
          required
          type="password"
        />
        {error ? (
          <p
            className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]"
            role="alert"
          >
            {error}
          </p>
        ) : null}
        <button
          className="btn btn-primary mt-5 w-full justify-center"
          disabled={busy || !ready}
          type="submit"
        >
          {busy ? <Loader2 className="animate-spin" size={15} /> : null}
          {busy ? "Signing in" : "Sign in"}
        </button>
        <noscript>
          <p className="mt-4 text-xs leading-5 text-[var(--danger)]">
            Sign-in needs JavaScript. Enable it and reload this page.
          </p>
        </noscript>
      </form>

      <p className="mt-5 text-xs leading-6 text-[var(--text-muted)]">
        No account yet?{" "}
        <a className="underline decoration-dotted" href="/register">
          Create a workspace
        </a>
        , ask an administrator to invite you, or open the sample workspace from the home page.
      </p>
      <form action="/api/sample-workspace" className="mt-3" method="post">
        <button className="text-xs underline decoration-dotted" type="submit">
          Open the sample workspace without an account
        </button>
      </form>
    </div>
  );
}
