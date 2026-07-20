import type { AgentRunEvent } from "../../lib/api/client";

export const agentRunKeys = {
  run: (runId: string | undefined) => ["agent-run", runId] as const,
  tasks: (runId: string | undefined) => ["agent-run-tasks", runId] as const,
  artifacts: (runId: string | undefined) => ["agent-run-artifacts", runId] as const,
  reviews: (runId: string | undefined) => ["agent-run-reviews", runId] as const,
  audit: (runId: string | undefined) => ["agent-run-audit", runId] as const,
};

// Mirrors the terminal set in proseforge/api/routes/agent_runs.py (_control transitions)
// plus BUDGET_EXHAUSTED from the V3 executor; a paused run is non-terminal but idle,
// so the events poll only runs while the run is active.
const TERMINAL_RUN_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"]);
const ACTIVE_RUN_STATUSES = new Set(["PENDING", "RUNNING"]);

export function isTerminalAgentRun(status: string) {
  return TERMINAL_RUN_STATUSES.has(status.toUpperCase());
}

export function isActiveAgentRun(status: string) {
  return ACTIVE_RUN_STATUSES.has(status.toUpperCase());
}

// 篆刻单字章：each agent role is sealed with a single carved character; no colored
// avatars or robot icons (DESIGN_SYSTEM_INK §4.4). Roles come from
// proseforge/domain/agents/roles.py; unknown roles fall back to a neutral task seal.
export const AGENT_ROLE_SEALS: Record<string, string> = {
  chief_planner: "规",
  story_architect: "规",
  timeline_analyst: "规",
  scene_writer: "写",
  world_builder: "写",
  character_designer: "写",
  continuity_reviewer: "审",
  adversarial_reviewer: "审",
  style_editor: "主编",
  merge_editor: "主编",
  chief_editor: "主编",
};

export function agentRoleSeal(role: string) {
  return AGENT_ROLE_SEALS[role] ?? "事";
}

// Artifact type seals: ink line-glyphs per type (文稿/批注/记忆/评审…), dual-encoded
// with the type text next to the seal.
export const AGENT_ARTIFACT_SEALS: Record<string, string> = {
  candidate: "文",
  draft: "文",
  annotation: "批",
  story_fact: "忆",
  memory: "忆",
  review: "评",
  report: "报",
};

export function agentArtifactSeal(artifactType: string) {
  return AGENT_ARTIFACT_SEALS[artifactType] ?? "册";
}

/**
 * Appends a page of sequence-ordered events to the accumulated replay, dropping
 * duplicates by sequence so a reconnect (overlap between the last cursor and the
 * replayed page) never renders an event twice.
 */
export function mergeAgentEvents(current: AgentRunEvent[], incoming: AgentRunEvent[]) {
  if (!incoming.length) return current;
  const seen = new Set(current.map(event => event.sequence));
  const merged = [...current, ...incoming.filter(event => !seen.has(event.sequence))];
  return merged.length === current.length ? current : merged;
}

export function agentEventCursor(events: AgentRunEvent[]) {
  return events.reduce((max, event) => Math.max(max, event.sequence), 0);
}
