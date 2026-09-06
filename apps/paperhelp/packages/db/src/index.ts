export {
  closeDatabase,
  DEFAULT_DB_PATH,
  executeStatement,
  initDatabase,
  runMigrations,
  selectRows,
} from "./client";
export type {
  InitDatabaseResult,
  PaperHelpDatabase,
} from "./client";

export { getMigrationStatements, MIGRATIONS, MIGRATION_0000_NAME } from "./migrate";
export type { MigrationDefinition } from "./migrate";

export * from "./schema";
export * from "./paper";
export * from "./autosave";
export { persistHistoryEntry } from "./history/persist";
