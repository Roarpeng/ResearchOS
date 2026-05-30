export type DocumentFontFamily = "times" | "arial" | "simsun" | "serif" | "sans";

export type DocumentFontSize = 10 | 11 | 12 | 14;

export const DOCUMENT_FONT_OPTIONS: ReadonlyArray<{
  value: DocumentFontFamily;
  label: string;
  css: string;
}> = [
  {
    value: "times",
    label: "Times New Roman",
    css: '"Times New Roman", Times, serif',
  },
  { value: "arial", label: "Arial", css: "Arial, Helvetica, sans-serif" },
  { value: "simsun", label: "宋体", css: '"SimSun", "宋体", serif' },
  { value: "serif", label: "Serif", css: "Georgia, Cambria, serif" },
  { value: "sans", label: "Sans-serif", css: "system-ui, -apple-system, sans-serif" },
];

export const DOCUMENT_FONT_SIZE_OPTIONS: readonly DocumentFontSize[] = [
  10, 11, 12, 14,
];

export function resolveFontFamilyCss(family: DocumentFontFamily): string {
  return (
    DOCUMENT_FONT_OPTIONS.find((option) => option.value === family)?.css ??
    DOCUMENT_FONT_OPTIONS[0].css
  );
}
