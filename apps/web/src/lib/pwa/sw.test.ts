import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("service worker cache policy", () => {
  const source = readFileSync("public/sw.js", "utf8");

  it("explicitly bypasses API requests before Cache Storage access", () => {
    const bypass = source.indexOf('url.pathname.startsWith("/api/")');
    const cacheLookup = source.indexOf("caches.match(event.request)");
    expect(bypass).toBeGreaterThan(-1);
    expect(cacheLookup).toBeGreaterThan(bypass);
  });

  it("only runtime-caches static browser destinations", () => {
    expect(source).toContain('event.request.method !== "GET"');
    expect(source).toContain('"script", "style", "font", "image", "manifest"');
    expect(source).not.toMatch(/cache\.put\([^,]+,\s*(credentials|messages|manuscript)/i);
  });
});
