import { readFileSync } from "node:fs";
import puppeteer from "puppeteer";

export interface GeneratePdfOptions {
  format?: "A4" | "Letter";
  printBackground?: boolean;
}

/**
 * Render HTML string to a PDF file via headless Chrome (Node-only).
 * First run may download a Chromium build (~150 MB).
 */
export async function generatePdfFromHtml(
  html: string,
  outputPath: string,
  options: GeneratePdfOptions = {},
): Promise<void> {
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "load" });
    await page.pdf({
      path: outputPath,
      format: options.format ?? "A4",
      printBackground: options.printBackground ?? true,
      margin: {
        top: "25mm",
        right: "25mm",
        bottom: "25mm",
        left: "25mm",
      },
    });
  } finally {
    await browser.close();
  }
}

/** Load HTML from disk and write a PDF to the given output path. */
export async function generatePdfFromFile(
  htmlPath: string,
  outputPath: string,
  options?: GeneratePdfOptions,
): Promise<void> {
  const html = readFileSync(htmlPath, "utf8");
  return generatePdfFromHtml(html, outputPath, options);
}
