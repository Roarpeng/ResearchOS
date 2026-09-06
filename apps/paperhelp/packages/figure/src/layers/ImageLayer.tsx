import { Group, Image as KonvaImage } from "react-konva";
import type Konva from "konva";
import {
  useAssetStore,
  useFigureStore,
  type Figure,
  type LayoutItem,
} from "@paperhelp/shared";
import { useHtmlImage } from "../hooks/useHtmlImage";
import { snapToGrid } from "../utils/grid";

interface ImageLayerProps {
  figure: Figure;
}

function PlacedImage({
  figureId,
  item,
  gridSize,
  selected,
  onSelect,
}: {
  figureId: string;
  item: LayoutItem;
  gridSize: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const asset = useAssetStore((s) => s.assets[item.assetId]);
  const thumbnail = useAssetStore((s) =>
    asset ? s.getThumbnail(asset.hash) : undefined,
  );
  const image = useHtmlImage(thumbnail);
  const updateFigure = useFigureStore((s) => s.updateFigure);

  if (!asset || !image) {
    return null;
  }

  const handleDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const node = e.target;
    const x = snapToGrid(node.x(), gridSize);
    const y = snapToGrid(node.y(), gridSize);
    node.position({ x, y });

    updateFigure(figureId, (current) => ({
      layout: {
        ...current.layout,
        items: current.layout.items.map((entry) =>
          entry.assetId === item.assetId ? { ...entry, x, y } : entry,
        ),
      },
    }));
  };

  return (
    <Group
      x={item.x}
      y={item.y}
      draggable
      onClick={onSelect}
      onTap={onSelect}
      onDragEnd={handleDragEnd}
    >
      <KonvaImage
        image={image}
        width={item.width}
        height={item.height}
        stroke={selected ? "#2563eb" : undefined}
        strokeWidth={selected ? 2 : 0}
      />
    </Group>
  );
}

export function ImageLayer({ figure }: ImageLayerProps) {
  const selectedElementId = useFigureStore((s) => s.selectedElementId);
  const selectElement = useFigureStore((s) => s.selectElement);
  const figureId = figure.id;
  const gridSize = figure.layout.gridSize;

  return (
    <>
      {figure.layout.items.map((item) => (
        <PlacedImage
          key={item.assetId}
          figureId={figureId}
          item={item}
          gridSize={gridSize}
          selected={selectedElementId === `image:${item.assetId}`}
          onSelect={() => selectElement(`image:${item.assetId}`)}
        />
      ))}
    </>
  );
}
