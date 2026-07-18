import { useEffect, useState } from "react";
import { addContext, listContext, updateContext, type ContextItem } from "../../lib/api/client";

export function ContextPage({ projectId }: { projectId: string }) {
  const [items, setItems] = useState<ContextItem[]>([]);
  const [used, setUsed] = useState(0);
  const [content, setContent] = useState("");
  const reload = () => listContext(projectId).then(result => { setItems(result.items); setUsed(result.used_tokens); }).catch(() => undefined);
  useEffect(() => { void reload(); }, [projectId]);
  const add = async () => { if (!content.trim()) return; const item = await addContext(projectId, content); setItems([...items, item]); setContent(""); };
  const pin = async (item: ContextItem) => { const updated = await updateContext(item.id, { pinned: !item.pinned }); setItems(items.map(value => value.id === item.id ? updated : value)); };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">PROJECT MEMORY</p><h2>Context library</h2><p>{used.toLocaleString()} tokens currently selected. Pin facts you never want the writer to forget.</p></div><div className="settings-form"><label>Add a memory<textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Mira is afraid of deep water…" /></label><button className="primary" onClick={add}>Add context</button></div><div className="detail-list">{items.map(item => <div className="detail-card" key={item.id}><div><strong>{item.pinned ? "📌 " : ""}{item.source_type}</strong><span>{item.content}</span></div><button onClick={() => pin(item)}>{item.pinned ? "Unpin" : "Pin"}</button></div>)}</div></section>;
}
