import { invoke } from "@tauri-apps/api/core";
import type { PaperFileIO, ReadImageAssetResult } from "@paperhelp/db";

function toUint8Array(data: number[] | Uint8Array): Uint8Array {
  return data instanceof Uint8Array ? data : Uint8Array.from(data);
}

export async function getAppDataDir(): Promise<string> {
  return invoke<string>("get_app_data_dir");
}

export const paperFileIO: PaperFileIO = {
  pickSavePath: (defaultName) =>
    invoke<string | null>("pick_save_paper_path", { defaultName }),

  pickOpenPath: () => invoke<string | null>("pick_open_paper_path"),

  writeBinaryFile: async (path, data) => {
    await invoke("write_binary_file", { path, data: Array.from(data) });
  },

  readBinaryFile: async (path) => {
    const data = await invoke<number[]>("read_binary_file", { path });
    return toUint8Array(data);
  },

  copyFile: (src, dest) => invoke("copy_file", { src, dest }),

  createTempDir: (prefix) => invoke<string>("create_temp_dir", { prefix }),

  removePath: (path) => invoke("remove_path", { path }),

  listFiles: (directory) => invoke<string[]>("list_files", { directory }),
};

export async function readImageAssetForPaper(
  path: string,
): Promise<ReadImageAssetResult> {
  return invoke<ReadImageAssetResult>("read_image_asset", { path });
}

function dataUrlToUint8Array(dataUrl: string): Uint8Array {
  const comma = dataUrl.indexOf(",");
  const base64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export { dataUrlToUint8Array };
