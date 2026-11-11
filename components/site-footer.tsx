import Link from "next/link";
import { site } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-[var(--border)]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-[var(--text-muted)] sm:flex-row sm:items-center sm:justify-between">
        <p>
          Portfolio project built on public documents. Source documents are GitLab&apos;s, licensed{" "}
          <a
            className="underline decoration-dotted hover:text-[var(--text)]"
            href={site.handbook.licenseUrl}
            rel="noreferrer noopener"
            target="_blank"
          >
            {site.handbook.license}
          </a>
          .
        </p>
        <nav aria-label="Footer" className="flex items-center gap-4">
          <Link className="hover:text-[var(--text)]" href="/credits">
            Credits
          </Link>
          <Link className="hover:text-[var(--text)]" href="/trust">
            Security
          </Link>
          <a
            className="hover:text-[var(--text)]"
            href={site.repo}
            rel="noreferrer noopener"
            target="_blank"
          >
            Repository
          </a>
        </nav>
      </div>
    </footer>
  );
}
