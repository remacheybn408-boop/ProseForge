import { useState } from "react";
import { ApiError, type ModelResolution } from "../../lib/api/client";
import { ModelPicker } from "./ModelPicker";
import { ReasoningPicker } from "./ReasoningPicker";
import { modelKey, supportedReasoning, useModelCatalog, validateResolution, type ModelCapability, type ReasoningLevel } from "./modelCapabilities";

function formatWindow(tokens?: number | null): string {
  if (!tokens || tokens <= 0) return "unknown";
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k tokens` : `${tokens} tokens`;
}

function reasoningSummary(model: ModelCapability): string {
  if (!model.capabilities.reasoning) return "auto only";
  const parameter = typeof model.capabilities.reasoning_parameter === "string" ? model.capabilities.reasoning_parameter : null;
  return parameter ? `fast–max via ${parameter}` : "fast–max";
}

export function SettingsModelsPage() {
  const catalogQuery = useModelCatalog();
  const models = catalogQuery.data ?? [];
  const providers = [...new Set(models.map(model => model.provider))].sort();
  const [selectedKey, setSelectedKey] = useState("");
  const [level, setLevel] = useState<ReasoningLevel>("auto");
  const [result, setResult] = useState<ModelResolution | null>(null);
  const [notice, setNotice] = useState("");
  const [supportedLevels, setSupportedLevels] = useState<string[]>([]);
  const [validating, setValidating] = useState(false);
  const selected = models.find(model => modelKey(model) === selectedKey);

  const validate = async () => {
    if (!selected) {
      setNotice("Pick a model from the catalog first.");
      return;
    }
    setValidating(true);
    setNotice("");
    setResult(null);
    setSupportedLevels([]);
    try {
      setResult(await validateResolution({ provider: selected.provider, model_id: selected.model_id, level }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const detail = (error.detail || {}) as { message?: string; details?: { supported_levels?: string[] } };
        setNotice(detail.message ?? "This reasoning level is unsupported by the model.");
        setSupportedLevels(detail.details?.supported_levels ?? []);
      } else {
        setNotice("Validation failed. Try again shortly.");
      }
    } finally {
      setValidating(false);
    }
  };

  return <section className="detail-view settings-models">
    <div className="detail-heading">
      <p className="eyebrow">MODEL CATALOG</p>
      <h2>Models &amp; reasoning</h2>
      <p>The catalog is the source of truth. Context windows, output limits and reasoning support come from provider sync — unsupported levels are greyed out and rejected with 422, never silently downgraded.</p>
    </div>
    {catalogQuery.isError ? <p className="form-message" role="status">The model catalog is unavailable. Sign in and sync a provider first.</p> : null}
    {!catalogQuery.isError && models.length === 0 ? <p className="form-message" role="status">No models in the catalog yet. Save a provider below and sync its models.</p> : null}
    {providers.map(provider => <div className="model-provider-group" key={provider}>
      <h3>{provider}</h3>
      <div className="detail-list">
        {models.filter(model => model.provider === provider).map(model => <div className="detail-card" key={modelKey(model)}>
          <strong>{model.model_id}</strong>
          <span>{formatWindow(model.context_window)} · max output {formatWindow(model.max_output_tokens)}</span>
          <span>{reasoningSummary(model)}</span>
        </div>)}
      </div>
    </div>)}
    <div className="settings-form">
      <h3>Validate a reasoning level</h3>
      <ModelPicker models={models} value={selectedKey} onChange={model => { setSelectedKey(modelKey(model)); setResult(null); setNotice(""); setSupportedLevels([]); }} />
      <ReasoningPicker value={level} supported={selected ? supportedReasoning(selected) : ["auto"]} onChange={setLevel} />
      <button className="primary" type="button" disabled={validating} onClick={() => void validate()}>{validating ? "Validating…" : "Validate"}</button>
      <p className="form-message" aria-live="polite">{notice}{supportedLevels.length > 0 ? ` Supported levels: ${supportedLevels.join(", ")}.` : ""}</p>
    </div>
    {result ? <div className="detail-list resolution-result" data-testid="resolution-result">
      <div className="detail-card"><strong>Normalized level</strong><span>{result.normalized_level}</span><span /></div>
      <div className="detail-card"><strong>Provider parameter</strong><span><code>{JSON.stringify(result.provider_parameter)}</code></span><span /></div>
      <div className="detail-card"><strong>Context window</strong><span>{formatWindow(result.context_window)}</span><span /></div>
      <div className="detail-card"><strong>Warnings</strong><span>{result.warnings.length > 0 ? result.warnings.join("; ") : "none"}</span><span /></div>
    </div> : null}
  </section>;
}
