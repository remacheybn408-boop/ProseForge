import { useEffect, useState } from "react";
import { addContext, listContext, listModelProfiles, updateContext, type ContextItem, type ModelProfile, type Project } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";
import { ContextBudgetBar } from "../usage/ContextBudgetBar";

export function ContextView({ project }: { project: Project }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<ContextItem[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [used, setUsed] = useState(0);
  const [contextWindow, setContextWindow] = useState(128000);
  const [content, setContent] = useState("");

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
    }).catch(() => undefined);
  }, [project.id, profileId]);

  const add = async () => {
    if (!content.trim()) return;
    const item = await addContext(project.id, content);
    setItems(current => [...current, item]);
    setContent("");
  };

  const pin = async (item: ContextItem) => {
    const updated = await updateContext(item.id, { pinned: !item.pinned });
    setItems(current => current.map(value => value.id === item.id ? updated : value));
  };

  return <section className="detail-view">
    <div className="detail-heading">
      <p className="eyebrow">{t("context")}</p>
      <h2>{t("contextHero")}</h2>
      <p>{t("contextIntro")}</p>
      {profiles.length > 0 && <label>{t("modelProfile")}<select value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>}
      <ContextBudgetBar used={used} available={Math.max(0, contextWindow - used)} total={contextWindow} />
    </div>
    <div className="settings-form"><label>{t("addMemory")}<textarea value={content} onChange={event => setContent(event.target.value)} placeholder={t("addMemoryPlaceholder")} /></label><button className="primary" onClick={add}>{t("addContext")}</button></div>
    <div className="detail-list">{items.map(item => <div className="detail-card" key={item.id}><div><strong>{item.pinned ? `${t("pinned")} · ` : ""}{item.source_type}</strong><span>{item.content}</span></div><button onClick={() => pin(item)}>{item.pinned ? t("unpin") : t("pin")}</button></div>)}</div>
  </section>;
}
