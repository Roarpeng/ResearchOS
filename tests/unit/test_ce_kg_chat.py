"""CE demo: Main CALLS ce + USES ceD; chat SCL Markdown fence."""

from __future__ import annotations

from pathlib import Path

from agents.plc.tia.flgnet_fold import attach_folded, fold_project
from agents.plc.tia.kg import build_knowledge_graph
from agents.plc.tia.simaticml import extract_project
from gateway.app.services.plc_jobs import _block_list, _logic_graph_from_kg, answer_block_chat

CE = Path(__file__).resolve().parents[1] / "fixtures" / "tia_ce"


def test_ce_kg_main_calls_fc_and_uses_db() -> None:
    project = attach_folded(extract_project(CE, project_name="CeDemo"))
    kg = build_knowledge_graph(project)

    assert set(project.blocks) >= {"Main", "ce", "ceD"}
    assert kg.callees_of("Main") == ["ce"]
    assert kg.callers_of("ce") == ["Main"]
    assert "ceD" in kg.uses_of("Main")
    assert "IEC_Counter_0_DB" in kg.uses_of("ce")

    lg = _logic_graph_from_kg(kg.to_json())
    edges = {(e["type"], e["source"].split("::")[-1], e["target"].split("::")[-1]) for e in lg["edges"]}
    assert ("CALLS", "Main", "ce") in edges
    assert ("USES", "Main", "ceD") in edges
    assert ("USES", "ce", "IEC_Counter_0_DB") in edges
    # USES already covers Main→ceD; no redundant DEPENDS_ON
    assert ("DEPENDS_ON", "Main", "ceD") not in edges


def test_ce_chat_scl_markdown_fence() -> None:
    project = attach_folded(extract_project(CE, project_name="CeDemo"))
    kg = build_knowledge_graph(project)
    job = {
        "project_name": "CeDemo",
        "summary": {},
        "blocks": _block_list(project),
        "knowledge_graph": kg.to_json(),
        "folded_logic": fold_project(project),
        "scl_sources": {},
    }
    text = answer_block_chat(job, "@ce 描述", "ce")
    assert "```scl" in text
    assert "END_IF;" in text
    assert '"IEC_Counter_0_DB"(CU := #in5, PV := 1, CV => #out3);' in text
    assert "被调用：Main" in text
    assert "使用：IEC_Counter_0_DB" in text

    main = answer_block_chat(job, "@Main", "Main")
    assert "调用：ce" in main
    assert "使用：ceD" in main
