// Single source of truth for the audit verification cadence. The scheduled
// workflow runs every AUDIT_CHECK_INTERVAL_HOURS, and the admin panel treats a
// checkpoint older than one interval as stale. `lib/audit.test.ts` fails if the
// workflow cron drifts from this value.
export const AUDIT_CHECK_INTERVAL_HOURS = 6;
export const CHECKPOINT_STALE_MS = AUDIT_CHECK_INTERVAL_HOURS * 60 * 60 * 1000;

/** A checkpoint older than one scheduled interval has not advanced in a while. */
export function isStaleCheckpoint(value?: string | null, now = Date.now()) {
  if (!value) return false;
  const updated = new Date(value).getTime();
  if (!Number.isFinite(updated)) return false;
  return now - updated > CHECKPOINT_STALE_MS;
}
