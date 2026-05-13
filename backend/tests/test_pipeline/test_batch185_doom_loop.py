"""Tests for BATCH-185: Doom Loop Detection for Pipeline Stages.

AIV §13 Test Integrity: Tests verify behavioral outcomes
(doom detected or not detected), not code structure.
"""

import pytest

from backend.pipeline.monitoring.doom_loop import (
    StageOutputSignature,
    check_pipeline_doom,
    detect_identical_consecutive,
    detect_repeating_sequence,
    extract_stage_fingerprint,
    hash_stage_output,
)


class TestHashStageOutput:
    """hash_stage_output produces consistent hashes."""

    def test_01_string_input(self):
        h1 = hash_stage_output("hello")
        h2 = hash_stage_output("hello")
        assert h1 == h2
        assert len(h1) == 12

    def test_02_dict_canonical_order(self):
        """Dict key order doesn't affect hash."""
        h1 = hash_stage_output({"a": 1, "b": 2})
        h2 = hash_stage_output({"b": 2, "a": 1})
        assert h1 == h2

    def test_03_none_input(self):
        h = hash_stage_output(None)
        assert h == hash_stage_output("")

    def test_04_unicode_content(self):
        h = hash_stage_output("Uberprüfung der Qualität")
        assert len(h) == 12
        assert h == hash_stage_output("Uberprüfung der Qualität")

    def test_05_empty_string(self):
        h = hash_stage_output("")
        assert len(h) == 12

    def test_06_list_input(self):
        h = hash_stage_output(["gap1", "gap2"])
        assert len(h) == 12


class TestDetectIdenticalConsecutive:
    """detect_identical_consecutive catches repeated stage outputs."""

    def _sig(self, stage: str, hash_val: str) -> StageOutputSignature:
        return StageOutputSignature(stage_name=stage, output_hash=hash_val)

    def test_01_three_identical_detected(self):
        sigs = [self._sig("gap_analysis", "abc123")] * 3
        result = detect_identical_consecutive(sigs, threshold=3)
        assert result == "gap_analysis"

    def test_02_two_identical_not_enough(self):
        sigs = [self._sig("gap_analysis", "abc123")] * 2
        result = detect_identical_consecutive(sigs, threshold=3)
        assert result is None

    def test_03_different_outputs_ok(self):
        sigs = [
            self._sig("gap_analysis", "aaa"),
            self._sig("gap_analysis", "bbb"),
            self._sig("gap_analysis", "ccc"),
        ]
        result = detect_identical_consecutive(sigs, threshold=3)
        assert result is None

    def test_04_empty_list(self):
        result = detect_identical_consecutive([], threshold=3)
        assert result is None

    def test_05_realistic_gaps(self):
        """Use realistic gap titles (FLAG-02 from Review)."""
        titles = [
            "Limited understanding of attention head superposition in MoE layers",
            "No systematic comparison of sparse vs dense retrieval for scientific literature",
            "Gap in understanding how retrieval-augmented generation affects factual accuracy",
        ]
        # Same titles 3 times = doom
        hashes = [hash_stage_output(t) for t in titles]
        full_hash = hash_stage_output(titles)
        sigs = [self._sig("gap_analysis", full_hash)] * 3
        result = detect_identical_consecutive(sigs, threshold=3)
        assert result == "gap_analysis"


