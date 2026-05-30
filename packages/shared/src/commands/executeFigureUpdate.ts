import {
  UpdateFigureCommand,
  buildFigurePatchSnapshot,
  resolveFigurePatch,
} from "../commands/UpdateFigureCommand";
import type { Figure } from "../types/figure";
import { useCommandHistoryStore } from "../stores/commandHistoryStore";
import { useFigureStore } from "../stores/figureStore";

export function executeFigureUpdate(
  figureId: string,
  patch: Partial<Figure> | ((figure: Figure) => Partial<Figure>),
): void {
  const figure = useFigureStore.getState().figures[figureId];
  if (!figure) {
    return;
  }

  const nextPatch = resolveFigurePatch(figure, patch);
  const prevPatch = buildFigurePatchSnapshot(figure, nextPatch);
  useCommandHistoryStore
    .getState()
    .execute(new UpdateFigureCommand(figureId, prevPatch, nextPatch));
}
