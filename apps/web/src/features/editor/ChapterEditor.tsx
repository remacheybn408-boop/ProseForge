export function ChapterEditor({ content, dirty, onChange, onSave }: { content: string; dirty: boolean; onChange: (content: string) => void; onSave: () => void }) {
  return <section className="chapter-editor"><textarea aria-label="Chapter editor" value={content} onChange={event => onChange(event.target.value)} /><span>{dirty ? "Unsaved draft" : "Saved"}</span><button onClick={onSave} disabled={!dirty}>Save version</button></section>;
}
