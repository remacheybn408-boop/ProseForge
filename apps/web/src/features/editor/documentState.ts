export type ChapterDraftKey = {
  projectId: string;
  chapterId: string;
  draftType: "chapter";
};

export type LocalChapterState = {
  chapterId: string | null;
  loadedVersionId: string | null;
  dirty: boolean;
};

export type ServerChapterVersion = {
  chapterId: string;
  versionId: string;
};

export function chapterDraftKey(projectId: string, chapterId: string): ChapterDraftKey {
  return { projectId, chapterId, draftType: "chapter" };
}

export function shouldApplyServerVersion(
  local: LocalChapterState,
  server: ServerChapterVersion,
): boolean {
  if (local.chapterId !== server.chapterId) return true;
  if (local.dirty) return false;
  return local.loadedVersionId !== server.versionId;
}
