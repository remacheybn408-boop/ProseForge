export type Project = { id: string; slug: string; title: string; genre: string; style: string; language: string; status: string };
export type Credential = { id: string; provider: string; masked_key: string };
export type Outline = { id: string; project_id: string; title: string; status: string; payload: Record<string, unknown>; missing_questions: string[]; missing_fields: string[]; confirmed: boolean };
export type ContextItem = { id: string; project_id: string; source_type: string; content: string; pinned: boolean; priority: number; excluded: boolean; provenance: Record<string, unknown> };
export type Chapter = { id: string; project_id: string; chapter_no: number; title: string; status: string; active_version_id?: string | null };
export type ChapterVersion = { id: string; chapter_id: string; version_no: number; content: string; word_count: number };
export type Workflow = { id: string; project_id: string; workflow_type: string; status: string };
export type ChatMessage = { id: string; role: "user" | "assistant"; content: string; status: string };
export type ModelProfile = { id: string; name: string; config: Record<string, unknown> };
export type UsageBucket = { input_tokens: number; output_tokens: number; cached_input_tokens: number; reasoning_tokens: number; total_tokens: number; cost_usd: number | null };
export type UsageSummary = { scope: string; project_id?: string | null; conversation_id?: string | null; workflow_id?: string | null; actual: UsageBucket; estimated: UsageBucket };
export type ProviderOption = { id: string; status: string };
export type CatalogModel = { provider: string; model_id: string; display_name: string; capabilities: Record<string, unknown>; context_window?: number | null; max_output_tokens?: number | null };
export type AgentRun = { id: string; project_id: string; status: string; goal_hash: string; graph_revision: number; checkpoint_id?: string | null; budget_used: number; budget_limit: number; event_cursor: number; policy_version: string; terminal_reason?: string | null };
export type AgentTask = { id: string; task_key: string; role: string; status: string; attempts: number; depends_on: string[] };

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
export function probeProvider(provider: string) { return request<{ provider: string; valid: boolean }>(`/api/v1/providers/${provider}/probe`, { method: "POST" }); }
export function listModelProfiles() { return request<ModelProfile[]>("/api/v1/model-profiles"); }
export function saveModelProfile(payload: { name: string; role: "writer" | "editor"; config: Record<string, unknown> }) { return request<ModelProfile>("/api/v1/model-profiles", { method: "POST", body: JSON.stringify(payload) }); }
export function login(payload: { email: string; password: string }) { return request<{ access_token: string; token_type: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) }); }
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
export function listContext(projectId: string) { return request<{ items: ContextItem[]; used_tokens: number; context_window: number; context_window_source: string; available_tokens: number }>(`/api/v1/projects/${projectId}/context`); }
export function addContext(projectId: string, content: string, sourceType = "manual") { return request<ContextItem>(`/api/v1/projects/${projectId}/context/items`, { method: "POST", body: JSON.stringify({ content, source_type: sourceType }) }); }
export function updateContext(itemId: string, payload: Partial<Pick<ContextItem, "content" | "pinned" | "priority" | "excluded">>) { return request<ContextItem>(`/api/v1/context/items/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function createWorkflow(projectId: string, chapterNumbers: number[]) { return request<Workflow>(`/api/v1/projects/${projectId}/workflows/novel`, { method: "POST", body: JSON.stringify({ chapter_numbers: chapterNumbers }) }); }
export function getWorkflow(workflowId: string) { return request<Workflow>(`/api/v1/workflows/${workflowId}`); }
export function controlWorkflow(workflowId: string, action: "pause" | "resume" | "cancel" | "retry") { return request<Workflow>(`/api/v1/workflows/${workflowId}/${action}`, { method: "POST" }); }
export function createConversation(projectId: string) { return request<{ id: string; branch_id: string; title: string }>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ project_id: projectId, title: "Writing companion" }) }); }
export function sendMessage(conversationId: string, payload: { branch_id: string; content: string; client_request_id: string; provider?: string; model?: string; reasoning_level?: string }) { return request<{ user_message_id: string; assistant_message_id: string; task_id: string }>(`/api/v2/conversations/${conversationId}/messages`, { method: "POST", body: JSON.stringify(payload) }); }
export function listMessages(conversationId: string, branchId: string) { return request<ChatMessage[]>(`/api/v1/conversations/${conversationId}/branches/${branchId}/messages`); }
export function forkConversation(conversationId: string, messageId: string, name: string) { return request<{ id: string; name: string }>(`/api/v1/conversations/${conversationId}/branches`, { method: "POST", body: JSON.stringify({ message_id: messageId, name }) }); }
export function requestExport(projectId: string, format: "txt" | "md" | "json" | "docx" | "epub", versionIds: string[] = []) { return request<{ status: string; format: string; download_url: string; version_ids: string[] }>(`/api/v1/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ format, version_ids: versionIds }) }); }
export function getUsageSummary(filters: { project_id?: string; conversation_id?: string; workflow_id?: string } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value) as [string, string][]).toString(); return request<UsageSummary>(`/api/v1/usage/summary${query ? `?${query}` : ""}`); }
export function listUsageRecords(filters: { project_id?: string; conversation_id?: string; workflow_id?: string; limit?: number } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined) as [string, string][]).toString(); return request<Record<string, unknown>[]>(`/api/v1/usage/records${query ? `?${query}` : ""}`); }
export function createAgentRun(projectId: string, payload: { goal: string; graph_revision?: number; budget_limit?: number }, idempotencyKey?: string) { return request<AgentRun>("/api/v3/projects/" + projectId + "/agent-runs", { method: "POST", headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined, body: JSON.stringify(payload) }); }
export function getAgentRun(runId: string) { return request<AgentRun>("/api/v3/agent-runs/" + runId); }
export function listAgentTasks(runId: string) { return request<AgentTask[]>("/api/v3/agent-runs/" + runId + "/tasks"); }
export function controlAgentRun(runId: string, action: "pause" | "resume" | "cancel" | "retry") { return request<AgentRun>("/api/v3/agent-runs/" + runId + "/" + action, { method: "POST" }); }

