"""Meeting brief: deterministic summary of recent vault notes (R4, LLM polish later)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "was", "are", "from", "have",
    "has", "had", "not", "but", "our", "into", "over", "than", "then", "them",
}

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if w.lower() not in _STOPWORDS]


def build_meeting_brief(
    notes: list[dict[str, Any]],
    *,
    top_n: int = 5,
    keywords: int = 8,
) -> dict[str, Any]:
    """notes: [{title?, text, created_at?, tag?}] → Markdown brief + keywords."""
    recent = sorted(notes, key=lambda n: str(n.get("created_at") or ""), reverse=True)[:top_n]

    counter: Counter[str] = Counter()
    for n in notes:
        counter.update(_tokens(str(n.get("text") or "")))

    top_keywords = [w for w, _ in counter.most_common(keywords)]

    lines = ["# 组会简报", ""]
    if recent:
        for n in recent:
            title = n.get("title") or (str(n.get("text") or "")[:80])
            tag = f" · {n['tag']}" if n.get("tag") else ""
            lines.append(f"- {title}{tag}")
    else:
        lines.append("- (暂无笔记)")
    lines.append("")
    lines.append("## 关键词")
    lines.append("、".join(top_keywords) if top_keywords else "(无)")

    return {"markdown": "\n".join(lines), "recent": recent, "keywords": top_keywords}
