import { useState } from "react";
import { answerOutline, confirmOutline, createWorkflow, importOutline, type Outline, type Project, type Workflow } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";

export function OutlineView({ project, onWorkflow }: { project: Project; onWorkflow: (workflow: Workflow) => void }) {
  const { t } = useLanguage();
  const [outline, setOutline] = useState<Outline | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [startChapter, setStartChapter] = useState(1);
  const [endChapter, setEndChapter] = useState(1);
  const [message, setMessage] = useState(t("outlineInitialMessage"));
  const submit = async () => { try { const item = await importOutline(project.id, { title: title || t("outlineTitle"), content }); setOutline(item); setMessage(item.missing_questions.length ? t("outlineNeedsAnswers") : t("outlineReady")); } catch { setMessage(t("outlineImportFailed")); } };
  const answerField = (question: string, index: number) => outline?.missing_fields[index] ?? question.match(/：(.+)/)?.[1] ?? `question_${index}`;
  const answerMissing = async () => { if (!outline || !Object.values(answers).some(value => value.trim())) return; try { const normalized = Object.fromEntries(Object.entries(answers).map(([key, value]) => [key, /^\d+$/.test(value) ? Number(value) : key === "characters" ? [value] : value])); const item = await answerOutline(outline.id, normalized); setOutline(item); setAnswers({}); setMessage(item.missing_questions.length ? t("outlineMoreAnswers") : t("outlineReady")); } catch { setMessage(t("outlineAnswerFailed")); } };
  const confirm = async () => { if (!outline) return; try { await confirmOutline(outline.id); const workflow = await createWorkflow(project.id, Array.from({ length: Math.max(1, endChapter - startChapter + 1) }, (_, index) => startChapter + index)); onWorkflow(workflow); setMessage(t("outlineConfirmedWorkflow")); } catch { setMessage(t("outlineCompleteAnswers")); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("outlineIntake")}</p><h2>{t("outlineHero")}</h2><p>{t("outlineIntro")}</p></div><div className="settings-form"><label>{t("outlineTitle")}<input value={title} onChange={event => setTitle(event.target.value)} placeholder={t("outlineTitlePlaceholder")} /></label><label>{t("outlineNotes")}<textarea value={content} onChange={event => setContent(event.target.value)} placeholder={t("outlineNotesPlaceholder")} /></label><button className="primary" onClick={submit}>{t("importAnalyze")}</button></div>{outline && <div className="outline-status"><strong>{outline.title}</strong><span>{t("status")}: {outline.status}</span>{outline.missing_questions.map((question, index) => <label key={question}>{question}<input value={answers[answerField(question, index)] ?? ""} onChange={event => setAnswers(current => ({ ...current, [answerField(question, index)]: event.target.value }))} placeholder={t("answerMissing")} /></label>)}{outline.missing_questions.length > 0 && <button onClick={answerMissing}>{t("saveAnswer")}</button>}{outline.missing_questions.length === 0 && <><div className="answer-row"><label>{t("startChapter")}<input type="number" min="1" value={startChapter} onChange={event => setStartChapter(Number(event.target.value))} /></label><label>{t("endChapter")}<input type="number" min={startChapter} value={endChapter} onChange={event => setEndChapter(Number(event.target.value))} /></label></div><button className="primary" onClick={confirm}>{t("confirmWorkflow")}</button></>}</div>}<p className="form-message" aria-live="polite">{message}</p></section>;
}
