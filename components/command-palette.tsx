"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";

type Item = { id: string; label: string; hint?: string; run: () => void };

const THEME_EVENT = "ekc-theme-change";

function toggleTheme() {
  const root = document.documentElement;
  const next = root.classList.contains("dark") ? "light" : "dark";
  root.classList.toggle("light", next === "light");
  root.classList.toggle("dark", next === "dark");
  try {
    localStorage.setItem("ekc-theme", next);
  } catch {
    /* storage can be blocked; the class still applies */
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

function recentQuestions(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem("ekc-recent-questions");
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

/**
 * Cmd+K navigation. Admin entries appear only after `/me` confirms the role, so the
 * palette never advertises a page the account cannot open.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>(() => recentQuestions());
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => setRecent(recentQuestions()), 0);
    inputRef.current?.focus();
    if (role) return;
    const supabase = supabaseBrowser();
    supabase.auth
      .getSession()
      .then(async ({ data }) => {
        if (!data.session) return;
        const me = await apiFetch<{ role: string }>("/me", data.session.access_token);
        setRole(me.role);
      })
      .catch(() => undefined);
    return () => window.clearTimeout(timer);
  }, [open, role]);

  const items = useMemo<Item[]>(() => {
    const go = (href: string) => () => {
      setOpen(false);
      router.push(href);
    };
    const navigation: Item[] = [
      { id: "home", label: "Home", hint: "landing page", run: go("/") },
      { id: "chat", label: "Chat", hint: "ask the handbook", run: go("/chat") },
      { id: "library", label: "Library", hint: "documents", run: go("/library") },
      {
        id: "theme",
        label: "Toggle theme",
        hint: "light / dark",
        run: () => {
          toggleTheme();
          setOpen(false);
        },
      },
    ];
    const admin: Item[] =
      role === "admin"
        ? [
            { id: "admin", label: "Admin", hint: "ingestion, audit, documents", run: go("/admin") },
            { id: "quality", label: "Quality", hint: "answer quality and performance", run: go("/admin/quality") },
          ]
        : [];
    const recents: Item[] = recent.map((question) => ({
      id: `ask-${question}`,
      label: question,
      hint: "ask again",
      run: go(`/chat?ask=${encodeURIComponent(question)}`),
    }));
    const all = [...navigation, ...admin, ...recents];
    const needle = query.trim().toLowerCase();
    if (!needle) return all;
    return all.filter((item) => `${item.label} ${item.hint ?? ""}`.toLowerCase().includes(needle));
  }, [query, recent, role, router]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 px-4 pt-24"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        aria-label="Command palette"
        aria-modal="true"
        className="panel w-full max-w-lg overflow-hidden"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <input
          ref={inputRef}
          aria-label="Search commands"
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 text-sm outline-none"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Jump to a page, toggle the theme, ask again…"
          value={query}
        />
        <ul className="max-h-80 overflow-y-auto py-1">
          {items.length === 0 ? (
            <li className="px-4 py-3 text-xs text-[var(--text-muted)]">No command matches.</li>
          ) : (
            items.map((item) => (
              <li key={item.id}>
                <button
                  className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm hover:bg-[var(--panel-2)]"
                  onClick={item.run}
                  type="button"
                >
                  <span className="truncate">{item.label}</span>
                  {item.hint ? (
                    <span className="mono shrink-0 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                      {item.hint}
                    </span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="mono border-t border-[var(--border)] px-4 py-2 text-[10px] text-[var(--text-muted)]">
          ⌘K / Ctrl+K to open · Esc to close
        </p>
      </div>
    </div>
  );
}
