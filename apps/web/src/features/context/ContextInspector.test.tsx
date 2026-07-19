import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContextInspector } from "./ContextInspector";

describe("ContextInspector", () => {
  it("renders included facts, omitted reasons, and the token budget", () => {
    render(<ContextInspector snapshot={{
      id: "snapshot-1", snapshot_hash: "hash", payload: {
        blocks: [{ source_type: "story_bible", source_id: "fact-1", text: "Mira", token_estimate: 12, pinned: true }],
        omitted: [{ source_id: "fact-2", reason: "not_triggered" }],
        budget: { context_window: 8192, input_tokens: 6000, output_reserve: 1024 },
      },
    }} />);

    expect(screen.getByText("Included context")).toBeTruthy();
    expect(screen.getByText("fact-1")).toBeTruthy();
    expect(screen.getByText(/not triggered/i)).toBeTruthy();
    expect(screen.getByText(/6,000/)).toBeTruthy();
  });
});
