import Link from "next/link";
import { LogoLink } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { site } from "@/lib/site";

const links = [
  { href: "/chat", label: "Chat" },
  { href: "/evals", label: "Evaluations" },
  { href: "/trust", label: "Trust" },
  { href: "/credits", label: "Credits" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_86%,transparent)] backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4">
        <LogoLink />
        <nav aria-label="Main" className="ml-auto hidden items-center gap-1 sm:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md px-3 py-2 text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:ml-0">
          <a
            className="hidden text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text)] md:inline"
            href={site.repo}
            rel="noreferrer noopener"
            target="_blank"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
