import type { Command } from "./Command";

export class InsertBlockCommand implements Command {
  readonly name = "insertBlock";

  constructor(
    private readonly prevJSON: unknown,
    private readonly nextJSON: unknown,
    private readonly applyJSON: (json: unknown) => void,
  ) {}

  execute(): void {
    this.applyJSON(this.nextJSON);
  }

  undo(): void {
    this.applyJSON(this.prevJSON);
  }

  getPayload(): unknown {
    return { prevJSON: this.prevJSON, nextJSON: this.nextJSON };
  }
}
