import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelPicker } from "./ModelPicker";
import { ReasoningPicker } from "./ReasoningPicker";

describe("model controls", () => {
  it("keeps model and reasoning controls separate", () => {
    const model = { provider: "local", model_id: "writer", capabilities: { reasoning: false } };
    const onModel = vi.fn(); const onReasoning = vi.fn();
    render(<><ModelPicker models={[model]} onChange={onModel} /><ReasoningPicker value="auto" supported={["auto"]} onChange={onReasoning} /></>);
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "local/writer" } });
    expect(onModel).toHaveBeenCalledWith(model);
    expect((screen.getByRole("option", { name: "max" }) as HTMLOptionElement).disabled).toBe(true);
  });
});
