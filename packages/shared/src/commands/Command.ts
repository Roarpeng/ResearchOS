export interface Command {
  readonly name: string;
  execute(): void;
  undo(): void;
  /** Optional payload for history persistence. */
  getPayload?(): unknown;
}
