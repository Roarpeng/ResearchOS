import { Group, Image as KonvaImage, Rect } from "react-konva";
import { useAssetStore, type Layout, type LayoutItem } from "@paperhelp/shared";
import { useHtmlImage } from "../hooks/useHtmlImage";

interface PreviewLayerProps {
  preview: Layout;
}

function PreviewGhost({ item }: { item: LayoutItem }) {
  const asset = useAssetStore((s) => s.assets[item.assetId]);
  const thumbnail = useAssetStore((s) =>
    asset ? s.getThumbnail(asset.hash) : undefined,
  );
  const image = useHtmlImage(thumbnail);

  if (!asset || !image) {
    return (
      <Rect
        x={item.x}
        y={item.y}
        width={item.width}
        height={item.height}
        fill="rgba(37, 99, 235, 0.15)"
        stroke="#2563eb"
        strokeWidth={2}
        dash={[8, 4]}
      />
    );
  }

  return (
    <Group x={item.x} y={item.y} opacity={0.45}>
      <KonvaImage image={image} width={item.width} height={item.height} />
      <Rect
        width={item.width}
        height={item.height}
        stroke="#2563eb"
        strokeWidth={2}
        dash={[8, 4]}
      />
    </Group>
  );
}

export function PreviewLayer({ preview }: PreviewLayerProps) {
  return (
    <>
      {preview.items.map((item) => (
        <PreviewGhost key={`preview-${item.assetId}`} item={item} />
      ))}
    </>
  );
}
