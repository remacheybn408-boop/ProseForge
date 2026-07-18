import { create } from "zustand";

type ChatUiState = {
  inspectorOpen: boolean;
  commandPaletteOpen: boolean;
  streaming: boolean;
  /** parentMessageId -> visible candidate message id (regenerate siblings). */
  visibleCandidates: Record<string, string>;
  toggleInspector: () => void;
  setInspectorOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setVisibleCandidate: (parentMessageId: string, messageId: string) => void;
  clearVisibleCandidates: () => void;
};

export const useChatStore = create<ChatUiState>()(set => ({
  inspectorOpen: false,
  commandPaletteOpen: false,
  streaming: false,
  visibleCandidates: {},
  toggleInspector: () => set(state => ({ inspectorOpen: !state.inspectorOpen })),
  setInspectorOpen: inspectorOpen => set({ inspectorOpen }),
  setCommandPaletteOpen: commandPaletteOpen => set({ commandPaletteOpen }),
  setStreaming: streaming => set({ streaming }),
  setVisibleCandidate: (parentMessageId, messageId) => set(state => ({ visibleCandidates: { ...state.visibleCandidates, [parentMessageId]: messageId } })),
  clearVisibleCandidates: () => set({ visibleCandidates: {} }),
}));
