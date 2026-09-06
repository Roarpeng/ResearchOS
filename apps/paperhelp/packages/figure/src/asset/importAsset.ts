import { invoke } from "@tauri-apps/api/core";
import { nanoid } from "nanoid";
import { useAssetStore, type Asset } from "@paperhelp/shared";
import type { ReadImageAssetResult } from "./types";

export async function importImages(): Promise<Asset[]> {
  const paths = await invoke<string[]>("pick_image_files");
  if (!paths.length) {
    return [];
  }

  const store = useAssetStore.getState();
  const imported: Asset[] = [];

  for (const path of paths) {
    const result = await invoke<ReadImageAssetResult>("read_image_asset", {
      path,
    });

    const existing = store.getAssetByHash(result.hash);
    if (existing) {
      if (!store.getThumbnail(result.hash)) {
        store.cacheThumbnail(result.hash, result.thumbnail);
      }
      imported.push(existing);
      continue;
    }

    const asset: Asset = {
      id: nanoid(),
      path: result.path,
      hash: result.hash,
      width: result.width,
      height: result.height,
      mime: result.mime,
    };

    store.addAsset(asset, result.thumbnail);
    imported.push(asset);
  }

  return imported;
}
