import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LanguageProvider } from "../../lib/i18n";
import { ContextBudgetBar } from "./ContextBudgetBar";

describe("ContextBudgetBar", () => {
  beforeEach(() => localStorage.setItem("proseforge.web.language", "en-US"));
  afterEach(cleanup);

  it("labels the context estimate independently from historical usage", () => {
    render(<LanguageProvider><ContextBudgetBar used={8500} available={1500} total={10000} /></LanguageProvider>);

    expect(screen.getByText("8.5K used")).toBeTruthy();
    expect(screen.getByText("1.5K available")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("85");
  });

  it("warns at the high context thresholds and separates output reserve", () => {
    render(<LanguageProvider><ContextBudgetBar used={7650} available={1350} total={10000} outputReserve={1000} /></LanguageProvider>);

    expect(screen.getByText("1K output reserve")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("85% of the context is in use");
  });
});
