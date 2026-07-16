import { describe, expect, it, vi } from "vitest";
import { request } from "./client";

describe("api request responses", () => {
  it("accepts a successful 204 without trying to parse JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(request<void>("/api/v1/example", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("accepts a successful empty non-JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", {
      status: 200,
      headers: { "content-type": "text/plain" },
    })));

    await expect(request<void>("/api/v1/example")).resolves.toBeUndefined();
  });
});
