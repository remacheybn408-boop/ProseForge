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
    expect(standard.textContent).toContain("●●○○○");
    expect(screen.getByRole("radio", { name: "fast" }).textContent).toContain("●○○○○");
    expect(screen.getByRole("radio", { name: "deep" }).textContent).toContain("●●●○○");
    expect(screen.getByRole("radio", { name: "max" }).textContent).toContain("●●●●●");
    expect(screen.getByRole("radio", { name: "auto" }).textContent).not.toContain("●");
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

  it("moves selection with arrow keys per APG radiogroup semantics", () => {
    const onChange = vi.fn();
    render(<ReasoningPicker value="standard" supported={all} onChange={onChange} />);
    const standard = screen.getByRole("radio", { name: "standard" });
    fireEvent.keyDown(standard, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("deep");
    fireEvent.keyDown(standard, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("fast");
    fireEvent.keyDown(standard, { key: "ArrowDown" });
    expect(onChange).toHaveBeenCalledWith("deep");
    fireEvent.keyDown(standard, { key: "ArrowUp" });
    expect(onChange).toHaveBeenCalledWith("fast");
  });

  it("wraps around and skips disabled levels during arrow navigation", () => {
    const onChange = vi.fn();
    render(<ReasoningPicker value="standard" supported={["auto", "standard"]} onChange={onChange} />);
    fireEvent.keyDown(screen.getByRole("radio", { name: "standard" }), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("auto"); // deep/max disabled → 跳过并回卷
    fireEvent.keyDown(screen.getByRole("radio", { name: "auto" }), { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("standard"); // 反向同样跳过 disabled
  });

  it("jumps to the first and last enabled levels with Home and End", () => {
    const onChange = vi.fn();
    render(<ReasoningPicker value="fast" supported={all} onChange={onChange} />);
    const fast = screen.getByRole("radio", { name: "fast" });
    fireEvent.keyDown(fast, { key: "End" });
    expect(onChange).toHaveBeenCalledWith("max");
    fireEvent.keyDown(fast, { key: "Home" });
    expect(onChange).toHaveBeenCalledWith("auto");
  });

  it("keeps a roving tabindex with only the checked radio in the tab order", () => {
    render(<ReasoningPicker value="standard" supported={all} onChange={() => undefined} />);
    expect((screen.getByRole("radio", { name: "standard" }) as HTMLButtonElement).tabIndex).toBe(0);
    for (const name of ["auto", "fast", "deep", "max"]) {
      expect((screen.getByRole("radio", { name }) as HTMLButtonElement).tabIndex).toBe(-1);
    }
  });

  it("puts the first enabled level in the tab order when the current value is unsupported", () => {
    render(<ReasoningPicker value="deep" supported={["auto"]} onChange={() => undefined} />);
    expect((screen.getByRole("radio", { name: "auto" }) as HTMLButtonElement).tabIndex).toBe(0);
  });
});
