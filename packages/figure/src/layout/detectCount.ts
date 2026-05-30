import { buildFallbackPreset, LAYOUT_PRESETS, type LayoutPreset } from "./presets";

const COUNT_PRESET_MAP: Record<number, LayoutPreset> = {
  1: LAYOUT_PRESETS["1x1"],
  2: LAYOUT_PRESETS["1x2"],
  3: LAYOUT_PRESETS["1x3"],
  4: LAYOUT_PRESETS["2x2"],
  6: LAYOUT_PRESETS["2x3"],
  9: LAYOUT_PRESETS["3x3"],
};

/** Map image count to the default symmetric layout preset. */
export function detectCount(count: number): LayoutPreset {
  if (count <= 0) {
    return LAYOUT_PRESETS["1x1"];
  }
  return COUNT_PRESET_MAP[count] ?? buildFallbackPreset(count);
}

/** Alternate presets for counts with multiple valid layouts. */
export function detectCountAlternatives(count: number): LayoutPreset[] {
  const primary = detectCount(count);
  if (count === 3) {
    return [primary, LAYOUT_PRESETS["2+1"]];
  }
  return [primary];
}
