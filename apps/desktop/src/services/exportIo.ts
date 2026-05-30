import { invoke } from "@tauri-apps/api/core";

export async function pickExportPdfPath(defaultName: string): Promise<string | null> {
  return invoke<string | null>("pick_export_pdf_path", { defaultName });
}

export async function exportPdfHtml(html: string, outputPath: string): Promise<void> {
  await invoke("export_pdf", { html, outputPath });
}
