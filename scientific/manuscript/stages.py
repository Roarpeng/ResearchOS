"""Manuscript pipeline stage machine (ADR-0010, SCIENTIFIC-DOMAIN-SPEC §3)."""

from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    OUTLINE = "outline"
    EVIDENCE = "evidence"
    FIGURE_PLAN = "figure_plan"
    DRAFTING = "drafting"
    REVIEW = "review"
    JOURNALIZE = "journalize"
    EXPORTED = "exported"


_SEQUENCE: list[Stage] = [
    Stage.OUTLINE,
    Stage.EVIDENCE,
    Stage.FIGURE_PLAN,
    Stage.DRAFTING,
    Stage.REVIEW,
    Stage.JOURNALIZE,
    Stage.EXPORTED,
]

_INDEX = {s: i for i, s in enumerate(_SEQUENCE)}


def stage_index(stage: Stage | str) -> int:
    return _INDEX[Stage(stage)]


def next_stage(stage: Stage | str) -> Stage | None:
    i = stage_index(stage)
    return _SEQUENCE[i + 1] if i + 1 < len(_SEQUENCE) else None


def allowed_transition(source: Stage | str, target: Stage | str) -> bool:
    """Forward moves (any distance) plus REVIEW loop-back to DRAFTING for rework."""
    s, t = Stage(source), Stage(target)
    if s == Stage.REVIEW and t == Stage.DRAFTING:
        return True
    return stage_index(t) > stage_index(s)


def is_terminal(stage: Stage | str) -> bool:
    return Stage(stage) == Stage.EXPORTED
