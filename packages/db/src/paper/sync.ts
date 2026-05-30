import {
  useAssetStore,
  useEditorStore,
  useFigureStore,
  type Asset,
  type Figure,
} from "@paperhelp/shared";
import type { SqliteDatabase } from "../client";
import { executeStatement, selectRows } from "../client";
import { assetContainerPath, extensionFromPath, joinContainerPath } from "./format";

export interface ReadImageAssetResult {
  path: string;
  hash: string;
  width: number;
  height: number;
  mime: string;
  thumbnail: string;
}

export interface SyncContext {
  getEditorJSON: () => unknown;
  setEditorJSON: (json: unknown) => void;
  readImageAsset: (path: string) => Promise<ReadImageAssetResult>;
}

interface DocumentRow extends Record<string, unknown> {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

interface BlockRow extends Record<string, unknown> {
  id: string;
  document_id: string;
  type: string;
  content: string;
  position: number;
}

interface AssetRow extends Record<string, unknown> {
  id: string;
  path: string;
  hash: string;
  width: number;
  height: number;
}

interface FigureRow extends Record<string, unknown> {
  id: string;
  document_id: string;
  layout: string;
  metadata: string;
}

function figureMetadataFromRow(row: FigureRow): Figure {
  const metadata = JSON.parse(row.metadata) as {
    title?: string;
    assetIds?: string[];
    labels?: Figure["labels"];
    annotations?: Figure["annotations"];
    scaleBar?: Figure["scaleBar"];
    style?: Figure["style"];
  };

  return {
    id: row.id,
    title: metadata.title ?? "Untitled Figure",
    assetIds: metadata.assetIds ?? [],
    layout: JSON.parse(row.layout),
    labels: metadata.labels ?? [],
    annotations: metadata.annotations ?? [],
    scaleBar: metadata.scaleBar,
    style: metadata.style ?? {
      labelFontSize: 14,
      labelColor: "#111827",
      labelBackground: "#ffffffcc",
      backgroundColor: "#f3f4f6",
    },
  };
}

async function clearDocumentTables(sqlite: SqliteDatabase): Promise<void> {
  await executeStatement(sqlite, "DELETE FROM blocks");
  await executeStatement(sqlite, "DELETE FROM figures");
  await executeStatement(sqlite, "DELETE FROM assets");
  await executeStatement(sqlite, "DELETE FROM documents");
}

export async function syncStoresToDb(
  sqlite: SqliteDatabase,
  context: SyncContext = getSyncContext(),
): Promise<{ documentId: string }> {
  const editorState = useEditorStore.getState();
  const figureState = useFigureStore.getState();
  const assetState = useAssetStore.getState();

  const documentId = editorState.documentId ?? crypto.randomUUID();
  const title = editorState.title.trim() || "Untitled";
  const now = Date.now();
  const editorJSON = context.getEditorJSON();

  await clearDocumentTables(sqlite);

  await executeStatement(
    sqlite,
    "INSERT INTO documents (id, title, created_at, updated_at) VALUES ($1, $2, $3, $4)",
    [documentId, title, now, now],
  );

  await executeStatement(
    sqlite,
    "INSERT INTO blocks (id, document_id, type, content, position) VALUES ($1, $2, $3, $4, $5)",
    [crypto.randomUUID(), documentId, "tiptap", JSON.stringify(editorJSON), 0],
  );

  for (const asset of Object.values(assetState.assets)) {
    const ext = extensionFromPath(asset.path);
    const containerPath = assetContainerPath(asset.hash, ext);
    await executeStatement(
      sqlite,
      "INSERT INTO assets (id, path, hash, width, height) VALUES ($1, $2, $3, $4, $5)",
      [asset.id, containerPath, asset.hash, asset.width, asset.height],
    );
  }

  for (const figure of Object.values(figureState.figures)) {
    const metadata = {
      title: figure.title,
      assetIds: figure.assetIds,
      labels: figure.labels,
      annotations: figure.annotations,
      scaleBar: figure.scaleBar,
      style: figure.style,
    };

    await executeStatement(
      sqlite,
      "INSERT INTO figures (id, document_id, layout, metadata) VALUES ($1, $2, $3, $4)",
      [figure.id, documentId, JSON.stringify(figure.layout), JSON.stringify(metadata)],
    );
  }

  if (!editorState.documentId) {
    useEditorStore.getState().setDocumentId(documentId);
  }

  return { documentId };
}

export async function hydrateStoresFromDb(
  sqlite: SqliteDatabase,
  containerRoot: string,
  context: SyncContext,
): Promise<{ documentId: string; title: string }> {
  useEditorStore.getState().reset();
  useFigureStore.getState().reset();
  useAssetStore.getState().reset();

  const documents = await selectRows<DocumentRow>(
    sqlite,
    "SELECT id, title, created_at, updated_at FROM documents ORDER BY updated_at DESC LIMIT 1",
  );
  const document = documents[0];
  if (!document) {
    throw new Error("No document found in .paper container");
  }

  const blocks = await selectRows<BlockRow>(
    sqlite,
    "SELECT id, document_id, type, content, position FROM blocks WHERE document_id = $1 ORDER BY position ASC",
    [document.id],
  );
  const editorBlock =
    blocks.find((block) => block.type === "tiptap") ?? blocks[0];
  if (editorBlock) {
    context.setEditorJSON(JSON.parse(editorBlock.content));
  }

  const assetRows = await selectRows<AssetRow>(
    sqlite,
    "SELECT id, path, hash, width, height FROM assets",
  );
  const assetMap: Record<string, Asset> = {};

  for (const row of assetRows) {
    const absolutePath = row.path.includes(":")
      ? row.path
      : joinContainerPath(containerRoot, row.path);

    const image = await context.readImageAsset(absolutePath);
    const asset: Asset = {
      id: row.id,
      path: absolutePath,
      hash: row.hash,
      width: row.width,
      height: row.height,
      mime: image.mime,
    };
    useAssetStore.getState().addAsset(asset, image.thumbnail);
    assetMap[asset.id] = asset;
  }

  const figureRows = await selectRows<FigureRow>(
    sqlite,
    "SELECT id, document_id, layout, metadata FROM figures WHERE document_id = $1",
    [document.id],
  );
  const figures: Record<string, Figure> = {};
  for (const row of figureRows) {
    const figure = figureMetadataFromRow(row);
    figures[figure.id] = figure;
  }

  useFigureStore.setState({
    figures,
    currentFigureId: null,
    selectedElementId: null,
    layoutPreviews: {},
  });

  useEditorStore.setState((state) => ({
    documentId: document.id,
    title: document.title,
    isDirty: false,
    sessionKey: state.sessionKey + 1,
  }));

  return { documentId: document.id, title: document.title };
}

let syncContext: SyncContext | null = null;

export function registerSyncContext(context: SyncContext): void {
  syncContext = context;
}

export function getSyncContext(): SyncContext {
  if (!syncContext) {
    throw new Error("Paper sync context is not registered");
  }
  return syncContext;
}
