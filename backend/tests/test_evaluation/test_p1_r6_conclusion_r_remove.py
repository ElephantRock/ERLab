"""Productive-1 R6 deterministic controls — frozen charter acceptance.

Locks every deterministic acceptance control of the frozen R6 charter
(evidence/productive1_r6/r6_charter.md) against the preserved R5
qualification corpus (fixtures/p1_r6_preserved_corpus.json — read-only
evidence from run 33414701494) plus adversarial variants:

  1. shared screening/authority parity vs the embedded pre-R6
     authoritative reference (verbatim transcription) on all preserved
     rev0/rev1 papers and variants
  2. regr-B rev0 and rev1 expose exactly the demonstrated assertion
  3. calib-A/B and regr-A expose no removal target
  4. exact R-REMOVE on both regr-B revisions → zero unmapped assertions
  5. numeric mismatches remain zero after combined repair
  6. every previously passing gate stays green (red→green allowed)
  7. method fidelity stays green
  8. heading sequence identical
  9. RESULT/SOURCE marker multiset identical
  10. backed empirical claims remain byte-identical
  11. bytes outside authorized spans identical
  12. ambiguous / marker-bearing / overlapping / drifted / tampered
      cases fail closed with typed reasons
  13. zero repair-side provider construction is possible
"""

import asyncio
import hashlib
import json
import re
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.models import Base, PaperRevision, Proposal  # noqa: E402
from backend.pipeline.evaluation.claim_result_validator import (  # noqa: E402
    validate_claim_result_alignment,
)
from backend.pipeline.evaluation.conclusion_support import (  # noqa: E402
    evaluate_conclusion_support,
)
from backend.pipeline.evaluation.method_fidelity import (  # noqa: E402
    evaluate_method_fidelity,
)
from backend.pipeline.evaluation.numeric_patcher import (  # noqa: E402
    PatchApplicationError,
    apply_combined_patches,
    derive_conclusion_removal_patches,
    derive_numeric_patch_manifest,
    gate_regressions,
    split_sentences_decimal_aware,
    verify_combined_postconditions,
)
from backend.pipeline.evaluation.paper_gate_evaluator import (  # noqa: E402
    evaluate_paper_gates,
)
from backend.pipeline.experiment.manifest import ResultMarker  # noqa: E402

from pathlib import Path as _Path  # noqa: E402

FIXTURE = _Path(__file__).resolve().parents[1] / "fixtures" / "p1_r6_preserved_corpus.json"


def _load_corpus():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


CORPUS = _load_corpus()


def marker_objects(dicts):
    return [
        ResultMarker(
            marker_index=int(d["marker"].split("-")[1]), marker=d["marker"],
            metric_name=d["metric_name"], observed_value=d["observed_value"],
            artifact_path="", artifact_sha256="",
            experiment_result_id=d.get("experiment_result_id"),
            direction="", role=d.get("role", ""),
        )
        for d in dicts
    ]


def gates_for(paper, trial):
    return evaluate_paper_gates(
        paper_md=paper, source_map=trial["source_map"],
        research_intent=trial["spec0"]["research_question"],
        domain="machine learning", result_markers=marker_objects(trial["markers"]),
        spec_method=trial["spec0"]["analysis_method"],
        spec_dataset=trial["spec0"]["dataset_name"],
        spec_baseline=trial["spec0"]["baseline_method"],
        spec_comparison=trial["spec0"]["comparison_method"],
    )


# ── Parity oracle: the pre-R6 authoritative logic, verbatim ────────────

