import JSZip from "jszip";

export interface SubmissionPackMetadata {
  title: string;
  authors: string[];
  exportedAt: string;
  figureCount: number;
}

export interface SubmissionFigureEntry {
  filename: string;
  pngBytes: Uint8Array;
}

export async function buildSubmissionPackZip(options: {
  pdfBytes: Uint8Array;
  figures: SubmissionFigureEntry[];
  metadata: SubmissionPackMetadata;
}): Promise<Uint8Array> {
  const zip = new JSZip();
  zip.file("manuscript.pdf", options.pdfBytes);
  zip.file("metadata.json", JSON.stringify(options.metadata, null, 2));

  for (const figure of options.figures) {
    zip.file(`figures/${figure.filename}`, figure.pngBytes);
  }

  return zip.generateAsync({ type: "uint8array", compression: "DEFLATE" });
}
