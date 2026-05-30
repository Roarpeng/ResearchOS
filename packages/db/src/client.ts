import Database from "@tauri-apps/plugin-sql";
import { drizzle, type SqliteRemoteDatabase } from "drizzle-orm/sqlite-proxy";
import { getMigrationStatements, MIGRATIONS } from "./migrate";
import { schema } from "./schema";

export const DEFAULT_DB_PATH = "sqlite:paperhelp.db";

type SqliteDatabase = Awaited<ReturnType<typeof Database.load>>;

export type PaperHelpDatabase = SqliteRemoteDatabase<typeof schema>;

export interface InitDatabaseResult {
  db: PaperHelpDatabase;
  sqlite: SqliteDatabase;
}

let sqliteInstance: SqliteDatabase | null = null;
let drizzleInstance: PaperHelpDatabase | null = null;

function isSelectQuery(sql: string): boolean {
  return sql.trimStart().toLowerCase().startsWith("select");
}

async function runProxyQuery(
  sqlite: SqliteDatabase,
  sql: string,
  params: unknown[],
  method: "all" | "run" | "get" | "values",
): Promise<{ rows: unknown[] }> {
  if (isSelectQuery(sql)) {
    const rows = await sqlite.select<Record<string, unknown>[]>(sql, params);
    const rowList = Array.isArray(rows) ? rows : rows ? [rows] : [];
    const values = rowList.map((row) => Object.values(row));
    const results = method === "all" ? values : values[0] ?? [];
    return { rows: Array.isArray(results) ? results : [results] };
  }

  await sqlite.execute(sql, params);
  return { rows: [] };
}

function createDrizzle(sqlite: SqliteDatabase): PaperHelpDatabase {
  return drizzle(
    (sql, params, method) => runProxyQuery(sqlite, sql, params, method),
    { schema },
  );
}

async function ensureMigrationTable(sqlite: SqliteDatabase): Promise<void> {
  await sqlite.execute(
    `CREATE TABLE IF NOT EXISTS _migrations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      applied_at INTEGER NOT NULL
    )`,
    [],
  );
}

async function getAppliedMigrationNames(sqlite: SqliteDatabase): Promise<Set<string>> {
  const rows = await sqlite.select<Array<{ name: string }>>(
    "SELECT name FROM _migrations",
    [],
  );
  const rowList = Array.isArray(rows) ? rows : rows ? [rows] : [];
  return new Set(rowList.map((row) => row.name));
}

export async function runMigrations(sqlite: SqliteDatabase): Promise<void> {
  await ensureMigrationTable(sqlite);
  const applied = await getAppliedMigrationNames(sqlite);

  for (const migration of MIGRATIONS) {
    if (applied.has(migration.name)) {
      continue;
    }

    for (const statement of getMigrationStatements(migration)) {
      await sqlite.execute(statement, []);
    }

    await sqlite.execute("INSERT INTO _migrations (name, applied_at) VALUES ($1, $2)", [
      migration.name,
      Date.now(),
    ]);
  }
}

export async function initDatabase(
  connectionString: string = DEFAULT_DB_PATH,
): Promise<InitDatabaseResult> {
  if (sqliteInstance && drizzleInstance) {
    return { db: drizzleInstance, sqlite: sqliteInstance };
  }

  const sqlite = await Database.load(connectionString);
  await runMigrations(sqlite);

  sqliteInstance = sqlite;
  drizzleInstance = createDrizzle(sqlite);

  return { db: drizzleInstance, sqlite };
}

export async function closeDatabase(): Promise<void> {
  if (!sqliteInstance) {
    return;
  }

  await sqliteInstance.close();
  sqliteInstance = null;
  drizzleInstance = null;
}

export async function selectRows<T extends Record<string, unknown>>(
  sqlite: SqliteDatabase,
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const rows = await sqlite.select<T[]>(sql, params);
  return Array.isArray(rows) ? rows : rows ? [rows] : [];
}

export async function executeStatement(
  sqlite: SqliteDatabase,
  sql: string,
  params: unknown[] = [],
): Promise<void> {
  await sqlite.execute(sql, params);
}
