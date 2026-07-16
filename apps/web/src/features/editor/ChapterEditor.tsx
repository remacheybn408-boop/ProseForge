import { useLanguage } from "../../lib/i18n";

export function ChapterEditor({ content, dirty, onChange, onSave }: { content: string; dirty: boolean; onChange: (content: string) => void; onSave: () => void }) {
  const { t } = useLanguage();
  return <section className="chapter-editor"><textarea aria-label={t("chapterEditor")} value={content} onChange={event => onChange(event.target.value)} /><span>{dirty ? t("unsavedDraft") : t("saved")}</span><button onClick={onSave} disabled={!dirty}>{t("saveVersion")}</button></section>;
}
