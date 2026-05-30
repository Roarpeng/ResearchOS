export { importImages } from "./asset/importAsset";
export type { ReadImageAssetResult } from "./asset/types";
export { FigureStudio, type FigureStudioProps } from "./FigureStudio";
export { applyAutoLayout, applyLayout, suggestAutoLayout } from "./layout/applyLayout";
export { detectCount, detectCountAlternatives } from "./layout/detectCount";
export { buildFallbackPreset, LAYOUT_PRESETS, type LayoutPreset } from "./layout/presets";
export { mergeFigureAssets, resolveFigureAssets } from "./layout/syncFigureAssets";
export {
  suggestLayout,
  type SuggestLayoutOptions,
  OUTER_PADDING,
  CELL_GAP,
  MAX_CELL_SIZE,
} from "./layout/suggestLayout";
export { buildFigureFromAssets } from "./utils/buildFigure";
