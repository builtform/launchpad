import { describe, expect, it } from "vitest";

import { formatDate } from "./index";

describe("formatDate", () => {
  it("formats a date as YYYY-MM-DD", () => {
    expect(formatDate(new Date("2026-07-12T10:30:00.000Z"))).toBe("2026-07-12");
  });

  it("normalizes to UTC rather than local time", () => {
    // 2026-01-01 23:30 at UTC-05:00 is 2026-01-02 04:30 UTC.
    expect(formatDate(new Date("2026-01-01T23:30:00-05:00"))).toBe("2026-01-02");
  });

  it("zero-pads single-digit months and days", () => {
    expect(formatDate(new Date("2026-03-05T00:00:00.000Z"))).toBe("2026-03-05");
  });
});
