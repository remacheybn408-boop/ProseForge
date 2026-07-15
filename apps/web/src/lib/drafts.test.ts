import { describe, expect, it } from "vitest";

import { loadDraft, saveDraft } from "./drafts";

describe("draft persistence", () => {
  it("is safe when IndexedDB is unavailable in a restricted browser context", async () => {
    await expect(saveDraft({ conversationId: "c1", branchId: "b1", draftType: "chat" }, "draft")).resolves.toBeUndefined();
    await expect(loadDraft({ conversationId: "c1", branchId: "b1", draftType: "chat" })).resolves.toBe("");
  });
});
