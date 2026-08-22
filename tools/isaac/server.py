"""Isaac Sim MCP — mock backend implementing docs/industrial/03-cad-and-isaacsim.md
acceptance slice: ``submit → status → artifacts`` without a GPU.

Real Isaac nodes plug in behind the same tool surface later (proxy queue);
``ISAAC_BACKEND=real`` is reserved and refuses until a proxy is configured.
Trials require an explicit ``approved=True`` (docs: 未批准时提交被拒绝;
Runtime HITL interrupt feeds this flag).
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("isaac")

SCENE_TEMPLATES: list[dict[str, str]] = [
    {"id": "narrow_corridor_pick", "title": "Narrow corridor grasp", "metrics": ["collisions", "trajectory_error_cm", "cycle_time_s"]},
    {"id": "bin_picking_random", "title": "Randomized bin picking", "metrics": ["pick_success_rate", "cycle_time_s"]},
    {"id": "palletizing_cycle", "title": "Palletizing cycle", "metrics": ["cycle_time_s", "payload_sway_mm"]},
    {"id": "dual_arm_handover", "title": "Dual-arm handover", "metrics": ["collisions", "handover_success_rate"]},
]

_LOCK = threading.Lock()
_TRIALS: dict[str, dict[str, Any]] = {}


def _backend() -> str:
    import os

    return os.getenv("ISAAC_BACKEND", "mock").strip().lower()


def _new_trial_id(scene: str, seed: int) -> str:
    digest = hashlib.sha1(f"{scene}|{seed}|{time.time_ns()}".encode()).hexdigest()[:10]
    return f"trial_{digest}"


def _deterministic_metrics(scene: str, seed: int, duration_s: int) -> dict[str, float]:
    """Stable pseudo-metrics so CI assertions are reproducible per seed."""
    blob = hashlib.sha256(f"{scene}|{seed}|{duration_s}".encode()).digest()
    def u(i: int) -> float:
        return blob[i] / 255.0
    return {
        "collisions": float(blob[0] % 4),
        "trajectory_error_cm": round(0.5 + u(1) * 4.0, 3),
        "cycle_time_s": round(max(2.0, min(duration_s, 1800) * (0.6 + u(2) * 0.8)), 2),
        "pick_success_rate": round(0.7 + u(3) * 0.29, 3),
    }


@mcp.tool(name="isaac.scene.list")
def isaac_scene_list() -> dict[str, Any]:
    """Available scene templates and their metric schemas."""
    return {"ok": True, "backend": _backend(), "scenes": SCENE_TEMPLATES}


@mcp.tool(name="isaac.trial.submit")
def isaac_trial_submit(
    scene: str,
    duration_s: int = 60,
    seed: int = 0,
    robot_asset: str = "",
    approved: bool = False,
) -> dict[str, Any]:
    """Submit a trial; requires explicit approval (HITL gate per docs)."""
    if not approved:
        return {
            "ok": False,
            "error": "approval_required",
            "detail": "confirm scene/duration with the engineer before submitting",
            "scene": scene,
        }
    if _backend() != "mock":
        return {"ok": False, "error": "backend_unavailable", "detail": f"isaac backend {_backend()!r} not configured"}
    if not any(s["id"] == scene for s in SCENE_TEMPLATES):
        return {"ok": False, "error": "invalid_argument", "detail": f"unknown scene {scene!r}"}
    duration_s = max(1, min(int(duration_s), 1800))
    trial_id = _new_trial_id(scene, int(seed))
    metrics = _deterministic_metrics(scene, int(seed), duration_s)
    trial = {
        "trial_id": trial_id,
        "scene": scene,
        "duration_s": duration_s,
        "seed": int(seed),
        "robot_asset": robot_asset,
        "status": "completed",
        "submitted_at": time.time(),
        "metrics": metrics,
    }
    with _LOCK:
        _TRIALS[trial_id] = trial
    return {"ok": True, **{k: trial[k] for k in ("trial_id", "scene", "status")}}


@mcp.tool(name="isaac.trial.status")
def isaac_trial_status(trial_id: str) -> dict[str, Any]:
    trial = _TRIALS.get(trial_id)
    if trial is None:
        return {"ok": False, "error": "not_found", "trial_id": trial_id}
    return {
        "ok": True,
        "trial_id": trial_id,
        "status": trial["status"],
        "scene": trial["scene"],
        "duration_s": trial["duration_s"],
    }


@mcp.tool(name="isaac.trial.artifacts")
def isaac_trial_artifacts(trial_id: str) -> dict[str, Any]:
    """Metrics JSON + log lines produced by the (mock) run."""
    trial = _TRIALS.get(trial_id)
    if trial is None:
        return {"ok": False, "error": "not_found", "trial_id": trial_id}
    log_lines = [
        f"[isaac-mock] scene={trial['scene']} seed={trial['seed']}",
        f"[isaac-mock] duration={trial['duration_s']}s robot={trial['robot_asset'] or 'default'}",
        f"[isaac-mock] metrics={trial['metrics']}",
    ]
    return {
        "ok": True,
        "trial_id": trial_id,
        "status": trial["status"],
        "artifacts": [
            {"kind": "metrics.json", "data": trial["metrics"]},
            {"kind": "log.txt", "lines": log_lines},
        ],
    }


@mcp.tool(name="isaac.trial.cancel")
def isaac_trial_cancel(trial_id: str) -> dict[str, Any]:
    trial = _TRIALS.get(trial_id)
    if trial is None:
        return {"ok": False, "error": "not_found", "trial_id": trial_id}
    if trial["status"] in {"completed", "cancelled"}:
        return {"ok": False, "error": "not_cancellable", "status": trial["status"]}
    trial["status"] = "cancelled"
    return {"ok": True, "trial_id": trial_id, "status": "cancelled"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
