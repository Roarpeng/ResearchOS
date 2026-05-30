import { executeStatement, initDatabase } from "../client";

export async function persistHistoryEntry(
  action: string,
  payload: unknown,
): Promise<void> {
  const { sqlite } = await initDatabase();
  await executeStatement(
    sqlite,
    "INSERT INTO history (id, action, payload, created_at) VALUES ($1, $2, $3, $4)",
    [crypto.randomUUID(), action, JSON.stringify(payload), Date.now()],
  );
}
