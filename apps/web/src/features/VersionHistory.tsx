import { useEffect, useState } from "react";
import { activateChapterVersion, getChapterDiff, listChapterVersions, listChapters, type Chapter, type ChapterVersion, type Project } from "../lib/api/client";
import { useLanguage } from "../lib/i18n";

type Props = {
  versions: ChapterVersion[];
  activeVersion?: number;
  diff: string[];
  onRestore: (version: ChapterVersion) => void;
  onDiff: (version: ChapterVersion) => void;
};

export function VersionHistory({ versions, activeVersion, diff = [], onRestore, onDiff }: Props) {
  const { t } = useLanguage();
  if (versions.length === 0) return <section className="version-history"><strong>{t("versionHistory")}</strong><p className="empty">{t("savedVersionsEmpty")}</p></section>;
  return <section className="version-history" aria-label={t("versionHistory")}><strong>{t("versionHistory")}</strong>{versions.slice().reverse().map(version => <div className="version-row" key={version.id}><div><b>{t("version")} {version.version_no}</b>{version.version_no === activeVersion && <span className="version-active">{t("activeVersion")}</span>}<small>{version.word_count} {t("words")}</small></div><div className="version-actions"><button onClick={() => onDiff(version)} aria-label={`${t("compare")} ${t("version")} ${version.version_no}`}>{t("compare")}</button><button onClick={() => onRestore(version)} aria-label={`${t("restore")} ${t("version")} ${version.version_no}`} disabled={version.version_no === activeVersion}>{t("restore")}</button></div></div>)}{diff.length > 0 && <div className="version-diff" aria-label={t("changes")}><b>{t("changes")}</b>{diff.map((line, index) => <code key={`${index}-${line}`}>{line}</code>)}</div>}</section>;
}

export function ProjectVersionHistory({ project }: { project: Project }) {
  const { t } = useLanguage();
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
  return <section><label className="version-chapter">{t("chapter")}<select value={chapterId} onChange={event => { setChapterId(event.target.value); setDiff([]); }}>{chapters.map(chapter => <option key={chapter.id} value={chapter.id}>{t("chapter")} {chapter.chapter_no}: {chapter.title}</option>)}</select></label><VersionHistory versions={versions} activeVersion={activeVersion} diff={diff} onRestore={restore} onDiff={showDiff} /></section>;
}
