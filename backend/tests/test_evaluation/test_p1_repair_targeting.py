"""Productive-1 deterministic controls (P1-7/P1-8).

The Case-4 final specimen proved the single-shot repair's failure
shape: with the directive's bare `RESULT-N = value` map and no
per-marker targeting, two independent one-shot repairs each fixed five
of six numeric defects and left exactly one (runfail_3: [RESULT-38]
rendered 165.0 vs persisted 0.515625; P1-2 baseline: [RESULT-41]
rendered 197.0 vs persisted ~0.5x — both wine_quality 0-1 accuracies
rendered as counts).

The correction transports information the system already possesses:
structured numeric repair targets from the EXISTING validator, plus full
dataset-qualified result context. No new numeric judgment, no
deterministic post-generation fixer, no second LLM call, no retry loop;
the validator remains the authority and one repair remains the maximum.
"""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.evaluation.claim_result_validator import (
    validate_claim_result_alignment,
)
from backend.pipeline.evaluation.paper_remediator import (
    derive_numeric_repair_targets,
)
from backend.pipeline.evaluation.revision_directive import (
    EvidenceInvariant,
    RevisionDirective,
)
from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.gateway.transport import GatewayTransportError


def _marker(idx, metric, value, role="comparison", er_id=1,
            dataset=None):
    return ResultMarker(
        marker_index=idx,
        marker=f"RESULT-{idx}",
        metric_name=metric,
        observed_value=value,
        artifact_path=f"{dataset or metric.split('.')[0]}/metrics.json",
        artifact_sha256=f"sha{idx:064d}"[:64],
        experiment_result_id=er_id,
        direction="",
        role=role,
    )


def _case4_shaped_markers():
    """The Case-4 failure shape: two datasets, same metric names,
    0-1 accuracies the model tends to render as counts."""
    return [
        _marker(1, "iris.0_0_sigmoid_accuracy", 0.51, "comparison", 1),
        _marker(2, "iris.baseline_accuracy", 0.49, "baseline", 1),
        _marker(3, "wine_quality.0_0_sigmoid_accuracy", 0.515625,
                "comparison", 2),
        _marker(4, "wine_quality.baseline_accuracy", 0.4875,
                "baseline", 2),
    ]


def _paper(pairs):
    """Build a paper rendering `value [RESULT-n]` for each pair."""
    lines = ["# Paper", "", "## Results", ""]
    for value, marker in pairs:
        lines.append(f"The method achieves {value} {marker} on the eval.")
    return "\n".join(lines)


def _directive(targets, context, **overrides):
    base = dict(
        blocking_findings=("numeric_fidelity failed",),
        research_question="rq", task_type="classification",
        target_name="target", executed_method="sigmoid calibration",
        baseline_method="uncalibrated", comparison_method="isotonic",
        primary_metric="accuracy", metric_direction="higher",
        dataset_name="iris+wine_quality", split_method="shift",
        random_seed=42,
        evidence=EvidenceInvariant(
            result_map=(("RESULT-1", 0.51),),
            source_map=("[S1]",),
            experiment_manifest_hash="h", dataset_hash="d",
            analysis_code_hash="c",
        ),
        unexecuted_methods_detected=(),
        method_facts=None,
        numeric_repair_targets=targets,
        result_context=context,
    )
    base.update(overrides)
    return RevisionDirective(**base)


# ── P1-7: target derivation ────────────────────────────────────────────


