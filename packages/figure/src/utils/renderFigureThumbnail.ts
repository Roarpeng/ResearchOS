import type { Asset, Figure } from "@paperhelp/shared";

export interface RenderFigureThumbnailOptions {
  width?: number;
  height?: number;
  maxCells?: number;
}

function gridDimensions(count: number): { cols: number; rows: number } {
  if (count <= 1) return { cols: 1, rows: 1 };
  if (count === 2) return { cols: 2, rows: 1 };
  if (count <= 4) return { cols: 2, rows: 2 };
  if (count <= 6) return { cols: 3, rows: 2 };
  return { cols: 3, rows: 3 };
}

/**
 * Composes asset thumbnails into a single canvas image for inline figure previews or export.
 */
export function renderFigureThumbnailToDataUrl(
  figure: Figure,
  resolveAsset: (assetId: string) => Asset | undefined,
  getThumbnail: (hash: string) => string | undefined,
  options: RenderFigureThumbnailOptions = {},
): Promise<string | null> {
  const width = options.width ?? 320;
  const height = options.height ?? 200;
  const maxCells = options.maxCells ?? 9;

  const assets = figure.assetIds
    .map((assetId) => resolveAsset(assetId))
    .filter((asset): asset is Asset => Boolean(asset))
    .slice(0, maxCells);

  if (assets.length === 0) {
    return Promise.resolve(null);
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return Promise.resolve(null);
  }

  ctx.fillStyle = figure.style.backgroundColor;
  ctx.fillRect(0, 0, width, height);

  const { cols, rows } = gridDimensions(assets.length);
  const gap = 4;
  const cellWidth = (width - gap * (cols + 1)) / cols;
  const cellHeight = (height - gap * (rows + 1)) / rows;

  const loadImage = (src: string) =>
    new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Failed to load thumbnail"));
      img.src = src;
    });

  return Promise.all(
    assets.map(async (asset, index) => {
      const src = getThumbnail(asset.hash);
      if (!src) return;

      const img = await loadImage(src);
      const col = index % cols;
      const row = Math.floor(index / cols);
      const x = gap + col * (cellWidth + gap);
      const y = gap + row * (cellHeight + gap);

      const scale = Math.min(cellWidth / img.width, cellHeight / img.height);
      const drawWidth = img.width * scale;
      const drawHeight = img.height * scale;
      const drawX = x + (cellWidth - drawWidth) / 2;
      const drawY = y + (cellHeight - drawHeight) / 2;

      ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
    }),
  ).then(() => canvas.toDataURL("image/png"));
}
