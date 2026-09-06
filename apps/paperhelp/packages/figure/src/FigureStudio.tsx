import { useCallback, useRef } from "react";
import { Layer, Rect, Stage } from "react-konva";
import type Konva from "konva";
import { useFigureStore } from "@paperhelp/shared";
import { AnnotationLayer } from "./layers/AnnotationLayer";
import { ImageLayer } from "./layers/ImageLayer";
import { LabelLayer } from "./layers/LabelLayer";
import { PreviewLayer } from "./layers/PreviewLayer";
import { ScaleBarLayer } from "./layers/ScaleBarLayer";

export interface FigureStudioProps {
  figureId: string;
  className?: string;
}

export function FigureStudio({ figureId, className }: FigureStudioProps) {
  const figure = useFigureStore((s) => s.figures[figureId]);
  const previewLayout = useFigureStore((s) => s.layoutPreviews[figureId] ?? null);
  const selectElement = useFigureStore((s) => s.selectElement);
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);

  const clearSelection = useCallback(() => {
    selectElement(null);
  }, [selectElement]);

  if (!figure) {
    return (
      <div className={className} ref={containerRef}>
        <p>Figure not found.</p>
      </div>
    );
  }

  const { layout, style } = figure;
  const stageLayout = previewLayout ?? layout;

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        width: "100%",
        height: "100%",
        overflow: "auto",
        background: style.backgroundColor,
      }}
      onPointerDown={(event) => {
        if (event.target === containerRef.current) {
          clearSelection();
        }
      }}
    >
      <Stage
        ref={stageRef}
        width={stageLayout.stageWidth}
        height={stageLayout.stageHeight}
        onMouseDown={(e) => {
          if (e.target === e.target.getStage()) {
            clearSelection();
          }
        }}
      >
        <Layer>
          <Rect
            x={0}
            y={0}
            width={stageLayout.stageWidth}
            height={stageLayout.stageHeight}
            fill={style.backgroundColor}
          />
          <ImageLayer figure={figure} />
          {previewLayout ? <PreviewLayer preview={previewLayout} /> : null}
          <LabelLayer figure={figure} />
          <AnnotationLayer figure={figure} />
          <ScaleBarLayer figure={figure} />
        </Layer>
      </Stage>
    </div>
  );
}