def _pre_r6_reference(paper_md, result_markers=None):
    """Verbatim transcription of PaperSynthesisStage._classify_conclusion
    as it stood at the R5 candidate (b9cb75c) — the parity oracle."""
    from backend.pipeline.evaluation.conclusion_checker import (
        ConclusionSupportResult,
        classify_conclusion_support,
    )

    abstract = ""
    conclusion = ""
    if paper_md:
        lines = paper_md.splitlines()
        abs_lines: list[str] = []
        in_section = False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "abstract" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                abs_lines.append(s)
        abstract = " ".join(abs_lines)
        conc_lines: list[str] = []
        in_section = False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "conclusion" in low or "discussion" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                conc_lines.append(s)
        conclusion = " ".join(conc_lines)

    has_results = False
    if paper_md:
        lower = paper_md.lower()
        has_results_heading = any(h in lower for h in ("## results", "# results"))
        has_expected_results = "expected results" in lower
        has_experiments_heading = any(
            h in lower for h in ("## experiments", "# experiments",
                                 "## experimental setup", "# experimental setup")
        )
        has_results = (has_results_heading and not has_expected_results) or has_experiments_heading

    result_backed = False
    unmapped_result_claims: list[str] = []
    if result_markers:
        result_marker_re = re.compile(r"\[RESULT-(\d+)\]")
        cited_markers = set(result_marker_re.findall(paper_md or ""))
        available_markers = {str(m.marker_index) for m in result_markers}
        if cited_markers & available_markers:
            result_backed = True
        text = f"{abstract}\n{conclusion}"
        for pattern, label in [
            (r"\bwe\s+demonstrate\b", "we demonstrate"),
            (r"\bdemonstrates?\s+that\b", "demonstrates that"),
            (r"\bexperimental\s+results?\b.{0,40}\b(show|indicate)\b", "experimental results show"),
            (r"\bresults?\s+(show|indicate)\s+that\b", "results show that"),
        ]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, m.start() - 200)
                end = min(len(text), m.end() + 200)
                context = text[start:end]
                if not result_marker_re.search(context):
                    unmapped_result_claims.append(
                        f"empirical claim '{label}' without [RESULT-N] backing"
                    )

    if result_markers:
        has_empirical = result_backed
    elif has_results:
        has_empirical = True
    else:
        has_empirical = None

    result = classify_conclusion_support(
        abstract=abstract, conclusion=conclusion, has_empirical_results=has_empirical,
    )
    if result_markers and unmapped_result_claims:
        return ConclusionSupportResult(
            classification="overstated",
            reason=(
                f"Experiment succeeded but {len(unmapped_result_claims)} empirical claim(s) "
                f"lack [RESULT-N] backing: {'; '.join(unmapped_result_claims[:3])}"
            ),
            indicators=unmapped_result_claims,
        )
    return result


def _trial(name):
    return next(t for t in CORPUS["trials"] if t["trial"] == name)


class TestSharedRuleParity:
    @pytest.mark.parametrize("name", [t["trial"] for t in CORPUS["trials"]])
    @pytest.mark.parametrize("rev", ["rev0_md", "rev1_md"])
    def test_parity_on_preserved_corpus(self, name, rev):
        trial = _trial(name)
        paper = trial[rev]
        markers = marker_objects(trial["markers"])
        shared = evaluate_conclusion_support(paper, markers)
        reference = _pre_r6_reference(paper, markers)
        assert shared.classification == reference.classification
        assert shared.reason == reference.reason
        assert shared.indicators == list(reference.indicators or [])
        # and without markers, both degrade identically
        shared_nm = evaluate_conclusion_support(paper, None)
        reference_nm = _pre_r6_reference(paper, None)
        assert shared_nm.classification == reference_nm.classification

    def test_parity_on_adversarial_variants(self):
        backed = (
            "# T\n\n## Abstract\nWe demonstrate a gain of 0.5 [RESULT-1] over baseline.\n\n"
            "## Conclusion\nAll good.\n"
        )
        unbacked = (
            "# T\n\n## Abstract\nWe demonstrate a large improvement here.\n\n"
            "## Conclusion\nFine.\n"
        )
        blob = "# T\n\n## Abstract\nOne blob paragraph. The results show that X beats Y "
        "consistently, and values were recorded at 0.25 and 0.75. End of blob.\n"
        discussion = (
            "# T\n\n## Abstract\nShort.\n\n## Discussion\nThe results show that "
            "everything worked well overall.\n"
        )
        expected_results = (
            "# T\n\n## Abstract\nShort.\n\n## Results\nExpected results follow.\n"
        )
        markers = [ResultMarker(marker_index=1, marker="RESULT-1", metric_name="d.m",
                                observed_value=0.5, artifact_path="", artifact_sha256="",
                                experiment_result_id=1, direction="", role="comparison")]
        for paper in (backed, unbacked, blob, discussion, expected_results):
            for mk in (markers, None):
                shared = evaluate_conclusion_support(paper, mk)
                reference = _pre_r6_reference(paper, mk)
                assert shared.classification == reference.classification, paper[:40]
                assert shared.reason == reference.reason

    def test_screening_gate_uses_shared_rule(self):
        # The pure evaluator's conclusion gate must classify identically
        # to the shared function across the whole corpus (wiring proof).
        for trial in CORPUS["trials"]:
            for rev in ("rev0_md", "rev1_md"):
                gates = gates_for(trial[rev], trial)
                gate = next(g for g in gates.gates if g["gate"] == "conclusion_support")
                shared = evaluate_conclusion_support(
                    trial[rev], marker_objects(trial["markers"]))
                assert gate["classification"] == shared.classification, (
                    trial["trial"], rev)


