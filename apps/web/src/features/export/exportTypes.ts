export type ExportFormat = "md" | "txt" | "docx" | "epub";
export type ExportTemplate = "web-serial" | "submission" | "archive";
export type ExportRequest = { project_id: string; format: ExportFormat; chapter_range?: [number, number]; version_ids: string[]; locale: string; title?: string; author?: string; template: ExportTemplate };
export type ExportManifest = { id: string; project_id: string; format: ExportFormat; template: ExportTemplate; title?: string | null; locale: string; version_ids: string[]; content_hashes: Record<string, string>; file_sha256: string; byte_size: number; download_url: string };
