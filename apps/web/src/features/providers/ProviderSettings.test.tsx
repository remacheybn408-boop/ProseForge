import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProviderSettings } from "./ProviderSettings";

describe("ProviderSettings", () => {
  it("renders provider-backed model choices", () => {
    render(<ProviderSettings providers={["openai"]} models={[{ model_id: "future-model", display_name: "Future model" }]} provider="openai" model="" onProvider={() => undefined} onModel={() => undefined} />);
    expect(screen.getByDisplayValue("openai")).toBeTruthy();
    expect(screen.getByText("Future model")).toBeTruthy();
  });
});
