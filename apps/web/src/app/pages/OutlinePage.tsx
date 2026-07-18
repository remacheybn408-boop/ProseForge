import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { answerOutline, confirmOutline, createWorkflow, importOutline, type Outline } from "../../lib/api/client";

export function OutlinePage({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [outline, setOutline] = useState<Outline | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState("Import an outline or describe your story below.");
  const submit = async () => { try { const item = await importOutline(projectId, { title: title || "Untitled outline", content }); setOutline(item); setMessage(item.missing_questions.length ? "A few answers are needed before confirmation." : "Ready to confirm."); } catch { setMessage("Outline import failed"); } };
  const answerMissing = async () => { if (!outline || !answer.trim()) return; try { const item = await answerOutline(outline.id, { characters: [answer], genre: "小说", point_of_view: "third-person", title: outline.title, planned_chapters: 12, chapter_word_target: 1500 }); setOutline(item); setAnswer(""); setMessage(item.missing_questions.length ? "More answers are needed." : "Ready to confirm."); } catch { setMessage("Could not save the answer"); } };
  const confirm = async () => { if (!outline) return; try { await confirmOutline(outline.id); const workflow = await createWorkflow(projectId, [1]); setMessage("Outline confirmed; workflow created."); await navigate({ to: "/projects/$projectId/workflows/$workflowId", params: { projectId, workflowId: workflow.id } }); } catch { setMessage("Complete the required answers first."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">OUTLINE INTAKE</p><h2>Start from your story idea</h2><p>ProseForge saves the outline before asking only the questions it still needs.</p></div><div className="settings-form"><label>Outline title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="The Moonlit Archive" /></label><label>Outline or story notes<textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Paste your outline, characters and ending…" /></label><button className="primary" onClick={submit}>Import and analyze</button></div>{outline && <div className="outline-status"><strong>{outline.title}</strong><span>Status: {outline.status}</span>{outline.missing_questions.map(question => <span key={question}>{question}</span>)}{outline.missing_questions.length > 0 && <div className="answer-row"><input value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Answer the missing requirement" /><button onClick={answerMissing}>Save answer</button></div>}{outline.missing_questions.length === 0 && <button className="primary" onClick={confirm}>Confirm and create workflow</button>}</div>}<p className="form-message" aria-live="polite">{message}</p></section>;
}
