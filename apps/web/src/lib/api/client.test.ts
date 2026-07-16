import { describe, expect, it, vi } from "vitest";
import { ApiError, deleteCredential, listContext, request } from "./client";

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

  it("preserves the HTTP status for session and permission handling", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"expired"}', { status: 401 })));

    await expect(request<void>("/api/v1/example")).rejects.toEqual(expect.objectContaining({
      name: "ApiError",
      status: 401,
    } satisfies Partial<ApiError>));
  });

  it("requests context using the selected model profile", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], used_tokens: 0, context_window: 200000, available_tokens: 200000 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listContext("project-1", { profileId: "profile-1" });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/projects/project-1/context?profile_id=profile-1", expect.objectContaining({ credentials: "include" }));
  });

  it("deletes a credential by id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteCredential("credential-1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/credentials/credential-1", expect.objectContaining({ method: "DELETE", credentials: "include" }));
  });
});
