"""Productive-1 R3 deterministic repair-targeting controls.

Ports only the justified structured numeric-targeting behavior onto the
PAC-corrected candidate-producer architecture and freezes the explicit
conclusion-support prompt requirement. Existing validators, gates, retry
count, provider/model routing, persistence, and promotion semantics remain
unchanged.
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


def _marker(idx, metric, value, role="comparison", er_id=1, dataset=None):
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


def _paper(pairs):
    lines = ["# Paper", "", "## Results", ""]
    for value, marker in pairs:
        lines.append(f"The method achieves {value} {marker} on the eval.")
    return "\n".join(lines)


def _directive(targets=(), context=()):
    return RevisionDirective(
        blocking_findings=("numeric_fidelity failed",),
        research_question="rq",
        task_type="classification",
        target_name="target",
        executed_method="sigmoid calibration",
        baseline_method="uncalibrated",
        comparison_method="isotonic",
        primary_metric="accuracy",
        metric_direction="higher",
        dataset_name="iris+wine_quality",
        split_method="shift",
        random_seed=42,
        evidence=EvidenceInvariant(
            result_map=(("RESULT-1", 0.51),),
            source_map=("[SOURCE-1]",),
            experiment_manifest_hash="h",
            dataset_hash="d",
            analysis_code_hash="c",
        ),
        unexecuted_methods_detected=(),
        method_facts=None,
        numeric_repair_targets=targets,
        result_context=context,
    )


def _case4_markers():
    return [
        _marker(1, "iris.0_0_sigmoid_accuracy", 0.51, "comparison", 1),
        _marker(2, "iris.baseline_accuracy", 0.49, "baseline", 1),
        _marker(
            3,
            "wine_quality.0_0_sigmoid_accuracy",
            0.515625,
            "comparison",
            2,
        ),
        _marker(4, "wine_quality.baseline_accuracy", 0.4875, "baseline", 2),
    ]


def test_regr_b1_exact_numeric_target_is_complete_and_untruncated():
    markers = _case4_markers()
    paper = _paper([
        (0.51, "[RESULT-1]"),
        (0.49, "[RESULT-2]"),
        (165.0, "[RESULT-3]"),
        (0.4875, "[RESULT-4]"),
    ])

    targets, context = derive_numeric_repair_targets(paper, markers)

    assert len(targets) == 1
    assert targets[0] == {
        "marker": "[RESULT-3]",
        "rendered_value": "165.0",
        "required_value": 0.515625,
        "metric_name": "wine_quality.0_0_sigmoid_accuracy",
        "role": "comparison",
        "experiment_result_id": 2,
        "artifact_path": "wine_quality/metrics.json",
        "artifact_sha256": markers[2].artifact_sha256,
    }
    assert len(context) == 4


def test_all_numeric_mismatches_are_targeted_without_touching_correct_pairs():
    markers = [
        _marker(i, f"dataset.metric_{i}", 0.10 + i / 1000, er_id=1)
        for i in range(1, 9)
    ]
    pairs = []
    defective = {1, 2, 3, 4, 5, 6}
    for marker in markers:
        rendered = (
            marker.observed_value * 100000
            if marker.marker_index in defective
            else marker.observed_value
        )
        pairs.append((rendered, f"[RESULT-{marker.marker_index}]"))

    targets, context = derive_numeric_repair_targets(_paper(pairs), markers)

    assert {t["marker"] for t in targets} == {
        f"[RESULT-{i}]" for i in defective
    }
    assert len(targets) == 6
    assert len(context) == 8
    assert "[RESULT-7]" not in {t["marker"] for t in targets}
    assert "[RESULT-8]" not in {t["marker"] for t in targets}


def test_full_74_marker_context_preserves_identity_without_collapse():
    markers = []
    pairs = []
    for i in range(74):
        idx = i + 1
        dataset = "iris" if i < 37 else "wine_quality"
        value = 0.1 + i * 0.001
        markers.append(_marker(
            idx,
            f"{dataset}.metric_{i}",
            value,
            "baseline" if i % 2 else "comparison",
            1 if i < 37 else 2,
        ))
        pairs.append((4242.0 if i == 53 else value, f"[RESULT-{idx}]"))

    targets, context = derive_numeric_repair_targets(_paper(pairs), markers)

    assert len(targets) == 1
    assert targets[0]["marker"] == "[RESULT-54]"
    assert targets[0]["required_value"] == 0.153
    assert len(context) == 74
    assert len({row[0] for row in context}) == 74


def test_prompt_carries_targets_context_preservation_and_conclusion_support():
    markers = _case4_markers()
    paper = _paper([
        (0.51, "[RESULT-1]"),
        (0.49, "[RESULT-2]"),
        (165.0, "[RESULT-3]"),
        (0.4875, "[RESULT-4]"),
    ])
    targets, context = derive_numeric_repair_targets(paper, markers)

    prompt = _directive(targets, context).build_revision_prompt()

    assert "NUMERIC REPAIR TARGETS" in prompt
    assert "Required persisted value: 0.515625" in prompt
    assert "PRESERVATION RULE" in prompt
    assert "already correct MUST remain unchanged" in prompt
    assert "Full result context (marker | metric | role | value):" in prompt
    assert "[RESULT-3] | wine_quality.0_0_sigmoid_accuracy | comparison | 0.515625" in prompt
    assert "CONCLUSION SUPPORT" in prompt
    assert "we demonstrate" in prompt
    assert "demonstrates that" in prompt
    assert "experimental results show/indicate" in prompt
    assert "results show/indicate that" in prompt
    assert "MUST include a supporting [RESULT-N] marker" in prompt


def test_no_numeric_target_block_when_validator_finds_no_numeric_defect():
    markers = _case4_markers()
    paper = _paper([
        (0.51, "[RESULT-1]"),
        (0.49, "[RESULT-2]"),
        (0.515625, "[RESULT-3]"),
        (0.4875, "[RESULT-4]"),
    ])
    targets, context = derive_numeric_repair_targets(paper, markers)

    assert targets == ()
    prompt = _directive(targets, context).build_revision_prompt()
    assert "NUMERIC REPAIR TARGETS" not in prompt
    assert "Full result context" in prompt


def test_existing_numeric_validator_remains_authoritative():
    markers = [_marker(1, "iris.accuracy", 0.515625)]
    percentage_scaled = _paper([(51.5625, "[RESULT-1]")])

    mismatches = [
        m for m in validate_claim_result_alignment(percentage_scaled, markers)
        if m.section == "numeric_fidelity"
    ]

    assert len(mismatches) == 1
    assert mismatches[0].marker == "[RESULT-1]"


def test_single_revision_call_and_typed_transport_semantics_unchanged(monkeypatch):
    import backend.pipeline.evaluation.paper_remediator as pr

    @contextlib.contextmanager
    def _fake_session():
        session = MagicMock()
        session.execute = MagicMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))
        session.get = MagicMock(return_value=None)
        session.add = MagicMock()
        session.commit = MagicMock()
        yield session

    monkeypatch.setattr(pr, "get_session", _fake_session)
    monkeypatch.setattr(pr, "_persist_revision", MagicMock())

    provider = MagicMock()
    calls = {"n": 0}

    async def _spy_complete(*args, **kwargs):
        calls["n"] += 1
        prompt = kwargs["messages"][0]["content"]
        assert "NUMERIC REPAIR TARGETS" in prompt
        assert "CONCLUSION SUPPORT" in prompt
        assert "DEFECT-SCOPED PAPER REVISION" in prompt
        raise GatewayTransportError(
            "paper_synthesis", "injected: usage limit reached"
        )

    provider.complete = AsyncMock(side_effect=_spy_complete)

    import backend.providers.provider_factory as pf
    monkeypatch.setattr(pf, "get_generation_provider", lambda settings: provider)

    markers = _case4_markers()
    paper = _paper([
        (0.51, "[RESULT-1]"),
        (0.49, "[RESULT-2]"),
        (165.0, "[RESULT-3]"),
        (0.4875, "[RESULT-4]"),
    ])
    spec = SimpleNamespace(
        research_question="rq",
        task_type="classification",
        target_name="t",
        analysis_method="m",
        baseline_method="b",
        comparison_method="c",
        primary_metric="acc",
        metric_directions={"acc": "higher"},
        dataset_name="d",
        split_method="s",
        random_seed=42,
        dataset_raw_sha256="",
    )

    with pytest.raises(GatewayTransportError):
        asyncio.run(pr.auto_revise_paper(
            proposal_id=1,
            experiment_result_id=1,
            original_paper_md=paper,
            blocking_findings=["numeric_fidelity failed"],
            source_map=[],
            result_markers=markers,
            spec=spec,
        ))

    assert calls["n"] == 1
