import { useEffect, useState } from "react";
import { addContext, deleteContext, listContext, listModelProfiles, updateContext, type ContextItem, type ModelProfile, type Project } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";
import { ContextBudgetBar } from "../usage/ContextBudgetBar";

export function ContextView({ project }: { project: Project }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<ContextItem[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [used, setUsed] = useState(0);
  const [contextWindow, setContextWindow] = useState<number | null>(null);
  const [available, setAvailable] = useState(0);
  const [outputReserve, setOutputReserve] = useState(0);
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    listModelProfiles().then(result => {
      setProfiles(result);
      setProfileId(current => current || result[0]?.id || "");
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    listContext(project.id, profileId ? { profileId } : {}).then(result => {
      setItems(result.items);
      setUsed(result.used_tokens);
      setContextWindow(result.context_window);
      setAvailable(result.available_tokens);
      setOutputReserve(result.output_reserve_tokens);
    }).catch(() => undefined);
  }, [project.id, profileId]);

  const add = async () => {
    if (!content.trim()) return;
    try {
      const item = await addContext(project.id, content);
      setItems(current => [...current, item]);
      setContent("");
    } catch {
      setMessage(t("contextActionFailed"));
    }
  };

  const saveItem = async (itemId: string, payload: Partial<Pick<ContextItem, "content" | "pinned" | "priority" | "excluded">>) => {
    setSavingId(itemId);
    setMessage("");
    try {
      const updated = await updateContext(itemId, payload);
      setItems(current => current.map(value => value.id === itemId ? updated : value));
    } catch {
      setMessage(t("contextActionFailed"));
    } finally {
      setSavingId(null);
    }
  };

  const pin = (item: ContextItem) => saveItem(item.id, { pinned: !item.pinned });

  const saveEdit = async (itemId: string) => {
    await saveItem(itemId, { content: editingContent });
    setEditingId(null);
  };

  const remove = async (item: ContextItem) => {
    if (!window.confirm(t("confirmDeleteMemory"))) return;
    setSavingId(item.id);
    setMessage("");
    try {
      await deleteContext(item.id);
      setItems(current => current.filter(value => value.id !== item.id));
    } catch {
      setMessage(t("contextActionFailed"));
    } finally {
      setSavingId(null);
    }
  };

  return <section className="detail-view">
    <div className="detail-heading">
      <p className="eyebrow">{t("context")}</p>
      <h2>{t("contextHero")}</h2>
      <p>{t("contextIntro")}</p>
      {profiles.length > 0 && <label>{t("modelProfile")}<select value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>}
      {contextWindow !== null && <ContextBudgetBar used={used} available={available} total={contextWindow} outputReserve={outputReserve} />}
    </div>
    {message && <p role="alert">{message}</p>}
    <div className="settings-form"><label>{t("addMemory")}<textarea value={content} onChange={event => setContent(event.target.value)} placeholder={t("addMemoryPlaceholder")} /></label><button className="primary" onClick={() => void add()}>{t("addContext")}</button></div>
    <div className="detail-list">{items.map(item => <div className={`detail-card context-item-card${item.excluded ? " is-excluded" : ""}`} key={item.id}>
      <div>
        <strong>{item.pinned ? `${t("pinned")} · ` : ""}{item.source_type}</strong>
        {editingId === item.id ? <textarea aria-label={t("editMemory")} value={editingContent} onChange={event => setEditingContent(event.target.value)} /> : <span>{item.content}</span>}
        <small>{item.token_estimate ?? 0} {t("tokens")}</small>
        <label>{t("priority")}<input aria-label={t("priority")} type="number" min="0" max="100" value={item.priority} disabled={savingId === item.id} onChange={event => void saveItem(item.id, { priority: Number(event.target.value) })} /></label>
        <label><input aria-label={t("excluded")} type="checkbox" checked={item.excluded} disabled={savingId === item.id} onChange={event => void saveItem(item.id, { excluded: event.target.checked })} />{t("excluded")}</label>
      </div>
      <div className="context-item-actions">
        <button onClick={() => void pin(item)} disabled={savingId === item.id}>{item.pinned ? t("unpin") : t("pin")}</button>
        {editingId === item.id ? <><button onClick={() => void saveEdit(item.id)} disabled={savingId === item.id}>{t("saveMemory")}</button><button onClick={() => setEditingId(null)}>{t("cancel")}</button></> : <button aria-label={t("editMemory")} onClick={() => { setEditingId(item.id); setEditingContent(item.content); }}>{t("editMemory")}</button>}
        <button aria-label={t("deleteMemory")} onClick={() => void remove(item)} disabled={savingId === item.id}>{t("deleteMemory")}</button>
      </div>
    </div>)}</div>
  </section>;
}
