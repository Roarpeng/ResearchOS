import { create } from "zustand";

/** Asset entity — full model deferred to Sprint 3 */
export interface Asset {
  id: string;
  name: string;
  mimeType: string;
}

export interface AssetState {
  assets: Asset[];
}

export interface AssetActions {
  reset: () => void;
}

export type AssetStore = AssetState & AssetActions;

const initialAssetState: AssetState = {
  assets: [],
};

export const useAssetStore = create<AssetStore>((set) => ({
  ...initialAssetState,
  reset: () => set(initialAssetState),
}));
