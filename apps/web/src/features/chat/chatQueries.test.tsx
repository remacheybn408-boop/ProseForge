import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRegenerate, useRetryMessage } from "./chatQueries";
import type { SendOptions } from "./chatTypes";

function Probe({ options }: { options?: SendOptions }) {
  const retry = useRetryMessage();
  return <button onClick={() => retry.mutate({ messageId: "m1", options })}>retry</button>;
}

function RegenerateProbe({ options }: { options?: SendOptions }) {
  const regenerate = useRegenerate();
  return <button onClick={() => regenerate.mutate({ conversationId: "c1", messageId: "m1", options })}>regenerate</button>;
}

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function stubFetch() {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"id":"m1","status":"PENDING","task_id":"t1"}', {
    status: 200,
    headers: { "content-type": "application/json" },
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useRetryMessage", () => {
  it("forwards the reasoning level the same way provider and model are passed", async () => {
    const fetchMock = stubFetch();
    renderWithQuery(<Probe options={{ provider: "anthropic", model: "claude-sonnet", reasoning: "deep" }} />);

    fireEvent.click(screen.getByText("retry"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/messages/m1/retry");
    // 重试不得悄悄丢掉思考强度（后端对缺省值会复用消息落库的原级别）。
    expect(JSON.parse(String(init.body))).toEqual({ provider: "anthropic", model: "claude-sonnet", reasoning_level: "deep" });
  });

  it("sends an empty payload when there is no override, letting the backend reuse the stored level", async () => {
    const fetchMock = stubFetch();
    renderWithQuery(<Probe />);

    fireEvent.click(screen.getByText("retry"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({});
  });
});

describe("useRegenerate", () => {
  it("forwards the reasoning level the same way retry does", async () => {
    const fetchMock = stubFetch();
    renderWithQuery(<RegenerateProbe options={{ provider: "anthropic", model: "claude-sonnet", reasoning: "deep" }} />);

    fireEvent.click(screen.getByText("regenerate"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v2/conversations/c1/messages/m1/regenerate");
    // regenerate 不得悄悄丢掉思考强度（后端对缺省值会复用源消息落库的原级别）。
    expect(JSON.parse(String(init.body))).toEqual({ provider: "anthropic", model: "claude-sonnet", reasoning_level: "deep" });
  });

  it("sends an empty payload when there is no override, letting the backend reuse the stored level", async () => {
    const fetchMock = stubFetch();
    renderWithQuery(<RegenerateProbe />);

    fireEvent.click(screen.getByText("regenerate"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({});
  });
});
