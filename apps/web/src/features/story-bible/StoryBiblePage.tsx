import { useCallback, useEffect, useState } from "react";
import { EmptyScroll, InkButton, PaperPanel, SealBadge, StatusStamp } from "../../components/ink/Ink";
import { ApiError, request } from "../../lib/api/client";
import { FactEditor, type FactDraft, type StoryFactKind, type StoryFactValue } from "./FactEditor";

export type StoryBibleFact = FactDraft & {
  id: string;
  project_id: string;
  status: string;
  confidence: number;
  source: string;
  version: number;
};

const factsPath = (projectId: string) => `/api/v2/projects/${encodeURIComponent(projectId)}/story-bible`;

function listFacts(projectId: string) {
  return request<StoryBibleFact[]>(factsPath(projectId));
}

function createFact(projectId: string, draft: FactDraft) {
  return request<StoryBibleFact>(`${factsPath(projectId)}/entries`, { method: "POST", body: JSON.stringify(draft) });
}

function updateFact(fact: StoryBibleFact, draft: FactDraft) {
  return request<StoryBibleFact>(`/api/v2/story-bible/${encodeURIComponent(fact.id)}`, { method: "PATCH", body: JSON.stringify({ ...draft, version: fact.version }) });
}

function changePromiseStatus(fact: StoryBibleFact, status: string) {
  return request<StoryBibleFact>(`/api/v2/story-bible/${encodeURIComponent(fact.id)}/status`, { method: "POST", body: JSON.stringify({ status, version: fact.version }) });
}

function togglePin(fact: StoryBibleFact) {
  return request<StoryBibleFact>(`/api/v2/story-bible/${encodeURIComponent(fact.id)}/pin`, { method: "POST", body: JSON.stringify({}) });
}

function statusTone(status: string): "default" | "success" | "warning" {
  if (status === "resolved") return "success";
  if (status === "abandoned") return "warning";
  return "default";
}

const PROMISE_TRANSITIONS: Record<string, string[]> = {
  open: ["developing"],
  developing: ["resolved", "abandoned"],
  resolved: [],
  abandoned: [],
};

function factSummary(fact: StoryBibleFact): string {
  return fact.value.summary || fact.value.triggers.join(", ") || "No summary yet";
}

export function StoryBiblePage({ projectId }: { projectId: string }) {
  const [facts, setFacts] = useState<StoryBibleFact[]>([]);
  const [editing, setEditing] = useState<StoryBibleFact | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const reload = useCallback(async () => {
    try {
      setFacts(await listFacts(projectId));
      setNotice("");
    } catch {
      setNotice("Story Bible could not be loaded.");
    }
  }, [projectId]);

  useEffect(() => { void reload(); }, [reload]);

  const save = async (draft: FactDraft) => {
    setSaving(true);
    try {
      const result = editing ? await updateFact(editing, draft) : await createFact(projectId, draft);
      setFacts(current => editing ? current.map(fact => fact.id === result.id ? result : fact) : [...current, result].sort((left, right) => left.key.localeCompare(right.key)));
      setCreating(false);
      setEditing(null);
      setNotice(editing ? "Fact updated." : "Fact added.");
    } catch (error) {
      setNotice(error instanceof ApiError && error.status === 409 ? "This fact changed elsewhere. Reload before saving." : "Fact could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const updateLocal = async (action: () => Promise<StoryBibleFact>) => {
    try {
      const updated = await action();
      setFacts(current => current.map(fact => fact.id === updated.id ? updated : fact));
      setNotice("Fact updated.");
    } catch {
      setNotice("Fact could not be updated.");
    }
  };

  const editor = creating || editing ? <PaperPanel className="story-bible-editor"><h3>{editing ? "Edit fact" : "New fact"}</h3><FactEditor initialValue={editing ?? undefined} onSave={draft => void save(draft)} onCancel={() => { setCreating(false); setEditing(null); }} saving={saving} /></PaperPanel> : null;
  return <section className="story-bible-page">
    <header className="story-bible-heading">
      <div><p className="eyebrow">STORY BIBLE</p><h2>Facts that earn their context</h2><p>Pinned facts stay present. Everything else must be triggered by the current writing context.</p></div>
      <InkButton type="button" tone="vermilion" onClick={() => { setCreating(true); setEditing(null); }}>New fact</InkButton>
    </header>
    <p className="story-bible-notice" aria-live="polite">{notice}</p>
    {editor}
    {facts.length === 0 && !editor ? <EmptyScroll><p className="empty-scroll-title">No facts yet</p><p className="empty-scroll-hint">Create a character, world rule, plot thread, or promise to make context explainable.</p></EmptyScroll> : null}
    <div className="story-bible-list">
      {facts.map(fact => <article className="story-fact-card" key={fact.id}>
        <div className="story-fact-title"><div><span className="eyebrow">{fact.kind.replace("_", " ")}</span><h3>{fact.key}</h3></div><StatusStamp status={fact.pinned ? "success" : "default"}>{fact.pinned ? "PIN" : "FACT"}</StatusStamp></div>
        <p>{factSummary(fact)}</p>
        <div className="story-fact-meta"><span>{fact.value.budget_tokens.toLocaleString()} token budget</span>{fact.value.triggers.length > 0 ? <span>Triggers: {fact.value.triggers.join(", ")}</span> : <span>Uses its key as trigger</span>}{fact.kind === "promise" ? <SealBadge tone={statusTone(fact.status)}>{fact.status}</SealBadge> : null}</div>
        <div className="story-fact-actions"><InkButton type="button" onClick={() => { setEditing(fact); setCreating(false); }}>Edit</InkButton><InkButton type="button" onClick={() => void updateLocal(() => togglePin(fact))}>{fact.pinned ? "Unpin" : "Pin"}</InkButton>{fact.kind === "promise" && (PROMISE_TRANSITIONS[fact.status] ?? []).map(status => <InkButton type="button" key={status} onClick={() => void updateLocal(() => changePromiseStatus(fact, status))}>Mark {status}</InkButton>)}</div>
      </article>)}
    </div>
  </section>;
}

export type { StoryFactKind, StoryFactValue };
