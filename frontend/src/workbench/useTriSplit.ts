import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  CANVAS_MIN,
  CHAT_MAX,
  CHAT_MIN,
  clamp,
  HISTORY_COLLAPSED_W,
  HISTORY_MAX,
  HISTORY_MIN,
  isTypingTarget,
  loadTriSizes,
  PANE_STEP,
  TRI_DEFAULT,
  TRI_SIZES_KEY,
} from "./layout";

export function useTriSplit() {
  const initialTri = loadTriSizes();
  const [historyW, setHistoryW] = useState(initialTri.history);
  const [chatW, setChatW] = useState(initialTri.chat);
  const [historyCollapsed, setHistoryCollapsed] = useState(initialTri.historyCollapsed);
  const triRef = useRef<HTMLDivElement | null>(null);
  const historyWRef = useRef(historyW);
  const chatWRef = useRef(chatW);
  const historyShownW = historyCollapsed ? HISTORY_COLLAPSED_W : historyW;

  useEffect(() => {
    historyWRef.current = historyW;
  }, [historyW]);
  useEffect(() => {
    chatWRef.current = chatW;
  }, [chatW]);
  useEffect(() => {
    localStorage.setItem(
      TRI_SIZES_KEY,
      JSON.stringify({ history: historyW, chat: chatW, historyCollapsed }),
    );
  }, [historyW, chatW, historyCollapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey) return;
      if (e.key !== "[" && e.key !== "]") return;
      e.preventDefault();
      const grow = e.key === "]";
      const delta = grow ? PANE_STEP : -PANE_STEP;
      const hostW = triRef.current?.getBoundingClientRect().width ?? 1200;
      if (e.altKey) {
        if (historyCollapsed) {
          if (grow) setHistoryCollapsed(false);
          return;
        }
        setHistoryW((w) => {
          const maxHistory = Math.max(
            HISTORY_MIN,
            hostW - chatWRef.current - CANVAS_MIN - 14,
          );
          return clamp(w + delta, HISTORY_MIN, Math.min(HISTORY_MAX, maxHistory));
        });
        return;
      }
      setChatW((w) => {
        const hist = historyCollapsed ? HISTORY_COLLAPSED_W : historyWRef.current;
        const maxChat = Math.max(CHAT_MIN, hostW - hist - CANVAS_MIN - 14);
        return clamp(w + delta, CHAT_MIN, Math.min(CHAT_MAX, maxChat));
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [historyCollapsed]);

  function onTriSplitPointerDown(which: "history" | "chat", e: ReactPointerEvent<HTMLDivElement>) {
    if (which === "history" && historyCollapsed) return;
    e.preventDefault();
    const host = triRef.current;
    if (!host) return;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    document.body.classList.add("col-resizing");
    const startX = e.clientX;
    const startHistory = historyW;
    const startChat = chatW;
    const hostW = host.getBoundingClientRect().width;
    const histNow = historyCollapsed ? HISTORY_COLLAPSED_W : startHistory;

    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      if (which === "history") {
        const next = clamp(startHistory + dx, HISTORY_MIN, HISTORY_MAX);
        const maxHistory = Math.max(HISTORY_MIN, hostW - startChat - CANVAS_MIN - 14);
        setHistoryW(Math.min(next, maxHistory));
      } else {
        const next = clamp(startChat + dx, CHAT_MIN, CHAT_MAX);
        const maxChat = Math.max(CHAT_MIN, hostW - histNow - CANVAS_MIN - 14);
        setChatW(Math.min(next, maxChat));
      }
    };
    const up = (ev: PointerEvent) => {
      el.releasePointerCapture(ev.pointerId);
      document.body.classList.remove("col-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function resetTriSplit(which: "history" | "chat") {
    if (which === "history") {
      setHistoryCollapsed(false);
      setHistoryW(TRI_DEFAULT.history);
    } else setChatW(TRI_DEFAULT.chat);
  }

  function toggleHistoryCollapsed() {
    setHistoryCollapsed((c) => !c);
  }

  return {
    chatW,
    historyCollapsed,
    historyShownW,
    historyW,
    onTriSplitPointerDown,
    resetTriSplit,
    toggleHistoryCollapsed,
    triRef,
  };
}
