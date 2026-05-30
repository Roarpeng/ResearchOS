import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { documents } from "./documents";

export const blocks = sqliteTable("blocks", {
  id: text("id").primaryKey(),
  documentId: text("document_id")
    .notNull()
    .references(() => documents.id, { onDelete: "cascade" }),
  type: text("type").notNull(),
  content: text("content").notNull(),
  position: integer("position").notNull(),
});

export type Block = typeof blocks.$inferSelect;
export type NewBlock = typeof blocks.$inferInsert;