class TestDetectRepeatingSequence:
    """detect_repeating_sequence catches cyclic patterns."""

    def _sig(self, stage: str, hash_val: str) -> StageOutputSignature:
        return StageOutputSignature(stage_name=stage, output_hash=hash_val)

    def test_01_abab_pattern(self):
        sigs = [
            self._sig("gap_analysis", "aaa"),
            self._sig("idea_generation", "bbb"),
            self._sig("gap_analysis", "aaa"),
            self._sig("idea_generation", "bbb"),
        ]
        result = detect_repeating_sequence(sigs)
        assert result is not None
        assert len(result) == 2

    def test_02_no_pattern(self):
        sigs = [
            self._sig("gap_analysis", "aaa"),
            self._sig("idea_generation", "bbb"),
            self._sig("proposal_synthesis", "ccc"),
        ]
        result = detect_repeating_sequence(sigs)
        assert result is None

    def test_03_abc_abc_pattern(self):
        sigs = [
            self._sig("gap_analysis", "a"),
            self._sig("idea_generation", "b"),
            self._sig("evaluation", "c"),
            self._sig("gap_analysis", "a"),
            self._sig("idea_generation", "b"),
            self._sig("evaluation", "c"),
        ]
        result = detect_repeating_sequence(sigs)
        assert result is not None
        assert len(result) == 3


class TestCheckPipelineDoom:
    """check_pipeline_doom integrates all detection methods."""

    def test_01_empty_history(self):
        assert check_pipeline_doom([]) is None

    def test_02_two_entries_no_doom(self):
        history = [
            {"stage_name": "gap_analysis", "output_hash": "abc"},
            {"stage_name": "gap_analysis", "output_hash": "def"},
        ]
        assert check_pipeline_doom(history) is None

    def test_03_identical_gaps_doom(self):
        """Realistic scenario: gap analysis produces same gaps 3 times."""
        history = [
            {"stage_name": "gap_analysis", "output_hash": "aaa111"},
            {"stage_name": "idea_generation", "output_hash": "bbb222"},
            {"stage_name": "gap_analysis", "output_hash": "aaa111"},
            {"stage_name": "idea_generation", "output_hash": "bbb222"},
        ]
        result = check_pipeline_doom(history)
        assert result is not None
        assert "DOOM LOOP" in result

    def test_04_three_identical_outputs_doom(self):
        history = [
            {"stage_name": "gap_analysis", "output_hash": "same"},
            {"stage_name": "gap_analysis", "output_hash": "same"},
            {"stage_name": "gap_analysis", "output_hash": "same"},
        ]
        result = check_pipeline_doom(history)
        assert result is not None
        assert "gap_analysis" in result


class TestExtractStageFingerprint:
    """extract_stage_fingerprint produces useful fingerprints."""

    def test_01_gap_titles(self):
        gaps = [
            {"title": "Limited understanding of MoE routing"},
            {"title": "No comparison of sparse vs dense retrieval"},
        ]
        fp = extract_stage_fingerprint("gap_analysis", gaps=gaps)
        assert "MoE routing" in fp
        assert "sparse vs dense" in fp

    def test_02_idea_titles_with_scores(self):
        ideas = [
            {"title": "Adaptive MoE Router", "novelty_score": 0.88},
            {"title": "Cross-domain Transfer", "novelty_score": 0.75},
        ]
        fp = extract_stage_fingerprint("idea_generation", ideas=ideas)
        assert "Adaptive MoE Router" in fp
        assert "0.88" in fp

    def test_03_proposal_first_500_chars(self):
        proposals = [
            {"content": "A" * 1000},
            {"content": "B" * 1000},
        ]
        fp = extract_stage_fingerprint("proposal_synthesis", proposals=proposals)
        assert len(fp) <= 1000 + 3 + 1000  # 500 + " | " + 500

    def test_04_other_stage_empty(self):
        fp = extract_stage_fingerprint("literature_search")
        assert fp == ""

    def test_05_none_inputs(self):
        fp = extract_stage_fingerprint("gap_analysis", gaps=None)
        assert fp == ""

    def test_06_realistic_gap_objects(self):
        """Gaps might be objects with .title attribute."""
        gaps = [
            {"title": "Understanding attention patterns in mixture-of-experts models"},
            {"title": "Bridging retrieval-augmented generation with knowledge distillation"},
        ]
        fp = extract_stage_fingerprint("gap_analysis", gaps=gaps)
        assert "attention patterns" in fp
        assert "retrieval-augmented" in fp
