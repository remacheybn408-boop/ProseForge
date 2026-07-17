export type ExportFormat = "md" | "txt" | "docx" | "epub";
export type ExportRequest = { project_id: string; format: ExportFormat; version_ids: string[]; locale?: string; title?: string; author?: string };
