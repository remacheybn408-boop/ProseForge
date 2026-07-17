import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("web entrypoint", () => {
  it("only mounts the application shell", () => {
    const source = readFileSync("src/main.tsx", "utf8");

    expect(source).toContain('import App from "./app/App"');
    expect(source).toContain("createRoot");
    expect(source).not.toContain("function Studio");
    expect(source).not.toContain("function SettingsView");
    expect(source.length).toBeLessThan(1000);
  });
});
