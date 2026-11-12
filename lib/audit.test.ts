import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  AUDIT_CHECK_INTERVAL_HOURS,
  CHECKPOINT_STALE_MS,
  isStaleCheckpoint,
} from "./audit";

describe("audit checkpoint staleness", () => {
  const now = Date.parse("2026-11-12T18:00:00Z");

  it("is stale only past one full interval", () => {
    expect(isStaleCheckpoint("2026-11-12T12:01:00Z", now)).toBe(false);
    expect(isStaleCheckpoint("2026-11-12T11:59:00Z", now)).toBe(true);
    expect(CHECKPOINT_STALE_MS).toBe(AUDIT_CHECK_INTERVAL_HOURS * 60 * 60 * 1000);
    expect(isStaleCheckpoint(null, now)).toBe(false);
    expect(isStaleCheckpoint("not-a-date", now)).toBe(false);
  });

  it("keeps the scheduled workflow on the same cadence", () => {
    const workflow = readFileSync(".github/workflows/audit-integrity.yml", "utf8");
    const crons = [...workflow.matchAll(/- cron: "([^"]+)"/g)].map((match) => match[1]);
    const recurring = crons.filter((cron) => cron.startsWith("17 */"));
    expect(recurring).toEqual([`17 */${AUDIT_CHECK_INTERVAL_HOURS} * * *`]);
  });
});
