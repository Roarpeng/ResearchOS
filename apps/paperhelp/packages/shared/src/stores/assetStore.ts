import { create } from "zustand";
import type { Asset } from "../types/asset";

const thumbnailCache = new Map<string, string>();

export interface AssetState {
  assets: Record<string, Asset>;
}

export interface AssetActions {
  addAsset: (asset: Asset, thumbnail: string) => void;
  cacheThumbnail: (hash: string, thumbnail: string) => void;
  getAssetByHash: (hash: string) => Asset | undefined;
  getThumbnail: (hash: string) => string | undefined;
  reset: () => void;
}

export type AssetStore = AssetState & AssetActions;

const initialAssetState: AssetState = {
  assets: {},
};

export const useAssetStore = create<AssetStore>((set, get) => ({
  ...initialAssetState,

  addAsset: (asset, thumbnail) => {
    thumbnailCache.set(asset.hash, thumbnail);
    set((state) => ({
      assets: { ...state.assets, [asset.id]: asset },
    }));
  },

  cacheThumbnail: (hash, thumbnail) => {
    thumbnailCache.set(hash, thumbnail);
  },

  getAssetByHash: (hash) => {
    const assets = get().assets;
    return Object.values(assets).find((asset) => asset.hash === hash);
  },

  getThumbnail: (hash) => thumbnailCache.get(hash),

  reset: () => {
    thumbnailCache.clear();
    set(initialAssetState);
  },
}));
