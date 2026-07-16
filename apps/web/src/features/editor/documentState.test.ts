import { describe, expect, it } from "vitest";
import { chapterDraftKey, shouldApplyServerVersion } from "./documentState";

describe("chapter document state", () => {
  it("names drafts by project and chapter", () => {
    expect(chapterDraftKey("project-1", "chapter-2")).toEqual({
      projectId: "project-1",
      chapterId: "chapter-2",
      draftType: "chapter",
    });
  });

  it("does not replace dirty local text with a server version", () => {
    expect(shouldApplyServerVersion(
      { chapterId: "chapter-2", loadedVersionId: "version-1", dirty: true },
      { chapterId: "chapter-2", versionId: "version-2" },
    )).toBe(false);
  });

  it("loads a new chapter or a newer version when the document is clean", () => {
    expect(shouldApplyServerVersion(
      { chapterId: "chapter-1", loadedVersionId: "version-1", dirty: false },
      { chapterId: "chapter-2", versionId: "version-1" },
    )).toBe(true);
    expect(shouldApplyServerVersion(
      { chapterId: "chapter-2", loadedVersionId: "version-1", dirty: false },
      { chapterId: "chapter-2", versionId: "version-2" },
    )).toBe(true);
  });
});