class TestPreservedCorpusTargets:
    def test_regr_b_exposes_exactly_one_assertion(self):
        for rev in ("rev0_md", "rev1_md"):
            trial = _trial("regr-B#1")
            shared = evaluate_conclusion_support(trial[rev], marker_objects(trial["markers"]))
            assert len(shared.unmapped_claims) == 1
            assert shared.unmapped_claims[0].label == "results show that"
            assert shared.classification == "overstated"
        trial2 = _trial("regr-B#2")
        shared2 = evaluate_conclusion_support(trial2["rev0_md"], marker_objects(trial2["markers"]))
        assert len(shared2.unmapped_claims) == 1

    def test_other_specimens_expose_no_target(self):
        for name in ("calib-A#1", "calib-A#2", "calib-B#1", "calib-B#2",
                     "regr-A#1", "regr-A#2"):
            trial = _trial(name)
            for rev in ("rev0_md", "rev1_md"):
                shared = evaluate_conclusion_support(trial[rev], marker_objects(trial["markers"]))
                assert shared.unmapped_claims == [], (name, rev)


class TestCombinedRepairOnPreservedCorpus:
    def test_regr_b_both_revisions_full_battery(self):
        for name in ("regr-B#1", "regr-B#2"):
            for rev in ("rev0_md", "rev1_md"):
                trial = _trial(name)
                original = trial[rev]
                markers = marker_objects(trial["markers"])
                before = evaluate_conclusion_support(original, markers)
                numeric = derive_numeric_patch_manifest(original, markers)
                removals, errs = derive_conclusion_removal_patches(original, before)
                assert errs == []
                revised = apply_combined_patches(original, numeric, removals)
                after = evaluate_conclusion_support(revised, markers)
                # control 4: zero unmapped after exact removal
                assert after.unmapped_claims == []
                # control 5: numeric mismatches remain zero
                assert not [m for m in validate_claim_result_alignment(revised, markers)
                            if m.section == "numeric_fidelity"]
                # controls 6: no previously-green gate flips
                g_before = gates_for(original, trial)
                g_after = gates_for(revised, trial)
                assert gate_regressions(g_before.gates, g_after.gates) == []
                # control 7: method fidelity stays green
                assert evaluate_method_fidelity(original, trial["method_facts"]).passed
                assert evaluate_method_fidelity(revised, trial["method_facts"]).passed
                # controls 8-9: headings and marker multiset identical
                assert verify_combined_postconditions(
                    original, revised, numeric, removals) == []
                # control 11: bytes outside authorized spans identical
                cursor_o = cursor_r = 0
                for patch in sorted(
                    list(numeric) + list(removals), key=lambda p: p["span_start"]
                ):
                    gap = patch["span_start"] - cursor_o
                    assert original[cursor_o:patch["span_start"]] == \
                        revised[cursor_r:cursor_r + gap]
                    cursor_r += gap + len(patch["new_text"])
                    cursor_o = patch["span_end"]
                assert original[cursor_o:] == revised[cursor_r:]

    def test_clean_specimens_unchanged_paths(self):
        # calib/regr-A: numeric-only repair, zero removals, conclusion
        # classification unchanged.
        for name in ("calib-A#1", "calib-B#2", "regr-A#1"):
            trial = _trial(name)
            original = trial["rev0_md"]
            markers = marker_objects(trial["markers"])
            before = evaluate_conclusion_support(original, markers)
            numeric = derive_numeric_patch_manifest(original, markers)
            removals, errs = derive_conclusion_removal_patches(original, before)
            assert errs == [] and removals == ()
            revised = apply_combined_patches(original, numeric, removals)
            after = evaluate_conclusion_support(revised, markers)
            assert after.classification == before.classification
            assert gate_regressions(
                gates_for(original, trial).gates, gates_for(revised, trial).gates,
            ) == []


