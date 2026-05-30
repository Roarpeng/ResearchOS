import type { Asset, Figure, Layout } from "@paperhelp/shared";
import { snapToGrid } from "../utils/grid";
import { detectCount } from "./detectCount";
import type { LayoutPreset } from "./presets";
import { suggestLayout, type SuggestLayoutOptions } from "./suggestLayout";

function repositionScaleBar(figure: Figure, layout: Layout): Figure["scaleBar"] {
  if (!figure.scaleBar) {
    return undefined;
  }

  return {
    ...figure.scaleBar,
    x: snapToGrid(layout.stageWidth - 220, layout.gridSize),
    y: snapToGrid(layout.stageHeight - 56, layout.gridSize),
  };
}

/** Write a computed layout onto a figure (does not mutate). */
export function applyLayout(figure: Figure, layout: Layout): Partial<Figure> {
  return {
    layout,
    scaleBar: repositionScaleBar(figure, layout),
  };
}

export interface AutoLayoutOptions extends SuggestLayoutOptions {
  preset?: LayoutPreset;
}

/** Detect preset, suggest coordinates, and return the figure patch. */
export function applyAutoLayout(
  figure: Figure,
  assets: Asset[],
  options: AutoLayoutOptions = {},
): Partial<Figure> {
  const preset = options.preset ?? detectCount(assets.length);
  const layout = suggestLayout(assets, preset, {
    gridSize: options.gridSize ?? figure.layout.gridSize,
    maxCellSize: options.maxCellSize,
  });
  return applyLayout(figure, layout);
}

/** Detect → Suggest (preview only, no commit). */
export function suggestAutoLayout(
  figure: Figure,
  assets: Asset[],
  options: AutoLayoutOptions = {},
): Layout {
  const preset = options.preset ?? detectCount(assets.length);
  return suggestLayout(assets, preset, {
    gridSize: options.gridSize ?? figure.layout.gridSize,
    maxCellSize: options.maxCellSize,
  });
}
