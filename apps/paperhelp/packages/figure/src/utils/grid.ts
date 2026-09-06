export const DEFAULT_GRID_SIZE = 20;

export function snapToGrid(value: number, gridSize: number = DEFAULT_GRID_SIZE): number {
  return Math.round(value / gridSize) * gridSize;
}