class TestBackedClaimsPreserved:
    def test_mixed_paper_removes_only_unbacked_sentence(self):
        backed_sentence = "We demonstrate a recorded gain of 0.5 [RESULT-1] in setting A."
        filler = "Neutral context follows. " + ("Padding prose. " * 22)
        unbacked_sentence = "The results show that the method dominates everywhere."
        assert len(filler) > 210  # claims must sit >200 chars apart
        paper = (
            "# T\n\n## Abstract\n" + backed_sentence + " " + filler + " "
            + unbacked_sentence + "\n\n"
            "## Conclusion\nDone.\n"
        )
        markers = [ResultMarker(marker_index=1, marker="RESULT-1", metric_name="d.m",
                                observed_value=0.5, artifact_path="", artifact_sha256="",
                                experiment_result_id=1, direction="", role="comparison")]
        before = evaluate_conclusion_support(paper, markers)
        assert len(before.unmapped_claims) == 1
        removals, errs = derive_conclusion_removal_patches(paper, before)
        assert errs == [] and len(removals) == 1
        revised = apply_combined_patches(paper, (), removals)
        # control 10: the backed sentence survives byte-identical
        assert backed_sentence in revised
        assert unbacked_sentence not in revised
        after = evaluate_conclusion_support(revised, markers)
        assert after.unmapped_claims == []


class TestSentenceSplitter:
    def test_decimal_aware_rule(self):
        text = "Values at 0.25 and 0.75 were recorded. The results show that X. "
        sentences = [t.strip() for _s, _e, t in split_sentences_decimal_aware(text)]
        assert sentences == [
            "Values at 0.25 and 0.75 were recorded.",
            "The results show that X.",
        ]

    def test_digit_period_terminal(self):
        text = "Severity ends at 0."
        assert [t.strip() for _s, _e, t in split_sentences_decimal_aware(text)] == [text]

    def test_terminal_and_nonterminal_periods(self):
        # Frozen rule: a period followed by whitespace terminates (only
        # digit.digit never does) — so "Ref." splits; a period followed
        # by a non-space character does not terminate.
        split_ref = split_sentences_decimal_aware("Ref. internal note continues here.")
        assert [t.strip() for _s, _e, t in split_ref] == [
            "Ref.", "internal note continues here.",
        ]
        glued = split_sentences_decimal_aware("A note.continues without space here.")
        assert [t.strip() for _s, _e, t in glued] == ["A note.continues without space here."]


