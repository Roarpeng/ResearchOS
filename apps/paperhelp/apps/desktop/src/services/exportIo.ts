import { invoke } from "@tauri-apps/api/core";
import { paperFileIO } from "./paperIo";

export async function pickExportPdfPath(defaultName: string): Promise<string | null> {
  return invoke<string | null>("pick_export_pdf_path", { defaultName });
}

export async function pickExportZipPath(defaultName: string): Promise<string | null> {
  return invoke<string | null>("pick_export_zip_path", { defaultName });
}

export async function exportPdfHtml(html: string, outputPath: string): Promise<void> {
  await invoke("export_pdf", { html, outputPath });
}

export const exportFileIO = {
  pickZipSavePath: pickExportZipPath,
  createTempDir: paperFileIO.createTempDir,
  removePath: paperFileIO.removePath,
  readBinaryFile: paperFileIO.readBinaryFile,
  writeBinaryFile: paperFileIO.writeBinaryFile,
};
