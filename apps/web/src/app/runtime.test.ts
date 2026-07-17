import { describe, expect, it, vi } from "vitest";
import { loadRuntimeConfig } from "./runtime";

describe("runtime configuration", () => {
  it("loads the same-origin API configuration before application queries", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ api_base_url: "/api", profile: "native" }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));

    await expect(loadRuntimeConfig(fetcher)).resolves.toEqual({
      api_base_url: "/api",
      profile: "native",
    });
    expect(fetcher).toHaveBeenCalledWith("/runtime-config.json", { cache: "no-store" });
  });

  it("rejects an incomplete runtime configuration", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ api_base_url: "http://localhost:8000" }),
      { status: 200 },
    ));

    await expect(loadRuntimeConfig(fetcher)).rejects.toThrow("Invalid runtime configuration");
  });
});
