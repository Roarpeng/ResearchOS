import { create } from "zustand";
import type { Figure, FigureElementId, Layout } from "../types/figure";

export interface FigureState {
  figures: Record<string, Figure>;
  currentFigureId: string | null;
  selectedElementId: FigureElementId | null;
  /** Non-committed layout previews keyed by figure id. */
  layoutPreviews: Record<string, Layout | null>;
}

export interface FigureActions {
  addFigure: (figure: Figure) => void;
  updateFigure: (id: string, patch: Partial<Figure> | ((figure: Figure) => Partial<Figure>)) => void;
  selectFigure: (id: string | null) => void;
  selectElement: (elementId: FigureElementId | null) => void;
  setLayoutPreview: (figureId: string, layout: Layout | null) => void;
  clearLayoutPreview: (figureId: string) => void;
  reset: () => void;
}

export type FigureStore = FigureState & FigureActions;

const initialFigureState: FigureState = {
  figures: {},
  currentFigureId: null,
  selectedElementId: null,
  layoutPreviews: {},
};

function applyFigurePatch(
  figure: Figure,
  patch: Partial<Figure> | ((figure: Figure) => Partial<Figure>),
): Figure {
  const next = typeof patch === "function" ? patch(figure) : patch;
  return { ...figure, ...next };
}

export const useFigureStore = create<FigureStore>((set) => ({
  ...initialFigureState,

  addFigure: (figure) =>
    set((state) => ({
      figures: { ...state.figures, [figure.id]: figure },
      currentFigureId: figure.id,
      selectedElementId: null,
    })),

  updateFigure: (id, patch) =>
    set((state) => {
      const figure = state.figures[id];
      if (!figure) return state;
      return {
        figures: {
          ...state.figures,
          [id]: applyFigurePatch(figure, patch),
        },
      };
    }),

  selectFigure: (id) =>
    set({
      currentFigureId: id,
      selectedElementId: null,
    }),

  selectElement: (elementId) => set({ selectedElementId: elementId }),

  setLayoutPreview: (figureId, layout) =>
    set((state) => ({
      layoutPreviews: { ...state.layoutPreviews, [figureId]: layout },
    })),

  clearLayoutPreview: (figureId) =>
    set((state) => ({
      layoutPreviews: { ...state.layoutPreviews, [figureId]: null },
    })),

  reset: () => set(initialFigureState),
}));

export type { Figure, FigureElementId } from "../types/figure";
