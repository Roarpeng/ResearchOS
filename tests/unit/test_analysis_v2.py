"""Unit tests: analysis v2 specialist fan-out (rule-based, no LLM)."""

from __future__ import annotations

from agents.analysis.node import DEFAULT_SPECIALTIES, run as analysis_run
from runtime.researchos_runtime.state import initial_state


def _state(priority=None):
    state = initial_state("tsk_ana", "对比协作机器人选型")
    state["evidence"] = [
        {
            "id": "ev_1",
            "source_id": "src_a",
            "title": "Model X datasheet",
            "content": (
                "Model X 最大负载 12 kg，重复定位精度 ±0.02 mm，额定功率 1.2 kW，"
                "工作电压 48 V，电流 5 A，关节最高转速 150 rpm，关节扭矩 50 Nm，"
                "防护等级 IP67。"
            ),
            "url": "https://example.com/x",
        },
        {
            "id": "ev_2",
            "source_id": "src_b",
            "title": "Model X 用户评测",
            "content": (
                "用户普遍好评，认为这款协作机器人稳定耐用，重复定位精准；"
                "但部分用户差评，反馈末端抖动明显、噪音偏大，售后维修响应慢，价格偏高。"
            ),
            "url": "https://example.com/reviews",
        },
        {
            "id": "ev_3",
            "source_id": "src_c",
            "title": "报价单",
            "content": (
                "Model X 标准版 ¥128,000，含税，支持分期；租赁方案月租 ¥4,500；"
                "维保年费 $1,200。新品上市折扣 8 折。"
            ),
            "url": "https://example.com/pricing",
        },
        {
            "id": "ev_4",
            "source_id": "src_d",
            "title": "专利公告",
            "content": (
                "本方案涉及力控与力传感器标定技术，核心专利 CN109999999A、"
                "US2019/0123456A1 以及 WO2020/123456A1，权利要求涵盖力传感器标定方法。"
            ),
            "url": "https://example.com/patent",
        },
    ]
    if priority is not None:
        state["goal"]["priority_specialties"] = priority
    return state


def _blocks(state):
    return analysis_run(state)["analysis_results"]


def test_default_runs_all_specialties():
    blocks = _blocks(_state())
    assert set(blocks.keys()) == set(DEFAULT_SPECIALTIES)
    # every default specialist produced non-empty content from this evidence
    for specialty in DEFAULT_SPECIALTIES:
        assert blocks[specialty]["content"], f"{specialty} produced empty content"
        assert blocks[specialty]["citation_ids"], f"{specialty} lacks citation_ids"


def test_specs_extracts_params_into_table():
    block = _blocks(_state())["specs"]
    content = block["content"]
    assert "| 参数 | 数值 | 来源 | 引用 |" in content
    assert "IP67" in content
    assert "kW" in content
    assert "kg" in content
    assert "50 Nm" in content
    assert "TMP:ev_1" in block["citation_ids"]
    assert "TMP:ev_1" in content  # trailing citation id list in content


def test_reviews_counts_polarity_and_pain_points():
    block = _blocks(_state())["reviews"]
    content = block["content"]
    assert "正面评价" in content
    assert "负面评价" in content
    assert "Top 痛点" in content
    assert "抖动" in content  # real pain-point fragment quoted
    assert "TMP:ev_2" in block["citation_ids"]


def test_pricing_extracts_amounts_and_range():
    block = _blocks(_state())["pricing"]
    content = block["content"]
    assert "¥128,000" in content
    assert "月租" in content
    assert "价格区间提示" in content
    assert "折扣" in content  # commercial term keyword
    assert "TMP:ev_3" in block["citation_ids"]


def test_patents_extracts_numbers_and_claims():
    block = _blocks(_state())["patents"]
    content = block["content"]
    assert "CN109999999A" in content
    assert "US2019/0123456A1" in content
    assert "WO2020/123456A1" in content
    assert "权利要求" in content
    assert "TMP:ev_4" in block["citation_ids"]


def test_innovation_clusters_trend_keywords():
    block = _blocks(_state())["innovation"]
    content = block["content"]
    assert "力控" in content
    assert "协作" in content
    assert "安全认证" in content or "防护等级" in content
    assert "TMP:ev_4" in block["citation_ids"]


def test_priority_specialties_limits_fanout():
    blocks = _blocks(_state(["specs", "pricing"]))
    assert set(blocks.keys()) == {"specs", "pricing"}
    assert "reviews" not in blocks
    assert "competitors" not in blocks


def test_unknown_specialties_are_skipped():
    blocks = _blocks(_state(["specs", "bogus"]))
    assert set(blocks.keys()) == {"specs"}


def test_no_evidence_outputs_empty_structure_with_gaps():
    state = initial_state("tsk_empty", "无证据")
    out = analysis_run(state)
    blocks = out["analysis_results"]
    assert set(blocks.keys()) == set(DEFAULT_SPECIALTIES)
    for specialty, block in blocks.items():
        assert block["content"] == "", f"{specialty} should be empty without evidence"
        assert block["citation_ids"] == [], f"{specialty} should have no citations"
        assert block["gaps"], f"{specialty} should record a gap"
