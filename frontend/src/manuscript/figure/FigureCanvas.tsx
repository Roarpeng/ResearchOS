import { useEffect, useState } from "react";
import { Layer, Rect, Stage, Image as KonvaImage, Text } from "react-konva";
import { autoLayout } from "./layout";

export interface FigureAsset {
  id: string;
  src: string;
  width?: number;
  height?: number;
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
 * Figure canvas: auto-layout N images with (a,b,c…) labels.
 * Ported core of PaperHelp Figure Studio (no Tauri; images via src/dataURL).
 */
export function FigureCanvas({ assets }: { assets: FigureAsset[] }) {
  const normalized = assets.map((a) => ({ id: a.id, width: a.width || 200, height: a.height || 200 }));
  const layout = autoLayout(normalized);

  return (
    <Stage width={layout.stageWidth} height={layout.stageHeight}>
      <Layer>
        {layout.items.map((item, i) => (
          <FigureImage key={item.assetId} item={item} src={assets[i].src} />
        ))}
        {layout.items.map((item, i) => (
          <Text
            key={`${item.assetId}-label`}
            text={String.fromCharCode(97 + i)}
            x={item.x + item.width / 2}
            y={item.y - 20}
            fontSize={16}
            fontStyle="bold"
            align="center"
            width={30}
            offsetX={15}
          />
        ))}
      </Layer>
    </Stage>
  );
}

function FigureImage({ item, src }: { item: { x: number; y: number; width: number; height: number }; src: string }) {
  const img = useImageUrl(src);
  if (!img) {
    return <Rect x={item.x} y={item.y} width={item.width} height={item.height} fill="#eee" stroke="#ccc" />;
  }
  return <KonvaImage image={img} x={item.x} y={item.y} width={item.width} height={item.height} />;
}
