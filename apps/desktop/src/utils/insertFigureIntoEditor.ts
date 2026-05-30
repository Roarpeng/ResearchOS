import { buildFigureFromAssets } from "@paperhelp/figure";
import {
  InsertBlockCommand,
  useAssetStore,
  useCommandHistoryStore,
  useFigureStore,
  type EditorCommands,
} from "@paperhelp/shared";

export interface InsertFigureResult {
  figureId: string;
  inserted: boolean;
}

/**
 * Creates a figure from current asset store entries (if any) and inserts a Figure block.
 */
export function insertFigureIntoEditor(
  editorCommands: EditorCommands | null,
): InsertFigureResult | null {
  if (!editorCommands) {
    return null;
  }

  const assets = Object.values(useAssetStore.getState().assets);
  const addFigure = useFigureStore.getState().addFigure;
  const recordCommand = useCommandHistoryStore.getState().record;

  const prevJSON = editorCommands.getJSON();

  const figure =
    assets.length > 0
      ? buildFigureFromAssets(assets)
      : buildFigureFromAssets([], "Untitled Figure");

  addFigure(figure);
  editorCommands.focus();
  editorCommands.insertFigure(figure.id);

  const nextJSON = editorCommands.getJSON();
  recordCommand(
    new InsertBlockCommand(prevJSON, nextJSON, (json) => {
      editorCommands.setContent(json);
    }),
  );

  return { figureId: figure.id, inserted: true };
}
