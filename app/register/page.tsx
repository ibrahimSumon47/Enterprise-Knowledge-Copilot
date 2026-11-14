"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import { site } from "@/lib/site";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function register(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const inviteToken = new URLSearchParams(window.location.search).get("invite");
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${site.apiBaseUrl.replace(/\/$/, "")}/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, invite_token: inviteToken }),
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        setError(
          response.status === 409
            ? "An account with that email already exists. Sign in instead."
            : `Could not create the account (${response.status}). ${detail.slice(0, 120)}`,
        );
        return;
      }
      const { error: authError } = await supabaseBrowser().auth.signInWithPassword({
        email,
        password,
      });
      if (authError) {
        setError(authError.message);
        return;
      }
      router.replace(inviteToken ? "/chat" : "/onboarding");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-20">
      <h1 className="text-2xl font-semibold">Create a workspace</h1>
      <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
        You become the owner. Add your team&apos;s first document next.
      </p>
      <form className="panel mt-6 p-6" onSubmit={register}>
        <label className="block text-xs text-[var(--text-muted)]" htmlFor="email">
          Work email
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
          autoComplete="new-password"
          className="input mt-1"
          id="password"
          minLength={10}
          name="password"
          required
          type="password"
        />
        <p className="mt-2 text-xs text-[var(--text-muted)]">At least 10 characters.</p>
        {error ? (
          <p
            className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]"
            role="alert"
          >
            {error}
          </p>
        ) : null}
        <button className="btn btn-primary mt-5 w-full justify-center" disabled={busy} type="submit">
          {busy ? <Loader2 className="animate-spin" size={15} /> : null}
          {busy ? "Creating workspace" : "Create workspace"}
        </button>
      </form>
      <p className="mt-5 text-xs leading-6 text-[var(--text-muted)]">
        Already have an account?{" "}
        <Link className="underline decoration-dotted" href="/login">
          Sign in
        </Link>
        .
      </p>
    </div>
  );
}
