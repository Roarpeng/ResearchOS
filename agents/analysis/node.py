"""Analysis Agent node: rule-based specialist fan-out (no-LLM fallback).

Fan-out over ``goal.priority_specialties`` — default is the 7 domain
specialists from docs/agents/04-Analysis-Agents.md plus a ``decision`` memo.
Each specialist reads the shared ``evidence`` list and emits an
``AnalysisBlock`` whose ``content`` quotes real evidence fragments and whose
``citation_ids`` use ``TMP:ev_*`` placeholders (rewritten to stable ``C#`` ids
by the Citation Agent later). When evidence is absent or a specialist finds no
match, it emits an empty structure and records the reason in ``gaps`` — it
never fabricates facts.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState

# 7 domain specialists (docs/agents/04-Analysis-Agents.md) + decision memo.
SPECIALTIES = (
    "specs",
    "reviews",
    "pricing",
    "patents",
    "innovation",
    "competitors",
    "risks",
    "decision",
)
DEFAULT_SPECIALTIES = SPECIALTIES
KNOWN_SPECIALTIES = frozenset(SPECIALTIES)


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #


def _tmp_ref(eid: str) -> str:
    """Citation placeholder; rewritten to ``C#`` by the Citation Agent."""
    return f"TMP:{eid}"


def _eid_of(item: dict[str, Any]) -> str:
    return str(item.get("id") or "")


def _title_of(item: dict[str, Any]) -> str:
    return str(item.get("title") or item.get("source_id") or item.get("id") or "source")


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        eid = _eid_of(item)
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        out.append(item)
    return out


def _refs(items: list[dict[str, Any]]) -> list[str]:
    """TMP:ev_* citation placeholders for the given evidence items (de-duped)."""
    return [_tmp_ref(_eid_of(item)) for item in _dedupe(items) if _eid_of(item)]


def _with_refs(content: str, cite_ids: list[str]) -> str:
    """Append the citation-marker id list to the end of a block's content."""
    if not cite_ids:
        return content
    return content.rstrip() + "\n\n> 引用: " + " · ".join(cite_ids)


def _empty(specialty: str, gaps: list[str]) -> tuple[str, list[str], list[str]]:
    """Empty structure for a specialist with nothing to report."""
    return "", list(gaps), []


def _evidence_summary(evidence: list[dict[str, Any]], max_items: int = 3) -> str:
    parts: list[str] = []
    for item in evidence[:max_items]:
        title = item.get("title") or item.get("id") or "source"
        snippet = (item.get("content") or "")[:180]
        parts.append(f"- {title}: {snippet}")
    return "\n".join(parts) if parts else "- (no evidence)"


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"[^。！？!?；;\n]+", text or "") if s.strip()]


# --------------------------------------------------------------------------- #
# specs — numeric parameter extraction into a comparison table
# --------------------------------------------------------------------------- #

# value + unit pairs (order matters: longer/specific alternatives first).
_SPEC_UNIT_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>"
    r"n·m|n\.m|nm|μm|um|mm|cm|km|kg|mg|g\b|"
    r"kva|kw|kv|mw|w\b|v\b|ma|a\b|"
    r"rpm|r/min|khz|mhz|ghz|thz|hz|"
    r"°c|℃|°f|dba|db|px|mp|lbs|lb|in\b|ft\b"
    r")",
    re.IGNORECASE,
)
_IP_RE = re.compile(r"\bip\s?(?P<num>[0-9]{1,2})\b", re.IGNORECASE)


