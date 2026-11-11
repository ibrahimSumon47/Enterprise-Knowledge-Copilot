"use client";

import { createBrowserClient } from "@supabase/ssr";

/** Browser client used by the auth forms and the chat panel. */
export function supabaseBrowser() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("Supabase environment variables are not configured");
  }
  return createBrowserClient(url, key);
}
