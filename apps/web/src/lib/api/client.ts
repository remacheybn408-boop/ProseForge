export type Project = { id: string; slug: string; title: string; genre: string; style: string; language: string; status: string };
export type Credential = { id: string; provider: string; masked_key: string };
export type Outline = { id: string; project_id: string; title: string; status: string; payload: Record<string, unknown>; missing_questions: string[]; missing_fields: string[]; confirmed: boolean };
export type ContextItem = { id: string; project_id: string; source_type: string; content: string; pinned: boolean; priority: number; excluded: boolean; provenance: Record<string, unknown> };
export type Chapter = { id: string; project_id: string; chapter_no: number; title: string; status: string; active_version_id?: string | null };
export type ChapterVersion = { id: string; chapter_id: string; version_no: number; content: string; word_count: number };
export type Workflow = { id: string; project_id: string; workflow_type: string; status: string };
export type WorkflowDefinition = { id: string; project_id: string; name: string; revision: number; definition: { nodes: Record<string, unknown>[]; edges: Record<string, unknown>[] } };
export type WorkflowNodeState = { id: string; node_key: string; status: string; retry_count: number; reserved_tokens: number; used_tokens: number; reserved_cost: number; used_cost: number };
export type WorkflowRunSnapshot = { run: Workflow & { definition_id?: string; definition_revision?: number; token_limit: number; cost_limit: number }; nodes: WorkflowNodeState[]; event_cursor: number };
export type ChatMessage = { id: string; role: "user" | "assistant"; content: string; status: string; context_snapshot_id?: string | null };
export type StoryBibleFact = { id: string; project_id: string; kind: string; key: string; value: Record<string, unknown>; status: string; confidence: number; source: string; pinned: boolean; version: number };
export type ContextBlock = { type?: string; source_type: string; source_id: string; text: string; token_estimate: number; priority?: number; pinned: boolean; redaction?: boolean; reason?: string };
export type ContextOmission = { source_type?: string; source_id: string; message_id?: string; reason: string };
export type ContextSnapshot = { id: string; project_id?: string; snapshot_hash: string; payload: { blocks: ContextBlock[]; omitted: ContextOmission[]; budget: { context_window: number; input_tokens: number; output_reserve: number }; injected_fact_ids?: string[]; injected_fact_reasons?: Record<string, string> } };
export type ModelProfile = { id: string; name: string; config: Record<string, unknown> };
export type UsageBucket = { input_tokens: number; output_tokens: number; cached_input_tokens: number; reasoning_tokens: number; total_tokens: number; cost_usd: number | null };
export type UsageSummary = { scope: string; project_id?: string | null; conversation_id?: string | null; workflow_id?: string | null; actual: UsageBucket; estimated: UsageBucket };
export type ProviderOption = { id: string; status: string };
export type CatalogModel = { provider: string; model_id: string; display_name: string; capabilities: Record<string, unknown>; context_window?: number | null; max_output_tokens?: number | null };
export type AgentRun = { id: string; project_id: string; status: string; goal_hash: string; graph_revision: number; checkpoint_id?: string | null; budget_used: number; budget_limit: number; event_cursor: number; policy_version: string; terminal_reason?: string | null };
export type AgentTask = { id: string; task_key: string; role: string; status: string; attempts: number; depends_on: string[] };
export type ExportFormat = "txt" | "md" | "docx" | "epub";
export type ExportTemplate = "web-serial" | "submission" | "archive";
export type ExportRequestPayload = { format: ExportFormat; chapter_range?: [number, number]; version_ids?: string[]; locale?: string; title?: string; author?: string; template?: ExportTemplate };
export type ExportManifest = { id: string; project_id: string; format: ExportFormat; template: ExportTemplate; title?: string | null; locale: string; version_ids: string[]; content_hashes: Record<string, string>; file_sha256: string; byte_size: number; download_url: string };

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
export type SelectionAction = "continue" | "expand" | "shorten" | "rewrite" | "change-tone" | "review";
export type SelectionActionPayload = { action: SelectionAction; from: number; to: number; selected_text_hash: string; base_version_id: string; params?: Record<string, unknown> };
export type SelectionActionResult = { proposal_id?: string; candidate_proposal_ids?: string[]; review_id?: string };
export function createSelectionAction(chapterId: string, payload: SelectionActionPayload) { return request<SelectionActionResult>(`/api/v2/chapters/${chapterId}/selection-actions`, { method: "POST", body: JSON.stringify(payload) }); }
export type ProposalDiff = { proposal_id: string; guard_status?: "clear" | "blocked" | "pending"; hunks: { start: number; end: number; replacement: string }[]; after_text: string };
export function getProposalDiff(proposalId: string) { return request<ProposalDiff>(`/api/v2/proposals/${proposalId}/diff`); }
export function approveProposal(proposalId: string, acceptHunks?: number[]) { return request<{ status: string; version?: ChapterVersion | null }>(`/api/v2/proposals/${proposalId}/approve`, { method: "POST", body: JSON.stringify({ accept_hunks: acceptHunks }) }); }
export function rejectProposal(proposalId: string) { return request<{ status: string }>(`/api/v2/proposals/${proposalId}/reject`, { method: "POST", body: JSON.stringify({}) }); }
export function listOutlines(projectId: string) { return request<Outline[]>(`/api/v1/projects/${projectId}/outlines`); }
export function importOutline(projectId: string, payload: { title: string; content?: string; data?: Record<string, unknown> }) { return request<Outline>(`/api/v1/projects/${projectId}/outlines/import`, { method: "POST", body: JSON.stringify(payload) }); }
export function answerOutline(outlineId: string, answers: Record<string, unknown>) { return request<Outline>(`/api/v1/outlines/${outlineId}/parse`, { method: "POST", body: JSON.stringify({ answers }) }); }
export function confirmOutline(outlineId: string) { return request<Outline>(`/api/v1/outlines/${outlineId}/confirm`, { method: "POST" }); }
export function listContext(projectId: string) { return request<{ items: ContextItem[]; used_tokens: number; context_window: number; context_window_source: string; available_tokens: number }>(`/api/v1/projects/${projectId}/context`); }
export function getContextSnapshot(snapshotId: string) { return request<ContextSnapshot>(`/api/v1/context/snapshots/${snapshotId}`); }
export function previewContext(projectId: string, payload: { text: string; provider?: string; model?: string }) { return request<ContextSnapshot>(`/api/v2/projects/${projectId}/context/preview`, { method: "POST", body: JSON.stringify(payload) }); }
export function listStoryBible(projectId: string) { return request<StoryBibleFact[]>(`/api/v2/projects/${projectId}/story-bible`); }
export function createStoryFact(projectId: string, payload: { kind: string; key: string; value: Record<string, unknown>; pinned?: boolean; confidence?: number; source?: string }) { return request<StoryBibleFact>(`/api/v2/projects/${projectId}/story-bible/entries`, { method: "POST", body: JSON.stringify(payload) }); }
export function updateStoryFact(factId: string, payload: { expected_version: number; key?: string; value?: Record<string, unknown>; pinned?: boolean; confidence?: number; source?: string }) { return request<StoryBibleFact>(`/api/v2/story-bible/${factId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function setStoryFactStatus(factId: string, status: string) { return request<StoryBibleFact>(`/api/v2/story-bible/${factId}/status`, { method: "POST", body: JSON.stringify({ status }) }); }
export function addContext(projectId: string, content: string, sourceType = "manual") { return request<ContextItem>(`/api/v1/projects/${projectId}/context/items`, { method: "POST", body: JSON.stringify({ content, source_type: sourceType }) }); }
export function updateContext(itemId: string, payload: Partial<Pick<ContextItem, "content" | "pinned" | "priority" | "excluded">>) { return request<ContextItem>(`/api/v1/context/items/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function createWorkflow(projectId: string, chapterNumbers: number[]) { return request<Workflow>(`/api/v1/projects/${projectId}/workflows/novel`, { method: "POST", body: JSON.stringify({ chapter_numbers: chapterNumbers }) }); }
export function getWorkflow(workflowId: string) { return request<Workflow>(`/api/v1/workflows/${workflowId}`); }
export function controlWorkflow(workflowId: string, action: "pause" | "resume" | "cancel" | "retry") { return request<Workflow>(`/api/v1/workflows/${workflowId}/${action}`, { method: "POST" }); }
export function listWorkflowDefinitions(projectId: string) { return request<WorkflowDefinition[]>(`/api/v2/projects/${projectId}/workflow-definitions`); }
export function createWorkflowDefinition(projectId: string, payload: { name: string; definition: WorkflowDefinition["definition"] }) { return request<WorkflowDefinition>(`/api/v2/projects/${projectId}/workflow-definitions`, { method: "POST", body: JSON.stringify(payload) }); }
export function updateWorkflowDefinition(definitionId: string, payload: { name?: string; definition: WorkflowDefinition["definition"] }) { return request<WorkflowDefinition>(`/api/v2/workflow-definitions/${definitionId}`, { method: "PUT", body: JSON.stringify(payload) }); }
export function startWorkflowDefinition(definitionId: string, limits: { token_limit?: number; cost_limit?: number } = {}) { return request<{ run: WorkflowRunSnapshot["run"]; nodes: WorkflowNodeState[] }>(`/api/v2/workflow-definitions/${definitionId}/runs`, { method: "POST", body: JSON.stringify(limits) }); }
export function getWorkflowRun(runId: string) { return request<WorkflowRunSnapshot>(`/api/v2/workflow-runs/${runId}`); }
function newIdempotencyKey(): string {
  // crypto.randomUUID exists only in secure contexts; plain-http deployments
  // still need unique keys for the idempotent workflow controls.
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function controlWorkflowRun(runId: string, action: "pause" | "resume" | "cancel" | "retry", idempotencyKey = newIdempotencyKey()) { return request<{ run: WorkflowRunSnapshot["run"]; idempotent_replay: boolean }>(`/api/v2/workflow-runs/${runId}/${action}`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey } }); }
export function createConversation(projectId: string) { return request<{ id: string; branch_id: string; title: string }>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ project_id: projectId, title: "Writing companion" }) }); }
export function sendMessage(conversationId: string, payload: { branch_id: string; content: string; client_request_id: string; provider?: string; model?: string; reasoning_level?: string }) { return request<{ user_message_id: string; assistant_message_id: string; task_id: string }>(`/api/v2/conversations/${conversationId}/messages`, { method: "POST", body: JSON.stringify(payload) }); }
export function listMessages(conversationId: string, branchId: string) { return request<ChatMessage[]>(`/api/v1/conversations/${conversationId}/branches/${branchId}/messages`); }
export function forkConversation(conversationId: string, messageId: string, name: string) { return request<{ id: string; name: string }>(`/api/v1/conversations/${conversationId}/branches`, { method: "POST", body: JSON.stringify({ message_id: messageId, name }) }); }
export function requestExport(projectId: string, payload: ExportRequestPayload) { return request<ExportManifest>(`/api/v1/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify(payload) }); }
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

export type WorkflowRunStreamEvent = { id: number; event: string; data: Record<string, unknown> };

/**
 * Streams `/api/v2/workflow-runs/{runId}/events` (replay from `lastEventId`,
 * then live tail). The native EventSource API cannot send an initial
 * `Last-Event-ID` header, so the SSE wire format is parsed over fetch with the
 * same cookie auth as `request`. Heartbeat comment frames are skipped.
 * `onClose` fires when the server ends the stream (terminal run) or the
 * connection drops; the returned function closes the stream without `onClose`.
 */
export function subscribeWorkflowRunEvents(runId: string, options: { lastEventId?: number; onEvent: (event: WorkflowRunStreamEvent) => void; onClose?: () => void }) {
  const controller = new AbortController();
  const headers: Record<string, string> = { accept: "text/event-stream" };
  if (options.lastEventId && options.lastEventId > 0) headers["last-event-id"] = String(options.lastEventId);
  const parseFrame = (frame: string): WorkflowRunStreamEvent | null => {
    if (frame.startsWith(":")) return null;
    let id = 0;
    let event = "message";
    const data: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("id:")) id = Number(line.slice(3).trim()) || 0;
      else if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (!data.length) return null;
    try { return { id, event, data: JSON.parse(data.join("\n")) as Record<string, unknown> }; } catch { return null; }
  };
  void fetch(`/api/v2/workflow-runs/${runId}/events`, { credentials: "include", headers, signal: controller.signal }).then(async response => {
    if (!response.ok || !response.body) { options.onClose?.(); return; }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseFrame(frame);
        if (parsed) options.onEvent(parsed);
        boundary = buffer.indexOf("\n\n");
      }
    }
    options.onClose?.();
  }).catch(() => { if (!controller.signal.aborted) options.onClose?.(); });
  return () => controller.abort();
}
