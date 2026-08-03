"""Unit tests for Reciprocal Rank Fusion ordering."""

from __future__ import annotations

from knowledge.retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_prefers_multi_channel_agreement():
    ranked = {
        "vector": ["a", "b", "c"],
        "bm25": ["c", "a", "d"],
        "graph": ["c", "e"],
    }
    fused = reciprocal_rank_fusion(ranked, k=60)
    ids = [cid for cid, _, _ in fused]
    # c appears in all three → should rank first
    assert ids[0] == "c"
    assert "a" in ids
    channels_c = next(chs for cid, _, chs in fused if cid == "c")
    assert set(channels_c) == {"vector", "bm25", "graph"}


def test_rrf_respects_weights():
    ranked = {
        "vector": ["x", "y"],
        "bm25": ["y", "x"],
    }
    # Heavy BM25 weight should prefer y
    fused = reciprocal_rank_fusion(ranked, k=60, weights={"vector": 0.1, "bm25": 5.0})
    assert fused[0][0] == "y"


def test_rrf_missing_channel_ok():
    fused = reciprocal_rank_fusion({"bm25": ["only"]}, k=10)
    assert fused[0][0] == "only"
    assert fused[0][2] == ["bm25"]
