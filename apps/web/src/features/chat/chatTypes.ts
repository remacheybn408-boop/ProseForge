import type { ChatMessage as ApiChatMessage } from "../../lib/api/client";
import type { ReasoningLevel } from "../models/modelCapabilities";

export type ChatRole = "user" | "assistant" | "tool";
export type ChatStatus = "completed" | "streaming" | "pending" | "failed" | "cancelled";
export type ChatMessage = { id: string; role: ChatRole; content: string; status: ChatStatus; branchIndex?: number; branchCount?: number };
export type SendOptions = { provider?: string; model?: string; reasoning?: ReasoningLevel };

const API_STATUSES: ChatStatus[] = ["completed", "streaming", "pending", "failed", "cancelled"];

export function toChatMessage(message: ApiChatMessage): ChatMessage {
  const status = message.status.toLowerCase();
  const mapped: ChatStatus = status === "partial" ? "failed" : (API_STATUSES.find(value => value === status) ?? "completed");
  return { id: message.id, role: message.role === "assistant" ? "assistant" : "user", content: message.content, status: mapped };
}
