"""Evidence-gated PLC Analyst — deterministic findings from KG."""

from __future__ import annotations

from agents.plc.tia.analyst import (
    analyze_block,
    analyze_project,
    format_analysis_markdown,
)
from gateway.app.services.plc_jobs import answer_block_chat


def _job() -> dict:
    return {
        "project_name": "Demo",
        "summary": {"FB": 2, "OB": 1},
        "blocks": [
            {"name": "Main", "type": "OB", "number": 1, "language": "LAD", "networks": 1},
            {"name": "FB_A", "type": "FB", "number": 10, "language": "LAD", "networks": 1},
            {"name": "FB_orphan", "type": "FB", "number": 99, "language": "LAD", "networks": 0},
        ],
        "knowledge_graph": {
            "nodes": [
                {"id": "Block::Main", "type": "Block", "props": {"name": "Main", "block_type": "OB"}},
                {"id": "Block::FB_A", "type": "Block", "props": {"name": "FB_A", "block_type": "FB"}},
                {
                    "id": "Block::FB_orphan",
                    "type": "Block",
                    "props": {"name": "FB_orphan", "block_type": "FB"},
                },
                {"id": "Tag::MotorRun", "type": "Tag", "props": {"name": "MotorRun"}},
            ],
            "edges": [
                {"source": "Block::Main", "target": "Block::FB_A", "type": "CALLS", "props": {"evidence": "xml_call"}},
                {"source": "Block::FB_A", "target": "Tag::MotorRun", "type": "WRITES"},
                {"source": "Block::FB_A", "target": "Tag::MotorRun", "type": "READS"},
            ],
        },
        "scl_sources": {"FB_A": "FB FB_A\nBEGIN\n    #MotorRun := TRUE;\nEND_FB"},
        "folded_logic": {},
    }


def test_analyze_project_finds_dead_block():
    result = analyze_project(_job())
    assert "FB_orphan" in result["dead_blocks"]
    assert "Main" in result["ob_entry_points"]
    codes = {f["code"] for f in result["findings"]}
    assert "DEAD_BLOCK" in codes
    dead = next(f for f in result["findings"] if f["code"] == "DEAD_BLOCK")
    assert dead["evidence"]


def test_analyze_block_call_graph_evidence():
    result = analyze_block(_job(), "FB_A")
    assert result["calls"]["callers"] == ["Main"]
    codes = {f["code"] for f in result["findings"]}
    assert "CALL_GRAPH" in codes
    call = next(f for f in result["findings"] if f["code"] == "CALL_GRAPH")
    assert any(e.get("edge_type") == "CALLS" for e in call["evidence"])


def test_format_analysis_markdown_chinese():
    md = format_analysis_markdown(analyze_project(_job()))
    assert "证据门控分析" in md
    assert "DEAD_BLOCK" in md or "未从 OB" in md


def test_answer_block_chat_appends_analysis():
    text = answer_block_chat(_job(), "FB_A 做什么？", "FB_A")
    assert "`FB_A`" in text
    assert "作用：" in text
    assert "输入：" in text
    assert "输出：" in text
    # Concise chat: no boilerplate / full evidence appendix
    assert "ResearchOS PLC Intelligence" not in text
    assert "针对你的问题" not in text
    assert "证据门控分析" not in text
    assert "SCL 预览" not in text


def test_answer_resolves_at_mention_and_describes_function():
    text = answer_block_chat(_job(), "@ce 请描述功能", None)
    # ce not in fixture — should stay overview OR we use FB_A
    text2 = answer_block_chat(_job(), "@FB_A 请描述这个功能块的作用", None)
    assert "`FB_A`" in text2
    assert "作用：" in text2
    assert "MotorRun" in text2
    assert "被调用：Main" in text2
