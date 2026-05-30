import { Group, Line, Rect, Text } from "react-konva";
import type Konva from "konva";
import { useFigureStore, type Figure, type ScaleBar } from "@paperhelp/shared";
import { snapToGrid } from "../utils/grid";

interface ScaleBarLayerProps {
  figure: Figure;
}

function ScaleBarGroup({
  figureId,
  scaleBar,
  gridSize,
  selected,
  onSelect,
}: {
  figureId: string;
  scaleBar: ScaleBar;
  gridSize: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const updateFigure = useFigureStore((s) => s.updateFigure);
  const barHeight = scaleBar.barHeight ?? 4;
  const label = `${scaleBar.lengthValue} ${scaleBar.unit}`;

  const handleDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const node = e.target;
    const x = snapToGrid(node.x(), gridSize);
    const y = snapToGrid(node.y(), gridSize);
    node.position({ x, y });
    updateFigure(figureId, { scaleBar: { ...scaleBar, x, y } });
  };

  return (
    <Group
      x={scaleBar.x}
      y={scaleBar.y}
      draggable
      onClick={onSelect}
      onTap={onSelect}
      onDragEnd={handleDragEnd}
    >
      <Rect
        x={0}
        y={0}
        width={scaleBar.lengthPx + 16}
        height={36}
        fill="rgba(255,255,255,0.85)"
        cornerRadius={4}
        stroke={selected ? "#2563eb" : "#d4d4d8"}
        strokeWidth={selected ? 2 : 1}
      />
      <Line
        points={[8, 22, 8 + scaleBar.lengthPx, 22]}
        stroke="#111827"
        strokeWidth={barHeight}
        lineCap="round"
      />
      <Line points={[8, 16, 8, 28]} stroke="#111827" strokeWidth={2} />
      <Line
        points={[8 + scaleBar.lengthPx, 16, 8 + scaleBar.lengthPx, 28]}
        stroke="#111827"
        strokeWidth={2}
      />
      <Text x={8} y={4} text={label} fontSize={12} fill="#111827" />
    </Group>
  );
}

export function ScaleBarLayer({ figure }: ScaleBarLayerProps) {
  const selectedElementId = useFigureStore((s) => s.selectedElementId);
  const selectElement = useFigureStore((s) => s.selectElement);

  if (!figure.scaleBar) {
    return null;
  }

  return (
    <ScaleBarGroup
      figureId={figure.id}
      scaleBar={figure.scaleBar}
      gridSize={figure.layout.gridSize}
      selected={selectedElementId === "scaleBar"}
      onSelect={() => selectElement("scaleBar")}
    />
  );
}
