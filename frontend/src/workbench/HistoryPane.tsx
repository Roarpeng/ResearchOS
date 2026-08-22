import type { MouseEvent } from "react";
import { statusTone } from "./layout";
import type { Topic } from "./model";

type HistoryPaneProps = {
  activeId: string | null;
  collapsed: boolean;
  topics: Topic[];
  width: number;
  onClearAll: () => Promise<void> | void;
  onDeleteTopic: (topic: Topic, event: MouseEvent<HTMLButtonElement>) => Promise<void> | void;
  onOpenTopic: (topic: Topic) => Promise<void> | void;
  onStartNew: () => void;
  onToggleCollapsed: () => void;
};

export function HistoryPane({
  activeId,
  collapsed,
  topics,
  width,
  onClearAll,
  onDeleteTopic,
  onOpenTopic,
  onStartNew,
  onToggleCollapsed,
}: HistoryPaneProps) {
  return (
    <aside
      className={`col history${collapsed ? " collapsed" : ""}`}
      aria-label="历史话题"
      style={{ flex: `0 0 ${width}px`, width }}
    >
      {collapsed ? (
        <button
          type="button"
          className="history-expand"
          title="展开历史栏"
          aria-label="展开历史栏"
          onClick={onToggleCollapsed}
        >
          <span className="history-expand-label">历史</span>
        </button>
      ) : (
        <>
          <div className="col-head">
            <h2>历史</h2>
            <div className="col-head-actions">
              <button
                type="button"
                className="ghost compact"
                title="折叠历史栏"
                aria-label="折叠历史栏"
                onClick={onToggleCollapsed}
              >
                «
              </button>
              {topics.length ? (
                <button
                  type="button"
                  className="ghost compact"
                  title="清空全部历史"
                  onClick={() => void onClearAll()}
                >
                  清空
                </button>
              ) : null}
              <button type="button" className="ghost compact" onClick={onStartNew}>
                新建
              </button>
            </div>
          </div>
          <ul className="topic-list">
            {topics.length === 0 ? (
              <li className="empty-li">暂无话题</li>
            ) : (
              topics.map((t) => (
                <li key={t.id} className="topic-row">
                  <button
                    type="button"
                    className={t.id === activeId ? "topic on" : "topic"}
                    onClick={() => void onOpenTopic(t)}
                  >
                    <span className="topic-title">{t.title}</span>
                    <span className={`topic-meta tone-${statusTone(t.status)}`}>{t.status}</span>
                  </button>
                  <button
                    type="button"
                    className="topic-delete"
                    title="删除此对话"
                    aria-label={`删除 ${t.title}`}
                    onClick={(e) => void onDeleteTopic(t, e)}
                  >
                    ×
                  </button>
                </li>
              ))
            )}
          </ul>
        </>
      )}
    </aside>
  );
}
