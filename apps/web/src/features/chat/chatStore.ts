import { create } from "zustand";

type ChatUiState = {
  inspectorOpen: boolean;
  commandPaletteOpen: boolean;
  streaming: boolean;
  toggleInspector: () => void;
  setInspectorOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setStreaming: (streaming: boolean) => void;
};

export const useChatStore = create<ChatUiState>()(set => ({
  inspectorOpen: false,
  commandPaletteOpen: false,
  streaming: false,
  toggleInspector: () => set(state => ({ inspectorOpen: !state.inspectorOpen })),
  setInspectorOpen: inspectorOpen => set({ inspectorOpen }),
  setCommandPaletteOpen: commandPaletteOpen => set({ commandPaletteOpen }),
  setStreaming: streaming => set({ streaming }),
}));
