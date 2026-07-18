import type { BranchTreeMessage } from "../../lib/api/client";
import type { ChatMessage } from "./chatTypes";

export type CandidateInfo = { index: number; count: number; parentMessageId: string };

/** Group assistant messages that are regenerate candidates of the same prompt. */
export function groupAssistantCandidates(treeMessages: BranchTreeMessage[]): Map<string, BranchTreeMessage[]> {
  const groups = new Map<string, BranchTreeMessage[]>();
  for (const message of treeMessages) {
    if (message.role !== "assistant" || !message.parent_message_id) continue;
    const siblings = groups.get(message.parent_message_id) ?? [];
    siblings.push(message);
    groups.set(message.parent_message_id, siblings);
  }
  for (const [parentMessageId, siblings] of groups) {
    if (siblings.length < 2) {
      groups.delete(parentMessageId);
    } else {
      siblings.sort((a, b) => (a.generation_attempt ?? 1) - (b.generation_attempt ?? 1));
    }
  }
  return groups;
}

/** Keep only the selected candidate per sibling group; default to the latest attempt. */
export function applyCandidateVisibility(
  messages: ChatMessage[],
  groups: Map<string, BranchTreeMessage[]>,
  selection: Record<string, string>,
): { visible: ChatMessage[]; candidateInfo: Map<string, CandidateInfo> } {
  const byId = new Map<string, { parentMessageId: string; siblings: BranchTreeMessage[] }>();
  for (const [parentMessageId, siblings] of groups) {
    for (const sibling of siblings) byId.set(sibling.id, { parentMessageId, siblings });
  }
  const visible: ChatMessage[] = [];
  const candidateInfo = new Map<string, CandidateInfo>();
  for (const message of messages) {
    const group = byId.get(message.id);
    if (!group) {
      visible.push(message);
      continue;
    }
    const selectedId = selection[group.parentMessageId];
    const selected = group.siblings.find(sibling => sibling.id === selectedId) ?? group.siblings[group.siblings.length - 1];
    if (message.id !== selected.id) continue;
    candidateInfo.set(message.id, { index: group.siblings.indexOf(selected) + 1, count: group.siblings.length, parentMessageId: group.parentMessageId });
    visible.push(message);
  }
  return { visible, candidateInfo };
}

/** Wrap-around sibling navigation for the ‹ n/m › switcher. */
export function nextCandidateId(groups: Map<string, BranchTreeMessage[]>, selection: Record<string, string>, parentMessageId: string, direction: 1 | -1): string | undefined {
  const siblings = groups.get(parentMessageId);
  if (!siblings || siblings.length === 0) return undefined;
  const currentIndex = siblings.findIndex(sibling => sibling.id === selection[parentMessageId]);
  const index = currentIndex >= 0 ? currentIndex : siblings.length - 1;
  return siblings[(index + direction + siblings.length) % siblings.length].id;
}
