import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChapterTree } from "./ChapterTree";

describe("ChapterTree", () => {
  const chapters = [
    { id: "c1", project_id: "p1", chapter_no: 1, title: "Arrival", status: "draft" },
    { id: "c2", project_id: "p1", chapter_no: 2, title: "Departure", status: "final" },
  ];

  it("selects a chapter and reports drag reordering", () => {
    const onSelect = vi.fn();
    const onReorder = vi.fn();
    render(<ChapterTree chapters={chapters} currentChapterId="c1" onSelect={onSelect} onReorder={onReorder} />);

    fireEvent.click(screen.getByText(/Departure/));
    expect(onSelect).toHaveBeenCalledWith(chapters[1]);
    const first = screen.getByText(/Arrival/).closest("button") as HTMLButtonElement;
    const second = screen.getByText(/Departure/).closest("button") as HTMLButtonElement;
    fireEvent.dragStart(second);
    fireEvent.drop(first);
    expect(onReorder).toHaveBeenCalledWith(["c2", "c1"]);
    expect(screen.getByText("DRAFT")).toBeTruthy();
    expect(screen.getByText("FINAL")).toBeTruthy();
  });
});
