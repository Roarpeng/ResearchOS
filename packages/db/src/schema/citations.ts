import { sqliteTable, text } from "drizzle-orm/sqlite-core";

export const citations = sqliteTable("citations", {
  id: text("id").primaryKey(),
  doi: text("doi"),
  title: text("title").notNull(),
  authors: text("authors").notNull(),
  journal: text("journal"),
});

export type Citation = typeof citations.$inferSelect;
export type NewCitation = typeof citations.$inferInsert;
