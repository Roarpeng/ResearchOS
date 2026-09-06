import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const history = sqliteTable("history", {
  id: text("id").primaryKey(),
  action: text("action").notNull(),
  payload: text("payload").notNull(),
  createdAt: integer("created_at", { mode: "timestamp_ms" }).notNull(),
});

export type HistoryEntry = typeof history.$inferSelect;
export type NewHistoryEntry = typeof history.$inferInsert;
