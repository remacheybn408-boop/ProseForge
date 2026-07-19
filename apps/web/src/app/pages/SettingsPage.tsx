import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listCredentials, listModelProfiles, probeProvider, saveCredential, saveModelProfile, type Credential, type ModelProfile } from "../../lib/api/client";

type Theme = "paper" | "rubbing";
type Language = "zh" | "en";
const PROVIDERS = ["openai", "anthropic", "google", "deepseek", "kimi", "dashscope", "zhipu", "volcengine", "baidu", "tencent", "minimax", "xai", "mistral", "cohere", "ollama", "vllm"];

function initialTheme(): Theme {
  if (typeof window === "undefined") return "paper";
  return window.localStorage.getItem("proseforge.theme") === "rubbing" ? "rubbing" : "paper";
}

export function SettingsPage() {
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileName, setProfileName] = useState("");
  const [modelId, setModelId] = useState("");
  const [profileRole, setProfileRole] = useState<"writer" | "editor">("writer");
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const { i18n } = useTranslation();
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") return "en";
    const stored = window.localStorage.getItem("proseforge.language");
    return stored === "zh" || stored === "en" ? stored : i18n.language === "zh" ? "zh" : "en";
  });
  const [message, setMessage] = useState("Secrets are never prefilled.");

  useEffect(() => { void listCredentials().then(setCredentials).catch(() => undefined); void listModelProfiles().then(setProfiles).catch(() => undefined); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; window.localStorage.setItem("proseforge.theme", theme); }, [theme]);

  const changeLanguage = (next: Language) => {
    setLanguage(next);
    window.localStorage.setItem("proseforge.language", next);
    void i18n.changeLanguage(next);
  };

  const save = async () => {
    if (!apiKey.trim()) return setMessage("Enter an API key to continue.");
    try {
      const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined });
      setCredentials(current => [...current, record]);
      setApiKey("");
      setMessage("Saved securely. The key is now masked.");
    } catch { setMessage("Sign in to save provider settings."); }
  };
  const probe = async (item: Credential) => {
    setMessage(`Checking ${item.provider}…`);
    try { await probeProvider(item.provider); setMessage(`${item.provider} connection is healthy.`); }
    catch { setMessage(`${item.provider} probe failed; check the endpoint or key.`); }
  };
  const saveProfile = async () => {
    if (!profileName.trim() || !modelId.trim()) return setMessage("Enter a profile name and model ID.");
    try {
      const profile = await saveModelProfile({ name: profileName.trim(), role: profileRole, config: { provider, model: modelId.trim() } });
      setProfiles(current => [...current, profile]);
      setProfileName(""); setModelId("");
      setMessage(`${profileRole === "writer" ? "Writer" : "Editor"} profile saved.`);
    } catch { setMessage("Could not save the model profile."); }
  };

  return <section className="detail-view">
    <div className="detail-heading"><p className="eyebrow">MODEL SETTINGS</p><h2>Provider connections</h2><p>Connect a provider once. The raw secret is never rendered back into the browser.</p></div>
    <div className="settings-form"><h3>Appearance</h3><label>Theme<select aria-label="Workspace theme" value={theme} onChange={event => setTheme(event.target.value as Theme)}><option value="paper">Paper</option><option value="rubbing">碑拓 / Rubbing</option></select></label><label>Language<select aria-label="Interface language" value={language} onChange={event => changeLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">English</option></select></label><p>The rubbing theme keeps WCAG AA text contrast while reducing glare.</p></div>
    <div className="settings-form"><label>Provider<select value={provider} onChange={event => setProvider(event.target.value)}>{PROVIDERS.map(item => <option key={item} value={item}>{item}</option>)}</select></label><label>API key<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} autoComplete="new-password" /></label><label>Base URL (optional)<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} /></label><button className="primary" onClick={() => void save()}>Save provider</button><p className="form-message" aria-live="polite">{message}</p></div>
    <div className="detail-list">{credentials.map(item => <div className="detail-card" key={item.id}><strong>{item.provider}</strong><span>{item.masked_key}</span><span>Configured</span><button onClick={() => void probe(item)}>Test connection</button></div>)}</div>
    <div className="settings-form"><h3>Writer / Editor profile</h3><label>Role<select value={profileRole} onChange={event => setProfileRole(event.target.value as "writer" | "editor")}><option value="writer">Writer — drafting</option><option value="editor">Editor — review and rewrite</option></select></label><label>Profile name<input value={profileName} onChange={event => setProfileName(event.target.value)} placeholder="Fast draft writer" /></label><label>Model ID<input value={modelId} onChange={event => setModelId(event.target.value)} placeholder="gpt-4.1-mini" /></label><button onClick={() => void saveProfile()}>Save profile</button></div>
    <div className="detail-list">{profiles.map(profile => <div className="detail-card" key={profile.id}><strong>{String(profile.config.role ?? "writer")} · {profile.name}</strong><span>{String(profile.config.provider)} / {String(profile.config.model)}</span></div>)}</div>
  </section>;
}
