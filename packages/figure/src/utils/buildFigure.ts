import { nanoid } from "nanoid";
import type { Asset, Figure, FigureLabel, Layout, LayoutItem, ScaleBar } from "@paperhelp/shared";
import { snapToGrid } from "./grid";

const PADDING = 40;
const MAX_DISPLAY = 280;

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

function buildLayoutItems(assets: Asset[]): LayoutItem[] {
  let cursorX = PADDING;
  const y = PADDING;
  const items: LayoutItem[] = [];

  for (const asset of assets) {
    const scale = Math.min(MAX_DISPLAY / asset.width, MAX_DISPLAY / asset.height, 1);
    const width = Math.round(asset.width * scale);
    const height = Math.round(asset.height * scale);
    items.push({
      assetId: asset.id,
      x: snapToGrid(cursorX),
      y: snapToGrid(y),
      width,
      height,
    });
    cursorX += width + PADDING;
  }

  return items;
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

function buildLayout(items: LayoutItem[]): Layout {
  const maxRight = Math.max(...items.map((item) => item.x + item.width), 0);
  const maxBottom = Math.max(...items.map((item) => item.y + item.height), 0);

  return {
    stageWidth: Math.max(800, maxRight + PADDING),
    stageHeight: Math.max(600, maxBottom + PADDING),
    gridSize: 20,
    items,
  };
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
  const items = buildLayoutItems(assets);
  const layout = buildLayout(items);

  return {
    id: nanoid(),
    title,
    assetIds,
    layout,
    labels: buildLabels(assets),
    annotations: [],
    scaleBar: defaultScaleBar(layout),
    style: { ...defaultStyle },
  };
}
