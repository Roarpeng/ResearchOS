/** Placed image on the figure canvas (positions in stage pixels). */
export interface LayoutItem {
  assetId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Layout {
  stageWidth: number;
  stageHeight: number;
  gridSize: number;
  items: LayoutItem[];
}

export interface FigureLabel {
  id: string;
  assetId: string;
  text: string;
  x: number;
  y: number;
}

export type AnnotationType = "arrow" | "text" | "rect";

export interface Annotation {
  id: string;
  type: AnnotationType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  text?: string;
  points?: number[];
}

export interface ScaleBar {
  x: number;
  y: number;
  lengthPx: number;
  lengthValue: number;
  unit: string;
  barHeight?: number;
}

export interface FigureStyle {
  labelFontSize: number;
  labelColor: string;
  labelBackground: string;
  backgroundColor: string;
}

/** Figure references assets by id (canonical copy lives in assetStore). */
export interface Figure {
  id: string;
  title: string;
  assetIds: string[];
  layout: Layout;
  labels: FigureLabel[];
  annotations: Annotation[];
  scaleBar?: ScaleBar;
  style: FigureStyle;
}

export type FigureElementId =
  | `image:${string}`
  | `label:${string}`
  | "scaleBar"
  | `annotation:${string}`;
