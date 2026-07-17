export function chatDraftKey(conversationId: string, branchId: string): string {
  return `proseforge:draft:${conversationId}:${branchId}`;
}

export function loadChatDraft(conversationId: string, branchId: string): string {
  return window.localStorage.getItem(chatDraftKey(conversationId, branchId)) ?? "";
}

export function saveChatDraft(conversationId: string, branchId: string, value: string): void {
  window.localStorage.setItem(chatDraftKey(conversationId, branchId), value);
}
