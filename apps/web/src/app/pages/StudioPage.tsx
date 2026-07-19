import { useEffect, useRef, useState } from "react";
import { createSelectionAction, listChapters, listChapterVersions, requestExport, saveChapterVersion, type Chapter, type ChapterVersion } from "../../lib/api/client";
import { loadDraft, saveDraft } from "../../lib/drafts";
import { ChapterTree } from "../../features/editor/ChapterTree";
import { ManuscriptEditor } from "../../features/editor/ManuscriptEditor";
import { toSelectionActionRequest, type EditorAction } from "../../features/editor/editorState";
import { ExportDialog } from "../../features/export/ExportDialog";
import { ProjectVersionHistory } from "../../features/VersionHistory";
import { useProjectsQuery } from "../query";

export function StudioPage({ projectId, chapterId }: { projectId: string; chapterId?: string }) {
  const projectsQuery = useProjectsQuery();
  const project = projectsQuery.data?.find(item => item.id === projectId);
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [content, setContent] = useState("");
  const [baseVersion, setBaseVersion] = useState<number | undefined>();
  const [baseVersionId, setBaseVersionId] = useState<string | null>(null);
  const [message, setMessage] = useState("Loading chapters…");
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => { window.localStorage.setItem("proseforge.current-project", projectId); }, [projectId]);
  useEffect(() => {
    listChapters(projectId).then(items => {
      setChapters(items);
      setChapter(items.find(item => item.id === chapterId) ?? items[0] ?? null);
      setMessage(items.length ? "Ready to write" : "Import an outline to create chapters");
    }).catch(() => setMessage("Unable to load chapters"));
  }, [projectId, chapterId]);

  const contentRef = useRef(content);
  contentRef.current = content;
  useEffect(() => {
    if (!chapter) return;
    let active = true;
    const loadVersions = (initial = false) => listChapterVersions(chapter.id).then(items => {
      if (!active) return;
      setVersions(items);
      const current = items.find(item => item.id === chapter.active_version_id) ?? items.at(-1);
      if (!initial && contentRef.current.trim()) return;
      if (!contentRef.current.trim() || current?.content) setContent(current?.content ?? "");
      setBaseVersion(current?.version_no);
      setBaseVersionId(current?.id ?? null);
      if (items.length) setMessage(`Loaded saved version ${current?.version_no ?? items.at(-1)?.version_no}`);
    }).catch(() => setMessage("Unable to load the saved chapter"));
    loadVersions(true);
    const timer = window.setInterval(() => { if (!contentRef.current.trim()) loadVersions(); }, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [chapter]);

  const chapterDraftKey = { projectId, chapterId: chapter?.id ?? "none", draftType: "chapter" as const };
  useEffect(() => { if (chapter) loadDraft(chapterDraftKey).then(value => { if (value.trim()) setContent(current => current.trim() ? current : value); }).catch(() => undefined); }, [chapter?.id]);
  useEffect(() => { if (chapter && content.trim()) saveDraft(chapterDraftKey, content).catch(() => undefined); }, [chapter?.id, content]);

  const save = async () => {
    if (!chapter) return;
    try {
      const version = await saveChapterVersion(chapter.id, content, baseVersion);
      setVersions(items => [...items, version]);
      setBaseVersion(version.version_no);
      setBaseVersionId(version.id);
      await saveDraft(chapterDraftKey, "");
      setMessage(`Saved version ${version.version_no}`);
    } catch { setMessage("Save conflict: reload the latest version"); }
  };

  const createProposal = async (action: EditorAction) => {
    if (!chapter || !baseVersionId) { setMessage("Save the chapter before creating a proposal."); return; }
    try {
      const result = await createSelectionAction(chapter.id, { ...toSelectionActionRequest(action), base_version_id: baseVersionId });
      const count = result.candidate_proposal_ids?.length ?? (result.proposal_id ? 1 : 0);
      setMessage(count === 1 ? "Proposal ready for review." : `${count} candidate proposals ready for review.`);
    } catch { setMessage("Selection changed elsewhere. Reload and try again."); }
  };

  const downloadMarkdown = async () => { try { const result = await requestExport(projectId, "md", versions.map(item => item.id)); window.open(result.download_url, "_blank", "noopener,noreferrer"); } catch { setMessage("Export could not be prepared."); } };
  const exportSnapshot = async (payload: { format: "txt" | "md" | "docx" | "epub"; version_ids: string[] }) => { try { const result = await requestExport(projectId, payload.format, payload.version_ids); window.open(result.download_url, "_blank", "noopener,noreferrer"); setExportOpen(false); } catch { setMessage("Export could not be prepared."); } };

  return <><section className="studio-layout"><ChapterTree chapters={chapters} currentChapterId={chapter?.id} onSelect={setChapter} /><div className="editor-pane"><div className="chapter-head"><span>{chapter ? `Chapter ${String(chapter.chapter_no).padStart(2, "0")}` : (project?.title ?? "Writing Studio")}</span><span className="status" aria-live="polite">{message}</span></div><ManuscriptEditor content={content} baseVersionId={baseVersionId} onContentChange={setContent} onAction={createProposal} /><button className="primary" onClick={save} disabled={!chapter}>Save version</button><button onClick={downloadMarkdown}>Download Markdown</button><button onClick={() => setExportOpen(true)}>Export snapshot</button>{exportOpen && <div role="dialog" aria-modal="true" aria-label="Export snapshot"><ExportDialog projectId={projectId} versionIds={versions.map(item => item.id)} onExport={exportSnapshot} /><button onClick={() => setExportOpen(false)}>Cancel</button></div>}</div></section>{project && <ProjectVersionHistory project={project} />}</>;
}
