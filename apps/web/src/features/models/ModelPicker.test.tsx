import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelPicker } from "./ModelPicker";
import { ReasoningPicker } from "./ReasoningPicker";
import { supportedReasoning, type ModelCapability } from "./modelCapabilities";

function catalogModel(provider: string, model_id: string, reasoning: boolean, context_window = 128000): ModelCapability {
  return { provider, model_id, context_window, max_output_tokens: 4096, capabilities: reasoning ? { reasoning: true, reasoning_parameter: "reasoning_effort" } : { reasoning: false } };
}

describe("ModelPicker", () => {
  it("groups catalog entries by provider", () => {
    render(<ModelPicker models={[catalogModel("openai", "gpt-4.1", false), catalogModel("anthropic", "claude-sonnet", true, 200000)]} onChange={() => undefined} />);
    expect(screen.getByRole("group", { name: "openai" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "anthropic" })).toBeTruthy();
  });

  it("shows the catalog context window next to each model", () => {
    render(<ModelPicker models={[catalogModel("openai", "gpt-4.1", false)]} onChange={() => undefined} />);
    expect(screen.getByRole("option", { name: /gpt-4\.1 · 128k ctx/ })).toBeTruthy();
  });

  it("emits the selected catalog model", () => {
    const model = catalogModel("openai", "gpt-4.1", false);
    const onChange = vi.fn();
    render(<ModelPicker models={[model]} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "openai/gpt-4.1" } });
    expect(onChange).toHaveBeenCalledWith(model);
  });
});

describe("ReasoningPicker", () => {
  const all = supportedReasoning(catalogModel("openai", "gpt-4.1", true));

  it("renders five ink-dot levels with the current strength filled", () => {
    render(<ReasoningPicker value="standard" supported={all} onChange={() => undefined} />);
    const standard = screen.getByRole("radio", { name: "standard" });
    expect(standard.getAttribute("aria-checked")).toBe("true");
    expect(standard.textContent).toContain("●●○○");
    expect(screen.getByRole("radio", { name: "fast" }).textContent).toContain("●○○○");
    expect(screen.getByRole("radio", { name: "deep" }).textContent).toContain("●●●○");
    expect(screen.getByRole("radio", { name: "max" }).textContent).toContain("●●●●");
  });

  it("greys out unsupported levels with a tooltip reason and blocks selection", () => {
    const onChange = vi.fn();
    render(<ReasoningPicker value="auto" supported={["auto"]} onChange={onChange} />);
    const max = screen.getByRole("radio", { name: "max" }) as HTMLButtonElement;
    expect(max.disabled).toBe(true);
    expect(max.title).toMatch(/does not support/i);
    fireEvent.click(max);
    expect(onChange).not.toHaveBeenCalled(); // 禁静默降级：选不动，也不会悄悄切换
  });

  it("flags an unsupported current value instead of silently downgrading", () => {
    const onChange = vi.fn();
    render(<ReasoningPicker value="deep" supported={["auto"]} onChange={onChange} />);
    expect(screen.getByRole("status").textContent).toMatch(/not supported/i);
    expect(onChange).not.toHaveBeenCalledWith("auto"); // 保持用户选择并显式提示
  });

  it("keeps model and reasoning controls separate", () => {
    const model = { provider: "local", model_id: "writer", capabilities: { reasoning: false } };
    const onModel = vi.fn(); const onReasoning = vi.fn();
    render(<><ModelPicker models={[model]} onChange={onModel} /><ReasoningPicker value="auto" supported={supportedReasoning(model)} onChange={onReasoning} /></>);
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "local/writer" } });
    expect(onModel).toHaveBeenCalledWith(model);
    expect((screen.getByRole("radio", { name: "max" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
