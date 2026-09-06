import { useFigureStore } from "../stores/figureStore";
import type { Figure } from "../types/figure";
import type { Command } from "./Command";

export class UpdateFigureCommand implements Command {
  readonly name = "updateFigure";

  constructor(
    private readonly figureId: string,
    private readonly prevPatch: Partial<Figure>,
    private readonly nextPatch: Partial<Figure>,
  ) {}

  execute(): void {
    useFigureStore.getState().updateFigure(this.figureId, this.nextPatch);
  }

  undo(): void {
    useFigureStore.getState().updateFigure(this.figureId, this.prevPatch);
  }

  getPayload(): unknown {
    return {
      figureId: this.figureId,
      prev: this.prevPatch,
      next: this.nextPatch,
    };
  }
}

export function buildFigurePatchSnapshot(
  figure: Figure,
  patch: Partial<Figure>,
): Partial<Figure> {
  const prev: Record<string, unknown> = {};

  for (const key of Object.keys(patch) as (keyof Figure)[]) {
    const value = figure[key];
    prev[key] =
      value !== undefined && typeof value === "object" && value !== null
        ? structuredClone(value)
        : value;
  }

  return prev as Partial<Figure>;
}

export function resolveFigurePatch(
  figure: Figure,
  patch: Partial<Figure> | ((figure: Figure) => Partial<Figure>),
): Partial<Figure> {
  return typeof patch === "function" ? patch(figure) : patch;
}
