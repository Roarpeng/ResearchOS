export interface PrintTypography {
  fontFamilyCss: string;
  fontSizePt: number;
}

const PRINT_CSS_BODY = `
figure,
table,
img {
  page-break-inside: avoid;
}

figure.figure-block {
  margin: 1.25em 0;
  text-align: center;
}

figure.figure-block img {
  max-width: 100%;
  height: auto;
}

figure.figure-block--empty,
figure.figure-block--missing {
  border: 1px dashed #999;
  padding: 1em;
  color: #666;
}

figcaption {
  font-size: 0.833em;
  margin-top: 0.5em;
  text-align: center;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

th,
td {
  border: 1px solid #333;
  padding: 4px 8px;
  vertical-align: top;
}

th {
  font-weight: bold;
  background: #f5f5f5;
}

blockquote {
  margin: 0.75em 1.5em;
  padding-left: 1em;
  border-left: 3px solid #ccc;
  color: #333;
}

pre {
  font-family: "Courier New", Courier, monospace;
  font-size: 0.833em;
  background: #f8f8f8;
  padding: 0.75em;
  overflow-x: auto;
  page-break-inside: avoid;
}

code {
  font-family: "Courier New", Courier, monospace;
  font-size: 0.833em;
}

ul,
ol {
  margin: 0 0 0.75em 1.5em;
  padding: 0;
}

.citation-block {
  color: #555;
  font-style: italic;
  margin: 0.75em 0;
}

.page-break {
  page-break-before: always;
}

hr {
  border: none;
  border-top: 1px solid #ccc;
  margin: 1.5em 0;
}
`;

/** Build print stylesheet matching editor A4 typography (25mm margins). */
export function buildPrintCss({ fontFamilyCss, fontSizePt }: PrintTypography): string {
  return `@page {
  size: A4;
  margin: 25mm;
}

html,
body {
  font-family: ${fontFamilyCss};
  font-size: ${fontSizePt}pt;
  line-height: 1.7;
  color: #000;
  margin: 0;
  padding: 0;
  background: #fff;
}

.document-title {
  font-size: 1.5em;
  font-weight: bold;
  text-align: center;
  margin: 0 0 1.5em;
  page-break-after: avoid;
}

h1,
h2,
h3 {
  page-break-after: avoid;
  font-weight: bold;
}

h1 {
  font-size: 1.875em;
}

h2 {
  font-size: 1.5em;
}

h3 {
  font-size: 1.25em;
}

p {
  margin: 0 0 0.75em;
  text-align: justify;
}
${PRINT_CSS_BODY}`;
}

/** Default print CSS (Times New Roman 12pt) for backwards compatibility. */
export const PRINT_CSS = buildPrintCss({
  fontFamilyCss: '"Times New Roman", Times, serif',
  fontSizePt: 12,
});
