import { describe, expect, it } from "vitest";

import { formatBytes, formatRelative } from "@/lib/format";

describe("formatBytes", () => {
  it("uses binary units with at most one decimal", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25 MB");
    expect(formatBytes(150 * 1024 * 1024)).toBe("150 MB");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-22T12:00:00Z");
  it("reads naturally", () => {
    expect(formatRelative("2026-10-22T11:59:40Z", now)).toBe("just now");
    expect(formatRelative("2026-10-22T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelative("2026-10-21T12:00:00Z", now)).toBe("yesterday");
    expect(formatRelative("2026-10-19T12:00:00Z", now)).toBe("3 days ago");
    expect(formatRelative("2026-09-01T12:00:00Z", now)).toBe("1 Sept 2026");
  });
});
