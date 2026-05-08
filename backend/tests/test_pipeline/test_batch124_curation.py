"""BATCH-124 Tests — Curation Rules Engine.

AIV v5.3 — 6 tests.
"""

import logging
import pytest

from backend.pipeline.curation.models import CurationRule
from backend.pipeline.curation.engine import CurationEngine


def _sample_papers():
    return [
        {"id": "p1", "title": "Transformer Architecture for NLP", "abstract": "We propose a new attention mechanism", "authors": "Vaswani et al.", "venue": "NeurIPS"},
        {"id": "p2", "title": "A Survey of Deep Learning Methods", "abstract": "We survey 100 deep learning papers", "authors": "Smith et al.", "venue": "arXiv"},
        {"id": "p3", "title": "BERT Pre-training for Language Understanding", "abstract": "We pre-train bidirectional representations", "authors": "Devlin et al.", "venue": "NAACL"},
        {"id": "p4", "title": "GPT-3 Language Model", "abstract": "We train a 175B parameter autoregressive model", "authors": "Brown et al.", "venue": "NeurIPS"},
        {"id": "p5", "title": "Image Classification with ResNet", "abstract": "We propose residual connections for vision", "authors": "He et al.", "venue": "CVPR"},
    ]


class TestCurationEngine:
    def test_curation_rule_creates(self):
        """TEST-124-01-01: CurationRule creates with all fields."""
        rule = CurationRule(rule_id="r1", rule_type="must_include", field="keyword", value="transformer")
        assert rule.rule_id == "r1"
        assert rule.enabled is True

    def test_filter_empty_input(self):
        """TEST-124-01-02: filter returns [] on empty input (HB-01)."""
        engine = CurationEngine(rules=[])
        assert engine.filter([]) == []  # HB-01

    def test_must_include_keyword(self):
        """TEST-124-01-03: must_include keyword matches papers."""
        rules = [CurationRule(rule_id="r1", rule_type="must_include", field="keyword", value="transformer")]
        engine = CurationEngine(rules=rules)
        result = engine.filter(_sample_papers())
        assert len(result) >= 1
        assert any("Transformer" in p["title"] for p in result)

    def test_must_exclude_keyword(self):
        """TEST-124-01-04: must_exclude keyword removes papers."""
        rules = [CurationRule(rule_id="r1", rule_type="must_exclude", field="keyword", value="survey")]
        engine = CurationEngine(rules=rules)
        result = engine.filter(_sample_papers())
        assert not any("Survey" in p["title"] for p in result)

    def test_invalid_rule_skipped(self, caplog):
        """TEST-124-01-05: Invalid rule skipped with warning (HB-02)."""
        rules = [CurationRule(rule_id="bad", rule_type="unknown_type", field="keyword", value="test")]
        engine = CurationEngine(rules=rules)
        with caplog.at_level(logging.WARNING):
            result = engine.filter(_sample_papers())
        # Should not crash, returns papers unchanged
        assert len(result) == 5  # HB-02

    def test_max_papers_limits(self):
        """TEST-124-01-06: max_papers limits output."""
        rules = [CurationRule(rule_id="r1", rule_type="max_papers", field="keyword", value=2)]
        engine = CurationEngine(rules=rules)
        result = engine.filter(_sample_papers())
        assert len(result) == 2
