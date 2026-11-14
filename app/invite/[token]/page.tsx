"use client";

import { Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [state, setState] = useState<"checking" | "ready" | "error">("checking");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    supabaseBrowser()
      .auth.getSession()
      .then(({ data }) => {
        if (!data.session) {
          router.replace(`/register?invite=${encodeURIComponent(params.token)}`);
          return;
        }
        setState("ready");
      });
  }, [params.token, router]);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      const { data } = await supabaseBrowser().auth.getSession();
      const token = data.session?.access_token;
      if (!token) throw new Error("Sign in again to accept this invite.");
      await apiFetch(`/invites/${params.token}/accept`, token, { method: "POST" });
      router.replace("/chat");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not accept the invite");
      setState("error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="text-2xl font-semibold">Join the workspace</h1>
      <p className="mt-2 text-sm leading-7 text-[var(--text-muted)]">
        This link is single-use, expires, and can be revoked by a workspace admin.
      </p>
      {state === "checking" ? (
        <p className="mt-6 flex items-center gap-2 text-sm">
          <Loader2 className="animate-spin" size={15} /> Checking your session…
        </p>
      ) : (
        <button className="btn btn-primary mt-6" disabled={busy} onClick={accept} type="button">
          {busy ? <Loader2 className="animate-spin" size={15} /> : null} Accept invite
        </button>
      )}
      {error ? (
        <p className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
