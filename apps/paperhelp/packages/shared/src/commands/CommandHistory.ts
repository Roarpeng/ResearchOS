import type { Command } from "./Command";

export type CommandPersistFn = (action: string, payload: unknown) => void;

export class CommandHistory {
  private undoStack: Command[] = [];
  private redoStack: Command[] = [];
  private persistFn?: CommandPersistFn;
  private listeners = new Set<() => void>();

  setPersist(fn: CommandPersistFn | undefined): void {
    this.persistFn = fn;
  }

  execute(command: Command): void {
    command.execute();
    this.pushExecuted(command);
  }

  /** Record a command that was already applied (e.g. Tiptap-driven insert). */
  record(command: Command): void {
    this.pushExecuted(command);
  }

  undo(): boolean {
    const command = this.undoStack.pop();
    if (!command) {
      return false;
    }

    command.undo();
    this.redoStack.push(command);
    this.notify();
    return true;
  }

  redo(): boolean {
    const command = this.redoStack.pop();
    if (!command) {
      return false;
    }

    command.execute();
    this.undoStack.push(command);
    this.notify();
    return true;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
    this.notify();
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private pushExecuted(command: Command): void {
    this.undoStack.push(command);
    this.redoStack = [];
    this.persistFn?.(command.name, command.getPayload?.() ?? {});
    this.notify();
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}
