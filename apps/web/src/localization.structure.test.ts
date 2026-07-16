import { describe, expect, it } from "vitest";
import { createTranslator } from "./lib/i18n";

describe("bilingual feature copy", () => {
  it("provides readable Chinese and English labels for product feedback", () => {
    const zh = createTranslator("zh-CN");
    const en = createTranslator("en-US");

    expect(zh("removeCredential")).toBe("删除凭据");
    expect(zh("outlineInitialMessage")).toBe("导入大纲或在下方描述你的故事。");
    expect(zh("usageLoading")).toBe("正在加载用量…");
    expect(en("removeCredential")).toBe("Remove credential");
    expect(en("workflowActionUnavailable")).toBe("That action is not available in the current state.");
    expect(en("estimatedTotal")).toBe("Estimated total");
  });

  it("keeps user-facing feature copy in the translation dictionary", () => {
    const sources = Object.entries(import.meta.glob("./features/**/*.tsx", { query: "?raw", import: "default", eager: true }))
      .filter(([path]) => !path.includes(".test."))
      .map(([, source]) => source as string);
    const forbidden = [
      "Import an outline or describe your story below.",
      "A few answers are needed before confirmation.",
      "No workflow has been started yet.",
      "That action is not available in the current state.",
      "Loading usage…",
      "Usage is unavailable right now.",
      "Actual input",
      "Actual output",
      "Estimated total",
      "Version history",
      "Unsaved draft",
      "Cost unavailable",
      "Unable to load the saved chapter",
      "Save conflict: reload the latest version",
      "Restored version",
      "Could not restore that version",
      "Diff loaded:",
      "Could not load the version diff",
      "Chat could not be queued; check the worker and provider settings.",
      "Alternative branch created.",
      "Could not create an alternative branch.",
      "Export could not be prepared.",
      ">Email<",
      ">Password<",
      "Chapter editor",
    ];

    for (const source of sources) {
      for (const text of forbidden) expect(source).not.toContain(text);
    }
  });
});
