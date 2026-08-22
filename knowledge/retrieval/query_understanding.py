"""Rule-based query understanding (no LLM required).

Produces language, intent (question / comparison / list), expanded query
(synonym table), extracted model-like entities, ``need_hyde``, and per-channel
bias weights. Pure heuristics; deterministic and cheap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Built-in synonym table: canonical term -> expansion candidates.
# Only appended to the original query, never replacing it.
_SYNONYMS: dict[str, list[str]] = {
    "扭矩": ["torque", "转矩", "额定扭矩", "峰值扭矩"],
    "噪音": ["噪声", "异响", "noise", "吵"],
    "差评": ["投诉", "吐槽", "负面", "痛点", "不满"],
    "痛点": ["差评", "投诉", "负面", "defect", "issue"],
    "装配": ["安装", "组装", "上手", "setup"],
    "对比": ["比较", "差异", "区别", "vs", "竞品"],
    "价格": ["售价", "报价", "成本", "price"],
    "功率": ["power", "功耗", "瓦数"],
    "续航": ["电池", "battery", "续航时间"],
    "安全": ["safety", "防护", "保护"],
    "精度": ["accuracy", "误差", "重复定位"],
}

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "comparison": [
        "对比", "比较", "差异", "区别", "vs", "versus", "竞品",
        "哪个", "更", "compare", "difference", "better", "worse",
    ],
    "list": [
        "有哪些", "列举", "列表", "所有", "哪些", "都有什么", "清单",
        "list", "enumerate", "all",
    ],
}

_REVIEW_KEYWORDS = [
    "差评", "好评", "口碑", "痛点", "体验", "噪音", "噪声", "异响", "故障",
    "难用", "装配", "安装", "好不好", "怎么样", "review", "complaint",
    "pain", "noise", "issue", "problem", "experience",
]

_SPEC_UNIT_RE = re.compile(r"\d+(\.\d+)?\s*(Nm|N·m|W|kW|V|rpm|RPM|mm|kg|Hz|°C)")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_MODEL_TOKEN_RE = re.compile(r"\b[A-Z]{1,6}(?:-[A-Z0-9]{1,8}|\d{2,5})(?:-[A-Z0-9]{1,6})?\b")


@dataclass
class QueryUnderstanding:
    raw: str
    language: str = "unknown"
    intent: str = "question"
    entities: list[str] = field(default_factory=list)
    expanded_query: str = ""
    synonyms_applied: list[str] = field(default_factory=list)
    need_hyde: bool = False
    channel_bias: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "language": self.language,
            "intent": self.intent,
            "entities": self.entities,
            "expanded_query": self.expanded_query,
            "synonyms_applied": self.synonyms_applied,
            "need_hyde": self.need_hyde,
            "channel_bias": dict(self.channel_bias),
        }


def detect_language(query: str) -> str:
    has_cjk = bool(_CJK_RE.search(query or ""))
    has_latin = bool(_LATIN_RE.search(query or ""))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return "unknown"


def classify_intent(query: str) -> str:
    q = (query or "").lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(k.lower() in q for k in keywords):
            return intent
    return "question"


def extract_model_entities(query: str) -> list[str]:
    seen: list[str] = []
    for m in _MODEL_TOKEN_RE.findall(query or ""):
        if m.isdigit() and len(m) == 4:  # year false-positive
            continue
        if m not in seen:
            seen.append(m)
    return seen


def expand_keywords(query: str) -> tuple[str, list[str]]:
    terms: list[str] = []
    applied: list[str] = []
    for key, variants in _SYNONYMS.items():
        if key in query:
            terms.extend(v for v in variants if v not in query)
            applied.append(key)
    if not terms:
        return query, []
    return f"{query} {' '.join(terms)}".strip(), applied


def _channel_bias(intent: str, *, need_hyde: bool, spec_like: bool) -> dict[str, float]:
    if intent == "comparison":
        return {"graph": 1.4, "vector": 1.0, "bm25": 1.0}
    if intent == "list":
        return {"graph": 1.0, "vector": 1.2, "bm25": 0.9}
    # question
    if need_hyde:
        return {"graph": 0.7, "vector": 1.3, "bm25": 0.8}
    if spec_like:
        return {"graph": 0.8, "vector": 0.7, "bm25": 1.4}
    return {"graph": 1.0, "vector": 1.0, "bm25": 1.0}


def understand_query(query: str) -> QueryUnderstanding:
    raw = query or ""
    language = detect_language(raw)
    intent = classify_intent(raw)
    entities = extract_model_entities(raw)
    expanded, applied = expand_keywords(raw)
    need_hyde = any(k in raw.lower() for k in _REVIEW_KEYWORDS)
    spec_like = bool(_SPEC_UNIT_RE.search(raw))
    bias = _channel_bias(intent, need_hyde=need_hyde, spec_like=spec_like)
    return QueryUnderstanding(
        raw=raw,
        language=language,
        intent=intent,
        entities=entities,
        expanded_query=expanded,
        synonyms_applied=applied,
        need_hyde=need_hyde,
        channel_bias=bias,
    )
