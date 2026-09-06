import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const assets = sqliteTable("assets", {
  id: text("id").primaryKey(),
  path: text("path").notNull(),
  hash: text("hash").notNull(),
  width: integer("width").notNull(),
  height: integer("height").notNull(),
});

export type Asset = typeof assets.$inferSelect;
export type NewAsset = typeof assets.$inferInsert;
