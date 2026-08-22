import { useMemo, useState } from "react";
import type { ResearchEvent } from "./researchModel";

function formatTs(ts: string): string {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return ts;
  }
}

function eventTone(type: string): string {
  const t = type.toLowerCase();
  if (/(fail|error|cancel)/.test(t)) return "bad";
  if (/(interrupt|wait|human)/.test(t)) return "busy";
  if (/(final|completed|end)/.test(t)) return "ok";
  return "idle";
}

type Props = {
  events: ResearchEvent[];
  max?: number;
};

/** Task event stream — chronological plan/step/tool/message flow. */
export default function Timeline({ events, max = 500 }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const shown = useMemo(() => {
    const sorted = [...events].sort(
      (a, b) => a.ts.localeCompare(b.ts) || (a.seq ?? 0) - (b.seq ?? 0),
    );
    return sorted.slice(-max);
  }, [events, max]);

  if (!shown.length) {
    return (
      <div className="timeline">
        <p className="empty">暂无事件 — 研究任务开始后，这里会实时展示阶段、工具与消息流。</p>
      </div>
    );
  }

  return (
    <div className="timeline" aria-label="任务时间线">
      <ul className="timeline-list">
        {shown.map((e, i) => {
          const isOpen = expanded === i;
          const hasPayload = Object.keys(e.payload).length > 0;
          return (
            <li key={`${e.seq ?? "e"}-${i}`} className={`timeline-item tone-${eventTone(e.type)}`}>
              <div className="timeline-row">
                <span className="timeline-dot" aria-hidden="true" />
                <span className="timeline-type">{e.type}</span>
                <span className="timeline-summary" title={e.summary}>
                  {e.summary}
                </span>
                <span className="timeline-ts">{formatTs(e.ts)}</span>
                {hasPayload ? (
                  <button
                    type="button"
                    className="ghost compact"
                    aria-expanded={isOpen}
                    onClick={() => setExpanded(isOpen ? null : i)}
                  >
                    {isOpen ? "收起" : "详情"}
                  </button>
                ) : null}
              </div>
              {isOpen && hasPayload ? (
                <pre className="timeline-detail">{JSON.stringify(e.payload, null, 2)}</pre>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
