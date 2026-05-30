import { nanoid } from "nanoid";
import type { Asset, Figure, FigureLabel, Layout, ScaleBar } from "@paperhelp/shared";
import { applyAutoLayout } from "../layout/applyLayout";
import { detectCount } from "../layout/detectCount";
import { snapToGrid } from "./grid";

const defaultStyle: Figure["style"] = {
  labelFontSize: 16,
  labelColor: "#ffffff",
  labelBackground: "rgba(0,0,0,0.55)",
  backgroundColor: "#f4f4f5",
};

function labelTextForIndex(index: number): string {
  if (index < 26) {
    return String.fromCharCode(97 + index);
  }
  return `a${index - 25}`;
}

function buildLabels(assets: Asset[]): FigureLabel[] {
  return assets.map((asset, index) => ({
    id: nanoid(),
    assetId: asset.id,
    text: labelTextForIndex(index),
    x: 8,
    y: 8,
  }));
}

function defaultScaleBar(layout: Layout): ScaleBar {
  return {
    x: snapToGrid(layout.stageWidth - 220),
    y: snapToGrid(layout.stageHeight - 56),
    lengthPx: 120,
    lengthValue: 10,
    unit: "μm",
    barHeight: 4,
  };
}

export function buildFigureFromAssets(assets: Asset[], title = "Untitled Figure"): Figure {
  const assetIds = assets.map((a) => a.id);
  const figureId = nanoid();

  const base: Figure = {
    id: figureId,
    title,
    assetIds,
    layout: {
      stageWidth: 800,
      stageHeight: 600,
      gridSize: 20,
      items: [],
    },
    labels: buildLabels(assets),
    annotations: [],
    scaleBar: undefined,
    style: { ...defaultStyle },
  };

  const layoutPatch = applyAutoLayout(base, assets, {
    preset: detectCount(assets.length),
  });
  const layout = layoutPatch.layout ?? base.layout;

  return {
    ...base,
    ...layoutPatch,
    scaleBar: defaultScaleBar(layout),
  };
}
