import { create } from "zustand";
import { CommandHistory } from "../commands/CommandHistory";
import type { Command } from "../commands/Command";
import type { CommandPersistFn } from "../commands/CommandHistory";
import { useEditorStore } from "./editorStore";

const history = new CommandHistory();

interface CommandHistoryStore {
  revision: number;
  canUndo: boolean;
  canRedo: boolean;
  execute: (command: Command) => void;
  record: (command: Command) => void;
  undo: () => void;
  redo: () => void;
  clear: () => void;
  setPersist: (fn: CommandPersistFn | undefined) => void;
}

function syncFromHistory(
  set: (partial: Pick<CommandHistoryStore, "revision" | "canUndo" | "canRedo">) => void,
): void {
  set({
    revision: Date.now(),
    canUndo: history.canUndo,
    canRedo: history.canRedo,
  });
}

history.subscribe(() => {
  syncFromHistory(useCommandHistoryStore.setState);
});

export const useCommandHistoryStore = create<CommandHistoryStore>(() => ({
  revision: 0,
  canUndo: false,
  canRedo: false,

  execute: (command) => {
    history.execute(command);
    useEditorStore.getState().setDirty(true);
  },

  record: (command) => {
    history.record(command);
    useEditorStore.getState().setDirty(true);
  },

  undo: () => {
    if (!history.undo()) {
      return;
    }
    useEditorStore.getState().setDirty(true);
  },

  redo: () => {
    if (!history.redo()) {
      return;
    }
    useEditorStore.getState().setDirty(true);
  },

  clear: () => {
    history.clear();
  },

  setPersist: (fn) => {
    history.setPersist(fn);
  },
}));
