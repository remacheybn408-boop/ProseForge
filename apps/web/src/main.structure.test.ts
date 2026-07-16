import { describe, expect, it } from "vitest";

describe("web entrypoint structure", () => {
  it("keeps business components out of main.tsx", () => {
    const source = (import.meta.glob("./main.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./main.tsx"];

    expect(source).not.toMatch(/function (Login|Projects|Studio|OutlineView|ContextView|WorkflowView|SettingsView|App)\b/);
    expect(source.split("\n").length).toBeLessThan(30);
  });

  it("uses the translated label for the usage navigation item", () => {
    const source = (import.meta.glob("./workspace.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./workspace.tsx"];

    expect(source).toContain('nav("usage", t("usage"))');
    expect(source).not.toContain('nav("usage", "Usage")');
  });
});
