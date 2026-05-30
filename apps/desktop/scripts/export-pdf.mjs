#!/usr/bin/env node
/**
 * Puppeteer PDF sidecar — invoked from Tauri export_pdf command.
 * Usage: node export-pdf.mjs <htmlPath> <outputPath>
 *
 * First run may download Chromium (~150 MB) via puppeteer postinstall.
 */
import { generatePdfFromFile } from "../../../packages/export/dist/pdf/generatePdf.js";

const [htmlPath, outputPath] = process.argv.slice(2);

if (!htmlPath || !outputPath) {
  console.error("Usage: node export-pdf.mjs <htmlPath> <outputPath>");
  process.exit(1);
}

try {
  await generatePdfFromFile(htmlPath, outputPath);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
