import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VersionHistory } from "./VersionHistory";
import { LanguageProvider, languageStorageKey } from "../lib/i18n";

describe("VersionHistory", () => {
  it("shows versions and exposes restore and diff actions", () => {
    const onRestore = vi.fn();
    const onDiff = vi.fn();
    localStorage.setItem(languageStorageKey, "en-US");
    render(<LanguageProvider><VersionHistory versions={[{ id: "v1", chapter_id: "c1", version_no: 1, content: "old", word_count: 1 }, { id: "v2", chapter_id: "c1", version_no: 2, content: "new", word_count: 1 }]} activeVersion={2} diff={[]} onRestore={onRestore} onDiff={onDiff} /></LanguageProvider>);

    expect(screen.getByText("Version history")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Restore version 1/i }));
    fireEvent.click(screen.getByRole("button", { name: /Compare version 1/i }));
    expect(onRestore).toHaveBeenCalledWith(expect.objectContaining({ version_no: 1 }));
    expect(onDiff).toHaveBeenCalledWith(expect.objectContaining({ version_no: 1 }));
  });
});
