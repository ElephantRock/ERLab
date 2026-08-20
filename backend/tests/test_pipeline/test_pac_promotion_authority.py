"""Promotion-Authority-Consistency deterministic controls (PAC-8/9/10).

The demonstrated defect (Productive-1 regr-B#2): auto_revise_paper()
promoted the revised paper when its internal screening returned ready;
the route then ran the full _evaluate_paper() on the already-promoted
paper — and if that authoritative evaluation blocked, the route
persisted the blocked evaluation but never reversed the canonical
mutation, yielding promoted=true + final blocked + mutated canonical.

The correction: the remediator is a candidate producer (no canonical
mutation); the route evaluates the PERSISTED revision-1 bytes and
promotes in one atomic transaction only when the authoritative
evaluation returns ready for the exact candidate — with three identity
assertions (canonical unchanged since entry; revision == candidate
hash; evaluation == candidate hash). Blocked/failed/stale candidates
never mutate the canonical paper.

Harness reuses the ead4a_v3 in-memory route scaffolding.
"""

import asyncio
import hashlib
import json
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod  # noqa: E402
from backend.db.models import PaperRevision, Proposal  # noqa: E402
from backend.pipeline.evaluation.paper_remediator import (  # noqa: E402
    RemediationResult,
)
from backend.tests.test_pipeline.test_ead4a_v3_actual_route import (  # noqa: E402
    _make_engine,
    _patched_session,
    _setup_blocked_autonomous,
)


def _canonical(engine, proposal_id):
    from sqlalchemy import select as _select

    with db_mod.get_session() as s:
        row = s.execute(
            _select(Proposal.paper_md, Proposal.paper_meta_json).where(
                Proposal.id == proposal_id
            )
        ).fetchone()
        rev1 = s.execute(
            _select(PaperRevision).where(
                PaperRevision.proposal_id == proposal_id,
                PaperRevision.revision_number == 1,
            )
        ).scalar_one_or_none()
        return (
            row[0],
            json.loads(row[1]) if row[1] else {},
            rev1,
        )


def _run_route(
    engine,
    idea_id,
    proposal_id,
    eval_status="ready",
    eval_hash_of="candidate",
    eval_gates=None,
    concurrent_mutation=None,
    revise_override=None,
):
    """Invoke the real repair_paper route with a candidate-producing
    remediator stub and a controlled _evaluate_paper stub."""

    async def _stub_revise(**kwargs):
        if revise_override is not None:
            return await revise_override(**kwargs)
        candidate_md = kwargs["original_paper_md"] + "\n\nrevised candidate"
        rev_hash = hashlib.sha256(candidate_md.encode()).hexdigest()
        sf = sessionmaker(bind=engine)
        s = sf()
        s.add(PaperRevision(
            proposal_id=kwargs["proposal_id"], revision_number=1,
            parent_revision_id=None, paper_md=candidate_md,
            paper_hash=rev_hash, source="auto_remediation",
            trigger="alignment_blocked",
            trigger_detail_json=json.dumps(
                {"blocking_findings": ["numeric_fidelity: test"]}),
            directive_json="{}", eval_status="ready", gates_json="[]",
        ))
        s.commit()
        s.close()
        return RemediationResult(
            success=True, promoted=False, revision_number=1,
            eval_status="ready", gates=[], blocking_reasons=[],
            original_paper_hash=kwargs.get("original_paper_hash", ""),
            revised_paper_hash=rev_hash, invariant_violations=[],
        )

    eval_calls = {"n": 0}

    async def _stub_evaluate(self, ctx, proposal_obj, meta, idx):
        eval_calls["n"] += 1
        candidate_hash = hashlib.sha256(
            proposal_obj.paper_md.encode()
        ).hexdigest()
        if eval_hash_of == "canonical":
            # Simulate an evaluation bound to the WRONG bytes.
            with db_mod.get_session() as s:
                prop = s.get(Proposal, proposal_id)
                candidate_hash = hashlib.sha256(
                    prop.paper_md.encode()).hexdigest()
        if concurrent_mutation is not None:
            with db_mod.get_session() as s:
                prop = s.get(Proposal, proposal_id)
                prop.paper_md = concurrent_mutation
                s.commit()
        meta["paper_evaluation"] = {
            "status": eval_status,
            "paper_hash": candidate_hash,
            "gates": eval_gates if eval_gates is not None else [
                {"gate": "provenance", "passed": True},
                {"gate": "conclusion_support",
                 "classification": (
                     "supported_by_paper" if eval_status == "ready"
                     else "overstated")},
            ],
        }

    with patch(
        "backend.pipeline.evaluation.paper_remediator.auto_revise_paper",
        new=_stub_revise,
    ), patch(
        "backend.providers.provider_factory.create_provider",
        return_value=MagicMock(),
    ), patch(
        "backend.pipeline.stages.PaperSynthesisStage._evaluate_paper",
        new=_stub_evaluate,
    ):
        from backend.api.routes.ideas import repair_paper
        return asyncio.run(repair_paper(idea_id)), eval_calls


