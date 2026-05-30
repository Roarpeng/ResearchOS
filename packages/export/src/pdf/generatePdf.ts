import { readFileSync } from "node:fs";
import { existsSync } from "node:fs";
import puppeteer from "puppeteer";

export interface GeneratePdfOptions {
  format?: "A4" | "Letter";
  printBackground?: boolean;
}

function resolveChromeExecutable(): string | undefined {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) {
    return process.env.PUPPETEER_EXECUTABLE_PATH;
  }
  if (process.platform === "win32") {
    const candidates = [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      `${process.env.LOCALAPPDATA ?? ""}\\Google\\Chrome\\Application\\chrome.exe`,
      `${process.env.PROGRAMFILES ?? ""}\\Google\\Chrome\\Application\\chrome.exe`,
    ];
    return candidates.find((p) => p && existsSync(p));
  }
  if (process.platform === "darwin") {
    const mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
    return existsSync(mac) ? mac : undefined;
  }
  return undefined;
}

/**
 * Render HTML string to a PDF file via headless Chrome (Node-only).
 * Uses system Chrome when available; otherwise Puppeteer's bundled Chromium.
 */
export async function generatePdfFromHtml(
  html: string,
  outputPath: string,
  options: GeneratePdfOptions = {},
): Promise<void> {
  const executablePath = resolveChromeExecutable();
  const browser = await puppeteer.launch({
    headless: true,
    executablePath,
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
