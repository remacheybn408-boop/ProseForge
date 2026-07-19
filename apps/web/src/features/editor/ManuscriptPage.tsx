import { StudioPage } from "../../app/pages/StudioPage";

/** Dedicated chapter route; the studio keeps the same editor when no chapter is preselected. */
export function ManuscriptPage({ projectId, chapterId }: { projectId: string; chapterId: string }) {
  return <StudioPage projectId={projectId} chapterId={chapterId} />;
}
