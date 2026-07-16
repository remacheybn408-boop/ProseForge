import { describe, expect, it, vi } from "vitest";
import { ApiError, deleteCredential, listContext, request, subscribeWorkflowEvents, type WorkflowEvent } from "./client";

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

  it("subscribes to durable workflow status events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("id: 7\nevent: RUNNING\ndata: {\"status\":\"RUNNING\"}\n\nid: 8\nevent: COMPLETED\ndata: {\"status\":\"COMPLETED\"}\n\n"));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    vi.stubGlobal("fetch", fetchMock);
    const events: WorkflowEvent[] = [];

    await subscribeWorkflowEvents("workflow-1", event => events.push(event), { lastEventId: 6 });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/workflows/workflow-1/events", expect.objectContaining({ credentials: "include", headers: { "Last-Event-ID": "6" } }));
    expect(events).toEqual([
      { id: 7, event: "RUNNING", data: { status: "RUNNING" } },
      { id: 8, event: "COMPLETED", data: { status: "COMPLETED" } },
    ]);
  });

  it("reconnects after a stream ends and resumes from the last event", async () => {
    const encoder = new TextEncoder();
    const stream = (payload: string) => new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(payload));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(stream('id: 7\nevent: RUNNING\ndata: {"status":"RUNNING"}\n\n'), { status: 200 }))
      .mockResolvedValueOnce(new Response(stream('id: 8\nevent: COMPLETED\ndata: {"status":"COMPLETED"}\n\n'), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const events: WorkflowEvent[] = [];

    await subscribeWorkflowEvents("workflow-1", event => events.push(event), { reconnectDelayMs: 0 });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ headers: { "Last-Event-ID": "7" } }));
    expect(events.at(-1)).toEqual({ id: 8, event: "COMPLETED", data: { status: "COMPLETED" } });
  });

  it("reconnects when the workflow stream drops during a read", async () => {
    const encoder = new TextEncoder();
    const droppedStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('id: 7\nevent: RUNNING\ndata: {"status":"RUNNING"}\n\n'));
        setTimeout(() => controller.error(new Error("connection dropped")), 0);
      },
    });
    const completedStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('id: 8\nevent: COMPLETED\ndata: {"status":"COMPLETED"}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(droppedStream, { status: 200 }))
      .mockResolvedValueOnce(new Response(completedStream, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await subscribeWorkflowEvents("workflow-1", () => undefined, { reconnectDelayMs: 0 });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ headers: { "Last-Event-ID": "7" } }));
  });

  it("reconnects when the workflow stream cannot be opened", async () => {
    const encoder = new TextEncoder();
    const completedStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('id: 8\nevent: COMPLETED\ndata: {"status":"COMPLETED"}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error("connection unavailable"))
      .mockResolvedValueOnce(new Response(completedStream, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await subscribeWorkflowEvents("workflow-1", () => undefined, { lastEventId: 7, reconnectDelayMs: 0 });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ headers: { "Last-Event-ID": "7" } }));
  });
});
