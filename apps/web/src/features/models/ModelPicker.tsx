import { modelKey, type ModelCapability } from "./modelCapabilities";

function formatWindow(tokens?: number | null): string {
  if (!tokens || tokens <= 0) return "—";
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k` : String(tokens);
}

export function ModelPicker({ models, value, onChange }: { models: ModelCapability[]; value?: string; onChange: (model: ModelCapability) => void }) {
  const providers = [...new Set(models.map(model => model.provider))].sort();
  return <label className="model-picker">Model
    <select aria-label="Model" value={value ?? ""} onChange={event => { const selected = models.find(model => modelKey(model) === event.target.value); if (selected) onChange(selected); }}>
      {value ? null : <option value="" disabled>Select model</option>}
      {providers.map(provider => <optgroup key={provider} label={provider}>
        {models.filter(model => model.provider === provider).map(model => <option key={modelKey(model)} value={modelKey(model)}>{model.model_id} · {formatWindow(model.context_window)} ctx</option>)}
      </optgroup>)}
    </select>
  </label>;
}
