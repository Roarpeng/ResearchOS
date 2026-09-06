/**
 * Auto-layout engine ported from PaperHelp `packages/figure/src/layout/*`
 * (self-contained, no Tauri/shared deps). Symmetric equal-margin grid.
 */

export interface LayoutPreset {
  id: string;
  label: string;
  rows: number[];
}

export interface LayoutAsset {
  id: string;
  width: number;
  height: number;
}

export interface LayoutItem {
  assetId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface FigureLayout {
  stageWidth: number;
  stageHeight: number;
  gridSize: number;
  items: LayoutItem[];
}

export const DEFAULT_GRID_SIZE = 20;
export const OUTER_PADDING = 40;
export const CELL_GAP = 40;
export const MIN_STAGE_WIDTH = 800;
export const MIN_STAGE_HEIGHT = 600;
export const MAX_CELL_SIZE = 280;

export const LAYOUT_PRESETS: Record<string, LayoutPreset> = {
  "1x1": { id: "1x1", label: "1×1", rows: [1] },
  "1x2": { id: "1x2", label: "1×2", rows: [2] },
  "1x3": { id: "1x3", label: "1×3", rows: [3] },
  "2+1": { id: "2+1", label: "2+1", rows: [2, 1] },
  "2x2": { id: "2x2", label: "2×2", rows: [2, 2] },
  "2x3": { id: "2x3", label: "2×3", rows: [3, 3] },
  "3x3": { id: "3x3", label: "3×3", rows: [3, 3, 3] },
};

export function snapToGrid(value: number, gridSize: number = DEFAULT_GRID_SIZE): number {
  return Math.round(value / gridSize) * gridSize;
}

export function buildFallbackPreset(count: number): LayoutPreset {
  const cols = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / cols);
  const rowPattern: number[] = [];
  for (let row = 0; row < rows; row += 1) {
    const remaining = count - row * cols;
    rowPattern.push(Math.min(cols, remaining));
  }
  return { id: "auto", label: `${rows}×${cols}`, rows: rowPattern };
}

const COUNT_PRESET_MAP: Record<number, LayoutPreset> = {
  1: LAYOUT_PRESETS["1x1"],
  2: LAYOUT_PRESETS["1x2"],
  3: LAYOUT_PRESETS["1x3"],
  4: LAYOUT_PRESETS["2x2"],
  6: LAYOUT_PRESETS["2x3"],
  9: LAYOUT_PRESETS["3x3"],
};

export function detectCount(count: number): LayoutPreset {
  if (count <= 0) return LAYOUT_PRESETS["1x1"];
  return COUNT_PRESET_MAP[count] ?? buildFallbackPreset(count);
}

export function detectCountAlternatives(count: number): LayoutPreset[] {
  const primary = detectCount(count);
  return count === 3 ? [primary, LAYOUT_PRESETS["2+1"]] : [primary];
}

function scaleAssetDimensions(asset: LayoutAsset, maxCellSize = MAX_CELL_SIZE) {
  const scale = Math.min(maxCellSize / asset.width, maxCellSize / asset.height, 1);
  return { width: Math.round(asset.width * scale), height: Math.round(asset.height * scale) };
}

export function suggestLayout(
  assets: LayoutAsset[],
  preset: LayoutPreset,
  gridSize: number = DEFAULT_GRID_SIZE,
  maxCellSize: number = MAX_CELL_SIZE,
): FigureLayout {
  if (assets.length === 0) {
    return { stageWidth: MIN_STAGE_WIDTH, stageHeight: MIN_STAGE_HEIGHT, gridSize, items: [] };
  }
  const scaled = assets.map((asset) => ({ asset, ...scaleAssetDimensions(asset, maxCellSize) }));
  const cellWidth = Math.max(...scaled.map((e) => e.width), maxCellSize);
  const cellHeight = Math.max(...scaled.map((e) => e.height), maxCellSize);
  const maxCols = Math.max(...preset.rows, 1);
  const numRows = preset.rows.length;

  const contentWidth = maxCols * cellWidth + (maxCols - 1) * CELL_GAP;
  const contentHeight = numRows * cellHeight + (numRows - 1) * CELL_GAP;
  const stageWidth = Math.max(MIN_STAGE_WIDTH, contentWidth + OUTER_PADDING * 2);
  const stageHeight = Math.max(MIN_STAGE_HEIGHT, contentHeight + OUTER_PADDING * 2);
  const offsetX = OUTER_PADDING + (stageWidth - OUTER_PADDING * 2 - contentWidth) / 2;
  const offsetY = OUTER_PADDING + (stageHeight - OUTER_PADDING * 2 - contentHeight) / 2;

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

/** Detect → Suggest (auto-layout entrypoint). */
export function autoLayout(assets: LayoutAsset[]): FigureLayout {
  return suggestLayout(assets, detectCount(assets.length));
}
