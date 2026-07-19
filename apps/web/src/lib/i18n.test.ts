import { describe, expect, it } from "vitest";
import { formatDate, formatNumber, resources } from "./i18n";

function keyShape(value: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof child === "object" && child !== null ? keyShape(child as Record<string, unknown>, path) : [path];
  }).sort();
}

describe("localization", () => {
  it("keeps English and Chinese resource keys structurally identical", () => { expect(keyShape(resources.zh)).toEqual(keyShape(resources.en)); });
  it("formats numbers and dates by locale", () => {
    expect(formatNumber(1234567.89, "en-US")).toBe("1,234,567.89");
    expect(formatNumber(1234567.89, "zh-CN")).toBe("1,234,567.89");
    expect(formatDate("2026-07-20T00:00:00Z", "en-US", { timeZone: "UTC", year: "numeric", month: "2-digit", day: "2-digit" })).toBe("07/20/2026");
    expect(formatDate("2026-07-20T00:00:00Z", "zh-CN", { timeZone: "UTC", year: "numeric", month: "2-digit", day: "2-digit" })).toBe("2026/07/20");
  });
});
