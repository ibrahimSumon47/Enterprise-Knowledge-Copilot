"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const password = String(new FormData(event.currentTarget).get("password") ?? "");
    setBusy(true);
    setError(null);
    const { error: authError } = await supabaseBrowser().auth.updateUser({ password });
    setBusy(false);
    if (authError) {
      setError(
        authError.message.toLowerCase().includes("session")
          ? "This reset link has expired. Request a new one."
          : authError.message,
      );
      return;
    }
    router.replace("/chat");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="text-2xl font-semibold">Choose a new password</h1>
      <form className="panel mt-6 p-6" onSubmit={submit}>
        <label className="block text-xs text-[var(--text-muted)]" htmlFor="password">
          New password
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
        <button className="btn btn-primary mt-5 w-full justify-center" disabled={busy} type="submit">
          Update password
        </button>
      </form>
      {error ? <p className="mt-4 text-xs text-[var(--danger)]">{error}</p> : null}
    </div>
  );
}
