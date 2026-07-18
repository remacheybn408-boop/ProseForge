import { useMemo } from "react";
import { PaperPanel } from "../../components/ink/Ink";
import { WorkspaceSplit } from "../../components/layout/WorkspaceSplit";
import type { BranchCompareResult, BranchInfo, BranchTreeMessage } from "../../lib/api/client";
import { BranchCompareView, type ComparePrefixMessage } from "../branches/BranchCompareView";
import { BranchTreeView } from "../branches/BranchTreeView";
import { ChatComposer } from "./ChatComposer";
import { MessageActions } from "./MessageActions";
import { MessageList } from "./MessageList";
import { applyCandidateVisibility, groupAssistantCandidates, nextCandidateId } from "./candidates";
import { useChatStore } from "./chatStore";
import type { ChatMessage, SendOptions } from "./chatTypes";

export type CompareViewData = {
  leftLabel: string;
  rightLabel: string;
  result: BranchCompareResult;
  prefix: ComparePrefixMessage[];
};

export function ChatPage({ conversationId, branchId, messages = [], error, notice, branches, treeMessages, compare, showArchived, onSend = () => undefined, onStop, onRetry, onFork, onReload, onSelectBranch, onCompareBranch, onEditMessage, onRegenerateMessage, onToggleArchived }: {
  conversationId: string;
  branchId: string;
  messages?: ChatMessage[];
  error?: string;
  notice?: string;
  branches?: BranchInfo[];
  treeMessages?: BranchTreeMessage[];
  compare?: CompareViewData;
  showArchived?: boolean;
  onSend?: (text: string, options?: SendOptions) => void;
  onStop?: () => void;
  onRetry?: (message: ChatMessage) => void;
  onFork?: () => void;
  onReload?: () => void;
  onSelectBranch?: (branchId: string) => void;
  onCompareBranch?: (branchId: string) => void;
  onEditMessage?: (message: ChatMessage, content: string) => void;
  onRegenerateMessage?: (message: ChatMessage) => void;
  onToggleArchived?: () => void;
}) {
  const generating = messages.some(message => message.status === "streaming" || message.status === "pending");
  const selection = useChatStore(state => state.visibleCandidates);
  const setVisibleCandidate = useChatStore(state => state.setVisibleCandidate);
  const groups = useMemo(() => groupAssistantCandidates(treeMessages ?? []), [treeMessages]);
  const { visible, candidateInfo } = useMemo(() => applyCandidateVisibility(messages, groups, selection), [messages, groups, selection]);
  const branchIndex = branches?.findIndex(branch => branch.id === branchId) ?? -1;
  const activeBranch = branchIndex >= 0 ? branches?.[branchIndex] : undefined;

  const renderActions = (message: ChatMessage) => {
    const candidate = candidateInfo.get(message.id);
    const canEdit = message.role === "user" && Boolean(onEditMessage);
    const canRegenerate = message.role === "assistant" && Boolean(onRegenerateMessage);
    if (!candidate && !canEdit && !canRegenerate) return null;
    return <MessageActions
      message={message}
      candidateIndex={candidate?.index}
      candidateCount={candidate?.count}
      onSwitchCandidate={candidate ? direction => {
        const next = nextCandidateId(groups, selection, candidate.parentMessageId, direction);
        if (next) setVisibleCandidate(candidate.parentMessageId, next);
      } : undefined}
      onEdit={canEdit ? content => onEditMessage?.(message, content) : undefined}
      onRegenerate={canRegenerate ? () => onRegenerateMessage?.(message) : undefined}
    />;
  };

  const inspector = <PaperPanel>
    <h3>Conversation</h3>
    <p>{visible.length} messages</p>
    {branches && <BranchTreeView branches={branches} activeBranchId={branchId} showArchived={showArchived} onSelect={onSelectBranch} onCompare={onCompareBranch} onToggleArchived={onToggleArchived} />}
    {compare && <BranchCompareView result={compare.result} leftLabel={compare.leftLabel} rightLabel={compare.rightLabel} prefix={compare.prefix} />}
  </PaperPanel>;

  return <WorkspaceSplit inspector={inspector}>
    <section className="chat-page-v2">
      <header>
        <span className="eyebrow">WRITING COMPANION</span>
        <span className="branch-indicator">{activeBranch?.name ?? `Branch ${branchId}`}</span>
        {branches && branches.length > 1 && branchIndex >= 0 && <span className="branch-counter">‹ {branchIndex + 1}/{branches.length} ›</span>}
        {onFork && <button type="button" onClick={onFork} disabled={!messages.some(message => message.role === "assistant")}>Fork branch</button>}
      </header>
      {notice && <p className="chat-notice" aria-live="polite">{notice}</p>}
      {error ? <div className="chat-error-card" role="alert"><p>We could not load this conversation.</p><code>{error}</code>{onReload && <button type="button" onClick={onReload}>Retry</button>}</div> : <MessageList messages={visible} onRetry={onRetry} renderActions={renderActions} />}
      <ChatComposer conversationId={conversationId} branchId={branchId} generating={generating} onSend={onSend} onStop={onStop} />
    </section>
  </WorkspaceSplit>;
}
