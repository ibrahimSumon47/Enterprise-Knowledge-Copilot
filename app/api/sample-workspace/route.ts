import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * Signs a visitor into the shared read-only guest account. The password lives in
 * the server environment (EKC_GUEST_PASSWORD) and never reaches the browser.
 */
export async function POST(request: Request) {
  const origin = new URL(request.url).origin;
  const suppliedOrigin = request.headers.get("origin");
  if (suppliedOrigin && suppliedOrigin !== origin) {
    return NextResponse.json({ detail: "cross-origin request rejected" }, { status: 403 });
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const password = process.env.EKC_GUEST_PASSWORD;
  if (!url || !key || !password) {
    return NextResponse.redirect(new URL("/login?sample=unavailable", origin), 303);
  }

  const cookieStore = await cookies();
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          cookieStore.set(name, value, options);
        });
      },
    },
  });

  const { error } = await supabase.auth.signInWithPassword({
    email: "guest@ekc.local",
    password,
  });
  if (error) {
    return NextResponse.redirect(new URL("/login?sample=unavailable", origin), 303);
  }
  return NextResponse.redirect(new URL("/chat", origin), 303);
}
