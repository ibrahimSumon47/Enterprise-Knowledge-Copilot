import { describe, expect, it } from "vitest";
import { formatDate, formatMs, shortId } from "./utils";

describe("formatMs", () => {
  it("renders sub-second values in milliseconds", () => {
    expect(formatMs(240)).toBe("240 ms");
  });

  it("renders longer values in seconds", () => {
    expect(formatMs(1500)).toBe("1.50 s");
  });

  it("renders a dash when the value is missing", () => {
    expect(formatMs(null)).toBe("—");
    expect(formatMs(undefined)).toBe("—");
  });
});

describe("shortId", () => {
  it("is stable for the same input", () => {
    expect(shortId("doc-123")).toBe(shortId("doc-123"));
  });

  it("differs for different inputs", () => {
    expect(shortId("doc-123")).not.toBe(shortId("doc-124"));
  });
});

describe("formatDate", () => {
  it("formats a date as a UTC timestamp", () => {
    expect(formatDate("2026-11-11T09:00:00.000Z")).toBe("2026-11-11 09:00 UTC");
  });
});
