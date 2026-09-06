/** Grid row pattern: each entry is the number of columns in that row. */
export interface LayoutPreset {
  id: string;
  label: string;
  rows: number[];
}

export const LAYOUT_PRESETS: Record<string, LayoutPreset> = {
  "1x1": { id: "1x1", label: "1×1", rows: [1] },
  "1x2": { id: "1x2", label: "1×2", rows: [2] },
  "1x3": { id: "1x3", label: "1×3", rows: [3] },
  "2+1": { id: "2+1", label: "2+1", rows: [2, 1] },
  "2x2": { id: "2x2", label: "2×2", rows: [2, 2] },
  "2x3": { id: "2x3", label: "2×3", rows: [3, 3] },
  "3x3": { id: "3x3", label: "3×3", rows: [3, 3, 3] },
};

export function buildFallbackPreset(count: number): LayoutPreset {
  const cols = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / cols);
  const rowPattern: number[] = [];

  for (let row = 0; row < rows; row += 1) {
    const remaining = count - row * cols;
    rowPattern.push(Math.min(cols, remaining));
  }

  return {
    id: "auto",
    label: `${rows}×${cols}`,
    rows: rowPattern,
  };
}
