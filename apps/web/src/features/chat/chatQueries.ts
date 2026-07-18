import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { compareBranches, editMessageV2, forkConversation, getBranchTree, listBranchesV2, listMessages, listV2Models, regenerateReply, retryMessage, sendMessage, stopMessage, subscribeConversationEvents, type ChatMessage as ApiChatMessage } from "../../lib/api/client";
import { useChatStore } from "./chatStore";
import type { SendOptions } from "./chatTypes";

function newClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function messageKeys(conversationId: string, branchId: string) {
  return ["conversations", conversationId, "branches", branchId, "messages"] as const;
}

export function useMessages(conversationId: string, branchId: string) {
  return useQuery({ queryKey: messageKeys(conversationId, branchId), queryFn: () => listMessages(conversationId, branchId), enabled: Boolean(conversationId && branchId) });
}

export function useSendMessage() {
  return useMutation({
    mutationFn: ({ conversationId, branchId, content, options }: { conversationId: string; branchId: string; content: string; options?: SendOptions }) =>
      sendMessage(conversationId, { branch_id: branchId, content, client_request_id: newClientId(), provider: options?.provider, model: options?.model }),
  });
}

export function useStopMessage() {
  return useMutation({ mutationFn: (messageId: string) => stopMessage(messageId) });
}

export function useRetryMessage() {
  return useMutation({
    mutationFn: ({ messageId, options }: { messageId: string; options?: SendOptions }) => retryMessage(messageId, { provider: options?.provider, model: options?.model }),
  });
}

export function useModelCatalog() {
  return useQuery({ queryKey: ["v2", "models"], queryFn: () => listV2Models(), staleTime: 300_000, retry: false });
}

export function branchKeys(conversationId: string) {
  return ["conversations", conversationId, "branches"] as const;
}

export function branchTreeKeys(conversationId: string, branchId: string) {
  return ["conversations", conversationId, "branches", branchId, "tree"] as const;
}

export function useBranches(conversationId: string, includeArchived = false) {
  return useQuery({ queryKey: [...branchKeys(conversationId), { includeArchived }], queryFn: () => listBranchesV2(conversationId, { includeArchived }), enabled: Boolean(conversationId) });
}

export function useBranchTree(conversationId: string, branchId: string) {
  return useQuery({ queryKey: branchTreeKeys(conversationId, branchId), queryFn: () => getBranchTree(conversationId, branchId), enabled: Boolean(conversationId && branchId) });
}

export function useCompareBranches(conversationId: string, left: string, right: string | null) {
  return useQuery({ queryKey: [...branchKeys(conversationId), "compare", left, right], queryFn: () => compareBranches(conversationId, left, right as string), enabled: Boolean(conversationId && left && right) });
}

export function useEditMessage() {
  return useMutation({
    mutationFn: ({ conversationId, messageId, content }: { conversationId: string; messageId: string; content: string }) => editMessageV2(conversationId, messageId, content),
  });
}

export function useRegenerate() {
  return useMutation({
    mutationFn: ({ conversationId, messageId, options }: { conversationId: string; messageId: string; options?: SendOptions }) => regenerateReply(conversationId, messageId, { provider: options?.provider, model: options?.model }),
  });
}

export function useChatConversation(conversationId: string, branchId: string) {
  const queryClient = useQueryClient();
  const key = messageKeys(conversationId, branchId);
  const messagesQuery = useMessages(conversationId, branchId);
  const sendMutation = useSendMessage();
  const stopMutation = useStopMessage();
  const retryMutation = useRetryMessage();
  const setStreaming = useChatStore(state => state.setStreaming);

  const appendLocal = (...messages: ApiChatMessage[]) => queryClient.setQueryData<ApiChatMessage[]>(key, (old = []) => [...old, ...messages]);
  const patchLocal = (id: string, patch: (message: ApiChatMessage) => ApiChatMessage) => queryClient.setQueryData<ApiChatMessage[]>(key, (old = []) => old.map(message => message.id === id ? patch(message) : message));

  const send = async (text: string, options?: SendOptions) => {
    const content = text.trim();
    if (!content) return;
    const placeholderId = newClientId();
    appendLocal({ id: newClientId(), role: "user", content, status: "COMPLETED" }, { id: placeholderId, role: "assistant", content: "", status: "PENDING" });
    setStreaming(true);
    const close = subscribeConversationEvents(conversationId, event => {
      if (event.event === "content.delta" && event.message_id) patchLocal(event.message_id, message => ({ ...message, content: `${message.content}${event.text ?? ""}`, status: "STREAMING" }));
      if (event.event === "message.completed" || event.event === "message.failed") void queryClient.invalidateQueries({ queryKey: key });
    });
    try {
      const queued = await sendMutation.mutateAsync({ conversationId, branchId, content, options });
      patchLocal(placeholderId, message => ({ ...message, id: queued.assistant_message_id }));
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const fresh = await queryClient.fetchQuery({ queryKey: key, queryFn: () => listMessages(conversationId, branchId) });
        const assistant = [...fresh].reverse().find(message => message.role === "assistant");
        if (assistant && ["COMPLETED", "FAILED", "PARTIAL", "CANCELLED"].includes(assistant.status)) break;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    } catch {
      patchLocal(placeholderId, message => ({ ...message, status: "FAILED" }));
    } finally {
      close();
      setStreaming(false);
    }
  };

  const stop = () => {
    const active = [...(messagesQuery.data ?? [])].reverse().find(message => message.role === "assistant" && ["PENDING", "STREAMING", "PARTIAL"].includes(message.status));
    if (active) stopMutation.mutate(active.id, { onSettled: () => void queryClient.invalidateQueries({ queryKey: key }) });
  };

  const retry = (messageId: string, options?: SendOptions) => {
    patchLocal(messageId, message => ({ ...message, status: "STREAMING" }));
    retryMutation.mutate({ messageId, options }, { onSettled: () => void queryClient.invalidateQueries({ queryKey: key }) });
  };

  const fork = async (name?: string) => {
    const latest = messagesQuery.data ?? [];
    const point = [...latest].reverse().find(message => message.role === "assistant") ?? latest.at(-1);
    if (!point) return undefined;
    return forkConversation(conversationId, point.id, name ?? `Alternative ${new Date().toLocaleTimeString()}`);
  };

  return { messagesQuery, send, stop, retry, fork };
}
