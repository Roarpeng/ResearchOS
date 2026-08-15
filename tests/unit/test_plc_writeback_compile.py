"""Unit tests — writeback stages SCL and does not archive on compile-fail."""

from __future__ import annotations

from pathlib import Path

from agents.plc.tia.changeset import PlcChangeOp, PlcChangeSet
from agents.plc.tia.writeback import execute_writeback, prepare_writeback


def test_execute_writeback_stages_scl_and_skips_archive_on_compile_fail(
    tmp_path: Path, monkeypatch
):
    bundle_root = tmp_path / "export"
    cs = PlcChangeSet(
        id="wb",
        ops=[
            PlcChangeOp(
                kind="rewrite_scl",
                payload={
                    "block_name": "FB_Motor",
                    "scl_text": (
                        'FUNCTION_BLOCK "FB_Motor"\n'
                        "BEGIN\n    #Q := TRUE;\nEND_FUNCTION_BLOCK\n"
                    ),
                },
            )
        ],
        notes=["optimize_plan:# plan\n"],
    )
    bundle = prepare_writeback(bundle_root, cs, [])
    staged = list((bundle / "external_sources").glob("*.scl"))
    assert staged, "expected staged .scl in import_bundle/external_sources"

    calls: list[str] = []

    def fake_xml(*_a, **_k):
        raise AssertionError("XML import should not run when no XML staged")

    def fake_scl(project_path, scl_path, **_k):
        calls.append(f"scl:{Path(scl_path).name}")
        return {"ok": True, "generate": {"ok": True}}

    def fake_compile(project_path, **_k):
        calls.append("compile")
        return {
            "ok": False,
            "compile": {
                "ok": False,
                "apiAvailable": True,
                "state": "Error",
                "errorCount": 2,
                "inconsistentBlocks": ["FB_Motor"],
                "error": {"code": "compile_failed", "message": "Compile State=Error errors=2"},
            },
        }

    def fake_archive(*_a, **_k):
        calls.append("archive")
        raise AssertionError("must not archive when compile fails")

    monkeypatch.setattr(
        "agents.plc.tia.writeback.import_block_via_openness_cli", fake_xml
    )
    monkeypatch.setattr(
        "agents.plc.tia.writeback.generate_from_source_via_openness_cli", fake_scl
    )
    monkeypatch.setattr(
        "agents.plc.tia.writeback.compile_plc_via_openness_cli", fake_compile
    )

    project = tmp_path / "Line.ap19"
    project.write_bytes(b"fake")
    result = execute_writeback(project, bundle, plc_name="PLC_1")
    assert result["import_ok"] is True
    assert result["compiled_ok"] is False
    assert result["ok"] is False
    assert result["scl_imported"] == 1
    assert "compile" in calls
    assert any(c.startswith("scl:") for c in calls)
    assert "archive" not in calls
    compile = result["compile"]["compile"]
    assert compile["inconsistentBlocks"] == ["FB_Motor"]


def test_confirm_job_writeback_no_zap_on_compile_fail(tmp_path: Path, monkeypatch):
    from gateway.app.services import plc_jobs as plc

    export = tmp_path / "job_export"
    export.mkdir()
    job = {
        "id": "plc_test",
        "status": "ready",
        "project_path": str(tmp_path / "Line.ap19"),
        "export_dir": str(export),
        "knowledge_graph": {"nodes": [], "edges": []},
        "blocks": [{"name": "FB_Motor", "type": "FB", "body_available": True}],
        "source_xmls": [],
        "changeset": PlcChangeSet(
            id="cs1",
            ops=[
                PlcChangeOp(
                    kind="rewrite_scl",
                    payload={
                        "block_name": "FB_Motor",
                        "scl_text": 'FUNCTION_BLOCK "FB_Motor"\nBEGIN\nEND_FUNCTION_BLOCK\n',
                    },
                )
            ],
        ).to_dict(),
    }
    (tmp_path / "Line.ap19").write_bytes(b"fake")

    monkeypatch.setattr(
        "agents.plc.tia.writeback.generate_from_source_via_openness_cli",
        lambda *a, **k: {"ok": True},
    )
    monkeypatch.setattr(
        "agents.plc.tia.writeback.compile_plc_via_openness_cli",
        lambda *a, **k: {
            "ok": False,
            "compile": {
                "ok": False,
                "apiAvailable": True,
                "errorCount": 1,
                "inconsistentBlocks": ["FB_Motor"],
            },
        },
    )
    archived = {"called": False}

    def boom(*_a, **_k):
        archived["called"] = True
        raise AssertionError("archive must not run")

    monkeypatch.setattr(
        "agents.plc.tia.openness_cli.archive_project_via_openness_cli", boom
    )

    result = plc.confirm_job_writeback(
        job,
        project_path=str(tmp_path / "Line.ap19"),
        execute_openness_import=True,
        archive_zap=True,
    )
    assert result.get("zap_path") is None
    assert result.get("zap_archive", {}).get("ok") is False
    assert archived["called"] is False
    assert result["openness"]["ok"] is False
