import { create } from "zustand";

export type Theme = "light" | "dark" | "system";

export interface UiState {
  theme: Theme;
  openDialogs: Record<string, boolean>;
}

export interface UiActions {
  setTheme: (theme: Theme) => void;
  openDialog: (dialogId: string) => void;
  closeDialog: (dialogId: string) => void;
  toggleDialog: (dialogId: string) => void;
  isDialogOpen: (dialogId: string) => boolean;
}

export type UiStore = UiState & UiActions;

const initialUiState: UiState = {
  theme: "system",
  openDialogs: {},
};

export const useUiStore = create<UiStore>((set, get) => ({
  ...initialUiState,
  setTheme: (theme) => set({ theme }),
  openDialog: (dialogId) =>
    set((state) => ({
      openDialogs: { ...state.openDialogs, [dialogId]: true },
    })),
  closeDialog: (dialogId) =>
    set((state) => ({
      openDialogs: { ...state.openDialogs, [dialogId]: false },
    })),
  toggleDialog: (dialogId) => {
    const isOpen = get().openDialogs[dialogId] ?? false;
    set((state) => ({
      openDialogs: { ...state.openDialogs, [dialogId]: !isOpen },
    }));
  },
  isDialogOpen: (dialogId) => get().openDialogs[dialogId] ?? false,
}));