export function stopMessage(messageId: string) { return request<{ id: string; status: string }>(`/api/v1/messages/${messageId}/stop`, { method: "POST" }); }
export function retryMessage(messageId: string, payload: { provider?: string; model?: string; reasoning_level?: string } = {}) { return request<{ id: string; status: string; task_id: string }>(`/api/v1/messages/${messageId}/retry`, { method: "POST", body: JSON.stringify(payload) }); }
export type V2CatalogModel = { provider: string; model_id: string; capabilities: Record<string, unknown>; context_window?: number | null; max_output_tokens?: number | null };
export function listV2Models(filters: { provider?: string; capability?: string } = {}) { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined) as [string, string][]).toString(); return request<V2CatalogModel[]>(`/api/v2/models${query ? `?${query}` : ""}`); }

export type ModelCapabilitiesInfo = { provider: string; model_id: string; context_window: number; max_output_tokens: number; supports_reasoning: boolean; reasoning_parameter: string | null; supports_tools: boolean; supports_vision: boolean; source: string };
export function getModelCapabilities(provider: string, modelId: string) { return request<ModelCapabilitiesInfo>(`/api/v2/models/${encodeURIComponent(provider)}/${encodeURIComponent(modelId)}/capabilities`); }

export type ModelResolution = { provider: string; model_id: string; normalized_level: string; provider_parameter: Record<string, unknown> | null; context_window: number; warnings: string[] };
export function validateModelResolution(payload: { provider: string; model_id: string; level: string }) { return request<ModelResolution>("/api/v2/model-resolutions/validate", { method: "POST", body: JSON.stringify(payload) }); }

export type BranchInfo = { id: string; conversation_id: string; name: string; parent_branch_id?: string | null; forked_from_message_id?: string | null; status: string; title?: string | null };
export type BranchTreeMessage = { id: string; branch_id: string; role: "user" | "assistant"; content: string; status: string; parent_message_id?: string | null; generation_attempt?: number };
export type BranchCompareEntry = { id: string; role: string; content: string; generation_attempt: number; parent_message_id?: string | null };
export type BranchCompareResult = { common_count: number; left: BranchCompareEntry[]; right: BranchCompareEntry[] };

export function listBranchesV2(conversationId: string, options: { includeArchived?: boolean } = {}) { return request<BranchInfo[]>(`/api/v2/conversations/${conversationId}/branches${options.includeArchived ? "?include_archived=true" : ""}`); }
export function getBranchTree(conversationId: string, branchId: string) { return request<BranchTreeMessage[]>(`/api/v2/conversations/${conversationId}/branches/${branchId}/tree`); }
export function compareBranches(conversationId: string, left: string, right: string) { return request<BranchCompareResult>(`/api/v2/conversations/${conversationId}/branches/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`); }
export function editMessageV2(conversationId: string, messageId: string, content: string) { return request<{ branch_id: string; source_message_id: string; replacement_message_id: string }>(`/api/v2/conversations/${conversationId}/messages/${messageId}/edit`, { method: "POST", body: JSON.stringify({ content }) }); }
export function regenerateReply(conversationId: string, messageId: string, payload: { provider?: string; model?: string; reasoning_level?: string } = {}) { return request<{ message_id: string; task_id: string }>(`/api/v2/conversations/${conversationId}/messages/${messageId}/regenerate`, { method: "POST", body: JSON.stringify(payload) }); }
export function archiveBranch(conversationId: string, branchId: string) { return request<{ id: string; status: string }>(`/api/v2/conversations/${conversationId}/branches/${branchId}/archive`, { method: "POST", body: JSON.stringify({}) }); }

export type ConversationEvent = { event?: string; message_id?: string; text?: string } & Record<string, unknown>;
export const CONVERSATION_EVENT_NAMES = ["content.delta", "usage.updated", "message.started", "message.completed", "message.failed"] as const;

export function subscribeConversationEvents(conversationId: string, onEvent: (event: ConversationEvent) => void) {
  const source = new EventSource(`/api/v1/conversations/${conversationId}/events`);
  const handle = (event: MessageEvent<string>) => {
    try { onEvent(JSON.parse(event.data) as ConversationEvent); } catch { /* reconnect will replay the durable event */ }
  };
  for (const name of CONVERSATION_EVENT_NAMES) source.addEventListener(name, handle);
  return () => source.close();
}
