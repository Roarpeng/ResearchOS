"""Engineer-understanding interview loop: welcome, persist facts, grounded optimize."""

from __future__ import annotations

from gateway.app.services.chat_turns import _assistant_from_plc
from gateway.app.services.plc_jobs import answer_block_chat
from agents.plc.tia.optimize import propose_optimization_changeset
from agents.plc.tia.understanding import (
    format_welcome_interview,
    ingest_engineer_reply,
    is_understanding_thin,
)
from tests.unit.test_plc_nested_fb_type import _job_from_project, _nested_project
from tests.unit.test_plc_analyst import _job as _analyst_job


def test_welcome_asks_questions_instead_of_claiming_understanding():
    job = _analyst_job()
    text = format_welcome_interview(job)
    assert "我还没懂" in text
    assert "画布已更新" in text
    assert "需要你确认" in text
    assert "扫描调用链（顺序来自逻辑图 CALLS）" not in text
    assert "本工程整体结构" not in text
    # Evidence chips, not an architecture essay
    assert "`Main`" in text or "`FB_A`" in text
    assert "工艺主控" in text

    wrapped = _assistant_from_plc({**job, "status": "ready", "source_type": "upload"})
    assert "我还没懂" in wrapped
    assert "画布已更新" in wrapped or "程序块" in wrapped
    assert "扫描调用链（顺序来自逻辑图 CALLS）" not in wrapped


def test_engineer_replies_are_stored_and_reused():
    job = _analyst_job()
    stored = ingest_engineer_reply(job, "这条线是金刚石钻削产线，负责上下料和钻孔。", None)
    assert stored
    assert "金刚石" in str(job["engineer_understanding"]["process_narrative"])

    stored2 = ingest_engineer_reply(job, "工艺主控", "FB_A")
    assert stored2
    roles = job["engineer_understanding"]["roles"]
    assert roles["FB_A"]["role"] == "process_main"
    assert roles["FB_A"]["label"] == "工艺主控"

    ack = answer_block_chat(job, "@FB_orphan 不要动", "FB_orphan")
    assert "已记下" in ack
    assert "不要动" in ack
    assert "FB_orphan" in job["engineer_understanding"]["constraints"]["do_not_touch"]

    hints = answer_block_chat(job, "优化建议", None)
    assert "金刚石" in hints
    assert "工艺主控" in hints
    assert "不要动" in hints
    assert not is_understanding_thin(job)


def test_optimize_advice_without_facts_asks_with_facts_cites():
    job = _analyst_job()
    thin = answer_block_chat(job, "优化建议", None)
    assert "优化建议" in thin or "优化提示" in thin
    assert "确认还不够" in thin or "需要你确认" in thin
    assert "编造" in thin or "不是结论" in thin or "只提问" in thin
    assert "拍平" not in thin or "未确认" in thin or "必须" in thin

    ingest_engineer_reply(job, "工艺主控", "FB_A")
    ingest_engineer_reply(job, "不要动", "FB_orphan")
    rich = answer_block_chat(job, "@FB_A 优化建议", "FB_A")
    assert "你确认" in rich or "工程师确认" in rich
    assert "工艺主控" in rich
    assert "FB_A" in rich


def test_optimize_propose_skips_must_keep_and_do_not_touch():
    job = _analyst_job()
    ingest_engineer_reply(job, "不要动", "FB_orphan")
    cs = propose_optimization_changeset(job)
    orphan_writes = [
        o
        for o in cs.ops
        if o.payload.get("block_name") == "FB_orphan"
        and o.kind in {"rewrite_scl", "stage_scl_source", "stage_xml_import", "set_block_comment"}
    ]
    assert orphan_writes == []
    plan = next(n for n in cs.notes if str(n).startswith("optimize_plan:"))
    assert "不要动" in plan
    assert "FB_orphan" in plan

    nested = _job_from_project(_nested_project())
    ingest_engineer_reply(nested, "必须的多实例", "FB_A")
    assert "FB_A" in nested["engineer_understanding"]["constraints"]["must_keep_nested"]
    cs2 = propose_optimization_changeset(nested, focus_block="FB_A")
    flatten = [
        o
        for o in cs2.ops
        if o.payload.get("block_name") == "FB_A"
        and o.kind in {"rewrite_scl", "stage_scl_source", "stage_xml_import"}
    ]
    assert flatten == []
    plan2 = next(n for n in cs2.notes if str(n).startswith("optimize_plan:"))
    assert "必须" in plan2 and "多实例" in plan2
    assert "不拍平" in plan2 or "跳过" in plan2


def test_nested_fb_questions_distinguish_required_vs_accidental():
    job = _job_from_project(_nested_project())
    welcome = format_welcome_interview(job)
    assert "必须的西门子多实例" in welcome
    assert "意外耦合" in welcome
    assert "FB_A" in welcome and "FB_B" in welcome
    assert "拍平" in welcome

    ask = answer_block_chat(job, "@FB_A 这个块干什么", "FB_A")
    assert "必须的西门子多实例" in ask or "意外耦合" in ask

    ack = answer_block_chat(job, "@FB_A 必须的多实例", "FB_A")
    assert "已记下" in ack
    nest = job["engineer_understanding"]["nested"]["FB_A"]
    assert nest["kind"] == "required_multi_instance"

    advice = answer_block_chat(job, "@FB_A 优化建议", "FB_A")
    assert "不建议拍平" in advice or "必须" in advice
    assert "FB_B" in advice and "FB_C" in advice

    other = _job_from_project(_nested_project())
    ingest_engineer_reply(other, "意外耦合", "FB_A")
    acc = answer_block_chat(other, "@FB_A 优化建议", "FB_A")
    assert "意外耦合" in acc
    assert "拍平" in acc or "提取" in acc
