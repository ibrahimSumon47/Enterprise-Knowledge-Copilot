"use client";

import { Moon, Sun } from "lucide-react";
import { useCallback, useSyncExternalStore } from "react";

type Mode = "dark" | "light";

const EVENT = "ekc-theme-change";

function subscribe(onChange: () => void): () => void {
  window.addEventListener(EVENT, onChange);
  return () => window.removeEventListener(EVENT, onChange);
}

function snapshot(): Mode {
  return document.documentElement.classList.contains("light") ? "light" : "dark";
}

function serverSnapshot(): Mode {
  return "dark";
}

/**
 * Light/dark toggle with a circular reveal (View Transitions API).
 * Falls back to an instant switch when the API or motion is unavailable.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const mode = useSyncExternalStore(subscribe, snapshot, serverSnapshot);

  const apply = useCallback((next: Mode, event?: React.MouseEvent<HTMLButtonElement>) => {
    const root = document.documentElement;
    if (event) {
      root.style.setProperty("--toggle-x", `${event.clientX}px`);
      root.style.setProperty("--toggle-y", `${event.clientY}px`);
    }
    const commit = () => {
      root.classList.toggle("light", next === "light");
      root.classList.toggle("dark", next === "dark");
      try {
        localStorage.setItem("ekc-theme", next);
      } catch {
        /* storage can be blocked; the class still applies for this session */
      }
      window.dispatchEvent(new Event(EVENT));
    };

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const doc = document as Document & { startViewTransition?: (cb: () => void) => void };
    if (!reduce && typeof doc.startViewTransition === "function") {
      root.classList.add("theme-transition");
      doc.startViewTransition(commit);
      window.setTimeout(() => root.classList.remove("theme-transition"), 600);
    } else {
      commit();
    }
  }, []);

  return (
    <button
      type="button"
      className={className ?? "btn"}
      aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      onClick={(event) => apply(mode === "dark" ? "light" : "dark", event)}
    >
      {mode === "light" ? <Sun size={15} /> : <Moon size={15} />}
      <span className="mono text-xs uppercase tracking-wider">{mode}</span>
    </button>
  );
}
