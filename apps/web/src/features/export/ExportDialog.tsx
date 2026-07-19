import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useT } from "../../lib/i18n";
import type { ExportFormat, ExportManifest, ExportRequest, ExportTemplate } from "./exportTypes";

const PRESETS: { value: ExportTemplate; labelKey: string; descriptionKey: string }[] = [
  { value: "web-serial", labelKey: "export:presetWebSerial", descriptionKey: "export:presetWebSerialHint" },
  { value: "submission", labelKey: "export:presetSubmission", descriptionKey: "export:presetSubmissionHint" },
  { value: "archive", labelKey: "export:presetArchive", descriptionKey: "export:presetArchiveHint" },
];

type Props = { projectId: string; versionIds: string[]; manifest?: ExportManifest | null; onExport: (request: ExportRequest) => void | Promise<void>; onClose?: () => void };

export function ExportDialog({ projectId, versionIds, manifest, onExport, onClose }: Props) {
  const t = useT();
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [format, setFormat] = useState<ExportFormat>("md");
  const [template, setTemplate] = useState<ExportTemplate>("archive");
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [selected, setSelected] = useState<string[]>(() => versionIds.slice(0, 1));

  useEffect(() => {
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.querySelector<HTMLElement>("button,select,input")?.focus();
    return () => returnFocusRef.current?.focus();
  }, []);

  const close = () => onClose?.();
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key !== "Tab") return;
    const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("button:not([disabled]),select:not([disabled]),input:not([disabled])") ?? []);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1)!;
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  const toggleVersion = (versionId: string) => setSelected(current => current.includes(versionId) ? current.filter(id => id !== versionId) : [...current, versionId]);
  const chapterRange = rangeStart && rangeEnd ? [Number(rangeStart), Number(rangeEnd)] as [number, number] : undefined;

  return <div className="export-dialog" role="dialog" aria-modal="true" aria-label={t("export:dialogTitle")} ref={dialogRef} onKeyDown={onKeyDown}>
    <form aria-label={t("export:formLabel")} onSubmit={event => { event.preventDefault(); void onExport({ project_id: projectId, format, version_ids: selected, chapter_range: chapterRange, title: title || undefined, author: author || undefined, template, locale: navigator.language || "en" }); }}>
      <header><div><p className="eyebrow">IMMUTABLE SNAPSHOT</p><h2 id="export-dialog-title">{t("export:heading")}</h2></div>{onClose ? <button type="button" aria-label={t("export:close")} onClick={close}>×</button> : null}</header>
      <label>{t("export:format")}<select aria-label={t("export:formatAria")} value={format} onChange={event => setFormat(event.target.value as ExportFormat)}>{["md", "txt", "docx", "epub"].map(item => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></label>
      <fieldset><legend>{t("export:templateLegend")}</legend>{PRESETS.map(preset => <label className="inline-choice" key={preset.value}><input aria-label={t(preset.labelKey)} type="radio" name="template" value={preset.value} checked={template === preset.value} onChange={() => setTemplate(preset.value)} /><span><strong>{t(preset.labelKey)}</strong><small>{t(preset.descriptionKey)}</small></span></label>)}</fieldset>
      <div className="export-grid"><label>{t("export:bookTitle")}<input aria-label={t("export:bookTitleAria")} value={title} onChange={event => setTitle(event.target.value)} /></label><label>{t("export:author")}<input aria-label={t("export:authorAria")} value={author} onChange={event => setAuthor(event.target.value)} /></label></div>
      <div className="export-grid"><label>{t("export:chapterStart")}<input aria-label={t("export:chapterStartAria")} inputMode="numeric" min="1" type="number" value={rangeStart} onChange={event => setRangeStart(event.target.value)} /></label><label>{t("export:chapterEnd")}<input aria-label={t("export:chapterEndAria")} inputMode="numeric" min={rangeStart || "1"} type="number" value={rangeEnd} onChange={event => setRangeEnd(event.target.value)} /></label></div>
      <fieldset><legend>{t("export:versionsLegend")}</legend>{versionIds.length ? versionIds.map((id, index) => <label className="inline-choice" key={id}><input aria-label={t("export:versionOption", { n: index + 1 })} type="checkbox" checked={selected.includes(id)} onChange={() => toggleVersion(id)} /><span>{t("export:versionOption", { n: index + 1 })}<small>{id}</small></span></label>) : <p>{t("export:versionsEmpty")}</p>}</fieldset>
      {manifest ? <output className="export-hashes" aria-live="polite"><strong>SHA-256</strong><code>{manifest.file_sha256}</code><span>{t("export:hashSummary", { bytes: manifest.byte_size.toLocaleString(), count: manifest.version_ids.length })}</span></output> : null}
      <footer className="dialog-actions"><button className="primary" type="submit">{t("export:submit")}</button>{onClose ? <button type="button" onClick={close}>{t("common:cancel")}</button> : null}</footer>
    </form>
  </div>;
}
