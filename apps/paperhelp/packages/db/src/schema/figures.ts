import { sqliteTable, text } from "drizzle-orm/sqlite-core";
import { documents } from "./documents";

export const figures = sqliteTable("figures", {
  id: text("id").primaryKey(),
  documentId: text("document_id")
    .notNull()
    .references(() => documents.id, { onDelete: "cascade" }),
  layout: text("layout").notNull(),
  metadata: text("metadata").notNull(),
});

export type Figure = typeof figures.$inferSelect;
export type NewFigure = typeof figures.$inferInsert;
