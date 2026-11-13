import Link from "next/link";
import { LogoLink } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { currentSession } from "@/lib/supabase/server";

const publicLinks = [
  { href: "/product", label: "Product" },
  { href: "/security", label: "Security" },
  { href: "/contact", label: "Contact" },
];

const appLinks = [
  { href: "/chat", label: "Chat" },
  { href: "/library", label: "Library" },
];

export async function SiteHeader() {
  const user = await currentSession();
  const links = user ? appLinks : publicLinks;

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_92%,transparent)] backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4">
        <LogoLink />
        <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
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
        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <Link className="btn" href="/chat">
              Open workspace
            </Link>
          ) : (
            <Link className="btn btn-primary" href="/login">
              Sign in
            </Link>
          )}
          <ThemeToggle className="btn" />
        </div>
      </div>
    </header>
  );
}
