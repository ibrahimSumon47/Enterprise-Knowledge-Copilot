"use client";

import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "").trim();
    const { error: authError } = await supabaseBrowser().auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    if (authError) setError(authError.message);
    else setSent(true);
  }

  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="text-2xl font-semibold">Reset your password</h1>
      <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
        We send a one-time link. It expires quickly and can only be used once.
      </p>
      {sent ? (
        <p className="mt-6 rounded-lg border border-[var(--border)] px-3 py-2 text-sm" role="status">
          If that address has an account, a reset link is on its way.
        </p>
      ) : (
        <form className="panel mt-6 p-6" onSubmit={submit}>
          <label className="block text-xs text-[var(--text-muted)]" htmlFor="email">
            Email
          </label>
          <input className="input mt-1" id="email" name="email" required type="email" />
          <button className="btn btn-primary mt-5 w-full justify-center" type="submit">
            Send reset link
          </button>
        </form>
      )}
      {error ? <p className="mt-4 text-xs text-[var(--danger)]">{error}</p> : null}
      <p className="mt-5 text-xs">
        <a className="underline decoration-dotted" href="/login">
          Back to sign in
        </a>
      </p>
    </div>
  );
}
