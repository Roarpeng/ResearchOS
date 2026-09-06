import { useMemo } from "react";
import type { Figure } from "@paperhelp/shared";
import { useAssetStore } from "@paperhelp/shared";

export interface FigureThumbnailPreviewProps {
  figure: Figure;
  className?: string;
  /** Max thumbnail cells shown in the collage. */
  maxCells?: number;
}

function gridVariant(count: number): "single" | "dual" | "triple" | "quad" | "grid" {
  if (count <= 1) return "single";
  if (count === 2) return "dual";
  if (count === 3) return "triple";
  if (count === 4) return "quad";
  return "grid";
}

export function FigureThumbnailPreview({
  figure,
  className,
  maxCells = 4,
}: FigureThumbnailPreviewProps) {
  const assets = useAssetStore((s) => s.assets);
  const getThumbnail = useAssetStore((s) => s.getThumbnail);

  const cells = useMemo(() => {
    return figure.assetIds
      .map((assetId) => assets[assetId])
      .filter((asset): asset is NonNullable<typeof asset> => Boolean(asset));
  }, [assets, figure.assetIds]);

  const visible = cells.slice(0, maxCells);
  const overflow = cells.length - visible.length;
  const variant = gridVariant(Math.min(cells.length, maxCells));

  return (
    <div
      className={["figure-thumb-preview", `figure-thumb-preview--${variant}`, className]
        .filter(Boolean)
        .join(" ")}
      style={{ backgroundColor: figure.style.backgroundColor }}
    >
      {visible.map((asset) => {
        const src = getThumbnail(asset.hash);
        return src ? (
          <img
            key={asset.id}
            className="figure-thumb-preview__cell"
            src={src}
            alt=""
            draggable={false}
          />
        ) : (
          <div key={asset.id} className="figure-thumb-preview__cell figure-thumb-preview__cell--empty" />
        );
      })}
      {overflow > 0 ? (
        <span className="figure-thumb-preview__overflow">+{overflow}</span>
      ) : null}
    </div>
  );
}
