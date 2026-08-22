"""Isaac mock + CAD MCP tests (docs/industrial/03 acceptance slice 1-2)."""

from __future__ import annotations

from tools.cad.server import cad_asset_register, cad_diff_revisions, cad_meta_extract
from tools.isaac.server import (
    isaac_trial_artifacts,
    isaac_trial_cancel,
    isaac_trial_status,
    isaac_trial_submit,
)

_STEP_A = """ISO-10303-21;
HEADER;
FILE_NAME('gripper_rev_a.step','2026-08-01');
ENDSEC;
DATA;
#1=PRODUCT('jaw_left','Gripper jaw left','',());
#2=PRODUCT('jaw_right','Gripper jaw right','',());
#3=NEXT_ASSEMBLY_USAGE_OCCURRENCE('a','b','c',#9,#1,$);
ENDSEC;
END-ISO-10303-21;
"""
_STEP_B = """ISO-10303-21;
HEADER;
FILE_NAME('gripper_rev_b.step','2026-08-20');
ENDSEC;
DATA;
#1=PRODUCT('jaw_left','Gripper jaw left v2','',());
#2=PRODUCT('pad_soft','Soft pad insert','',());
#3=NEXT_ASSEMBLY_USAGE_OCCURRENCE('a','b','c',#9,#1,$);
ENDSEC;
END-ISO-10303-21;
"""


# --- Isaac mock backend ------------------------------------------------------


def test_isaac_submit_requires_approval() -> None:
    res = isaac_trial_submit(scene="narrow_corridor_pick", duration_s=30)
    assert res["ok"] is False
    assert res["error"] == "approval_required"


def test_isaac_full_loop_submit_status_artifacts() -> None:
    sub = isaac_trial_submit(
        scene="narrow_corridor_pick", duration_s=45, seed=7, approved=True
    )
    assert sub["ok"] is True
    tid = sub["trial_id"]

    status = isaac_trial_status(tid)
    assert status["ok"] is True and status["status"] == "completed"

    arts = isaac_trial_artifacts(tid)
    assert arts["ok"] is True
    kinds = {a["kind"] for a in arts["artifacts"]}
    assert {"metrics.json", "log.txt"} <= kinds
    metrics = next(a for a in arts["artifacts"] if a["kind"] == "metrics.json")["data"]
    assert set(metrics) >= {"collisions", "trajectory_error_cm", "cycle_time_s"}


def test_isaac_metrics_deterministic_per_seed() -> None:
    a = isaac_trial_submit(scene="bin_picking_random", duration_s=60, seed=42, approved=True)
    b = isaac_trial_submit(scene="bin_picking_random", duration_s=60, seed=42, approved=True)
    ma = isaac_trial_artifacts(a["trial_id"])["artifacts"][0]["data"]
    mb = isaac_trial_artifacts(b["trial_id"])["artifacts"][0]["data"]
    assert ma == mb


def test_isaac_unknown_scene_and_missing_trial() -> None:
    bad = isaac_trial_submit(scene="does_not_exist", approved=True)
    assert bad["ok"] is False and bad["error"] == "invalid_argument"
    miss = isaac_trial_status("trial_missing")
    assert miss["ok"] is False and miss["error"] == "not_found"


def test_isaac_cancel_completed_is_rejected() -> None:
    sub = isaac_trial_submit(scene="palletizing_cycle", duration_s=10, approved=True)
    res = isaac_trial_cancel(sub["trial_id"])
    assert res["ok"] is False
    assert res["error"] == "not_cancellable"


# --- CAD metadata -------------------------------------------------------------


def test_cad_extract_structure_tree() -> None:
    res = cad_meta_extract(_STEP_A, name="gripper")
    assert res["ok"] is True
    assert res["part_count"] == 2
    assert res["is_assembly"] is True
    names = {p["name"] for p in res["parts"]}
    assert {"jaw_left", "jaw_right"} <= names


def test_cad_diff_revisions() -> None:
    res = cad_diff_revisions(_STEP_A, _STEP_B)
    assert res["ok"] is True
    assert "pad_soft" in res["added"]
    assert "jaw_right" in res["removed"]
    assert "jaw_left" not in res["removed"]


def test_cad_register_and_thumbnail_disabled() -> None:
    reg = cad_asset_register("gripper copy", fmt="STEP", object_key="cad/gripper.step")
    assert reg["ok"] is True and reg["readonly_copy"] is True
    from tools.cad.server import cad_view_thumbnail

    thumb = cad_view_thumbnail(reg["asset_id"])
    assert thumb["ok"] is False and thumb["error"] == "not_enabled"


def test_cad_empty_text_rejected() -> None:
    res = cad_meta_extract("   ")
    assert res["ok"] is False and res["error"] == "invalid_argument"
