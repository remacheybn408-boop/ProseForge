import { useEffect, useState } from "react";
import { StatusStamp } from "../../components/ink/Ink";
import type { Chapter } from "../../lib/api/client";

type ChapterTreeProps = {
  chapters: Chapter[];
  currentChapterId?: string;
  onSelect: (chapter: Chapter) => void;
  onReorder?: (chapterIds: string[]) => void;
};

function stampFor(status: string) {
  if (status === "final") return { label: "FINAL", tone: "success" as const };
  if (status === "revising") return { label: "REVISING", tone: "default" as const };
  return { label: "DRAFT", tone: "error" as const };
}

export function ChapterTree({ chapters, currentChapterId, onSelect, onReorder }: ChapterTreeProps) {
  const [ordered, setOrdered] = useState(chapters);
  const [draggedId, setDraggedId] = useState<string>();
  useEffect(() => setOrdered(chapters), [chapters]);

  const dropOn = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return;
    const from = ordered.findIndex(chapter => chapter.id === draggedId);
    const to = ordered.findIndex(chapter => chapter.id === targetId);
    if (from < 0 || to < 0) return;
    const next = [...ordered];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setOrdered(next);
    onReorder?.(next.map(chapter => chapter.id));
    setDraggedId(undefined);
  };

  return <aside className="chapter-tree" aria-label="Chapter tree">
    <strong>Chapters</strong>
    {ordered.map(chapter => {
      const stamp = stampFor(chapter.status);
      return <button
        className={chapter.id === currentChapterId ? "selected" : ""}
        draggable
        key={chapter.id}
        onClick={() => onSelect(chapter)}
        onDragStart={() => setDraggedId(chapter.id)}
        onDragEnd={() => setDraggedId(undefined)}
        onDragOver={event => event.preventDefault()}
        onDrop={() => dropOn(chapter.id)}
      ><span>{String(chapter.chapter_no).padStart(2, "0")} · {chapter.title}</span><StatusStamp status={stamp.tone}>{stamp.label}</StatusStamp></button>;
    })}
    {!ordered.length && <small>No chapters yet.</small>}
  </aside>;
}