class TestPromotionAuthorityStates:
    def _setup(self, engine):
        with _patched_session(engine):
            return _setup_blocked_autonomous(engine)

    def test_screening_ready_final_ready_promotes_atomically(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, before_meta, _ = _canonical(engine, proposal_id)
            out, eval_calls = _run_route(
                engine, idea_id, proposal_id, eval_status="ready")
        r = out["repair"]
        assert r["promoted"] is True
        assert out["evaluation"]["status"] == "ready"
        assert eval_calls["n"] == 1
        with _patched_session(engine):
            after_md, after_meta, rev1 = _canonical(engine, proposal_id)
        # revision + canonical + persisted evaluation identify the same bytes
        assert after_md == rev1.paper_md
        assert rev1.paper_hash == hashlib.sha256(
            after_md.encode()).hexdigest()
        assert after_meta["paper_evaluation"]["paper_hash"] == rev1.paper_hash
        assert rev1.eval_status == "ready"
        assert after_md != before_md
        detail = json.loads(rev1.trigger_detail_json)
        assert detail["authoritative"]["status"] == "ready"

    def test_screening_ready_final_blocked_preserves_canonical(self):
        """The regr-B#2 shape (PAC-9): screening passes, the full
        evaluation blocks on conclusion_support — canonical original
        unchanged, candidate preserved, promoted=false, no freeze
        eligibility."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, before_meta, _ = _canonical(engine, proposal_id)
            out, _ = _run_route(
                engine, idea_id, proposal_id, eval_status="blocked")
        assert out["repair"]["promoted"] is False
        assert out["evaluation"]["status"] == "blocked"
        with _patched_session(engine):
            after_md, after_meta, rev1 = _canonical(engine, proposal_id)
        assert after_md == before_md  # canonical byte-identical
        # canonical evaluation unchanged (hash-bound to the original)
        assert after_meta["paper_evaluation"] == before_meta["paper_evaluation"]
        # candidate revision preserved with the authoritative outcome
        assert rev1 is not None and rev1.paper_md != before_md
        assert rev1.eval_status == "blocked"
        detail = json.loads(rev1.trigger_detail_json)
        assert detail["authoritative"]["status"] == "blocked"
        # audit trail keeps BOTH the screening pass and the block
        assert detail["screening"]["status"] == "ready"

    def test_screening_ready_final_failed_preserves_canonical(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, _, _ = _canonical(engine, proposal_id)
            out, _ = _run_route(
                engine, idea_id, proposal_id, eval_status="failed")
        assert out["repair"]["promoted"] is False
        assert out["evaluation"]["status"] == "failed"
        with _patched_session(engine):
            after_md, _, rev1 = _canonical(engine, proposal_id)
        assert after_md == before_md
        assert rev1.eval_status == "failed"
        assert json.loads(rev1.trigger_detail_json)["authoritative"][
            "status"] == "failed"

    def test_screening_blocked_never_promotes(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)

        async def _blocked_revise(**kwargs):
            return RemediationResult(
                success=True, promoted=False, revision_number=1,
                eval_status="blocked", gates=[], blocking_reasons=["x"],
                original_paper_hash="", revised_paper_hash="",
                invariant_violations=[],
            )

        with _patched_session(engine):
            before_md, _, _ = _canonical(engine, proposal_id)
            out, eval_calls = _run_route(
                engine, idea_id, proposal_id,
                revise_override=_blocked_revise)
        assert out["repair"]["promoted"] is False
        assert eval_calls["n"] == 0  # full evaluator never runs
        with _patched_session(engine):
            after_md, _, _ = _canonical(engine, proposal_id)
        assert after_md == before_md

    def test_stale_canonical_prevents_promotion(self):
        """A concurrent canonical mutation between route entry and
        finalization must fail closed: no promotion, no overwrite."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            out, _ = _run_route(
                engine, idea_id, proposal_id, eval_status="ready",
                concurrent_mutation="# concurrently rewritten paper")
        assert out["repair"]["promoted"] is False
        assert "finalization_note" in out["repair"]
        assert "stale" in out["repair"]["finalization_note"]
        with _patched_session(engine):
            after_md, _, _ = _canonical(engine, proposal_id)
        # we did not overwrite the concurrent writer's bytes
        assert after_md == "# concurrently rewritten paper"

    def test_evaluation_hash_mismatch_prevents_promotion(self):
        """An evaluation bound to bytes other than the candidate must
        fail closed."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, _, _ = _canonical(engine, proposal_id)
            out, _ = _run_route(
                engine, idea_id, proposal_id, eval_status="ready",
                eval_hash_of="canonical")
        assert out["repair"]["promoted"] is False
        assert "finalization_note" in out["repair"]
        with _patched_session(engine):
            after_md, _, _ = _canonical(engine, proposal_id)
        assert after_md == before_md


class TestIdempotencyAndRecovery:
    def _setup(self, engine):
        with _patched_session(engine):
            return _setup_blocked_autonomous(engine)

    def test_crash_recovery_reuses_candidate_without_resynthesis(self):
        """Revision 1 persisted (crash between synthesis and
        authoritative evaluation): the remediator returns the persisted
        candidate and the route evaluates it — no second model call."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, _, _ = _canonical(engine, proposal_id)
            candidate_md = before_md + "\n\ncrash-recovered candidate"
            rev_hash = hashlib.sha256(candidate_md.encode()).hexdigest()
            sf = sessionmaker(bind=engine)
            s = sf()
            s.add(PaperRevision(
                proposal_id=proposal_id, revision_number=1,
                parent_revision_id=None, paper_md=candidate_md,
                paper_hash=rev_hash, source="auto_remediation",
                trigger="alignment_blocked",
                trigger_detail_json=json.dumps(
                    {"blocking_findings": ["numeric_fidelity: test"]}),
                directive_json="{}", eval_status="ready", gates_json="[]",
            ))
            s.commit()
            s.close()

            async def _idempotent_return(**kwargs):
                # Mirrors the real remediator's PAC-7 crash-recovery
                # branch: existing rev1 without an authoritative stamp
                # is returned as-is; no synthesis occurs.
                return RemediationResult(
                    success=True, promoted=False, revision_number=1,
                    eval_status="ready", gates=[],
                    blocking_reasons=["numeric_fidelity: test"],
                    original_paper_hash=kwargs.get(
                        "original_paper_hash", ""),
                    revised_paper_hash=rev_hash,
                    invariant_violations=[],
                )

            out, eval_calls = _run_route(
                engine, idea_id, proposal_id,
                eval_status="ready", revise_override=_idempotent_return)
        assert eval_calls["n"] == 1
        assert out["repair"]["promoted"] is True
        with _patched_session(engine):
            after_md, _, rev1 = _canonical(engine, proposal_id)
        assert after_md == rev1.paper_md == candidate_md

    def test_terminal_blocked_retry_no_reevaluation(self):
        """Revision 1 already carries a terminal authoritative blocked
        record: retry returns that result — no synthesis, no
        re-evaluation, canonical untouched."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = self._setup(engine)
        with _patched_session(engine):
            before_md, _, _ = _canonical(engine, proposal_id)
            candidate_md = before_md + "\n\nterminal blocked candidate"
            sf = sessionmaker(bind=engine)
            s = sf()
            s.add(PaperRevision(
                proposal_id=proposal_id, revision_number=1,
                parent_revision_id=None, paper_md=candidate_md,
                paper_hash=hashlib.sha256(
                    candidate_md.encode()).hexdigest(),
                source="auto_remediation", trigger="alignment_blocked",
                trigger_detail_json=json.dumps({
                    "blocking_findings": ["x"],
                    "authoritative": {
                        "status": "blocked", "paper_hash": "h",
                        "gates": [{"gate": "conclusion_support",
                                   "classification": "overstated"}],
                    },
                    "screening": {"status": "ready", "gates": []},
                }),
                directive_json="{}", eval_status="blocked",
                gates_json="[]",
            ))
            s.commit()
            s.close()

            auth_gates = [{"gate": "conclusion_support",
                           "classification": "overstated"}]

            async def _terminal_return(**kwargs):
                # Mirrors the real remediator's PAC-7 terminal branch.
                return RemediationResult(
                    success=True, promoted=False, revision_number=1,
                    eval_status="blocked", gates=auth_gates,
                    blocking_reasons=["x"],
                    original_paper_hash=kwargs.get(
                        "original_paper_hash", ""),
                    revised_paper_hash=hashlib.sha256(
                        candidate_md.encode()).hexdigest(),
                    invariant_violations=[],
                )

            out, eval_calls = _run_route(
                engine, idea_id, proposal_id,
                revise_override=_terminal_return)
        assert eval_calls["n"] == 0
        assert out["repair"]["promoted"] is False
        assert out["evaluation"]["status"] == "blocked"
        gates = {g.get("gate") for g in out["evaluation"]["gates"]}
        assert "conclusion_support" in gates
        with _patched_session(engine):
            after_md, _, _ = _canonical(engine, proposal_id)
        assert after_md == before_md


class TestPromotedImpliesReady:
    """Any promoted=true response necessarily has evaluation ready with
    matching hashes — asserted across every positive path above via the
    shared helpers; this test pins the invariant explicitly."""
    def test_promoted_response_shape(self):
        engine = _make_engine()
        with _patched_session(engine):
            run_id, idea_id, proposal_id = _setup_blocked_autonomous(
                engine)
        with _patched_session(engine):
            out, _ = _run_route(engine, idea_id, proposal_id,
                                eval_status="ready")
        if out["repair"]["promoted"]:
            assert out["evaluation"]["status"] == "ready"
            assert out["evaluation"]["paper_hash"] == \
                out["repair"]["revised_paper_hash"]


class TestRemediatorIdempotencyNoResynthesis:
    """PAC-7 at the remediator level: the REAL auto_revise_paper never
    synthesizes again when revision 1 already exists."""

    def test_existing_revision1_short_circuits_synthesis(self):
        engine = _make_engine()
        with _patched_session(engine):
            run_id, idea_id, proposal_id = _setup_blocked_autonomous(
                engine)
            with db_mod.get_session() as s:
                prop = s.get(Proposal, proposal_id)
                original = prop.paper_md
            existing_md = original + "\n\nexisting revision one"
            existing_hash = hashlib.sha256(
                existing_md.encode()).hexdigest()
            sf = sessionmaker(bind=engine)
            s = sf()
            s.add(PaperRevision(
                proposal_id=proposal_id, revision_number=1,
                parent_revision_id=None, paper_md=existing_md,
                paper_hash=existing_hash, source="auto_remediation",
                trigger="alignment_blocked",
                trigger_detail_json=json.dumps(
                    {"blocking_findings": ["x"]}),
                directive_json="{}", eval_status="ready",
                gates_json="[]",
            ))
            s.commit()
            s.close()

            synthesis_calls = {"n": 0}

            async def _counting_synthesize(self, **kwargs):
                synthesis_calls["n"] += 1
                raise AssertionError("must not synthesize again")

            import backend.pipeline.evaluation.paper_remediator as _pr_mod

            @contextmanager
            def _rem_session():
                s = sessionmaker(bind=engine)()
                try:
                    yield s
                except Exception:
                    s.rollback()
                    raise
                finally:
                    s.close()

            with patch(
                "backend.pipeline.synthesis.paper_synthesizer"
                ".PaperSynthesizer.synthesize",
                new=_counting_synthesize,
            ), patch(
                "backend.providers.provider_factory"
                ".get_generation_provider",
                lambda settings: MagicMock(),
            ), patch.object(
                _pr_mod, "get_session", _rem_session,
            ):
                from types import SimpleNamespace

                from backend.pipeline.evaluation.paper_remediator import auto_revise_paper
                spec_stub = SimpleNamespace(
                    research_question="rq", task_type="classification",
                    target_name="t", analysis_method="m",
                    baseline_method="b", comparison_method="c",
                    primary_metric="acc",
                    metric_directions={"acc": "higher"},
                    dataset_name="d", split_method="s",
                    random_seed=42, dataset_raw_sha256="",
                )
                result = asyncio.run(auto_revise_paper(
                    proposal_id=proposal_id, experiment_result_id=1,
                    original_paper_md=original,
                    blocking_findings=["x"], source_map=[],
                    result_markers=[], spec=spec_stub,
                ))
        assert synthesis_calls["n"] == 0
        assert result.revision_number == 1
        assert result.revised_paper_hash == existing_hash
        assert result.eval_status == "ready"
        # Owner review of PR #43: an unstamped screening-ready revision
        # must NOT be treated as an authoritative promotion.
        assert result.promoted is False

    @pytest.mark.parametrize("final_status,expect_promoted", [
        ("ready", True), ("blocked", False),
    ])
    def test_unstamped_ready_retry_full_real_path(
        self, final_status, expect_promoted,
    ):
        """The exact PR-#43 blocking sequence, through the REAL
        remediator and route: an unstamped screening-ready revision 1
        exists, the canonical paper is still the original — retry must
        perform NO synthesis, return promoted=False from the remediator,
        run the authoritative full evaluator exactly once, and only a
        final ready can promote."""
        engine = _make_engine()
        with _patched_session(engine):
            run_id, idea_id, proposal_id = _setup_blocked_autonomous(
                engine)
            with db_mod.get_session() as s:
                prop = s.get(Proposal, proposal_id)
                original = prop.paper_md
            candidate_md = original + "\n\nunstamped ready candidate"
            candidate_hash = hashlib.sha256(
                candidate_md.encode()).hexdigest()
            sf = sessionmaker(bind=engine)
            s = sf()
            s.add(PaperRevision(
                proposal_id=proposal_id, revision_number=1,
                parent_revision_id=None, paper_md=candidate_md,
                paper_hash=candidate_hash, source="auto_remediation",
                trigger="alignment_blocked",
                trigger_detail_json=json.dumps(
                    {"blocking_findings": ["x"]}),
                directive_json="{}", eval_status="ready",
                gates_json="[]",
            ))
            s.commit()
            s.close()

            synthesis_calls = {"n": 0}

            async def _counting_synthesize(self, **kwargs):
                synthesis_calls["n"] += 1
                raise AssertionError("must not synthesize again")

            eval_calls = {"n": 0}

            async def _stub_evaluate(self, ctx, proposal_obj, meta, idx):
                eval_calls["n"] += 1
                meta["paper_evaluation"] = {
                    "status": final_status,
                    "paper_hash": hashlib.sha256(
                        proposal_obj.paper_md.encode()).hexdigest(),
                    "gates": [
                        {"gate": "provenance", "passed": True},
                        {"gate": "conclusion_support",
                         "classification": (
                             "supported_by_paper"
                             if final_status == "ready"
                             else "overstated")},
                    ],
                }

            import backend.pipeline.evaluation.paper_remediator as _pr_mod

            @contextmanager
            def _rem_session():
                sess = sessionmaker(bind=engine)()
                try:
                    yield sess
                except Exception:
                    sess.rollback()
                    raise
                finally:
                    sess.close()

            with patch(
                "backend.pipeline.synthesis.paper_synthesizer"
                ".PaperSynthesizer.synthesize",
                new=_counting_synthesize,
            ), patch(
                "backend.providers.provider_factory"
                ".get_generation_provider",
                lambda settings: MagicMock(),
            ), patch.object(
                _pr_mod, "get_session", _rem_session,
            ), patch(
                "backend.pipeline.stages.PaperSynthesisStage"
                "._evaluate_paper",
                new=_stub_evaluate,
            ):
                from backend.api.routes.ideas import repair_paper
                out = asyncio.run(repair_paper(idea_id))

        assert synthesis_calls["n"] == 0      # no second model call
        assert eval_calls["n"] == 1           # evaluation ran, exactly once
        assert out["repair"]["promoted"] is expect_promoted
        assert out["evaluation"]["status"] == final_status
        with _patched_session(engine):
            after_md, _, rev1 = _canonical(engine, proposal_id)
        if expect_promoted:
            assert after_md == rev1.paper_md == candidate_md
        else:
            assert after_md == original       # canonical untouched