def _analyze_specs(
    evidence: list[dict[str, Any]], query: str
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("specs", ["specs: no evidence available"])

    rows: list[tuple[str, str, str, str]] = []  # (unit, display, title, eid)
    used: list[dict[str, Any]] = []
    for item in evidence:
        eid = _eid_of(item)
        title = _title_of(item)
        text = str(item.get("content") or "")
        for m in _IP_RE.finditer(text):
            rows.append(("ip", m.group(0).upper(), title, eid))
            used.append(item)
        for m in _SPEC_UNIT_RE.finditer(text):
            raw = m.group(0).strip()
            unit = (m.group("unit") or "").strip().lower()
            rows.append((unit, raw, title, eid))
            used.append(item)

    if not rows:
        return _empty("specs", ["specs: evidence 中未抽取到数值参数"])

    rows.sort(key=lambda r: r[0])
    lines = [
        "## Specs",
        f"规格参数对比（{query}）：",
        "",
        "| 参数 | 数值 | 来源 | 引用 |",
        "|------|------|------|------|",
    ]
    for unit, display, title, eid in rows:
        ref = _tmp_ref(eid) if eid else "-"
        lines.append(f"| {unit} | {display} | {title} | {ref} |")
    lines.append("")
    lines.append("抽取片段：")
    for item in _dedupe(used)[:8]:
        frag = str(item.get("content") or "").strip().replace("\n", " ")
        lines.append(f"- “{frag[:160]}” ({_tmp_ref(_eid_of(item))})")

    cite_ids = _refs(_dedupe(used))
    return _with_refs("\n".join(lines), cite_ids), [], cite_ids


# --------------------------------------------------------------------------- #
# reviews — polarity sentences + pain-point list
# --------------------------------------------------------------------------- #

_POS_RE = re.compile(
    r"好评|优点|可靠|稳定|好用|易用|满意|推荐|耐用|优秀|出色|精准|流畅|安静|省心|"
    r"good|excellent|great|reliable|stable|durable|accurate|smooth|easy|love|"
    r"recommend|recommended|satisfied|robust",
    re.IGNORECASE,
)
_NEG_RE = re.compile(
    r"差评|缺点|痛点|故障|不稳定|难用|不满|延迟|滞后|缺陷|昂贵|噪音|噪声|抖动|误差|"
    r"问题|维修|返修|卡顿|复杂|bug|"
    r"bad|poor|slow|unreliable|noisy|noise|lag|issue|problem|expensive|error|"
    r"buggy|fragile|complex",
    re.IGNORECASE,
)


def _analyze_reviews(
    evidence: list[dict[str, Any]], query: str
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("reviews", ["reviews: no evidence available"])

    pos = neg = 0
    pos_samples: list[tuple[str, str, str]] = []
    neg_samples: list[tuple[str, str, str]] = []
    used: list[dict[str, Any]] = []
    for item in evidence:
        eid = _eid_of(item)
        title = _title_of(item)
        for sent in _split_sentences(str(item.get("content") or "")):
            if _NEG_RE.search(sent):
                neg += 1
                neg_samples.append((sent, title, eid))
                used.append(item)
            elif _POS_RE.search(sent):
                pos += 1
                pos_samples.append((sent, title, eid))
                used.append(item)

    if pos == 0 and neg == 0:
        return _empty("reviews", ["reviews: evidence 中未抽取到极性评价句"])

    lines = [
        "## Reviews",
        f"评价极性统计（{query}）：",
        "",
        f"- 正面评价：{pos} 条",
        f"- 负面评价：{neg} 条",
    ]
    if neg_samples:
        lines.append("")
        lines.append("**Top 痛点（负面）**：")
        for sent, title, eid in neg_samples[:8]:
            ref = _tmp_ref(eid) if eid else "-"
            lines.append(f"- “{sent[:160]}” — {title} ({ref})")
    if pos_samples:
        lines.append("")
        lines.append("**正面代表**：")
        for sent, title, eid in pos_samples[:6]:
            ref = _tmp_ref(eid) if eid else "-"
            lines.append(f"- “{sent[:160]}” — {title} ({ref})")

    cite_ids = _refs(_dedupe(used))
    return _with_refs("\n".join(lines), cite_ids), [], cite_ids


# --------------------------------------------------------------------------- #
# pricing — price points, range hint, commercial terms
# --------------------------------------------------------------------------- #

_PRICE_SYM_RE = re.compile(
    r"(?P<sym>\$|€|£|¥|usd|eur|gbp|cny|rmb|美元|欧元|英镑|人民币)"
    r"\s*(?P<num>\d{1,3}(?:[,\s]\d{3})+|\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_PRICE_UNIT_RE = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>万|亿|千|元|块|美元|欧元|英镑|人民币)",
    re.IGNORECASE,
)
_COMMERCIAL_RE = re.compile(
    r"折扣|优惠|促销|特价|租赁|月租|年租|订阅|维保|保修|质保|维护|分期|含税|不含税|"
    r"discount|promo|lease|rental|subscription|warranty|maintenance|tax",
    re.IGNORECASE,
)

_CURRENCY_NORM = {
    "¥": "CNY", "cny": "CNY", "rmb": "CNY", "人民币": "CNY", "元": "CNY", "块": "CNY",
    "$": "USD", "usd": "USD", "美元": "USD",
    "€": "EUR", "eur": "EUR", "欧元": "EUR",
    "£": "GBP", "gbp": "GBP", "英镑": "GBP",
}
_SCALE = {"万": 1e4, "亿": 1e8, "千": 1e3}


def _num_value(num: str) -> float:
    return float(num.replace(",", "").replace(" ", ""))


def _analyze_pricing(
    evidence: list[dict[str, Any]], query: str
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("pricing", ["pricing: no evidence available"])

    points: list[dict[str, Any]] = []
    terms: list[str] = []
    used: list[dict[str, Any]] = []
    for item in evidence:
        eid = _eid_of(item)
        title = _title_of(item)
        text = str(item.get("content") or "")
        for m in _PRICE_SYM_RE.finditer(text):
            sym = (m.group("sym") or "").strip()
            num = (m.group("num") or "").strip()
            currency = _CURRENCY_NORM.get(sym.lower(), sym.upper())
            points.append(
                {
                    "raw": m.group(0).strip(),
                    "currency": currency,
                    "value": _num_value(num),
                    "title": title,
                    "eid": eid,
                }
            )
            used.append(item)
        for m in _PRICE_UNIT_RE.finditer(text):
            num = (m.group("num") or "").strip()
            unit = (m.group("unit") or "").strip()
            currency = _CURRENCY_NORM.get(unit, "CNY")
            points.append(
                {
                    "raw": m.group(0).strip(),
                    "currency": currency,
                    "value": _num_value(num) * _SCALE.get(unit, 1.0),
                    "title": title,
                    "eid": eid,
                }
            )
            used.append(item)
        for m in _COMMERCIAL_RE.finditer(text):
            term = m.group(0).strip()
            if term not in terms:
                terms.append(term)

    if not points and not terms:
        return _empty("pricing", ["pricing: evidence 中未发现价格或商业条款"])

    lines = ["## Pricing", f"价格点清单（{query}）：", ""]
    if points:
        for p in points[:12]:
            ref = _tmp_ref(p["eid"]) if p["eid"] else "-"
            lines.append(f"- {p['raw']}（{p['currency']}，≈{p['value']:g}）— {p['title']} ({ref})")
        by_cur: dict[str, list[float]] = {}
        for p in points:
            by_cur.setdefault(p["currency"], []).append(p["value"])
        lines.append("")
        lines.append("**价格区间提示**：")
        for cur, vals in by_cur.items():
            lines.append(f"- {cur}：最低 {min(vals):g}，最高 {max(vals):g}（{len(vals)} 条）")
        if len(by_cur) > 1:
            lines.append("- 注意：存在多种币种，需归一后对比。")
    if terms:
        lines.append("")
        lines.append("**商业条款关键词**：" + "、".join(terms))

    cite_ids = _refs(_dedupe(used))
    return _with_refs("\n".join(lines), cite_ids), [], cite_ids


# --------------------------------------------------------------------------- #
# patents — patent numbers + claim-clue sentences
# --------------------------------------------------------------------------- #

_PATENT_RE = re.compile(
    r"\b(?P<kind>CNKA|CN|US|WO|EP|JP|DE|TW|KR|PCT)"
    r"[-\s]?(?P<num>\d{4,}[\d/]{0,18}[A-Z]?\d?)\b",
    re.IGNORECASE,
)
_PATENT_WORD_RE = re.compile(r"专利|patent|权利要求|claim", re.IGNORECASE)


def _analyze_patents(
    evidence: list[dict[str, Any]], query: str
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("patents", ["patents: no evidence available"])

    patents: list[tuple[str, str, str]] = []
    claim_sents: list[tuple[str, str, str]] = []
    used: list[dict[str, Any]] = []
    for item in evidence:
        eid = _eid_of(item)
        title = _title_of(item)
        text = str(item.get("content") or "")
        for m in _PATENT_RE.finditer(text):
            patents.append((m.group(0).strip(), title, eid))
            used.append(item)
        for sent in _split_sentences(text):
            if _PATENT_WORD_RE.search(sent):
                claim_sents.append((sent, title, eid))
                used.append(item)

    if not patents and not claim_sents:
        return _empty("patents", ["patents: evidence 中未发现专利号或权利要求线索"])

    lines = ["## Patents", f"专利线索（{query}）：", ""]
    if patents:
        lines.append("识别到的专利号：")
        for raw, title, eid in patents[:10]:
            ref = _tmp_ref(eid) if eid else "-"
            lines.append(f"- {raw}（{ref}）— {title}")
    if claim_sents:
        lines.append("")
        lines.append("权利要求 / 专利句线索：")
        for sent, title, eid in claim_sents[:8]:
            ref = _tmp_ref(eid) if eid else "-"
            lines.append(f"- “{sent[:160]}” — {title} ({ref})")

    cite_ids = _refs(_dedupe(used))
    return _with_refs("\n".join(lines), cite_ids), [], cite_ids


# --------------------------------------------------------------------------- #
# innovation — tech-trend keyword clustering
# --------------------------------------------------------------------------- #

_TREND_CLUSTERS = {
    "AI / 视觉": (
        "ai", "人工智能", "机器学习", "深度学习", "机器视觉", "视觉", "vision",
        "machine learning", "ml", "神经网络", "neural", "图像识别",
    ),
    "力控 / 力觉": (
        "力控", "力觉", "力传感器", "力矩", "force control", "force sensor",
        "torque control", "触觉",
    ),
    "协作机器人": (
        "协作", "cobot", "collaborative", "人机协作", "human-robot", "human robot",
    ),
    "AMR / 移动": (
        "amr", "agv", "移动机器人", "mobile robot", "自主导航", "autonomous",
        "slam", "无人",
    ),
    "数字孪生 / 仿真": ("数字孪生", "digital twin", "仿真", "simulation"),
    "安全认证": (
        "安全认证", "safety", "iso 10218", "iso/ts 15066", "认证", "certification",
        "防护等级",
    ),
    "实时 / 边缘控制": (
        "边缘", "edge", "实时控制", "real-time", "realtime", "ethercat", "确定性",
    ),
}


def _analyze_innovation(
    evidence: list[dict[str, Any]], query: str
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("innovation", ["innovation: no evidence available"])

    lowered = [(str(item.get("content") or "").lower(), item) for item in evidence]
    hits: list[tuple[str, int, str, str, str]] = []
    used: list[dict[str, Any]] = []
    for cluster, kws in _TREND_CLUSTERS.items():
        count = 0
        sample: str | None = None
        sample_eid = sample_title = ""
        for low, item in lowered:
            if not any(kw in low for kw in kws):
                continue
            count += 1
            if sample is None:
                sample = str(item.get("content") or "").strip().replace("\n", " ")
                sample_eid = _eid_of(item)
                sample_title = _title_of(item)
                used.append(item)
        if count:
            hits.append((cluster, count, sample or "", sample_eid, sample_title))

    if not hits:
        return _empty("innovation", ["innovation: evidence 中未命中已知技术趋势关键词"])

    hits.sort(key=lambda h: -h[1])
    lines = ["## Innovation", f"技术趋势关键词聚类（{query}）：", ""]
    for cluster, count, sample, eid, title in hits:
        ref = _tmp_ref(eid) if eid else "-"
        lines.append(f"- **{cluster}**：命中 {count} 条；代表证据 “{sample[:160]}” — {title} ({ref})")

    cite_ids = _refs(_dedupe(used))
    return _with_refs("\n".join(lines), cite_ids), [], cite_ids


# --------------------------------------------------------------------------- #
# competitors / risks / decision — kept as rule templates, evidence-anchored
# --------------------------------------------------------------------------- #


def _analyze_competitors(
    evidence: list[dict[str, Any]], query: str, summary: str, all_cite_ids: list[str]
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("competitors", ["missing_competitors: no evidence collected"])
    content = (
        f"## Competitors\n"
        f"Based on available evidence for «{query}»:\n{summary}\n\n"
        f"Key players appear across manufacturer docs, industry reports, "
        f"and secondary commentary. Positioning should be validated against "
        f"primary sources before procurement decisions."
    )
    return _with_refs(content, all_cite_ids), [], all_cite_ids


def _analyze_risks(
    evidence: list[dict[str, Any]], query: str, summary: str, all_cite_ids: list[str]
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("risks", ["thin_evidence_for_risk_scoring"])
    gaps = [] if len(evidence) >= 2 else ["thin_evidence_for_risk_scoring"]
    content = (
        f"## Risks\n"
        f"Risk scan for «{query}»:\n{summary}\n\n"
        f"- Supply / vendor concentration risk if relying on a single OEM.\n"
        f"- Compliance risk if standards citations are incomplete.\n"
        f"- Data freshness risk for pricing or certification claims."
    )
    cite_ids = all_cite_ids if evidence else []
    return _with_refs(content, cite_ids), gaps, cite_ids


def _analyze_decision(
    evidence: list[dict[str, Any]], query: str, summary: str, all_cite_ids: list[str]
) -> tuple[str, list[str], list[str]]:
    if not evidence:
        return _empty("decision", ["no_citations_available"])
    content = (
        f"## Decision\n"
        f"Decision memo draft for «{query}»:\n{summary}\n\n"
        f"Recommendation: proceed with a shortlist of vendors backed by "
        f"cited primary documentation; defer final selection until Reviewer "
        f"citation gate passes and Decision Memo fields are complete."
    )
    return _with_refs(content, all_cite_ids), [], all_cite_ids


# --------------------------------------------------------------------------- #
# fan-out dispatcher
# --------------------------------------------------------------------------- #


def _build_block(
    specialty: str,
    evidence: list[dict[str, Any]],
    query: str,
    summary: str,
    all_cite_ids: list[str],
) -> dict[str, Any]:
    if specialty == "specs":
        content, gaps, cite_ids = _analyze_specs(evidence, query)
    elif specialty == "reviews":
        content, gaps, cite_ids = _analyze_reviews(evidence, query)
    elif specialty == "pricing":
        content, gaps, cite_ids = _analyze_pricing(evidence, query)
    elif specialty == "patents":
        content, gaps, cite_ids = _analyze_patents(evidence, query)
    elif specialty == "innovation":
        content, gaps, cite_ids = _analyze_innovation(evidence, query)
    elif specialty == "competitors":
        content, gaps, cite_ids = _analyze_competitors(evidence, query, summary, all_cite_ids)
    elif specialty == "risks":
        content, gaps, cite_ids = _analyze_risks(evidence, query, summary, all_cite_ids)
    else:  # decision
        content, gaps, cite_ids = _analyze_decision(evidence, query, summary, all_cite_ids)
    return {
        "specialty": specialty,
        "content": content,
        "gaps": gaps,
        "citation_ids": cite_ids,
    }


def run(state: TaskState) -> dict[str, Any]:
    goal = state.get("goal") or {}
    query = goal.get("raw_query") or goal.get("normalized_objective") or "topic"
    evidence = [e for e in (state.get("evidence") or []) if isinstance(e, dict)]

    requested = [str(s) for s in (goal.get("priority_specialties") or DEFAULT_SPECIALTIES)]
    specialties: list[str] = []
    seen: set[str] = set()
    for s in requested:
        if s in KNOWN_SPECIALTIES and s not in seen:
            seen.add(s)
            specialties.append(s)
    if not specialties:
        specialties = list(DEFAULT_SPECIALTIES)

    summary = _evidence_summary(evidence)
    all_cite_ids = _refs(evidence)
    now = datetime.now(timezone.utc).isoformat()
    blocks: dict[str, dict[str, Any]] = {
        s: _build_block(s, evidence, query, summary, all_cite_ids) for s in specialties
    }

    return {
        "analysis_results": blocks,
        "events": [
            {
                "type": "analysis.completed",
                "task_id": state.get("task_id", ""),
                "payload": {"specialties": list(blocks.keys())},
                "ts": now,
            }
        ],
        "route": "citation",
    }
