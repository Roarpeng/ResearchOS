import { useState } from "react";
import { ingestVault, scanVault, searchKnowledge } from "../api";

/** Research-folder capture panel: scan → ingest → grounded search. */
export function VaultPanel({ onClose }: { onClose: () => void }) {
  const [root, setRoot] = useState("");
  const [scan, setScan] = useState<{ count: number; supported: number } | null>(null);
  const [ingest, setIngest] = useState<{
    scanned: number;
    ingested: number;
    skipped_unchanged: number;
    failed: number;
    details: Array<Record<string, unknown>>;
  } | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<
    Array<{ citation_id: string; score: number; text: string; source_id: string }>
  >([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onScan() {
    setBusy(true);
    setError(null);
    try {
      const r = await scanVault(root);
      setScan({ count: r.count, supported: r.supported });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onIngest() {
    setBusy(true);
    setError(null);
    try {
      const r = await ingestVault(root);
      setIngest(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSearch() {
    setBusy(true);
    setError(null);
    try {
      const r = await searchKnowledge(query, undefined, 6, "hybrid");
      setHits(r.hits);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760 }}>
        <div className="modal-head">
          <h2>资料库 Vault</h2>
          <button type="button" className="ghost" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="modal-body" style={{ display: "grid", gap: 12 }}>
          <label style={{ display: "grid", gap: 4 }}>
            研究文件夹(拖入文献/笔记/数据即可,无需整理)
            <input
              value={root}
              onChange={(e) => setRoot(e.target.value)}
              placeholder="C:\path\to\research\folder"
            />
          </label>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={onScan} disabled={busy || !root}>
              扫描
            </button>
            <button type="button" onClick={onIngest} disabled={busy || !root}>
              入库(增量去重)
            </button>
          </div>

          {scan ? (
            <div>
              扫描:共 {scan.count} 个文件,其中支持解析 {scan.supported} 个
            </div>
          ) : null}

          {ingest ? (
            <div>
              入库:扫描 {ingest.scanned} · 新入库 {ingest.ingested} · 未变化跳过{" "}
              {ingest.skipped_unchanged} · 失败 {ingest.failed}
              {ingest.details.length > 0 ? (
                <ul>
                  {ingest.details.slice(0, 20).map((d, i) => (
                    <li key={i} style={{ fontSize: 12 }}>
                      {String(d.path ?? "")} — {String(d.status ?? d.error ?? "")}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <hr />

          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="问你的资料,例如:氮肥对小麦产量的影响"
              style={{ flex: 1 }}
            />
            <button type="button" onClick={onSearch} disabled={busy || !query}>
              检索
            </button>
          </div>

          {hits.length > 0 ? (
            <ol>
              {hits.map((h) => (
                <li key={h.citation_id} style={{ fontSize: 13, marginBottom: 8 }}>
                  <div>{h.text}</div>
                  <div style={{ color: "#667", fontSize: 12 }}>
                    来源 {h.source_id} · score {h.score.toFixed(3)}
                  </div>
                </li>
              ))}
            </ol>
          ) : null}

          {error ? <div style={{ color: "#b33" }}>{error}</div> : null}
        </div>
      </div>
    </div>
  );
}
