import { Arrow, Group, Rect, Text } from "react-konva";
import { useFigureStore, type Annotation, type Figure } from "@paperhelp/shared";

interface AnnotationLayerProps {
  figure: Figure;
}

function AnnotationShape({
  annotation,
  selected,
  onSelect,
}: {
  annotation: Annotation;
  selected: boolean;
  onSelect: () => void;
}) {
  const stroke = selected ? "#2563eb" : "#111827";
  const strokeWidth = selected ? 2 : 1.5;

  if (annotation.type === "arrow" && annotation.points && annotation.points.length >= 4) {
    return (
      <Arrow
        points={annotation.points}
        stroke={stroke}
        strokeWidth={strokeWidth}
        fill={stroke}
        pointerLength={8}
        pointerWidth={8}
        onClick={onSelect}
        onTap={onSelect}
      />
    );
  }

  if (annotation.type === "rect") {
    return (
      <Rect
        x={annotation.x}
        y={annotation.y}
        width={annotation.width ?? 80}
        height={annotation.height ?? 48}
        stroke={stroke}
        strokeWidth={strokeWidth}
        onClick={onSelect}
        onTap={onSelect}
      />
    );
  }

  return (
    <Text
      x={annotation.x}
      y={annotation.y}
      text={annotation.text ?? "Note"}
      fontSize={14}
      fill={stroke}
      onClick={onSelect}
      onTap={onSelect}
    />
  );
}

export function AnnotationLayer({ figure }: AnnotationLayerProps) {
  const selectedElementId = useFigureStore((s) => s.selectedElementId);
  const selectElement = useFigureStore((s) => s.selectElement);

  if (!figure.annotations.length) {
    return null;
  }

  return (
    <Group>
      {figure.annotations.map((annotation) => (
        <AnnotationShape
          key={annotation.id}
          annotation={annotation}
          selected={selectedElementId === `annotation:${annotation.id}`}
          onSelect={() => selectElement(`annotation:${annotation.id}`)}
        />
      ))}
    </Group>
  );
}
