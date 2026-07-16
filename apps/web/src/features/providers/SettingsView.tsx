import { useEffect, useState } from "react";
import {
  deleteCredential,
  listCredentials,
  listModelProfiles,
  probeProvider,
  saveCredential,
  saveModelProfile,
  type Credential,
  type ModelProfile,
} from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";
import { useModelsQuery, useProvidersQuery } from "../../app/query";
import { removeCredential, upsertCredential } from "./credentialState";

export function SettingsView() {
  const { t } = useLanguage();
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileName, setProfileName] = useState("");
  const [modelId, setModelId] = useState("");
  const [profileRole, setProfileRole] = useState<"writer" | "editor">("writer");
  const [probeStates, setProbeStates] = useState<Record<string, "connected" | "failed">>({});
  const [message, setMessage] = useState(t("secretsNeverPrefilled"));
  const providersQuery = useProvidersQuery();
  const modelsQuery = useModelsQuery(provider);

  useEffect(() => {
    listCredentials().then(setCredentials).catch(() => undefined);
    listModelProfiles().then(setProfiles).catch(() => undefined);
  }, []);

  const save = async () => {
    if (!apiKey.trim()) return setMessage(t("apiKeyHelp"));
    try {
      const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined });
      setCredentials(current => upsertCredential(current, record));
      setApiKey("");
      setMessage(t("configured"));
    } catch {
      setMessage(t("genericError"));
    }
  };

  const removeConfigured = async (item: Credential) => {
    if (!window.confirm(`${t("removeCredentialConfirm")} ${item.provider}?`)) return;
    try {
      await deleteCredential(item.id);
      setCredentials(current => removeCredential(current, item.id));
      setMessage(t("credentialRemoved"));
    } catch {
      setMessage(t("genericError"));
    }
  };

  const probe = async (item: Credential) => {
    setMessage(`${item.provider}…`);
    try {
      await probeProvider(item.provider);
      setProbeStates(states => ({ ...states, [item.id]: "connected" }));
      setMessage(`${item.provider} · ${t("connected")}`);
    } catch {
      setProbeStates(states => ({ ...states, [item.id]: "failed" }));
      setMessage(`${item.provider} · ${t("checkFailed")}`);
    }
  };

  const saveProfile = async () => {
    if (!profileName.trim() || !modelId.trim()) return setMessage(t("modelIdHelp"));
    try {
      const profile = await saveModelProfile({ name: profileName.trim(), role: profileRole, config: { provider, model: modelId.trim() } });
      setProfiles([...profiles, profile]);
      setProfileName("");
      setModelId("");
      setMessage(t("configured"));
    } catch {
      setMessage(t("genericError"));
    }
  };

  const providers = providersQuery.data?.map(item => item.id) ?? [];
  return <section className="detail-view settings-page">
    <div className="detail-heading"><p className="eyebrow">{t("modelSettings")}</p><h2>{t("providerConnections")}</h2><p>{t("providerIntro")}</p></div>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("providerConnections")}</h3><p>{t("apiKeyHelp")}</p></div><div className="settings-form">
      <label>{t("provider")}<select value={provider} onChange={event => setProvider(event.target.value)}>{providers.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>{t("apiKey")}<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} autoComplete="new-password" placeholder="sk-…" /></label><small className="field-help">{t("apiKeyHelp")}</small>
      <label>{t("baseUrl")}<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" /></label><small className="field-help">{t("baseUrlHelp")}</small>
      <button className="primary" onClick={save}>{t("saveProvider")}</button><p className="form-message" aria-live="polite">{message}</p>
    </div></section>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("configured")}</h3><p>{t("secretsNeverPrefilled")}</p></div><div className="settings-list">{credentials.length === 0 && <p className="empty">{t("notConnected")}</p>}{credentials.map(item => { const state = probeStates[item.id]; return <div className="settings-row" key={item.id}><div><strong>{item.provider}</strong><span>{item.masked_key}</span></div><span className={`connection-status ${state ?? "unknown"}`}>{state === "connected" ? t("connected") : state === "failed" ? t("checkFailed") : t("notConnected")}</span><button onClick={() => probe(item)}>{t("testConnection")}</button><button className="danger" aria-label={`${t("removeCredential")} ${item.provider}`} onClick={() => removeConfigured(item)}>{t("removeCredential")}</button></div>; })}</div></section>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("writerEditor")}</h3><p>{t("writerEditorIntro")}</p></div><div className="settings-form">
      <label>{t("writerEditor")}<select value={profileRole} onChange={event => setProfileRole(event.target.value as "writer" | "editor")}><option value="writer">{t("writerModel")}</option><option value="editor">{t("editorModel")}</option></select></label>
      <label>{t("profileName")}<input value={profileName} onChange={event => setProfileName(event.target.value)} placeholder={t("profileNamePlaceholder")} /></label>
      <label>{t("modelId")}<input list="model-options" value={modelId} onChange={event => setModelId(event.target.value)} placeholder="gpt-4.1-mini" /></label><datalist id="model-options">{modelsQuery.data?.map(item => <option key={`${item.provider}:${item.model_id}`} value={item.model_id}>{item.display_name}</option>)}</datalist><small className="field-help">{t("modelIdHelp")}</small>
      <button onClick={saveProfile}>{t("saveProfile")}</button>
    </div><div className="settings-list">{profiles.map(profile => <div className="settings-row" key={profile.id}><div><strong>{String(profile.config.role ?? "writer") === "writer" ? t("writerModel") : t("editorModel")} · {profile.name}</strong><span>{String(profile.config.provider)} / {String(profile.config.model)}</span></div><span className="connection-status connected">{t("configured")}</span></div>)}</div></section>
  </section>;
}
