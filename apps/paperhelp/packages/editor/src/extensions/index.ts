import StarterKit from "@tiptap/starter-kit";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import type { Extensions } from "@tiptap/core";
import { FigureNode } from "../nodes/FigureNode";
import { CitationNode } from "../nodes/CitationNode";

export function getExtensions(): Extensions {
  return [
    StarterKit.configure({
      heading: {
        levels: [1, 2, 3],
      },
    }),
    Table.configure({
      resizable: true,
    }),
    TableRow,
    TableHeader,
    TableCell,
    FigureNode,
    CitationNode,
  ];
}