class TestTargetDerivation:
    def test_case4_shaped_defect_yields_exact_untruncated_target(self):
        markers = _case4_shaped_markers()
        # The exact observed defect: a 0-1 accuracy rendered as a count.
        paper = _paper([
            (0.51, "[RESULT-1]"),
            (0.49, "[RESULT-2]"),
            (165.0, "[RESULT-3]"),   # defective: persisted 0.515625
            (0.4875, "[RESULT-4]"),
        ])
        targets, context = derive_numeric_repair_targets(paper, markers)
        assert len(targets) == 1
        t = targets[0]
        assert t["marker"] == "[RESULT-3]"
        assert t["rendered_value"] == "165.0"
        assert t["required_value"] == 0.515625
        assert t["metric_name"] == "wine_quality.0_0_sigmoid_accuracy"
        assert t["role"] == "comparison"
        assert t["experiment_result_id"] == 2
        assert t["artifact_path"] == "wine_quality/metrics.json"
        assert len(t["artifact_sha256"]) == 64

    def test_correct_pairs_not_marked_for_repair(self):
        markers = _case4_shaped_markers()
        paper = _paper([
            (0.51, "[RESULT-1]"),
            (0.49, "[RESULT-2]"),
            (0.515625, "[RESULT-3]"),
            (0.4875, "[RESULT-4]"),
        ])
        targets, _ = derive_numeric_repair_targets(paper, markers)
        assert targets == ()

    def test_same_metric_two_datasets_distinguishable(self):
        markers = [
            _marker(1, "iris.accuracy", 0.7, "comparison", 1),
            _marker(2, "wine_quality.accuracy", 0.8, "comparison", 2),
        ]
        paper = _paper([(0.7, "[RESULT-1]"), (123.0, "[RESULT-2]")])
        targets, context = derive_numeric_repair_targets(paper, markers)
        assert len(targets) == 1
        assert targets[0]["metric_name"] == "wine_quality.accuracy"
        ctx = {c[0]: c for c in context}
        assert ctx["[RESULT-1]"][1] == "iris.accuracy"
        assert ctx["[RESULT-2]"][1] == "wine_quality.accuracy"

    def test_roles_survive_into_targets_and_context(self):
        markers = _case4_shaped_markers()
        paper = _paper([
            (0.51, "[RESULT-1]"), (999.0, "[RESULT-2]"),
            (0.515625, "[RESULT-3]"), (0.4875, "[RESULT-4]"),
        ])
        targets, context = derive_numeric_repair_targets(paper, markers)
        assert targets[0]["role"] == "baseline"
        ctx = {c[0]: c for c in context}
        assert ctx["[RESULT-2]"][2] == "baseline"
        assert ctx["[RESULT-3]"][2] == "comparison"

    def test_74_marker_scale_no_identity_collapse(self):
        markers = []
        for i in range(74):
            ds = "iris" if i < 37 else "wine_quality"
            markers.append(_marker(
                i + 1, f"{ds}.metric_{i}", 0.1 + i * 0.001,
                "baseline" if i % 2 else "comparison", 1 if i < 37 else 2,
            ))
        pairs = [(0.1 + i * 0.001, f"[RESULT-{i + 1}]") for i in range(74)]
        pairs[53] = (4242.0, "[RESULT-54]")  # one defect
        paper = _paper(pairs)
        targets, context = derive_numeric_repair_targets(paper, markers)
        assert len(targets) == 1
        assert targets[0]["marker"] == "[RESULT-54]"
        assert targets[0]["required_value"] == 0.1 + 53 * 0.001
        assert len(context) == 74
        assert len({c[0] for c in context}) == 74  # no collapsed identities


# ── P1-7: unchanged validator remains the authority ────────────────────


class TestValidatorAuthorityUnchanged:
    def _mismatches(self, paper, markers):
        return [
            m for m in validate_claim_result_alignment(paper, markers)
            if m.section == "numeric_fidelity"
        ]

    def test_wrong_value_still_blocked(self):
        markers = _case4_shaped_markers()
        paper = _paper([(0.51, "[RESULT-1]"), (0.49, "[RESULT-2]"),
                        (0.42, "[RESULT-3]"), (0.4875, "[RESULT-4]")])
        assert len(self._mismatches(paper, markers)) == 1

    def test_percentage_scaling_still_blocked(self):
        markers = [_marker(1, "iris.accuracy", 0.515625)]
        paper = _paper([(51.5625, "[RESULT-1]")])  # x100 percent form
        assert len(self._mismatches(paper, markers)) == 1

    def test_marker_omission_not_marked_referential_prose_ok(self):
        markers = _case4_shaped_markers()
        paper = _paper([(0.51, "[RESULT-1]"), (0.49, "[RESULT-2]")])
        # markers 3/4 simply absent -> referential skip, no failure
        assert self._mismatches(paper, markers) == []


# ── P1-8: prompt contract (exact context the synthesizer receives) ────


