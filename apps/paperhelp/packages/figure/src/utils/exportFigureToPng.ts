import type { Asset, Figure, FigureLabel, ScaleBar } from "@paperhelp/shared";

export interface ExportFigureToPngOptions {
  /** Scale factor for ~300 dpi submission quality (default 2). */
  pixelRatio?: number;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = src;
  });
}

function dataUrlToUint8Array(dataUrl: string): Uint8Array {
  const comma = dataUrl.indexOf(",");
  const base64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  label: FigureLabel,
  layoutItem: { x: number; y: number },
  style: Figure["style"],
): void {
  const fontSize = style.labelFontSize;
  const padding = 6;
  const textWidth = Math.max(fontSize * 0.65 * label.text.length, fontSize);
  const boxWidth = textWidth + padding * 2;
  const boxHeight = fontSize + padding * 2;
  const x = layoutItem.x + label.x;
  const y = layoutItem.y + label.y;

  ctx.fillStyle = style.labelBackground;
  ctx.beginPath();
  ctx.roundRect(x, y, boxWidth, boxHeight, 4);
  ctx.fill();

  ctx.fillStyle = style.labelColor;
  ctx.font = `bold ${fontSize}px sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillText(label.text, x + padding, y + padding);
}

function drawScaleBar(ctx: CanvasRenderingContext2D, scaleBar: ScaleBar): void {
  const barHeight = scaleBar.barHeight ?? 4;
  const label = `${scaleBar.lengthValue} ${scaleBar.unit}`;
  const { x, y, lengthPx } = scaleBar;

  ctx.fillStyle = "rgba(255,255,255,0.85)";
  ctx.strokeStyle = "#d4d4d8";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(x, y, lengthPx + 16, 36, 4);
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = "#111827";
  ctx.lineWidth = barHeight;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(x + 8, y + 22);
  ctx.lineTo(x + 8 + lengthPx, y + 22);
  ctx.stroke();

  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x + 8, y + 16);
  ctx.lineTo(x + 8, y + 28);
  ctx.moveTo(x + 8 + lengthPx, y + 16);
  ctx.lineTo(x + 8 + lengthPx, y + 28);
  ctx.stroke();

  ctx.fillStyle = "#111827";
  ctx.font = "12px sans-serif";
  ctx.textBaseline = "top";
  ctx.fillText(label, x + 8, y + 4);
}

/**
 * Renders a figure layout to high-resolution PNG bytes for journal submission.
 */
export async function exportFigureToPng(
  figure: Figure,
  resolveAsset: (assetId: string) => Asset | undefined,
  getImageDataUrl: (asset: Asset) => Promise<string | null>,
  options: ExportFigureToPngOptions = {},
): Promise<Uint8Array | null> {
  const pixelRatio = options.pixelRatio ?? 2;
  const { layout, style } = figure;

  if (layout.items.length === 0) {
    return null;
  }

  const canvas = document.createElement("canvas");
  canvas.width = layout.stageWidth * pixelRatio;
  canvas.height = layout.stageHeight * pixelRatio;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return null;
  }

  ctx.scale(pixelRatio, pixelRatio);
  ctx.fillStyle = style.backgroundColor;
  ctx.fillRect(0, 0, layout.stageWidth, layout.stageHeight);

  for (const item of layout.items) {
    const asset = resolveAsset(item.assetId);
    if (!asset) {
      continue;
    }

    const dataUrl = await getImageDataUrl(asset);
    if (!dataUrl) {
      continue;
    }

    const img = await loadImage(dataUrl);
    ctx.drawImage(img, item.x, item.y, item.width, item.height);
  }

  const itemByAsset = new Map(layout.items.map((item) => [item.assetId, item]));
  for (const label of figure.labels) {
    const layoutItem = itemByAsset.get(label.assetId);
    if (layoutItem) {
      drawLabel(ctx, label, layoutItem, style);
    }
  }

  if (figure.scaleBar) {
    drawScaleBar(ctx, figure.scaleBar);
  }

  return dataUrlToUint8Array(canvas.toDataURL("image/png"));
}
