import { useState } from "react";
import { InkButton } from "../../components/ink/Ink";

export const STORY_FACT_KINDS = ["character", "relationship", "location", "timeline_event", "world_rule", "plot_thread", "style_rule", "promise"] as const;
export type StoryFactKind = (typeof STORY_FACT_KINDS)[number];

export type CharacterVoice = {
  sentence_len: [number, number];
  connectors: string[];
  banned_words: string[];
  emotion_baseline: string;
  register: string;
};

export type StoryFactValue = {
  summary?: string;
  triggers: string[];
  budget_tokens: number;
  voice?: CharacterVoice;
};

export type FactDraft = {
  kind: StoryFactKind;
  key: string;
  value: StoryFactValue;
  pinned: boolean;
};

type FactEditorProps = {
  initialValue?: Partial<FactDraft>;
  onSave: (draft: FactDraft) => void;
  onCancel?: () => void;
  saving?: boolean;
};

function commaSeparated(value: string): string[] {
  return value.split(",").map(item => item.trim()).filter(Boolean);
}

function initialVoice(value?: Partial<CharacterVoice>): CharacterVoice {
  return {
    sentence_len: value?.sentence_len ?? [8, 20],
    connectors: value?.connectors ?? [],
    banned_words: value?.banned_words ?? [],
    emotion_baseline: value?.emotion_baseline ?? "neutral",
    register: value?.register ?? "neutral",
  };
}

export function FactEditor({ initialValue, onSave, onCancel, saving = false }: FactEditorProps) {
  const initialFactValue = initialValue?.value;
  const [kind, setKind] = useState<StoryFactKind>(initialValue?.kind ?? "character");
  const [key, setKey] = useState(initialValue?.key ?? "");
  const [summary, setSummary] = useState(initialFactValue?.summary ?? "");
  const [triggers, setTriggers] = useState(initialFactValue?.triggers?.join(", ") ?? "");
  const [budgetTokens, setBudgetTokens] = useState(initialFactValue?.budget_tokens ?? 160);
  const [pinned, setPinned] = useState(initialValue?.pinned ?? false);
  const [voice, setVoice] = useState(() => initialVoice(initialFactValue?.voice));

  const save = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanKey = key.trim();
    if (!cleanKey) return;
    const value: StoryFactValue = {
      summary: summary.trim() || undefined,
      triggers: commaSeparated(triggers),
      budget_tokens: Math.max(1, Math.round(Number.isFinite(budgetTokens) ? budgetTokens : 160)),
    };
    if (kind === "character") value.voice = voice;
    onSave({ kind, key: cleanKey, value, pinned });
  };

  return <form className="fact-editor" aria-label="Story Bible fact editor" onSubmit={save}>
    <div className="fact-editor-grid">
      <label>Fact kind
        <select aria-label="Fact kind" value={kind} onChange={event => setKind(event.target.value as StoryFactKind)}>
          {STORY_FACT_KINDS.map(item => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
        </select>
      </label>
      <label>Fact key
        <input aria-label="Fact key" required value={key} onChange={event => setKey(event.target.value)} placeholder="Mira" />
      </label>
      <label>Budget tokens
        <input aria-label="Budget tokens" type="number" min="1" value={budgetTokens} onChange={event => setBudgetTokens(Number(event.target.value))} />
      </label>
      <label className="fact-editor-pin"><input type="checkbox" checked={pinned} onChange={event => setPinned(event.target.checked)} /> Always include</label>
    </div>
    <label>Summary
      <textarea value={summary} onChange={event => setSummary(event.target.value)} placeholder="A concise, durable fact for the writing context." />
    </label>
    <label>Triggers
      <input aria-label="Triggers" value={triggers} onChange={event => setTriggers(event.target.value)} placeholder="Mira, harbor" />
      <small>Comma-separated terms. An unpinned fact is included only after a trigger matches.</small>
    </label>
    {kind === "character" ? <fieldset className="fact-voice">
      <legend>Character voice</legend>
      <div className="fact-editor-grid">
        <label>Sentence length, min<input type="number" min="1" value={voice.sentence_len[0]} onChange={event => setVoice(current => ({ ...current, sentence_len: [Number(event.target.value), current.sentence_len[1]] }))} /></label>
        <label>Sentence length, max<input type="number" min="1" value={voice.sentence_len[1]} onChange={event => setVoice(current => ({ ...current, sentence_len: [current.sentence_len[0], Number(event.target.value)] }))} /></label>
        <label>Voice register<input aria-label="Voice register" required value={voice.register} onChange={event => setVoice(current => ({ ...current, register: event.target.value }))} placeholder="formal" /></label>
        <label>Emotion baseline<input required value={voice.emotion_baseline} onChange={event => setVoice(current => ({ ...current, emotion_baseline: event.target.value }))} placeholder="guarded" /></label>
      </div>
      <label>Connectors<input value={voice.connectors.join(", ")} onChange={event => setVoice(current => ({ ...current, connectors: commaSeparated(event.target.value) }))} placeholder="however, therefore" /></label>
      <label>Banned words<input value={voice.banned_words.join(", ")} onChange={event => setVoice(current => ({ ...current, banned_words: commaSeparated(event.target.value) }))} placeholder="very, suddenly" /></label>
    </fieldset> : null}
    <div className="fact-editor-actions">
      {onCancel ? <InkButton type="button" onClick={onCancel}>Cancel</InkButton> : null}
      <InkButton type="submit" tone="vermilion" disabled={saving}>{saving ? "Saving…" : "Save fact"}</InkButton>
    </div>
  </form>;
}
