import { buildFigureFromAssets } from "@paperhelp/figure";
import {
  useAssetStore,
  useEditorStore,
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
  const setDirty = useEditorStore.getState().setDirty;

  const figure =
    assets.length > 0
      ? buildFigureFromAssets(assets)
      : buildFigureFromAssets([], "Untitled Figure");

  addFigure(figure);
  editorCommands.focus();
  editorCommands.insertFigure(figure.id);
  setDirty(true);

  return { figureId: figure.id, inserted: true };
}
