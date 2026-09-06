import { useEditorStore } from "../stores/editorStore";
import type { Command } from "./Command";

export class UpdateDocumentTitleCommand implements Command {
  readonly name = "updateDocumentTitle";

  constructor(
    private readonly prevTitle: string,
    private readonly nextTitle: string,
  ) {}

  execute(): void {
    useEditorStore.getState().setTitle(this.nextTitle);
  }

  undo(): void {
    useEditorStore.getState().setTitle(this.prevTitle);
  }

  getPayload(): unknown {
    return { prevTitle: this.prevTitle, nextTitle: this.nextTitle };
  }
}
