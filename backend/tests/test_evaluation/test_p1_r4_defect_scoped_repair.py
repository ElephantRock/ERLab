"""Productive-1 R4 defect-scoped repair acceptance controls."""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.evaluation.paper_remediator import (
    _assemble_scoped_candidate,
    _build_scoped_revision_prompt,
    _derive_repair_sections,
    _finalize_conclusion_support,
    _parse_scoped_replacements,
    derive_numeric_repair_targets,
)
from backend.pipeline.evaluation.revision_directive import (
    EvidenceInvariant,
    RevisionDirective,
)
from backend.pipeline.experiment.manifest import ResultMarker


def _marker(idx, metric, value, role="comparison"):
    return ResultMarker(
        marker_index=idx,
        marker=f"RESULT-{idx}",
        metric_name=metric,
        observed_value=value,
        artifact_path=f"dataset/{metric}.json",
        artifact_sha256=f"sha{idx:064d}"[:64],
        experiment_result_id=1,
        direction="",
        role=role,
    )


def _spec():
    return SimpleNamespace(
        research_question="Does the method improve accuracy?",
        task_type="classification",
        target_name="label",
        analysis_method="logistic regression",
        baseline_method="majority-class baseline",
        comparison_method="logistic regression",
        primary_metric="accuracy",
        metric_directions={"accuracy": "higher_better"},
        dataset_name="dataset",
        split_method="stratified",
        random_seed=42,
        dataset_raw_sha256="dataset-sha",
    )


def _paper(result_value="9.9", conclusion=None):
    conclusion = conclusion or "We demonstrate that the method improves accuracy."
    return (
        "# Scoped Repair Paper\n\n"
        "## Abstract\n"
        "We study logistic regression on the declared dataset.\n\n"
        "## Introduction\n"
        "This introduction must remain byte-identical. [SOURCE-1]\n\n"
        "## Methods\n"
        "The protocol uses logistic regression and a stratified split.\n\n"
        "## Results\n"
        f"The model achieved {result_value} [RESULT-1] accuracy.\n\n"
        "## Conclusion\n"
        f"{conclusion}\n"
    )


def _directive(targets=(), context=()):
    return RevisionDirective(
        blocking_findings=("claim_result_alignment: numeric_fidelity",),
        research_question="Does the method improve accuracy?",
        task_type="classification",
        target_name="label",
        executed_method="logistic regression",
        baseline_method="majority-class baseline",
        comparison_method="logistic regression",
        primary_metric="accuracy",
        metric_direction="higher_better",
        dataset_name="dataset",
        split_method="stratified",
        random_seed=42,
        evidence=EvidenceInvariant(
            result_map=(("RESULT-1", 0.8),),
            source_map=("[SOURCE-1]",),
            experiment_manifest_hash="manifest",
            dataset_hash="dataset",
            analysis_code_hash="analysis",
        ),
        unexecuted_methods_detected=(),
        method_facts=None,
        numeric_repair_targets=targets,
        result_context=context,
    )


def _claim_result():
    return SimpleNamespace(
        unexecuted_method_in_abstract=None,
        unexecuted_method_in_conclusion=None,
    )


def test_scope_targets_numeric_section_and_unbacked_conclusion_only():
    markers = [_marker(1, "dataset.accuracy", 0.8)]
    paper = _paper()
    targets, _ = derive_numeric_repair_targets(paper, markers)

    sections = _derive_repair_sections(
        paper,
        ["claim_result_alignment: numeric_fidelity"],
        targets,
        markers,
        _claim_result(),
    )

    assert sections == ("results", "conclusion")
    assert "introduction" not in sections
    assert "methods" not in sections


def test_scoped_prompt_excludes_untargeted_paper_sections():
    markers = [_marker(1, "dataset.accuracy", 0.8)]
    paper = _paper()
    targets, context = derive_numeric_repair_targets(paper, markers)
    prompt = _build_scoped_revision_prompt(
        paper, _directive(targets, context), ("results", "conclusion")
    )

    assert "## Results" in prompt
    assert "## Conclusion" in prompt
    assert "This introduction must remain byte-identical" not in prompt
    assert "The protocol uses logistic regression" not in prompt
    assert "Required persisted value: 0.8" in prompt


def test_scoped_assembly_keeps_untargeted_sections_byte_identical():
    paper = _paper()
    replacements = {
        "results": "## Results\nThe model achieved 0.8 [RESULT-1] accuracy.",
        "conclusion": "## Conclusion\nThe analysis evaluates accuracy.",
    }
    revised = _assemble_scoped_candidate(paper, replacements)

    intro = "## Introduction\nThis introduction must remain byte-identical. [SOURCE-1]\n\n"
    methods = "## Methods\nThe protocol uses logistic regression and a stratified split.\n\n"
    assert intro in paper and intro in revised
    assert methods in paper and methods in revised
    assert "9.9 [RESULT-1]" not in revised
    assert "0.8 [RESULT-1]" in revised


