import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TokenMeter } from "./TokenMeter";

describe("TokenMeter", () => {
  it("shows actual and estimated tokens separately", () => {
    render(<TokenMeter actual={1200} estimated={300} limit={4000} />);

    expect(screen.getByRole("meter").getAttribute("aria-label")).toBe("Token usage");
    expect(screen.getByText("1.2K actual")).toBeTruthy();
    expect(screen.getByText("300 estimated")).toBeTruthy();
    expect(screen.getByText("4K limit")).toBeTruthy();
  });

  it("does not invent a cost when pricing is unavailable", () => {
    render(<TokenMeter actual={10} estimated={0} cost={null} />);

    expect(screen.getAllByText("Cost unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByText("$0.00")).toBeNull();
  });
});
