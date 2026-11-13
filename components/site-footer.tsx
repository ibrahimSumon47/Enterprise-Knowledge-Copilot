import Link from "next/link";

const links = [
  { href: "/product", label: "Product" },
  { href: "/security", label: "Security" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/contact", label: "Contact" },
];

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-[var(--border)] bg-[var(--bg-soft)]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-[var(--text-muted)] sm:flex-row sm:items-center sm:justify-between">
        <p>© {new Date().getFullYear()} Enterprise Knowledge Copilot</p>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {links.map((link) => (
            <Link key={link.href} className="hover:text-[var(--text)]" href={link.href}>
              {link.label}
            </Link>
          ))}
          <Link className="text-xs hover:text-[var(--text)]" href="/licenses">
            Licenses and sources
          </Link>
        </nav>
      </div>
    </footer>
  );
}
