import { create } from "zustand";

/** Figure entity — full model deferred to Sprint 2 */
export interface Figure {
  id: string;
  caption: string;
}

export interface FigureState {
  figures: Figure[];
}

export interface FigureActions {
  reset: () => void;
}

export type FigureStore = FigureState & FigureActions;

const initialFigureState: FigureState = {
  figures: [],
};

export const useFigureStore = create<FigureStore>((set) => ({
  ...initialFigureState,
  reset: () => set(initialFigureState),
}));
