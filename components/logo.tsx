import Link from "next/link";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

/** Wordmark: a small geometric mark plus the product name. */
export function Logo({ className, showName = true }: { className?: string; showName?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        aria-hidden
        className="grid h-7 w-7 place-items-center rounded-md border border-[var(--border-strong)] bg-[var(--accent-soft)]"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 4.5 8 2l6 2.5v7L8 14l-6-2.5v-7Z" stroke="var(--accent)" strokeWidth="1.3" />
          <path d="M5.5 6.5 8 5.2l2.5 1.3v3L8 10.8 5.5 9.5v-3Z" fill="var(--accent)" opacity="0.75" />
        </svg>
      </span>
      {showName ? <span className="text-[15px] font-semibold tracking-tight">{site.name}</span> : null}
    </span>
  );
}

/** Logo wrapped in a link, used by the header and footer. */
export function LogoLink({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={cn("inline-flex items-center", className)}
      aria-label={`${site.name} home`}
    >
      <Logo />
    </Link>
  );
}