class TestPromptContract:
    def _prompt(self, defective=True):
        markers = _case4_shaped_markers()
        pairs = [
            (0.51, "[RESULT-1]"), (0.49, "[RESULT-2]"),
            (165.0 if defective else 0.515625, "[RESULT-3]"),
            (0.4875, "[RESULT-4]"),
        ]
        paper = _paper(pairs)
        targets, context = derive_numeric_repair_targets(paper, markers)
        return _directive(targets, context).build_revision_prompt()

    def test_target_block_carries_full_identity_and_exact_value(self):
        prompt = self._prompt()
        assert "NUMERIC REPAIR TARGETS" in prompt
        assert "[RESULT-3]" in prompt
        assert "wine_quality.0_0_sigmoid_accuracy" in prompt
        assert "role=comparison" in prompt
        assert "165.0" in prompt
        assert "0.515625" in prompt
        # the exact persisted value appears untruncated (repr-safe)
        assert "Required persisted value: 0.515625" in prompt
        assert "Correct only this marker/value attribution" in prompt

    def test_full_result_context_rendered_with_identities(self):
        prompt = self._prompt()
        assert "Full result context (marker | metric | role | value):" in prompt
        assert "[RESULT-1] | iris.0_0_sigmoid_accuracy | comparison | 0.51" in prompt
        assert "[RESULT-2] | iris.baseline_accuracy | baseline | 0.49" in prompt
        assert "[RESULT-4] | wine_quality.baseline_accuracy | baseline | 0.4875" in prompt

    def test_preservation_rule_present(self):
        prompt = self._prompt()
        assert "PRESERVATION RULE" in prompt
        assert "already correct MUST remain unchanged" in prompt

    def test_no_target_block_without_defects(self):
        prompt = self._prompt(defective=False)
        assert "NUMERIC REPAIR TARGETS" not in prompt
        # context still rendered; bare-map fallback only when no context
        assert "Full result context" in prompt

    def test_backward_compatible_bare_map_without_context(self):
        d = _directive((), (), result_context=())
        prompt = d.build_revision_prompt()
        assert "RESULT-1 = 0.51" in prompt
        assert "Full result context" not in prompt

    def test_evidence_hashes_unchanged_by_new_fields(self):
        ev = EvidenceInvariant(
            result_map=(("RESULT-1", 0.51),),
            source_map=("[S1]",), experiment_manifest_hash="h",
            dataset_hash="d", analysis_code_hash="c",
        )
        d1 = _directive((), ())
        d2 = _directive(
            ({"marker": "[RESULT-3]", "rendered_value": "165.0",
              "required_value": 0.515625, "metric_name": "m",
              "role": "comparison", "experiment_result_id": 2,
              "artifact_path": "p", "artifact_sha256": "s"},),
            (("[RESULT-1]", "m", "comparison", 0.51),),
        )
        assert d1.evidence.result_map_hash == d2.evidence.result_map_hash


# ── P1-6: one repair, no fixer, typed transport unchanged ─────────────


class TestSingleCallSemantics:
    def test_one_synthesis_call_and_transport_propagates(self, monkeypatch):
        import backend.pipeline.evaluation.paper_remediator as pr

        @contextlib.contextmanager
        def _fake_session():
            session = MagicMock()
            session.execute = MagicMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)))
            session.get = MagicMock(return_value=None)
            session.add = MagicMock()
            session.commit = MagicMock()
            yield session

        monkeypatch.setattr(pr, "get_session", _fake_session)
        import backend.providers.provider_factory as pf
        monkeypatch.setattr(
            pf, "get_generation_provider", lambda s: MagicMock()
        )

        calls = {"n": 0}

        async def _spy_synthesize(self, **kwargs):
            calls["n"] += 1
            assert "NUMERIC REPAIR TARGETS" in kwargs.get(
                "proposal_text", "")
            assert "0.515625" in kwargs.get("proposal_text", "")
            raise GatewayTransportError(
                "paper_synthesis", "injected: usage limit reached"
            )

        from backend.pipeline.synthesis.paper_synthesizer import (
            PaperSynthesizer,
        )
        monkeypatch.setattr(PaperSynthesizer, "synthesize", _spy_synthesize)

        markers = _case4_shaped_markers()
        paper = _paper([(0.51, "[RESULT-1]"), (0.49, "[RESULT-2]"),
                        (165.0, "[RESULT-3]"), (0.4875, "[RESULT-4]")])
        spec = SimpleNamespace(
            research_question="rq", task_type="classification",
            target_name="t", analysis_method="m", baseline_method="b",
            comparison_method="c", primary_metric="acc",
            metric_directions={"acc": "higher"}, dataset_name="d",
            split_method="s", random_seed=42, dataset_raw_sha256="",
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(pr.auto_revise_paper(
                proposal_id=1, experiment_result_id=1,
                original_paper_md=paper,
                blocking_findings=["numeric_fidelity failed"],
                source_map=[], result_markers=markers, spec=spec,
            ))
        assert calls["n"] == 1  # no retry, no second call