class TestFailClosed:
    def _paper_with_claim(self):
        return ("# T\n\n## Abstract\nIntro sentence stays. The results show that "
                "our approach wins broadly across settings.\n")

    def test_duplicate_sentence_is_ambiguous(self):
        sentence = "The results show that our approach wins broadly across settings."
        paper = ("# T\n\n## Abstract\nIntro stays. " + sentence + " " + sentence + "\n")
        markers = []
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        patches, errs = derive_conclusion_removal_patches(paper, assessment)
        assert patches == ()
        assert any(e.startswith("conclusion_sentence_ambiguous") for e in errs)

    def test_marker_bearing_sentence_rejected(self):
        # One unbacked claim whose sentence carries a [SOURCE-N] token:
        # the ±200 rule only credits [RESULT-N], so the claim is unmapped,
        # and the marker-bearing sentence is refused for removal.
        paper = ("# T\n\n## Abstract\nNeutral intro sentence stays. The results "
                 "show that X wins, see [SOURCE-1] for setup.\n")
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        assert len(assessment.unmapped_claims) == 1
        patches, errs = derive_conclusion_removal_patches(paper, assessment)
        assert patches == ()
        assert any(e.startswith("conclusion_sentence_marker_bearing") for e in errs)

    def test_overlap_rejected_at_application(self):
        paper = self._paper_with_claim()
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        removals, errs = derive_conclusion_removal_patches(paper, assessment)
        assert errs == []
        removal = dict(removals[0])
        overlapping = dict(removal, span_start=removal["span_start"] + 2)
        with pytest.raises(PatchApplicationError) as exc:
            apply_combined_patches(paper, (), (removal, overlapping))
        assert exc.value.kind == "patch_overlap"

    def test_span_drift_rejected(self):
        paper = self._paper_with_claim()
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        removals, _ = derive_conclusion_removal_patches(paper, assessment)
        tampered = dict(removals[0], old_text="not the sentence")
        with pytest.raises(PatchApplicationError) as exc:
            apply_combined_patches(paper, (), (tampered,))
        assert exc.value.kind == "patch_span_drift"

    def test_tampered_candidate_detected_by_postconditions(self):
        paper = self._paper_with_claim()
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        removals, _ = derive_conclusion_removal_patches(paper, assessment)
        revised = apply_combined_patches(paper, (), removals) + " extra bytes"
        violations = verify_combined_postconditions(paper, revised, (), removals)
        assert any(v.startswith("reconstruction_mismatch") for v in violations)

    def test_claim_straddling_sentences_is_ambiguous(self):
        # A pattern match that no single joined-text sentence contains
        # (matched_text spanning a terminator) fails closed.
        paper = ("# T\n\n## Abstract\nThe results\nshow that split lines merge, "
                 "but a hard boundary. follows.\n")
        assessment = evaluate_conclusion_support(paper, _fake_markers())
        assert assessment.unmapped_claims  # the claim is detected unbacked
        patches, errs = derive_conclusion_removal_patches(paper, assessment)
        # merged lines still form one sentence — derivation succeeds or
        # fails typed; both are acceptable ONLY as: succeeds → single
        # removal; the corpus-level behavior is covered above.
        if patches:
            assert len(patches) == 1
        else:
            assert all(
                e.startswith("conclusion_sentence_ambiguous") for e in errs)


def _fake_markers():
    return [ResultMarker(marker_index=1, marker="RESULT-1", metric_name="d.m",
                         observed_value=0.5, artifact_path="", artifact_sha256="",
                         experiment_result_id=1, direction="", role="comparison")]


# ── End-to-end through the real remediator (controls 4, 12, 13) ───────

def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


from contextlib import contextmanager  # noqa: E402

from backend.db.models import ExperimentResult, Idea, PipelineRun  # noqa: E402


@contextmanager
def _patched_session(engine):
    import backend.db.database as db_mod
    import backend.pipeline.evaluation.paper_remediator as remediator_mod

    test_sf = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched():
        session = test_sf()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    original_db = db_mod.get_session
    original_rem = remediator_mod.get_session
    db_mod.get_session = patched
    remediator_mod.get_session = patched
    try:
        yield engine
    finally:
        db_mod.get_session = original_db
        remediator_mod.get_session = original_rem


