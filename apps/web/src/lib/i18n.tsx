import { createInstance, type i18n as I18nInstance } from "i18next";
import { I18nextProvider, useTranslation } from "react-i18next";
import { useMemo, type ReactNode } from "react";

export const resources = {
  en: {
    common: { cancel: "Cancel", close: "Close", export: "Export", retry: "Retry", save: "Save", offline: "Offline — saved drafts remain available, but generation and export are read-only." },
    chat: { send: "Send", stop: "Stop", edit: "Edit", regenerate: "Regenerate" },
    editor: { rewrite: "Rewrite", exportSnapshot: "Export snapshot", saveVersion: "Save version" },
    export: {
      dialogTitle: "Export snapshot",
      formLabel: "Export dialog",
      heading: "Export your work",
      close: "Close export dialog",
      format: "Format",
      formatAria: "Export format",
      templateLegend: "Template preset",
      presetWebSerial: "Web serial",
      presetWebSerialHint: "Clean chapter breaks for serial platforms.",
      presetSubmission: "Submission",
      presetSubmissionHint: "Includes title, author, and submission metadata.",
      presetArchive: "Archive",
      presetArchiveHint: "Keeps source versions and content hashes for auditability.",
      bookTitle: "Title",
      bookTitleAria: "Export title",
      author: "Author",
      authorAria: "Export author",
      chapterStart: "First chapter",
      chapterStartAria: "Chapter range start",
      chapterEnd: "Last chapter",
      chapterEndAria: "Chapter range end",
      versionsLegend: "Immutable versions",
      versionOption: "Version {{n}}",
      versionsEmpty: "No versions listed — the server pins the current active version as the snapshot.",
      submit: "Generate export snapshot",
      hashSummary: "{{bytes}} bytes · {{count}} versions",
    },
    workflows: { budget: "Budget", pause: "Pause", resume: "Resume", cancel: "Cancel", retry: "Retry" },
  },
  zh: {
    common: { cancel: "取消", close: "关闭", export: "导出", retry: "重试", save: "保存", offline: "当前离线——已保存草稿仍可查看，但生成与导出仅为只读状态。" },
    chat: { send: "发送", stop: "停止", edit: "编辑", regenerate: "重新生成" },
    editor: { rewrite: "改写", exportSnapshot: "导出快照", saveVersion: "保存版本" },
    export: {
      dialogTitle: "导出快照",
      formLabel: "导出对话框",
      heading: "导出作品",
      close: "关闭导出对话框",
      format: "格式",
      formatAria: "导出格式",
      templateLegend: "模板预设",
      presetWebSerial: "网文连载",
      presetWebSerialHint: "清晰的章节分隔，适合平台连载。",
      presetSubmission: "出版投稿",
      presetSubmissionHint: "包含书名、作者与投稿元数据。",
      presetArchive: "自存备份",
      presetArchiveHint: "保留来源版本与内容哈希，便于归档核验。",
      bookTitle: "书名",
      bookTitleAria: "导出书名",
      author: "作者",
      authorAria: "导出作者",
      chapterStart: "起始章节",
      chapterStartAria: "起始章节",
      chapterEnd: "结束章节",
      chapterEndAria: "结束章节",
      versionsLegend: "不可变版本",
      versionOption: "版本 {{n}}",
      versionsEmpty: "未指定版本时，服务器会把当前 active 版本解析为固定快照。",
      submit: "生成导出快照",
      hashSummary: "{{bytes}} 字节 · {{count}} 个版本",
    },
    workflows: { budget: "预算", pause: "暂停", resume: "继续", cancel: "取消", retry: "重试" },
  },
} as const;

export type Locale = keyof typeof resources;
export const namespaces = ["common", "chat", "editor", "export", "workflows"] as const;

export function createI18n(locale: Locale): I18nInstance {
  const instance = createInstance();
  void instance.init({ resources, lng: locale, fallbackLng: "en", defaultNS: "common", ns: namespaces, interpolation: { escapeValue: false }, initImmediate: false });
  return instance;
}

export function I18nProvider({ locale = "en", children }: { locale?: Locale; children: ReactNode }) {
  const instance = useMemo(() => createI18n(locale), [locale]);
  return <I18nextProvider i18n={instance}>{children}</I18nextProvider>;
}

export function useT() { return useTranslation(namespaces).t; }
export function formatDate(value: Date | string | number, locale: string, options?: Intl.DateTimeFormatOptions): string { return new Intl.DateTimeFormat(locale, options ?? { dateStyle: "medium" }).format(new Date(value)); }
export function formatNumber(value: number, locale: string, options?: Intl.NumberFormatOptions): string { return new Intl.NumberFormat(locale, options).format(value); }
