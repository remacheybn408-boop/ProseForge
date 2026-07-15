import { describe, expect, it, vi } from "vitest";
import { getHealth } from "./lib/api/client";

describe("ProseForge web", () => {
  it("has a stable product name", () => expect("ProseForge").toBe("ProseForge"));

  it("uses cookie-backed health requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"status":"ok"}', { status: 200 }));
    await expect(getHealth()).resolves.toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health/live", expect.objectContaining({ credentials: "include" }));
    fetchMock.mockRestore();
  });
});
