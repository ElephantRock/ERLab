"""Regression coverage: empirical synthesis-output fidelity.

Locks the corrective for run_6395d309b07a: the synthesizer rendered
``333333 [RESULT-1]`` beside a persisted ``0.333333`` (and ``966667`` for
``0.966667``), and one empirical conclusion carried no [RESULT-N] backing.
The reconciliation must restore exact persisted values deterministically,
fail closed on anything unrepairable, and re-synthesize once when
empirical conclusions lack markers. The numeric-fidelity validator is the
acceptance oracle: after reconciliation, the validator's own extractor
must find zero mismatches.

Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
import re

import pytest

from backend.pipeline.evaluation import claim_result_validator as crv
from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.synthesis import synthesis_service
from backend.pipeline.synthesis.result_marker_fidelity import (
    ResultMarkerFidelityError,
    build_correction_instruction,
    empirical_claim_violations,
    parse_marker_strings,
    reconcile_marker_values,
)

AUTHORITATIVE = [
    "[RESULT-1] baseline_accuracy = 0.333333 (role=baseline, "
    "direction=higher_better)",
    "[RESULT-2] improvement = 0.633333 (role=derived, "
    "direction=higher_better)",
    "[RESULT-3] model_accuracy = 0.966667 (role=model, "
    "direction=higher_better)",
]


def _markers():
    return parse_marker_strings(AUTHORITATIVE)


def _oracle_mismatches(paper_md: str) -> list:
    """Run the acceptance oracle with ResultMarker objects."""
    objs = []
    for m in _markers():
        objs.append(
            ResultMarker(
                marker_index=int(m.bracket[len("[RESULT-"):-1]),
                marker=m.bracket[1:-1],
                metric_name=m.metric_name,
                observed_value=m.observed_value,
                artifact_path="metrics.json",
                artifact_sha256="0" * 64,
                experiment_result_id=27,
                role="baseline"
                if "baseline" in m.metric_name
                else ("derived" if m.metric_name == "improvement" else "model"),
                direction="higher_better",
            )
        )
    return crv.validate_claim_result_alignment(paper_md, objs)


# ── Parsing ──────────────────────────────────────────────────────


def test_parse_authoritative_marker_string():
    parsed = _markers()
    assert parsed[0].bracket == "[RESULT-1]"
    assert parsed[0].metric_name == "baseline_accuracy"
    assert parsed[0].value_text == "0.333333"
    assert parsed[0].observed_value == pytest.approx(0.333333)


def test_unparseable_marker_string_fails_closed():
    with pytest.raises(ResultMarkerFidelityError):
        parse_marker_strings(["[RESULT-1] no value here"])


# ── Numeric reconciliation ───────────────────────────────────────


def test_exact_values_pass_through_untouched():
    paper = "The baseline scored 0.333333 [RESULT-1] on the frozen split."
    text, report = reconcile_marker_values(paper, _markers())
    assert text == paper
    assert report.ok and not report.repairs


def test_dropped_decimal_repaired_exact_failure_values():
    paper = (
        "The baseline scored 333333 [RESULT-1], and the model reached "
        "966667 [RESULT-3] on the frozen split."
    )
    text, report = reconcile_marker_values(paper, _markers())
    assert report.ok, report.violations
    assert "0.333333 [RESULT-1]" in text
    assert "0.966667 [RESULT-3]" in text
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", text)
    assert not re.search(r"(?<![\d.])966667 \[RESULT-3\]", text)
    # Acceptance oracle: zero mismatches after reconciliation.
    assert _oracle_mismatches(text) == []


def test_percentified_form_repaired_to_fraction():
    paper = "Accuracy reached 33.3333% [RESULT-1] on the frozen split."
    text, report = reconcile_marker_values(paper, _markers())
    assert report.ok, report.violations
    assert "0.333333 [RESULT-1]" in text
    assert "%" not in text
    assert _oracle_mismatches(text) == []


def test_number_after_marker_repaired():
    paper = "The frozen split yields [RESULT-1] of 333333 exactly."
    text, report = reconcile_marker_values(paper, _markers())
    assert report.ok, report.violations
    assert "[RESULT-1] of 0.333333" in text
    assert _oracle_mismatches(text) == []


def test_correct_after_marker_form_untouched():
    paper = "The frozen split yields [RESULT-1] of 0.333333 exactly."
    text, report = reconcile_marker_values(paper, _markers())
    assert text == paper
    assert report.ok and not report.repairs


def test_wrong_digits_fail_closed():
    paper = "The baseline scored 999999 [RESULT-1] on the frozen split."
    text, report = reconcile_marker_values(paper, _markers())
    assert not report.ok
    assert any("999999" in v for v in report.violations)
    assert "999999" in text  # never silently rewritten to a guess


def test_referential_marker_without_number_untouched():
    paper = "See [RESULT-1] for the per-class breakdown on the frozen split."
    text, report = reconcile_marker_values(paper, _markers())
    assert text == paper
    assert report.ok


def test_both_failure_markers_repaired_in_one_pass():
    paper = (
        "Results. 333333 [RESULT-1] baseline; 966667 [RESULT-3] model; "
        "improvement 0.633333 [RESULT-2]."
    )
    text, report = reconcile_marker_values(paper, _markers())
    assert report.ok
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", text)
    assert not re.search(r"(?<![\d.])966667 \[RESULT-3\]", text)
    assert "0.333333 [RESULT-1]" in text
    assert "0.966667 [RESULT-3]" in text
    assert _oracle_mismatches(text) == []


# ── Unbacked empirical conclusions ───────────────────────────────

_FILLER = (
    "The frozen partition is held fixed across every reported measurement, "
    "and each number cited in this study traces to the persisted manifest "
    "with its artifact hash. The protocol predeclares the split, the seed, "
    "the model family, and the metric definitions before execution, so the "
    "reported comparison is reproducible from the checked-in analysis "
    "entrypoint without any tuning, resampling, or post-hoc selection. "
    "Baseline-referenced reporting keeps the interpretation anchored to "
    "what the partition actually supports, and the discussion distinguishes "
    "observations from expectations throughout the paper. "
) * 3


def _paper_with(abstract: str, conclusion: str) -> str:
    return (
        f"# Paper\n\n## Abstract\n{abstract}\n\n"
        f"## Results\n{_FILLER}"
        f"The baseline scored 0.333333 [RESULT-1]; the model "
        f"0.966667 [RESULT-3]; improvement 0.633333 [RESULT-2].\n\n"
        f"## Conclusion\n{conclusion}\n"
    )


def test_unmarked_empirical_conclusion_detected():
    paper = _paper_with(
        "We evaluate a frozen baseline-referenced protocol.",
        "These observed gaps demonstrate that a closed-form classifier "
        "recovers nearly all discriminative signal.",
    )
    violations = empirical_claim_violations(paper, _markers())
    assert violations
    assert any("demonstrates that" in v or "we demonstrate" in v for v in violations)


def test_marker_backed_conclusion_clean():
    paper = _paper_with(
        "We evaluate a frozen baseline-referenced protocol.",
        "The model reached 0.966667 [RESULT-3], an improvement of "
        "0.633333 [RESULT-2] over the 0.333333 [RESULT-1] baseline.",
    )
    assert empirical_claim_violations(paper, _markers()) == []


def test_correction_instruction_quotes_violations():
    instruction = build_correction_instruction(
        ["empirical claim 'demonstrates that' without [RESULT-N] backing"]
    )
    assert "demonstrates that" in instruction
    assert "character-for-character" in instruction
    assert "[RESULT-N]" in instruction


# ── Service-level wiring (monolithic + section fallback) ─────────


class _FakeSynthesizer:
    """PaperSynthesizer stand-in returning scripted papers per call."""

    def __init__(self, papers):
        self._papers = list(papers)
        self.calls = 0

    async def synthesize_session(self, session):
        from backend.pipeline.synthesis.paper_synthesizer import (
            PaperSynthesisResult,
        )

        md = self._papers[min(self.calls, len(self._papers) - 1)]
        self.calls += 1
        return PaperSynthesisResult(
            proposal_id=0,
            paper_markdown=md,
            word_count=len(md.split()),
            venue="Generic",
            model_used="test",
            source_count=0,
        )


def _run_service(monkeypatch, synthesizer, section_fallback=False):
    if section_fallback:
        from backend.pipeline.synthesis.section_wise_synthesizer import (
            SectionDraft,
            SectionWiseSynthesizer,
        )

        async def _outline(self, proposal_text, domain):
            return "outline"

        async def _summary(self, proposal_text):
            return "summary"

        def _select(self, source_text, section_id, section_title, outline):
            return ""

        async def _gen_section(self, **kwargs):
            return SectionDraft(
                section_id=kwargs["section_id"],
                title=kwargs["section_title"],
                content=(
                    "filler "
                    + str(kwargs.get("result_markers") or "")
                    + " bad numbers 333333 [RESULT-1]"
                ),
                word_count=10,
                citations_used=[],
                model_used="test",
            )

        def _assemble(self, drafts, outline, domain, venue, n_sources):
            return "\n".join(d.content for d in drafts)

        monkeypatch.setattr(
            SectionWiseSynthesizer, "_generate_outline", _outline
        )
        monkeypatch.setattr(
            SectionWiseSynthesizer, "_summarize_proposal", _summary
        )
        monkeypatch.setattr(
            SectionWiseSynthesizer, "_select_relevant_sources", _select
        )
        monkeypatch.setattr(SectionWiseSynthesizer, "_generate_section", _gen_section)
        monkeypatch.setattr(SectionWiseSynthesizer, "_assemble_paper", _assemble)

    return asyncio.run(
        synthesis_service.synthesize_paper(
            provider=object(),
            proposal_text="proposal",
            source_papers=[],
            source_ids=[],
            domain="test",
            proposal_id=0,
            budget=None,
            experiment_context="observed: baseline 0.333333, model 0.966667",
            result_markers=list(AUTHORITATIVE),
            synthesizer_override=synthesizer,
        )
    )


def test_service_repairs_values_and_rewrites_unbacked_claims(monkeypatch):
    bad = _paper_with(
        "We evaluate a frozen protocol. 333333 [RESULT-1] baseline on the "
        "frozen split, 966667 [RESULT-3] model.",
        "These observed gaps demonstrate that the classifier recovers "
        "signal without any marker support here.",
    )
    good = _paper_with(
        "We evaluate a frozen protocol. The baseline scored 0.333333 "
        "[RESULT-1] on the frozen split. The model reached 0.966667 "
        "[RESULT-3].",
        "The baseline scored 0.333333 [RESULT-1]. The model reached "
        "0.966667 [RESULT-3]. The improvement was 0.633333 [RESULT-2], "
        "measured against the predeclared majority predictor.",
    )
    synth = _FakeSynthesizer([bad, good])
    result = _run_service(monkeypatch, synth)

    assert result.success
    assert synth.calls == 2  # corrective re-synthesis ran once
    assert "0.333333 [RESULT-1]" in result.paper_markdown
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", result.paper_markdown)
    assert _oracle_mismatches(result.paper_markdown) == []
    assert empirical_claim_violations(result.paper_markdown, _markers()) == []


def test_service_single_pass_when_already_compliant(monkeypatch):
    good = _paper_with(
        "We evaluate a frozen protocol. The baseline scored 0.333333 "
        "[RESULT-1].",
        "The model reached 0.966667 [RESULT-3] over 0.333333 [RESULT-1].",
    )
    synth = _FakeSynthesizer([good])
    result = _run_service(monkeypatch, synth)
    assert result.success
    assert synth.calls == 1


def test_service_fails_closed_on_unrepairable_number(monkeypatch):
    broken = _paper_with(
        "Baseline 999999 [RESULT-1] on the frozen split.",
        "The model reached 0.966667 [RESULT-3] over 0.333333 [RESULT-1].",
    )
    synth = _FakeSynthesizer([broken])
    with pytest.raises(ResultMarkerFidelityError):
        _run_service(monkeypatch, synth)


def test_service_fails_closed_when_claims_never_backed(monkeypatch):
    bad = _paper_with(
        "We evaluate a frozen protocol.",
        "These observed gaps demonstrate that the classifier recovers "
        "signal without any marker support here.",
    )
    synth = _FakeSynthesizer([bad])  # same output both attempts
    with pytest.raises(ResultMarkerFidelityError):
        _run_service(monkeypatch, synth)


def test_section_fallback_output_reconciled(monkeypatch):
    """The section-wise route is covered by the same return-boundary
    reconciliation: monolithic output too short forces fallback, and the
    assembled section paper is repaired before returning."""
    short = "too short"  # < 200 words forces section fallback
    synth = _FakeSynthesizer([short])
    result = _run_service(monkeypatch, synth, section_fallback=True)

    assert result.success
    assert result.synthesis_strategy == "section_wise"
    assert "0.333333 [RESULT-1]" in result.paper_markdown
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", result.paper_markdown)