def test_parser_requires_every_target_and_unchanged_heading():
    paper = _paper()
    good = (
        "<<<SECTION:results>>>\n"
        "## Results\nThe model achieved 0.8 [RESULT-1] accuracy.\n"
        "<<<END_SECTION>>>\n"
        "<<<SECTION:conclusion>>>\n"
        "## Conclusion\nThe analysis evaluates accuracy.\n"
        "<<<END_SECTION>>>"
    )
    parsed = _parse_scoped_replacements(
        good, ("results", "conclusion"), paper,
    )
    assert set(parsed) == {"results", "conclusion"}

    missing = good.split("<<<SECTION:conclusion>>>", 1)[0]
    assert _parse_scoped_replacements(
        missing, ("results", "conclusion"), paper,
    ) is None

    changed_heading = good.replace("## Results", "## Findings", 1)
    assert _parse_scoped_replacements(
        changed_heading, ("results", "conclusion"), paper,
    ) is None


def test_finalizer_removes_model_added_evidence_mapping_for_unbacked_claim():
    original = _paper(conclusion="Results show that the method improves accuracy.")
    candidate = _paper(
        result_value="0.8",
        conclusion=(
            "Results show that the method improves accuracy [RESULT-1]. "
            "The analysis remains bounded to the declared experiment."
        ),
    )

    finalized, removed, violations = _finalize_conclusion_support(
        original, candidate, ("results", "conclusion"),
    )

    assert violations == []
    assert len(removed) == 1
    assert "Results show that" not in finalized
    assert "The analysis remains bounded" in finalized
    assert "[RESULT-1]" not in finalized.split("## Conclusion", 1)[1]


def test_finalizer_preserves_preexisting_backed_empirical_mapping():
    original = _paper(
        result_value="0.8",
        conclusion="Results show that accuracy improved 0.8 [RESULT-1].",
    )
    candidate = original

    finalized, removed, violations = _finalize_conclusion_support(
        original, candidate, ("conclusion",),
    )

    assert finalized == candidate
    assert removed == []
    assert violations == []


def _fake_sessions():
    @contextlib.contextmanager
    def _session():
        session = MagicMock()
        session.execute = MagicMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))
        session.get = MagicMock(return_value=None)
        session.add = MagicMock()
        session.commit = MagicMock()
        yield session
    return _session


def test_auto_revision_uses_one_scoped_call_and_keeps_pac_candidate_only(monkeypatch):
    import backend.pipeline.evaluation.paper_gate_evaluator as pge
    import backend.pipeline.evaluation.paper_remediator as pr
    import backend.providers.provider_factory as pf

    monkeypatch.setattr(pr, "get_session", _fake_sessions())
    persisted = MagicMock()
    monkeypatch.setattr(pr, "_persist_revision", persisted)

    provider = MagicMock()
    provider.complete = AsyncMock(return_value=(
        "<<<SECTION:results>>>\n"
        "## Results\nThe model achieved 0.8 [RESULT-1] accuracy.\n"
        "<<<END_SECTION>>>\n"
        "<<<SECTION:conclusion>>>\n"
        "## Conclusion\nResults show that the method improves accuracy [RESULT-1]. "
        "The analysis is bounded to the declared experiment.\n"
        "<<<END_SECTION>>>"
    ))
    monkeypatch.setattr(pf, "get_generation_provider", lambda settings: provider)
    monkeypatch.setattr(
        pge,
        "evaluate_paper_gates",
        lambda **kwargs: SimpleNamespace(
            status="ready", gates=[{"gate": "all", "passed": True}],
            blocking_reasons=[],
        ),
    )

    markers = [_marker(1, "dataset.accuracy", 0.8)]
    result = asyncio.run(pr.auto_revise_paper(
        proposal_id=1,
        experiment_result_id=1,
        original_paper_md=_paper(),
        blocking_findings=["claim_result_alignment: numeric_fidelity"],
        source_map=[{"marker": "SOURCE-1"}],
        result_markers=markers,
        spec=_spec(),
    ))

    assert provider.complete.await_count == 1
    prompt = provider.complete.await_args.kwargs["messages"][0]["content"]
    assert "DEFECT-SCOPED PAPER REVISION" in prompt
    assert "This introduction must remain byte-identical" not in prompt
    assert result.success is True
    assert result.promoted is False
    assert result.eval_status == "ready"
    candidate = persisted.call_args.args[3]
    assert "0.8 [RESULT-1]" in candidate
    assert "Results show that" not in candidate
    assert "This introduction must remain byte-identical" in candidate


def test_timeout_is_explicitly_classified_without_candidate_mutation(monkeypatch):
    import backend.pipeline.evaluation.paper_remediator as pr
    import backend.providers.provider_factory as pf

    monkeypatch.setattr(pr, "get_session", _fake_sessions())
    persisted = MagicMock()
    monkeypatch.setattr(pr, "_persist_revision", persisted)

    async def _never_returns(**kwargs):
        await asyncio.sleep(1)
        return "unreachable"

    provider = MagicMock()
    provider.complete = AsyncMock(side_effect=_never_returns)
    monkeypatch.setattr(pf, "get_generation_provider", lambda settings: provider)

    original = _paper()
    result = asyncio.run(pr.auto_revise_paper(
        proposal_id=1,
        experiment_result_id=1,
        original_paper_md=original,
        blocking_findings=["claim_result_alignment: numeric_fidelity"],
        source_map=[{"marker": "SOURCE-1"}],
        result_markers=[_marker(1, "dataset.accuracy", 0.8)],
        spec=_spec(),
        timeout_seconds=0.01,
    ))

    assert provider.complete.await_count == 1
    assert result.success is False
    assert result.promoted is False
    assert result.error == "revision_timeout"
    assert result.revised_paper_hash == result.original_paper_hash
    assert persisted.call_args.args[3] == original
