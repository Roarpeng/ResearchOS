import { relations } from "drizzle-orm";
import { assets } from "./assets";
import { blocks } from "./blocks";
import { citations } from "./citations";
import { documents } from "./documents";
import { figures } from "./figures";
import { history } from "./history";

export { assets } from "./assets";
export { blocks } from "./blocks";
export { citations } from "./citations";
export { documents } from "./documents";
export { figures } from "./figures";
export { history } from "./history";

export type { Asset, NewAsset } from "./assets";
export type { Block, NewBlock } from "./blocks";
export type { Citation, NewCitation } from "./citations";
export type { Document, NewDocument } from "./documents";
export type { Figure, NewFigure } from "./figures";
export type { HistoryEntry, NewHistoryEntry } from "./history";

export const documentsRelations = relations(documents, ({ many }) => ({
  blocks: many(blocks),
  figures: many(figures),
}));

export const blocksRelations = relations(blocks, ({ one }) => ({
  document: one(documents, {
    fields: [blocks.documentId],
    references: [documents.id],
  }),
}));

export const figuresRelations = relations(figures, ({ one }) => ({
  document: one(documents, {
    fields: [figures.documentId],
    references: [documents.id],
  }),
}));

export const schema = {
  documents,
  blocks,
  figures,
  assets,
  citations,
  history,
  documentsRelations,
  blocksRelations,
  figuresRelations,
};
