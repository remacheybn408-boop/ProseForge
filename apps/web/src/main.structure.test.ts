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

  it("keeps authentication UI outside the application shell", () => {
    const workspace = (import.meta.glob("./workspace.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./workspace.tsx"];
    const login = (import.meta.glob("./features/auth/Login.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./features/auth/Login.tsx"];

    expect(workspace).not.toMatch(/function Login\b/);
    expect(login).toContain("export function Login");
  });

  it("keeps project-list UI outside the application shell", () => {
    const workspace = (import.meta.glob("./workspace.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./workspace.tsx"];
    const projects = (import.meta.glob("./features/projects/Projects.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./features/projects/Projects.tsx"];

    expect(workspace).not.toMatch(/function Projects\b/);
    expect(projects).toContain("export function Projects");
  });

  it("keeps outline intake UI outside the application shell", () => {
    const workspace = (import.meta.glob("./workspace.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./workspace.tsx"];
    const outline = (import.meta.glob("./features/outlines/OutlineView.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>)["./features/outlines/OutlineView.tsx"];

    expect(workspace).not.toMatch(/function OutlineView\b/);
    expect(outline).toContain("export function OutlineView");
  });
});
