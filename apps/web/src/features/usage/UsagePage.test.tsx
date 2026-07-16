import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../lib/i18n";
import { getUsageSummary } from "../../lib/api/client";
import { UsagePage } from "./UsagePage";

vi.mock("../../lib/api/client", () => ({
  getHealth: vi.fn(),
  getUsageSummary: vi.fn(),
  listModels: vi.fn(),
  listProjects: vi.fn(),
  listProviders: vi.fn(),
}));

describe("UsagePage", () => {
  it("loads the user usage summary when no project is selected", async () => {
    vi.mocked(getUsageSummary).mockResolvedValue({
      scope: "user",
      project_id: null,
      actual: { input_tokens: 120, output_tokens: 30, cached_input_tokens: 0, reasoning_tokens: 0, total_tokens: 150, cost_usd: null },
      estimated: { input_tokens: 0, output_tokens: 0, cached_input_tokens: 0, reasoning_tokens: 0, total_tokens: 0, cost_usd: null },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(<LanguageProvider><QueryClientProvider client={client}><UsagePage /></QueryClientProvider></LanguageProvider>);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Token 用量" })).toBeTruthy());
    expect(getUsageSummary).toHaveBeenCalledWith({});
  });
});
