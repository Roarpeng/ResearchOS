import { useAssetStore, type Asset } from "@paperhelp/shared";
import { paperFileIO } from "./paperIo";

function bytesToDataUrl(bytes: Uint8Array, mime: string): string {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return `data:${mime};base64,${btoa(binary)}`;
}

/** Load full-resolution image bytes from disk for export. */
export async function assetPathToDataUrl(asset: Asset): Promise<string | null> {
  try {
    const bytes = await paperFileIO.readBinaryFile(asset.path);
    return bytesToDataUrl(bytes, asset.mime);
  } catch {
    return useAssetStore.getState().getThumbnail(asset.hash) ?? null;
  }
}
