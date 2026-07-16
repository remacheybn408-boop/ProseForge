import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChapterEditor } from "./ChapterEditor";
import { LanguageProvider, languageStorageKey } from "../../lib/i18n";

describe("ChapterEditor", () => {
  it("exposes draft state and a save action", () => {
    const onChange = vi.fn();
    localStorage.setItem(languageStorageKey, "en-US");
    render(<LanguageProvider><ChapterEditor content="Draft" dirty onChange={onChange} onSave={vi.fn()} /></LanguageProvider>);

    fireEvent.change(screen.getByLabelText("Chapter editor"), { target: { value: "Updated" } });
    expect(onChange).toHaveBeenCalledWith("Updated");
    expect(screen.getByText("Unsaved draft")).toBeTruthy();
  });
});
