import type { Asset, Layout, LayoutItem } from "@paperhelp/shared";
import { snapToGrid } from "../utils/grid";
import type { LayoutPreset } from "./presets";

export const OUTER_PADDING = 40;
export const CELL_GAP = 40;
export const MIN_STAGE_WIDTH = 800;
export const MIN_STAGE_HEIGHT = 600;
export const MAX_CELL_SIZE = 280;
export const DEFAULT_GRID_SIZE = 20;

function scaleAssetDimensions(
  asset: Asset,
  maxCellSize: number = MAX_CELL_SIZE,
): { width: number; height: number } {
  const scale = Math.min(maxCellSize / asset.width, maxCellSize / asset.height, 1);
  return {
    width: Math.round(asset.width * scale),
    height: Math.round(asset.height * scale),
  };
}

export interface SuggestLayoutOptions {
  gridSize?: number;
  maxCellSize?: number;
}

/** Compute symmetric equal-margin coordinates for a preset grid. */
export function suggestLayout(
  assets: Asset[],
  preset: LayoutPreset,
  options: SuggestLayoutOptions = {},
): Layout {
  const gridSize = options.gridSize ?? DEFAULT_GRID_SIZE;
  const maxCellSize = options.maxCellSize ?? MAX_CELL_SIZE;

  if (assets.length === 0) {
    return {
      stageWidth: MIN_STAGE_WIDTH,
      stageHeight: MIN_STAGE_HEIGHT,
      gridSize,
      items: [],
    };
  }

  const scaled = assets.map((asset) => ({
    asset,
    ...scaleAssetDimensions(asset, maxCellSize),
  }));

  const cellWidth = Math.max(...scaled.map((entry) => entry.width), maxCellSize);
  const cellHeight = Math.max(...scaled.map((entry) => entry.height), maxCellSize);
  const maxCols = Math.max(...preset.rows, 1);
  const numRows = preset.rows.length;

  const contentWidth = maxCols * cellWidth + (maxCols - 1) * CELL_GAP;
  const contentHeight = numRows * cellHeight + (numRows - 1) * CELL_GAP;
  const stageWidth = Math.max(MIN_STAGE_WIDTH, contentWidth + OUTER_PADDING * 2);
  const stageHeight = Math.max(MIN_STAGE_HEIGHT, contentHeight + OUTER_PADDING * 2);

  const offsetX =
    OUTER_PADDING + (stageWidth - OUTER_PADDING * 2 - contentWidth) / 2;
  const offsetY =
    OUTER_PADDING + (stageHeight - OUTER_PADDING * 2 - contentHeight) / 2;

  const items: LayoutItem[] = [];
  let assetIndex = 0;

  for (let row = 0; row < preset.rows.length; row += 1) {
    const colsInRow = preset.rows[row];
    const rowWidth = colsInRow * cellWidth + (colsInRow - 1) * CELL_GAP;
    const rowStartX = offsetX + (contentWidth - rowWidth) / 2;

    for (let col = 0; col < colsInRow && assetIndex < scaled.length; col += 1) {
      const { asset, width, height } = scaled[assetIndex];
      const cellX = rowStartX + col * (cellWidth + CELL_GAP);
      const cellY = offsetY + row * (cellHeight + CELL_GAP);

      items.push({
        assetId: asset.id,
        x: snapToGrid(cellX + (cellWidth - width) / 2, gridSize),
        y: snapToGrid(cellY + (cellHeight - height) / 2, gridSize),
        width,
        height,
      });
      assetIndex += 1;
    }
  }

  return {
    stageWidth: snapToGrid(stageWidth, gridSize),
    stageHeight: snapToGrid(stageHeight, gridSize),
    gridSize,
    items,
  };
}
