export type ChatRole = "user" | "assistant" | "tool";
export type ChatStatus = "completed" | "streaming" | "pending" | "failed" | "cancelled";
export type ChatMessage = { id: string; role: ChatRole; content: string; status: ChatStatus; branchCount?: number };
