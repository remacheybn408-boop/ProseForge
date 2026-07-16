import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../lib/i18n";
import { ContextView } from "./ContextView";
import { deleteContext, listContext, listModelProfiles, updateContext } from "../../lib/api/client";

vi.mock("../../lib/api/client", () => ({
  addContext: vi.fn(),
  deleteContext: vi.fn(),
  listContext: vi.fn(),
  listModelProfiles: vi.fn(),
  updateContext: vi.fn(),
}));

const project = { id: "project-1", slug: "project", title: "Project", genre: "", style: "", language: "en-US", status: "ACTIVE" };

describe("ContextView", () => {
  afterEach(cleanup);

  beforeEach(() => {
    localStorage.setItem("proseforge.web.language", "en-US");
    vi.mocked(listModelProfiles).mockResolvedValue([]);
  });

  it("does not display a fixed context window while the model budget is loading", () => {
    vi.mocked(listContext).mockImplementation(() => new Promise(() => undefined));

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);

    expect(screen.queryByText("128K available")).toBeNull();
  });

  it("renders the context window returned for the selected model", async () => {
    vi.mocked(listContext).mockResolvedValue({ items: [], used_tokens: 5000, context_window: 20000, available_tokens: 11000, system_reserved_tokens: 0, history_tokens: 0, output_reserve_tokens: 4000 });

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);

    await waitFor(() => expect(screen.getByText("11K available")).toBeTruthy());
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("31");
  });

  it("shows each memory estimate and its editing controls", async () => {
    const item = { id: "item-1", project_id: "project-1", source_type: "manual", content: "Mira", pinned: false, priority: 20, excluded: false, provenance: {}, token_estimate: 4 };
    vi.mocked(listContext).mockResolvedValue({ items: [item], used_tokens: 4, context_window: 20000, available_tokens: 15996, system_reserved_tokens: 0, history_tokens: 0, output_reserve_tokens: 4000 } as never);

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);

    await waitFor(() => expect(screen.getByText("4 tokens")).toBeTruthy());
    expect(screen.getByRole("spinbutton", { name: "Priority" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "Excluded" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy();
  });

  it("persists priority, exclusion, edits, and confirmed deletion", async () => {
    const item = { id: "item-1", project_id: "project-1", source_type: "manual", content: "Mira", pinned: false, priority: 20, excluded: false, provenance: {}, token_estimate: 4 };
    vi.mocked(listContext).mockResolvedValue({ items: [item], used_tokens: 4, context_window: 20000, available_tokens: 15996, system_reserved_tokens: 0, history_tokens: 0, output_reserve_tokens: 4000 } as never);
    vi.mocked(updateContext).mockResolvedValue(item as never);
    vi.mocked(deleteContext).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);
    await waitFor(() => expect(screen.getByText("4 tokens")).toBeTruthy());

    fireEvent.change(screen.getByRole("spinbutton", { name: "Priority" }), { target: { value: "70" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Excluded" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save memory" })).toBeTruthy());
    fireEvent.change(screen.getByRole("textbox", { name: "Edit" }), { target: { value: "Mira remembers the lighthouse" } });
    fireEvent.click(screen.getByRole("button", { name: "Save memory" }));

    expect(updateContext).toHaveBeenCalledWith("item-1", { priority: 70 });
    expect(updateContext).toHaveBeenCalledWith("item-1", { excluded: true });
    await waitFor(() => expect(updateContext).toHaveBeenCalledWith("item-1", { content: "Mira remembers the lighthouse" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteContext).toHaveBeenCalledWith("item-1"));
  });
});
