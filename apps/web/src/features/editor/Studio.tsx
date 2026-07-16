import { useEffect, useState } from "react";
import {
  activateChapterVersion, createConversation, forkConversation, getChapterDiff, listChapters, listChapterVersions,
  listMessages, listModelProfiles, requestExport, saveChapterVersion, sendMessage, subscribeConversationEvents,
  type Chapter, type ChapterVersion, type ModelProfile, type Project,
} from "../../lib/api/client";
import { loadDraft, saveDraft } from "../../lib/drafts";
import { chapterDraftKey as makeChapterDraftKey, shouldApplyServerVersion } from "./documentState";
import { useLanguage } from "../../lib/i18n";

function newClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}

export function Studio({ project }: { project: Project }) {
  const { t } = useLanguage();
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [diff, setDiff] = useState<string[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [content, setContent] = useState("");
  const [baseVersion, setBaseVersion] = useState<number | undefined>();
  const [loadedChapterId, setLoadedChapterId] = useState<string | null>(null);
  const [loadedVersionId, setLoadedVersionId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState(t("loadingChapters"));
  const [conversation, setConversation] = useState<{ id: string; branch_id: string } | null>(null);
  const [chat, setChat] = useState<{ id: string; role: string; content: string; status: string }[]>([]);
  const [draft, setDraft] = useState("");
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(true);

  useEffect(() => {
    listChapters(project.id)
      .then(items => {
        setChapters(items);
        setChapter(items[0] ?? null);
        setMessage(items.length ? t("readyToWrite") : t("importOutlineToCreate"));
      })
      .catch(() => setMessage(t("unableLoad")));
    listModelProfiles()
      .then(items => {
        setProfiles(items);
        setProfileId(items[0]?.id ?? "");
      })
      .catch(() => undefined);
  }, [project.id, t]);

  useEffect(() => {
    if (!chapter) return;
    let active = true;
    let timer: number | undefined;
    const loadVersions = async () => {
      try {
        const items = await listChapterVersions(chapter.id);
        if (!active) return;
        setVersions(items);
        const current = items.find(item => item.id === chapter.active_version_id) ?? items.at(-1);
        const server = { chapterId: chapter.id, versionId: current?.id ?? "empty" };
        if (shouldApplyServerVersion({ chapterId: loadedChapterId, loadedVersionId, dirty }, server)) {
          setContent(current?.content ?? "");
          setLoadedChapterId(chapter.id);
          setLoadedVersionId(current?.id ?? null);
          setDirty(false);
        }
        setBaseVersion(current?.version_no);
        setDiff([]);
        if (items.length) setMessage(t("loadedVersion") + " " + (current?.version_no ?? items.at(-1)?.version_no));
        else timer = window.setTimeout(() => { void loadVersions(); }, 1000);
      } catch {
        if (active) {
          setMessage(t("loadSavedChapterFailed"));
          timer = window.setTimeout(() => { void loadVersions(); }, 1000);
        }
      }
    };
    void loadVersions();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [chapter?.id, chapter?.active_version_id, t]);

  const currentChapterDraftKey = chapter ? makeChapterDraftKey(project.id, chapter.id) : null;
  useEffect(() => {
    if (!currentChapterDraftKey) return;
    loadDraft(currentChapterDraftKey)
      .then(value => {
        if (value.trim()) {
          setContent(current => current.trim() ? current : value);
          setDirty(true);
        }
      })
      .catch(() => undefined);
  }, [currentChapterDraftKey?.projectId, currentChapterDraftKey?.chapterId]);

  useEffect(() => {
    if (!currentChapterDraftKey || !content.trim() || !dirty) return;
    const timer = window.setTimeout(() => {
      saveDraft(currentChapterDraftKey, content).catch(() => undefined);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [currentChapterDraftKey?.projectId, currentChapterDraftKey?.chapterId, content, dirty]);

  const draftKey = {
    conversationId: conversation?.id ?? ("project:" + project.id),
    branchId: conversation?.branch_id ?? "main",
    draftType: "chat" as const,
  };
  useEffect(() => {
    let active = true;
    loadDraft(draftKey)
      .then(value => { if (active && value) setDraft(value); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [draftKey.conversationId, draftKey.branchId, project.id]);

  useEffect(() => {
    saveDraft(draftKey, draft).catch(() => undefined);
  }, [draft, draftKey.conversationId, draftKey.branchId, project.id]);

  const save = async () => {
    if (!chapter) return;
    try {
      const version = await saveChapterVersion(chapter.id, content, baseVersion);
      setVersions(items => [...items, version]);
      setBaseVersion(version.version_no);
      setLoadedChapterId(chapter.id);
      setLoadedVersionId(version.id);
      setDirty(false);
      if (currentChapterDraftKey) await saveDraft(currentChapterDraftKey, "");
      setMessage(t("savedVersion") + " " + version.version_no);
    } catch {
      setMessage(t("saveConflict"));
    }
  };

  const restore = async (version: ChapterVersion) => {
    if (!chapter) return;
    try {
      await activateChapterVersion(chapter.id, version.id);
      setContent(version.content);
      setBaseVersion(version.version_no);
      setLoadedChapterId(chapter.id);
      setLoadedVersionId(version.id);
      setDirty(false);
      setMessage(t("restoredVersion"));
    } catch {
      setMessage(t("restoreFailed"));
    }
  };

  const showDiff = async (version: ChapterVersion) => {
    if (!chapter || !baseVersion || version.version_no === baseVersion) return setDiff([]);
    try {
      const result = await getChapterDiff(chapter.id, version.version_no, baseVersion);
      setDiff(result.diff);
      setMessage(t("diffLoaded") + ": " + result.diff.length + " " + t("changedLines"));
    } catch {
      setMessage(t("diffFailed"));
    }
  };

  const send = async () => {
    if (!draft.trim()) return;
    let closeEvents: (() => void) | undefined;
    try {
      const active = conversation ?? await createConversation(project.id);
      setConversation(active);
      const text = draft.trim();
      const selected = profiles.find(item => item.id === profileId);
      setDraft("");
      setChat(items => [...items,
        { id: newClientId(), role: "user", content: text, status: "COMPLETED" },
        { id: newClientId(), role: "assistant", content: "", status: "PENDING" },
      ]);
      closeEvents = subscribeConversationEvents(active.id, event => {
        if (event.event !== "content.delta" || !event.message_id) return;
        setChat(items => items.map(item => item.id === event.message_id
          ? { ...item, content: item.content + (event.text ?? ""), status: "STREAMING" }
          : item));
      });
      const queued = await sendMessage(active.id, {
        branch_id: active.branch_id,
        content: text,
        client_request_id: newClientId(),
        provider: String(selected?.config.provider ?? "openai"),
        model: String(selected?.config.model ?? "gpt-4.1-mini"),
      });
      setChat(items => items.map(item => item.role === "assistant" && item.status === "PENDING"
        ? { ...item, id: queued.assistant_message_id }
        : item));
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const messages = await listMessages(active.id, active.branch_id);
        setChat(messages);
        const assistant = [...messages].reverse().find(item => item.role === "assistant");
        if (assistant && ["COMPLETED", "FAILED", "PARTIAL", "CANCELLED"].includes(assistant.status)) break;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    } catch {
      setMessage(t("chatQueueFailed"));
    } finally {
      closeEvents?.();
    }
  };

  const fork = async () => {
    if (!conversation || !chat.length) return;
    try {
      const latest = await listMessages(conversation.id, conversation.branch_id);
      const point = [...latest].reverse().find(item => item.role === "assistant") ?? latest.at(-1);
      if (!point) return;
      const branch = await forkConversation(conversation.id, point.id, t("alternativeBranch") + " " + new Date().toLocaleTimeString());
      setConversation({ id: conversation.id, branch_id: branch.id });
      setChat(await listMessages(conversation.id, branch.id));
      setMessage(t("alternativeBranchCreated"));
    } catch {
      setMessage(t("alternativeBranchFailed"));
    }
  };

  const downloadMarkdown = async () => {
    try {
      const result = await requestExport(project.id, "md");
      window.open(result.download_url, "_blank", "noopener,noreferrer");
    } catch {
      setMessage(t("exportFailed"));
    }
  };

  return <section className="studio-layout">
    <aside className="chapter-tree">
      <strong>{t("chapters")}</strong>
      {chapters.map(item => <button className={chapter?.id === item.id ? "selected" : ""} key={item.id} onClick={() => setChapter(item)}>{String(item.chapter_no).padStart(2, "0")} · {item.title}</button>)}
      {!chapters.length && <small>{message}</small>}
    </aside>
    <div className="editor-pane">
      <div className="chapter-head"><span>{chapter ? t("chapters") + " " + String(chapter.chapter_no).padStart(2, "0") : project.title}</span><span className="status">{message}</span></div>
      <textarea aria-label={t("chapterEditor")} className="editor" value={content} onChange={event => { setContent(event.target.value); setDirty(true); }} placeholder={t("waitingForWorker")} />
      <div className="version-actions">{versions.map(version => <span key={version.id}><button onClick={() => restore(version)}>v{version.version_no}</button><button onClick={() => showDiff(version)} aria-label={t("diff") + " " + t("version") + " " + version.version_no}>{t("diff")}</button></span>)}</div>
      {diff.length > 0 && <pre className="diff-preview">{diff.join("\n")}</pre>}
      <button className="primary" onClick={save} disabled={!chapter}>{t("saveVersion")}</button>
      <button onClick={downloadMarkdown}>{t("downloadMarkdown")}</button>
    </div>
    <div className={`review-pane chat-pane${assistantOpen ? "" : " is-collapsed"}`}>
      <div className="assistant-heading"><strong>{t("writingCompanion")}</strong><button className="assistant-toggle" type="button" aria-expanded={assistantOpen} aria-controls="assistant-content" aria-label={assistantOpen ? t("collapseAssistant") : t("expandAssistant")} onClick={() => setAssistantOpen(value => !value)}>{assistantOpen ? "−" : "+"}</button></div>
      <div id="assistant-content" className="assistant-content" aria-hidden={!assistantOpen}>
        {profiles.length > 0 && <label>{t("modelProfile")}<select value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <div className="chat-messages">{chat.length === 0 && <p>{t("askCompanion")}</p>}{chat.map(item => <div className={"chat-message " + item.role} key={item.id}>{item.content || t("waitingForWorker")}<small>{item.status}</small></div>)}</div>
        <div className="chat-composer"><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={t("askCompanion")} /><button onClick={fork} disabled={!conversation || !chat.length}>{t("forkBranch")}</button><button className="primary" onClick={send}>{t("send")}</button></div>
      </div>
    </div>
  </section>;
}
