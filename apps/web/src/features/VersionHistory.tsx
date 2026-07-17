import { useEffect, useState } from "react";
import { activateChapterVersion, getChapterDiff, listChapterVersions, listChapters, type Chapter, type ChapterVersion, type Project } from "../lib/api/client";

type Props = {
  versions: ChapterVersion[];
  activeVersion?: number;
  diff: string[];
  onRestore: (version: ChapterVersion) => void;
  onDiff: (version: ChapterVersion) => void;
};

export function VersionHistory({ versions, activeVersion, diff = [], onRestore, onDiff }: Props) {
  if (versions.length === 0) return <section className="version-history"><strong>Version history</strong><p className="empty">Saved versions will appear here.</p></section>;
  return <section className="version-history" aria-label="Version history"><strong>Version history</strong>{versions.slice().reverse().map(version => <div className="version-row" key={version.id}><div><b>Version {version.version_no}</b>{version.version_no === activeVersion && <span className="version-active">Active</span>}<small>{version.word_count} words</small></div><div className="version-actions"><button onClick={() => onDiff(version)} aria-label={`Compare version ${version.version_no}`}>Compare</button><button onClick={() => onRestore(version)} aria-label={`Restore version ${version.version_no}`} disabled={version.version_no === activeVersion}>Restore</button></div></div>)}{diff.length > 0 && <div className="version-diff" aria-label="Version diff"><b>Changes</b>{diff.map((line, index) => <code key={`${index}-${line}`}>{line}</code>)}</div>}</section>;
}

export function ProjectVersionHistory({ project }: { project: Project }) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapterId, setChapterId] = useState<string>();
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [activeVersion, setActiveVersion] = useState<number>();
  const [diff, setDiff] = useState<string[]>([]);
  useEffect(() => { listChapters(project.id).then(items => { setChapters(items); setChapterId(items[0]?.id); }).catch(() => undefined); }, [project.id]);
  useEffect(() => { if (!chapterId) return; listChapterVersions(chapterId).then(items => { setVersions(items); setActiveVersion(chapters.find(item => item.id === chapterId)?.active_version_id ? items.find(item => item.id === chapters.find(chapter => chapter.id === chapterId)?.active_version_id)?.version_no : items.at(-1)?.version_no); }).catch(() => undefined); }, [chapterId, chapters]);
  if (!chapterId) return null;
  const restore = async (version: ChapterVersion) => { await activateChapterVersion(chapterId, version.id); setActiveVersion(version.version_no); };
  const showDiff = async (version: ChapterVersion) => { if (!activeVersion || version.version_no === activeVersion) return setDiff([]); const result = await getChapterDiff(chapterId, version.version_no, activeVersion); setDiff(result.diff); };
  return <section><label className="version-chapter">Chapter<select value={chapterId} onChange={event => { setChapterId(event.target.value); setDiff([]); }}>{chapters.map(chapter => <option key={chapter.id} value={chapter.id}>Chapter {chapter.chapter_no}: {chapter.title}</option>)}</select></label><VersionHistory versions={versions} activeVersion={activeVersion} diff={diff} onRestore={restore} onDiff={showDiff} /></section>;
}
