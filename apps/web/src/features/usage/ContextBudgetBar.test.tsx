import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContextBudgetBar } from "./ContextBudgetBar";

describe("ContextBudgetBar", () => {
  it("labels the context estimate independently from historical usage", () => {
    render(<ContextBudgetBar used={8500} available={1500} total={10000} />);

    expect(screen.getByText("8.5K used")).toBeTruthy();
    expect(screen.getByText("1.5K available")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("85");
  });
});
