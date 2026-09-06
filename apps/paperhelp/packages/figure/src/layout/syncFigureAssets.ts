import { nanoid } from "nanoid";
import type { Asset, Figure, FigureLabel } from "@paperhelp/shared";

function labelTextForIndex(index: number): string {
  if (index < 26) {
    return String.fromCharCode(97 + index);
  }
  return `a${index - 25}`;
}

/** Merge new assets into a figure and ensure labels exist for each asset. */
export function mergeFigureAssets(figure: Figure, newAssets: Asset[]): Figure {
  const nextIds = [...figure.assetIds];
  for (const asset of newAssets) {
    if (!nextIds.includes(asset.id)) {
      nextIds.push(asset.id);
    }
  }

  const labelsByAsset = new Map(figure.labels.map((label) => [label.assetId, label]));
  const labels: FigureLabel[] = nextIds.map((assetId, index) => {
    const existing = labelsByAsset.get(assetId);
    if (existing) {
      return existing;
    }
    return {
      id: nanoid(),
      assetId,
      text: labelTextForIndex(index),
      x: 8,
      y: 8,
    };
  });

  return { ...figure, assetIds: nextIds, labels };
}

export function resolveFigureAssets(
  figure: Figure,
  getAsset: (id: string) => Asset | undefined,
): Asset[] {
  return figure.assetIds
    .map((assetId) => getAsset(assetId))
    .filter((asset): asset is Asset => asset !== undefined);
}
