import { describe, expect, it } from "vitest";
import { createTranslator, defaultLanguage, languageStorageKey, loadLanguage, saveLanguage } from "./i18n";

describe("web language preferences", () => {
  it("defaults to simplified Chinese and translates representative labels", () => {
    localStorage.removeItem(languageStorageKey);
    expect(defaultLanguage).toBe("zh-CN");
    expect(loadLanguage()).toBe("zh-CN");
    expect(createTranslator("zh-CN")("projects")).toBe("项目");
  });

  it("persists English and translates the same label", () => {
    saveLanguage("en-US");
    expect(loadLanguage()).toBe("en-US");
    expect(createTranslator("en-US")("projects")).toBe("Projects");
    expect(createTranslator("en-US")("usage")).toBe("Usage");
  });

  it("rejects invalid stored values", () => {
    localStorage.setItem(languageStorageKey, "fr-FR");
    expect(loadLanguage()).toBe("zh-CN");
  });
});
