export type Project = { id: string; slug: string; title: string; genre: string; style: string; language: string; status: string };
export type Credential = { id: string; provider: string; masked_key: string };
export type Outline = { id: string; project_id: string; title: string; status: string; payload: Record<string, unknown>; missing_questions: string[]; missing_fields: string[]; confirmed: boolean };
export type ContextItem = { id: string; project_id: string; source_type: string; content: string; pinned: boolean; priority: number; excluded: boolean; token_estimate: number; provenance: Record<string, unknown> };
export type ContextSnapshot = { id: string; project_id: string; snapshot_hash: string; payload?: { items?: ContextItem[] } };
export type Chapter = { id: string; project_id: string; chapter_no: number; title: string; status: string; active_version_id?: string | null };
export type ChapterVersion = { id: string; chapter_id: string; version_no: number; content: string; word_count: number };
export type Workflow = {
  id: string;
  project_id: string;
  workflow_type: string;
  status: string;
  checkpoint?: string | null;
  current_step?: string | null;
  completed_steps?: string[];
  chapter_progress?: { current: number | null; completed: number[]; total: number; requested: number[] };
  retry_count?: number;
  model?: string | null;
  editor_model?: string | null;
  used_tokens?: number;
  token_limit?: number;
  estimated_cost?: number;
  cost_limit?: number;
  token_cost_estimate?: { used_tokens: number; token_limit: number; cost_usd: number; cost_limit: number };
};
export type WorkflowEvent = { id: number; event: string; data: Record<string, unknown> };
export type ChatMessage = { id: string; role: "user" | "assistant"; content: string; status: string };
export type ModelProfile = { id: string; name: string; config: Record<string, unknown> };
export type UsageBucket = { input_tokens: number; output_tokens: number; cached_input_tokens: number; reasoning_tokens: number; total_tokens: number; cost_usd: number | null };
export type UsageSummary = { scope: string; project_id?: string | null; conversation_id?: string | null; workflow_id?: string | null; actual: UsageBucket; estimated: UsageBucket };
export type ProviderOption = { id: string; status: string };
export type CatalogModel = { provider: string; model_id: string; display_name: string; capabilities: Record<string, unknown>; context_window?: number | null; max_output_tokens?: number | null };

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly detail = "") {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "include", headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) {
    let detail = "";
    try { const body = await response.clone().json() as { detail?: string }; detail = body.detail ?? ""; } catch { /* response may not be JSON */ }
    const messages: Record<number, string> = { 401: "Your session expired. Please sign in again.", 403: "You do not have permission to perform this action.", 404: "That item is no longer available.", 409: "This changed elsewhere. Reload the latest version and try again.", 429: "The provider is rate-limiting requests. Please wait and try again.", 500: "The service could not complete that request. Try again shortly.", 502: "The provider is unavailable. Check the connection and try again.", 503: "The workspace is temporarily unavailable. Try again shortly." };
    throw new ApiError(response.status, messages[response.status] || detail || `Request failed (${response.status})`, detail);
  }
  if (response.status === 204) return undefined as T;
  const body = await response.text();
  if (!body) return undefined as T;
  try { return JSON.parse(body) as T; } catch { /* successful plain-text responses are valid */ }
  return body as T;
}