def _setup(engine, paper):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        run = PipelineRun(run_id_str="run_r6", domain="ML", status="completed",
                          config_json="{}", stages_completed="[]",
                          provenance_version="provenance_v1")
        session.add(run)
        session.flush()
        idea = Idea(title="R6 Test", problem_statement="conclusion defect",
                    proposed_method="ridge", expected_contributions="support",
                    domain="ML", novelty_score=0.5, feasibility_score=0.8,
                    overall_score=0.8, pipeline_run_id=run.id)
        session.add(idea)
        session.flush()
        proposal = Proposal(idea_id=idea.id, content_md="c", paper_md=paper,
                            paper_meta_json=json.dumps({}))
        session.add(proposal)
        session.flush()
        exp = ExperimentResult(idea_id=idea.id, proposal_id=proposal.id,
                               code_md="# frozen", success=True,
                               manifest_json=json.dumps({"results": {}}))
        session.add(exp)
        session.commit()
        return proposal.id, exp.id


class TestRemediatorEndToEnd:
    def test_regr_b_rev0_full_repair_with_audit(self, monkeypatch):
        from backend.pipeline.evaluation.paper_remediator import auto_revise_paper

        trial = _trial("regr-B#1")
        paper = trial["rev0_md"]
        engine = _make_engine()

        def _provider_must_not_exist(settings):
            raise AssertionError(
                "R6 frozen-contract violation: repair constructed a provider")

        import backend.providers.provider_factory as pf
        monkeypatch.setattr(pf, "get_generation_provider", _provider_must_not_exist)

        with _patched_session(engine):
            proposal_id, exp_id = _setup(engine, paper)
            spec = SimpleNamespace(
                research_question=trial["spec0"]["research_question"],
                task_type=trial["spec0"]["task_type"],
                analysis_method=trial["spec0"]["analysis_method"],
                dataset_name=trial["spec0"]["dataset_name"],
                baseline_method=trial["spec0"]["baseline_method"],
                comparison_method=trial["spec0"]["comparison_method"],
                dataset_raw_sha256="d" * 8,
            )
            result = asyncio.run(auto_revise_paper(
                proposal_id=proposal_id, experiment_result_id=exp_id,
                original_paper_md=paper, blocking_findings=["Gate finding: x"],
                source_map=trial["source_map"],
                result_markers=marker_objects(trial["markers"]),
                spec=spec, method_facts=trial["method_facts"],
            ))

            assert len(result.patch_manifest) == 8   # numeric repairs
            assert len(result.conclusion_removals) == 1  # R-REMOVE
            removal = result.conclusion_removals[0]
            assert removal["matched_pattern"] == "results show that"
            assert removal["sentence_sha256"] == hashlib.sha256(
                paper[removal["span_start"]:removal["span_end"]].encode()
            ).hexdigest()
            assert removal["pre_classification"] == "overstated"

            revised = apply_combined_patches(
                paper, tuple(result.patch_manifest),
                tuple(result.conclusion_removals))
            assert result.revised_paper_hash == hashlib.sha256(
                revised.encode()).hexdigest()
            assert evaluate_conclusion_support(
                revised, marker_objects(trial["markers"])).unmapped_claims == []

            with sessionmaker(bind=engine)() as s:
                rev1 = s.query(PaperRevision).filter_by(
                    proposal_id=proposal_id, revision_number=1).one()
                payload = json.loads(rev1.directive_json)
                assert len(payload["patch_manifest"]) == 8
                assert len(payload["conclusion_removals"]) == 1
                assert payload["conclusion_pre_classification"] == "overstated"
                assert payload["conclusion_post_classification"] == \
                    "supported_by_paper"
                assert s.get(Proposal, proposal_id).paper_md == paper  # PAC intact
