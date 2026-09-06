import { useEffect, useRef, useState } from "react";
import type Konva from "konva";
import { Layer, Line, Rect, Stage, Image as KonvaImage, Text } from "react-konva";
import { autoLayout } from "./layout";

export interface FigureAsset {
  id: string;
  src: string;
  width?: number;
  height?: number;
}

export interface FigureCanvasProps {
  assets: FigureAsset[];
  showScaleBar?: boolean;
  scaleBarLabel?: string;
  onExportPng?: (dataUrl: string) => void;
}

function useImageUrl(src: string): HTMLImageElement | null {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    const image = new window.Image();
    image.crossOrigin = "anonymous";
    image.onload = () => setImg(image);
    image.src = src;
    return () => {
      image.onload = null;
    };
  }, [src]);
  return img;
}

/**
 * Figure canvas: auto-layout N images with (a,b,c…) labels, optional scale bar
 * and PNG export. Ported core of PaperHelp Figure Studio (no Tauri).
 */
export function FigureCanvas({
  assets,
  showScaleBar = false,
  scaleBarLabel = "scale",
  onExportPng,
}: FigureCanvasProps) {
  const stageRef = useRef<Konva.Stage>(null);
  const [labels, setLabels] = useState<Record<number, string>>({});
  const normalized = assets.map((a) => ({
    id: a.id,
    width: a.width || 200,
    height: a.height || 200,
  }));
  const layout = autoLayout(normalized);
  const barX = layout.stageWidth - 200;
  const barY = layout.stageHeight - 40;

  function exportPng() {
    const url = stageRef.current?.toDataURL({ pixelRatio: 2 });
    if (url && onExportPng) onExportPng(url);
  }

  return (
    <div>
      <Stage ref={stageRef} width={layout.stageWidth} height={layout.stageHeight}>
        <Layer>
          {layout.items.map((item, i) => (
            <FigureImage key={item.assetId} item={item} src={assets[i].src} />
          ))}
          {layout.items.map((item, i) => {
            const label = labels[i] ?? String.fromCharCode(97 + i);
            return (
              <Text
                key={`${item.assetId}-label`}
                text={label}
                x={item.x + item.width / 2}
                y={item.y - 20}
                fontSize={16}
                fontStyle="bold"
                align="center"
                width={30}
                offsetX={15}
                onClick={() => {
                  const next = window.prompt("标签文字", label);
                  if (next !== null && next !== "") {
                    setLabels((prev) => ({ ...prev, [i]: next }));
                  }
                }}
              />
            );
          })}
          {showScaleBar ? (
            <>
              <Line points={[barX, barY, barX + 160, barY]} stroke="#000" strokeWidth={2} />
              <Line points={[barX, barY - 6, barX, barY + 6]} stroke="#000" strokeWidth={2} />
              <Line points={[barX + 160, barY - 6, barX + 160, barY + 6]} stroke="#000" strokeWidth={2} />
              <Text
                text={scaleBarLabel}
                x={barX}
                y={barY + 8}
                fontSize={14}
                align="center"
                width={160}
              />
            </>
          ) : null}
        </Layer>
      </Stage>
      {onExportPng ? (
        <div style={{ marginTop: 8 }}>
          <button type="button" onClick={exportPng}>
            导出 PNG
          </button>
        </div>
      ) : null}
    </div>
  );
}

function FigureImage({
  item,
  src,
}: {
  item: { x: number; y: number; width: number; height: number };
  src: string;
}) {
  const img = useImageUrl(src);
  if (!img) {
    return <Rect x={item.x} y={item.y} width={item.width} height={item.height} fill="#eee" stroke="#ccc" />;
  }
  return <KonvaImage image={img} x={item.x} y={item.y} width={item.width} height={item.height} />;
}