export function getHealth() { return request<{ status: string }>("/api/v1/health/live"); }
export function listProviders() { return request<ProviderOption[]>("/api/v1/providers"); }
export function listModels(filters: { provider?: string; q?: string; available_only?: boolean } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined) as [string, string][]).toString(); return request<CatalogModel[]>(`/api/v1/models${query ? `?${query}` : ""}`); }
export function listProjects() { return request<Project[]>("/api/v1/projects"); }
export function listCredentials() { return request<Credential[]>("/api/v1/credentials"); }
export function saveCredential(payload: { provider: string; api_key: string; base_url?: string }) { return request<Credential>("/api/v1/credentials", { method: "POST", body: JSON.stringify(payload) }); }
export function deleteCredential(credentialId: string) { return request<void>(`/api/v1/credentials/${encodeURIComponent(credentialId)}`, { method: "DELETE" }); }
export function probeProvider(provider: string) { return request<{ provider: string; valid: boolean }>(`/api/v1/providers/${provider}/probe`, { method: "POST" }); }
export function listModelProfiles() { return request<ModelProfile[]>("/api/v1/model-profiles"); }
export function saveModelProfile(payload: { name: string; role: "writer" | "editor"; config: Record<string, unknown> }) { return request<ModelProfile>("/api/v1/model-profiles", { method: "POST", body: JSON.stringify(payload) }); }
export function login(payload: { email: string; password: string }) { return request<{ access_token: string; token_type: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) }); }
export function logout() { return request<void>("/api/v1/auth/logout", { method: "POST" }); }
export function setupAdmin(payload: { email: string; password: string }) { return request<{ id: string; email: string }>("/api/v1/auth/setup", { method: "POST", body: JSON.stringify(payload) }); }
export function createProject(payload: { slug: string; title: string; genre?: string; style?: string }) { return request<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(payload) }); }
export function listChapters(projectId: string) { return request<Chapter[]>(`/api/v1/projects/${projectId}/chapters`); }
export function saveChapterVersion(chapterId: string, content: string, baseVersion?: number) { return request<ChapterVersion>(`/api/v1/chapters/${chapterId}/versions`, { method: "POST", body: JSON.stringify({ content, base_version: baseVersion }) }); }
export function listChapterVersions(chapterId: string) { return request<ChapterVersion[]>(`/api/v1/chapters/${chapterId}/versions`); }
export function activateChapterVersion(chapterId: string, versionId: string) { return request<{ chapter_id: string; active_version_id: string; version_no: number }>(`/api/v1/chapters/${chapterId}/activate-version?version_id=${encodeURIComponent(versionId)}`, { method: "POST" }); }
export function getChapterDiff(chapterId: string, fromVersion: number, toVersion: number) { return request<{ changed: boolean; diff: string[] }>(`/api/v1/chapters/${chapterId}/diff?from_version=${fromVersion}&to_version=${toVersion}`); }
export function listOutlines(projectId: string) { return request<Outline[]>(`/api/v1/projects/${projectId}/outlines`); }
export function importOutline(projectId: string, payload: { title: string; content?: string; data?: Record<string, unknown> }) { return request<Outline>(`/api/v1/projects/${projectId}/outlines/import`, { method: "POST", body: JSON.stringify(payload) }); }
export function answerOutline(outlineId: string, answers: Record<string, unknown>) { return request<Outline>(`/api/v1/outlines/${outlineId}/parse`, { method: "POST", body: JSON.stringify({ answers }) }); }
export function confirmOutline(outlineId: string) { return request<Outline>(`/api/v1/outlines/${outlineId}/confirm`, { method: "POST" }); }
export function listContext(projectId: string, options: { profileId?: string; provider?: string; model?: string } = {}) {
  const query = new URLSearchParams(Object.entries({ profile_id: options.profileId, provider: options.provider, model: options.model }).filter(([, value]) => value !== undefined) as [string, string][]).toString();
  return request<{ items: ContextItem[]; used_tokens: number; context_window: number; available_tokens: number; system_reserved_tokens: number; history_tokens: number; output_reserve_tokens: number; provider?: string; model?: string }>(`/api/v1/projects/${projectId}/context${query ? `?${query}` : ""}`);
}
export function addContext(projectId: string, content: string, sourceType = "manual") { return request<ContextItem>(`/api/v1/projects/${projectId}/context/items`, { method: "POST", body: JSON.stringify({ content, source_type: sourceType }) }); }
export function updateContext(itemId: string, payload: Partial<Pick<ContextItem, "content" | "pinned" | "priority" | "excluded">>) { return request<ContextItem>(`/api/v1/context/items/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function deleteContext(itemId: string) { return request<void>(`/api/v1/context/items/${itemId}`, { method: "DELETE" }); }
export function compileContext(projectId: string) { return request<{ id: string; snapshot_hash: string; item_count: number }>(`/api/v1/projects/${projectId}/context/compile`, { method: "POST" }); }
export function getContextSnapshot(snapshotId: string) { return request<ContextSnapshot>(`/api/v1/context/snapshots/${encodeURIComponent(snapshotId)}`); }
export function validateContextSnapshot(snapshotId: string) { return request<{ id: string; valid: boolean; snapshot_hash: string; actual_hash: string }>(`/api/v1/context/snapshots/${encodeURIComponent(snapshotId)}/validate`, { method: "POST" }); }
export function restoreContext(projectId: string, snapshotId: string) { return request<{ snapshot_id: string; items: ContextItem[]; restored_count: number }>(`/api/v1/projects/${projectId}/context/restore`, { method: "POST", body: JSON.stringify({ snapshot_id: snapshotId }) }); }
export async function downloadContextSnapshot(snapshotId: string): Promise<Blob> {
  const response = await fetch(`/api/v1/context/snapshots/${encodeURIComponent(snapshotId)}/download`, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, `Snapshot download failed (${response.status})`);
  return response.blob();
}
export function createWorkflow(projectId: string, chapterNumbers: number[]) { return request<Workflow>(`/api/v1/projects/${projectId}/workflows/novel`, { method: "POST", body: JSON.stringify({ chapter_numbers: chapterNumbers }) }); }
export function getWorkflow(workflowId: string) { return request<Workflow>(`/api/v1/workflows/${workflowId}`); }
export function controlWorkflow(workflowId: string, action: "pause" | "resume" | "cancel" | "retry") { return request<Workflow>(`/api/v1/workflows/${workflowId}/${action}`, { method: "POST" }); }
export async function subscribeWorkflowEvents(workflowId: string, onEvent: (event: WorkflowEvent) => void, options: { lastEventId?: number; signal?: AbortSignal; reconnectDelayMs?: number } = {}): Promise<void> {
  let lastEventId = options.lastEventId ?? 0;
  const terminalStatuses = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
  while (!options.signal?.aborted) {
  const headers: Record<string, string> = {};
  if (lastEventId > 0) headers["Last-Event-ID"] = String(lastEventId);
  let response: Response | undefined;
  try {
    response = await fetch(`/api/v1/workflows/${encodeURIComponent(workflowId)}/events`, { credentials: "include", headers, signal: options.signal });
  } catch {
    if (options.signal?.aborted) return;
    await new Promise(resolve => setTimeout(resolve, options.reconnectDelayMs ?? 1000));
    continue;
  }
  if (!response) continue;
  if (!response.ok) throw new ApiError(response.status, `Workflow event stream failed (${response.status})`);
  if (!response.body) {
    await new Promise(resolve => setTimeout(resolve, options.reconnectDelayMs ?? 1000));
    continue;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let id = 0;
  let event = "message";
  let dataLines: string[] = [];
  let terminal = false;
  const dispatch = () => {
    if (dataLines.length === 0) return;
    const raw = dataLines.join("\n");
    let data: Record<string, unknown>;
    try { data = JSON.parse(raw) as Record<string, unknown>; } catch { data = { raw }; }
    if (id > 0) lastEventId = Math.max(lastEventId, id);
    onEvent({ id, event, data });
    terminal = terminalStatuses.has(typeof data.status === "string" ? data.status : event);
    id = 0;
    event = "message";
    dataLines = [];
  };
  const consumeLine = (line: string) => {
    if (!line) return dispatch();
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") id = Number(value) || 0;
    if (field === "event") event = value || "message";
    if (field === "data") dataLines.push(value);
  };
  try {
    while (true) {
      const result = await reader.read();
      buffer += decoder.decode(result.value ?? new Uint8Array(), { stream: !result.done });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) consumeLine(line.endsWith("\r") ? line.slice(0, -1) : line);
      if (result.done) break;
    }
    if (buffer) consumeLine(buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer);
    dispatch();
  } catch {
    if (options.signal?.aborted) return;
  }
  if (terminal || options.signal?.aborted) return;
  await new Promise(resolve => setTimeout(resolve, options.reconnectDelayMs ?? 1000));
  }
}
export function createConversation(projectId: string) { return request<{ id: string; branch_id: string; title: string }>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ project_id: projectId, title: "Writing companion" }) }); }
export function sendMessage(conversationId: string, payload: { branch_id: string; content: string; client_request_id: string; provider?: string; model?: string }) { return request<{ user_message_id: string; assistant_message_id: string; task_id: string }>(`/api/v1/conversations/${conversationId}/messages`, { method: "POST", body: JSON.stringify(payload) }); }
export function listMessages(conversationId: string, branchId: string) { return request<ChatMessage[]>(`/api/v1/conversations/${conversationId}/branches/${branchId}/messages`); }
export function forkConversation(conversationId: string, messageId: string, name: string) { return request<{ id: string; name: string }>(`/api/v1/conversations/${conversationId}/branches`, { method: "POST", body: JSON.stringify({ message_id: messageId, name }) }); }
export function requestExport(projectId: string, format: "txt" | "md" | "json" | "docx" | "epub") { return request<{ status: string; format: string; download_url: string }>(`/api/v1/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ format }) }); }
export function getUsageSummary(filters: { project_id?: string; conversation_id?: string; workflow_id?: string } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value) as [string, string][]).toString(); return request<UsageSummary>(`/api/v1/usage/summary${query ? `?${query}` : ""}`); }
export function listUsageRecords(filters: { project_id?: string; conversation_id?: string; workflow_id?: string; limit?: number } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined) as [string, string][]).toString(); return request<Record<string, unknown>[]>(`/api/v1/usage/records${query ? `?${query}` : ""}`); }

export function subscribeConversationEvents(conversationId: string, onEvent: (event: { event?: string; message_id?: string; text?: string }) => void) {
  const source = new EventSource(`/api/v1/conversations/${conversationId}/events`);
  const handle = (event: MessageEvent<string>) => {
    try { onEvent(JSON.parse(event.data) as { event?: string; message_id?: string; text?: string }); } catch { /* reconnect will replay the durable event */ }
  };
  source.addEventListener("content.delta", handle);
  return () => source.close();
}
