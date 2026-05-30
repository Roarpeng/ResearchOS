import { Group, Rect, Text } from "react-konva";
import type Konva from "konva";
import { useFigureStore, type Figure, type FigureLabel } from "@paperhelp/shared";
import { snapToGrid } from "../utils/grid";

interface LabelLayerProps {
  figure: Figure;
}

function PanelLabel({
  figureId,
  label,
  layoutItem,
  style,
  selected,
  onSelect,
}: {
  figureId: string;
  label: FigureLabel;
  layoutItem: { x: number; y: number } | undefined;
  style: Figure["style"];
  selected: boolean;
  onSelect: () => void;
}) {
  const updateFigure = useFigureStore((s) => s.updateFigure);
  const gridSize = useFigureStore(
    (s) => s.figures[figureId]?.layout.gridSize ?? 20,
  );

  if (!layoutItem) {
    return null;
  }

  const handleDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const group = e.target.getType() === "Group" ? e.target : e.target.getParent();
    if (!group) return;
    const x = snapToGrid(group.x() - layoutItem.x, gridSize);
    const y = snapToGrid(group.y() - layoutItem.y, gridSize);
    group.position({ x: layoutItem.x + x, y: layoutItem.y + y });

    updateFigure(figureId, (current) => ({
      labels: current.labels.map((entry) =>
        entry.id === label.id ? { ...entry, x, y } : entry,
      ),
    }));
  };

  const fontSize = style.labelFontSize;
  const padding = 6;
  const textWidth = Math.max(fontSize * 0.65 * label.text.length, fontSize);

  return (
    <Group
      x={layoutItem.x + label.x}
      y={layoutItem.y + label.y}
      draggable
      onClick={onSelect}
      onTap={onSelect}
      onDragEnd={handleDragEnd}
    >
      <Rect
        width={textWidth + padding * 2}
        height={fontSize + padding * 2}
        fill={style.labelBackground}
        cornerRadius={4}
        stroke={selected ? "#2563eb" : undefined}
        strokeWidth={selected ? 2 : 0}
      />
      <Text
        text={label.text}
        x={padding}
        y={padding}
        fontSize={fontSize}
        fill={style.labelColor}
        fontStyle="bold"
      />
    </Group>
  );
}

export function LabelLayer({ figure }: LabelLayerProps) {
  const selectedElementId = useFigureStore((s) => s.selectedElementId);
  const selectElement = useFigureStore((s) => s.selectElement);
  const itemByAsset = new Map(
    figure.layout.items.map((item) => [item.assetId, item]),
  );

  return (
    <>
      {figure.labels.map((label) => (
        <PanelLabel
          key={label.id}
          figureId={figure.id}
          label={label}
          layoutItem={itemByAsset.get(label.assetId)}
          style={figure.style}
          selected={selectedElementId === `label:${label.id}`}
          onSelect={() => selectElement(`label:${label.id}`)}
        />
      ))}
    </>
  );
}
