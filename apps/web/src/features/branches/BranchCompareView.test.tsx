import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BranchCompareResult } from "../../lib/api/client";
import { BranchCompareView } from "./BranchCompareView";

const result: BranchCompareResult = {
  common_count: 1,
  left: [
    { id: "a1", role: "assistant", content: "original reply", generation_attempt: 1, parent_message_id: "u1" },
  ],
  right: [
    { id: "u2", role: "user", content: "edited question", generation_attempt: 1, parent_message_id: "u1" },
    { id: "a2", role: "assistant", content: "new reply", generation_attempt: 1, parent_message_id: "u2" },
  ],
};

const prefix = [{ id: "u1", role: "user", content: "base question" }];

describe("BranchCompareView", () => {
  it("renders the divergent tails in two columns", () => {
    render(<BranchCompareView result={result} leftLabel="Main" rightLabel="Edited message" prefix={prefix} />);
    expect(screen.getByLabelText("Main branch")).toBeTruthy();
    expect(screen.getByLabelText("Edited message branch")).toBeTruthy();
    const left = screen.getByLabelText("Main branch");
    const right = screen.getByLabelText("Edited message branch");
    expect(left.textContent).toContain("original reply");
    expect(left.textContent).not.toContain("edited question");
    expect(right.textContent).toContain("edited question");
    expect(right.textContent).toContain("new reply");
  });

  it("dims the shared prefix instead of repeating it in the columns", () => {
    const { container } = render(<BranchCompareView result={result} leftLabel="Main" rightLabel="Edited message" prefix={prefix} />);
    const dimmed = container.querySelector(".branch-compare-prefix");
    expect(dimmed).toBeTruthy();
    expect(dimmed?.textContent).toContain("base question");
    expect(screen.getByLabelText("Main branch").textContent).not.toContain("base question");
    expect(screen.getByText("1 shared message")).toBeTruthy();
  });

  it("notes generation attempts for regenerated candidates", () => {
    const withAttempts: BranchCompareResult = {
      common_count: 1,
      left: [{ id: "a9", role: "assistant", content: "third take", generation_attempt: 3, parent_message_id: "u1" }],
      right: [],
    };
    render(<BranchCompareView result={withAttempts} leftLabel="Main" rightLabel="Empty" prefix={prefix} />);
    expect(screen.getByText("attempt 3")).toBeTruthy();
  });
});
