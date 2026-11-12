import cadence from "../audit-cadence.json";

// Single source of truth for the audit verification cadence. `audit-cadence.json`
// is read here for the panel, by scripts/check_audit_chain.py for the workflow
// summary, and by lib/audit.test.ts, which fails if the workflow cron drifts.
export const AUDIT_CHECK_INTERVAL_HOURS = cadence.check_interval_hours;
export const CHECKPOINT_STALE_MS = AUDIT_CHECK_INTERVAL_HOURS * 60 * 60 * 1000;

/** A checkpoint older than one scheduled interval has not advanced in a while. */
export function isStaleCheckpoint(value?: string | null, now = Date.now()) {
  if (!value) return false;
  const updated = new Date(value).getTime();
  if (!Number.isFinite(updated)) return false;
  return now - updated > CHECKPOINT_STALE_MS;
}
