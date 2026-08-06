"""Typed terminal outcomes for gap analysis — behavior contract spec.

This module freezes the intended behavior BEFORE the production code is
changed. It encodes the outcome matrix from the gap-contract plan:

    Input condition                         Expected analyzer behavior             Expected pipeline outcome
    Valid nonempty payload                  Return typed gaps                      running (continue)
    Valid {"gaps": []}                      Return empty typed result              no_research_gap (halt)
    Invalid schema                          Raise GapAnalysisOutputContractError   failed_output_contract (halt)
    Provider failure after retry exhaustion Raise GapAnalysisExecutionError        failed_execution (halt)
    Invalid cluster ID                      Contract error                         halt
    Blank required string                   Contract error                         halt
    String confidence such as "high"        Contract error                         halt
    Extra paper-shaped fields               Contract error                         halt
    Mixed valid/invalid gaps                Whole payload fails                    halt

It also freezes these invariants:

    Gap analysis uses structured_output(), not complete()
    No raw model response is logged
    No malformed result becomes []
    No execution failure becomes []
    No-gap is distinguishable from failure
    Later stages are marked not_reached after terminalization

These tests are the authoritative definition of correctness for commits 2 and 3.
They fail (red) until the production behavior lands.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.pipeline.gap_analysis.cluster_service import ClusterReport

# Commit 2 symbols — imported eagerly so collection fails clearly if absent.
from backend.pipeline.gap_analysis.contracts import (  # noqa: E402
    GapAnalysisExecutionError,
    GapCandidatePayload,
    gap_analysis_schema,
)
from backend.pipeline.gap_analysis.gap_analyzer import (
    GapAnalysisOutputContractError,
    GapAnalyzer,
)
from backend.pipeline.gap_analysis.models import ClusterInfo, ResearchGap
from backend.pipeline.literature.models import Author, Paper

# Commit 3 symbol — typed pipeline terminal outcome.
from backend.pipeline.result import PipelineOutcome  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────────


def _make_papers(n: int = 2) -> list[Paper]:
    return [
        Paper(
            id=f"p{i}",
            source="test",
            title=f"Research Paper {i}: Advances in NLP Method {i}",
            abstract=(
                f"Abstract for paper {i}. Investigates transformer attention with "
                "retrieval augmented generation for improved performance."
            ),
            authors=[Author(name=f"Author {i}")],
            year=2024,
        )
        for i in range(n)
    ]


def _cluster_report_with(*ids: int) -> ClusterReport:
    return ClusterReport(
        clusters=[ClusterInfo(cluster_id=cid, label=f"C{cid}", paper_count=2) for cid in ids],
        total_papers=len(_make_papers()),
    )


class _RecordingProvider:
    """Minimal provider stub that records the call method and serves a fixed
    structured payload.

    Implements only structured_output() — the canonical analyzer entrypoint.
    ``method_calls`` records every invocation so tests can assert the analyzer
    used structured_output() and never complete().
    """

    def __init__(self, payload: dict | list | Exception):
        self._payload = payload
        self.method_calls: list[str] = []
        self.structured_calls: list[dict] = []
        self._last_receipt = None

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096, **kw):
        self.method_calls.append("structured_output")
        self.structured_calls.append({"schema": schema, "messages": messages})
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def complete(self, messages, temperature=0.7, max_tokens=4096, **kw):  # pragma: no cover - defensive
        self.method_calls.append("complete")
        raise AssertionError("GapAnalyzer must NOT call complete(); use structured_output()")

    async def complete_stream(self, *a, **kw):  # pragma: no cover - defensive
        yield ""

    @property
    def provider_name(self):
        return "recording"

    @property
    def default_model(self):
        return "recording-model"


def _valid_gap(**over) -> dict:
    base = {
        "title": "Cross-domain transfer in transformer models",
        "description": "Current transformer models struggle to transfer across domains.",
        "gap_type": "methodological",
        "related_clusters": [0],
        "potential_impact": "Enables robust cross-domain NLP.",
        "confidence": 0.8,
    }
    base.update(over)
    return base


def _run(coro):
    return asyncio.run(coro)


# ── Analyzer behavior matrix ──────────────────────────────────────────


class TestAnalyzerOutcomes:
    """Freezes analyzer-level outcomes for every input condition."""

    def test_valid_nonempty_payload_returns_typed_gaps(self):
        provider = _RecordingProvider({"gaps": [_valid_gap()]})
        gaps, report = _run(GapAnalyzer(provider).analyze(_make_papers(), max_gaps=2))
        assert len(gaps) == 1
        assert isinstance(gaps[0], ResearchGap)
        assert gaps[0].title
        assert 0.0 <= gaps[0].confidence <= 1.0
        assert isinstance(report, ClusterReport)
        # Must be routed through structured_output, never complete().
        assert provider.method_calls == ["structured_output"]

    def test_valid_empty_payload_returns_empty_typed_result(self):
        provider = _RecordingProvider({"gaps": []})
        gaps, _ = _run(GapAnalyzer(provider).analyze(_make_papers()))
        assert gaps == []
        assert provider.method_calls == ["structured_output"]

    def test_invalid_schema_raises_output_contract_error(self):
        # Not a dict, not a list — structurally incompatible.
        provider = _RecordingProvider("a bare string is not valid")
        with pytest.raises(GapAnalysisOutputContractError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))
        assert provider.method_calls == ["structured_output"]

    def test_provider_failure_raises_execution_error(self):
        provider = _RecordingProvider(RuntimeError("provider down"))
        with pytest.raises(GapAnalysisExecutionError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))
        assert provider.method_calls == ["structured_output"]

    def test_invalid_cluster_id_raises_contract_error(self):
        # Cluster 99 does not exist in a report that only has cluster 0.
        # Validated directly so the cluster report is controlled (the
        # analyzer's clustering on synthetic papers may yield no clusters).
        from backend.pipeline.gap_analysis.gap_analyzer import _validate_payload
        report = _cluster_report_with(0)
        with pytest.raises(GapAnalysisOutputContractError):
            _validate_payload({"gaps": [_valid_gap(related_clusters=[99])]}, report)

    def test_blank_required_string_raises_contract_error(self):
        provider = _RecordingProvider({"gaps": [_valid_gap(title="   ")]})
        with pytest.raises(GapAnalysisOutputContractError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))

    def test_string_confidence_raises_contract_error(self):
        provider = _RecordingProvider({"gaps": [_valid_gap(confidence="high")]})
        with pytest.raises(GapAnalysisOutputContractError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))

    def test_extra_paper_shaped_fields_raise_contract_error(self):
        # Additional undeclared field must be rejected (extra forbidden).
        provider = _RecordingProvider({"gaps": [_valid_gap(references=["fake-ref"])]})
        with pytest.raises(GapAnalysisOutputContractError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))

    def test_mixed_valid_invalid_gaps_fails_whole_payload(self):
        # One valid, one with an invalid cluster id — the whole payload fails.
        # Validated directly so the cluster report is controlled.
        from backend.pipeline.gap_analysis.gap_analyzer import _validate_payload
        report = _cluster_report_with(0)
        with pytest.raises(GapAnalysisOutputContractError):
            _validate_payload(
                {"gaps": [_valid_gap(), _valid_gap(title="Second", related_clusters=[777])]},
                report,
            )


# ── Invariants ────────────────────────────────────────────────────────


class TestAnalyzerInvariants:
    """Freezes structural invariants that span conditions."""

    def test_uses_structured_output_not_complete(self):
        provider = _RecordingProvider({"gaps": [_valid_gap()]})
        _run(GapAnalyzer(provider).analyze(_make_papers()))
        assert "structured_output" in provider.method_calls
        assert "complete" not in provider.method_calls

    def test_no_raw_model_response_logged(self, caplog):
        import logging
        caplog.set_level(logging.DEBUG, logger="backend.pipeline.gap_analysis.gap_analyzer")
        provider = _RecordingProvider({"gaps": [_valid_gap(description="SECRETRAWPAYLOAD")]})
        _run(GapAnalyzer(provider).analyze(_make_papers()))
        # The semantic content of the model response must never appear in logs.
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "SECRETRAWPAYLOAD" not in joined

    def test_malformed_result_never_becomes_empty_list(self):
        provider = _RecordingProvider({"gaps": "not-a-list"})
        # Must raise, NOT return ([], report).
        with pytest.raises(GapAnalysisOutputContractError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))

    def test_execution_failure_never_becomes_empty_list(self):
        provider = _RecordingProvider(ConnectionError("transport closed"))
        # Must raise ExecutionError, NOT return ([], report).
        with pytest.raises(GapAnalysisExecutionError):
            _run(GapAnalyzer(provider).analyze(_make_papers()))

    def test_no_gap_is_distinguishable_from_failure(self):
        # No-gap → empty list, no exception.
        provider_ok = _RecordingProvider({"gaps": []})
        gaps, _ = _run(GapAnalyzer(provider_ok).analyze(_make_papers()))
        assert gaps == []
        # Failure → exception. The two paths must not collapse to the same result.
        provider_bad = _RecordingProvider(RuntimeError("boom"))
        with pytest.raises(GapAnalysisExecutionError):
            _run(GapAnalyzer(provider_bad).analyze(_make_papers()))


# ── Typed contract models ─────────────────────────────────────────────


class TestGapContractModels:
    """Freezes the canonical typed schema generated from the Pydantic models."""

    def test_payload_schema_is_generated_from_model(self):
        schema = gap_analysis_schema()
        # The provider schema must be derived from the model, not handwritten.
        assert schema["type"] == "object"
        assert "gaps" in schema["properties"]
        # The gap item must require all six canonical fields.
        gap_props = schema["properties"]["gaps"]["items"]["properties"]
        for field in (
            "title", "description", "gap_type", "related_clusters",
            "potential_impact", "confidence",
        ):
            assert field in gap_props

    def test_gap_candidate_validates_canonical_fields(self):
        g = GapCandidatePayload.model_validate(_valid_gap())
        assert g.confidence == pytest.approx(0.8)
        assert g.related_clusters == [0]

    def test_gap_candidate_strips_strings(self):
        g = GapCandidatePayload.model_validate(_valid_gap(title="  spaced  "))
        assert g.title == "spaced"

    def test_gap_candidate_rejects_blank_required_string(self):
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(title="   "))

    def test_gap_candidate_rejects_string_confidence(self):
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(confidence="high"))

    def test_gap_candidate_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(references=["x"]))

    def test_gap_candidate_confidence_bounds(self):
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(confidence=1.5))
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(confidence=-0.1))

    def test_gap_candidate_related_clusters_unique_nonnegative(self):
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(related_clusters=[0, 0]))
        with pytest.raises(ValidationError):
            GapCandidatePayload.model_validate(_valid_gap(related_clusters=[-1]))

    def test_gap_type_is_controlled_enum(self):
        schema = gap_analysis_schema()
        # gap_type must be a constrained enum, not free text.
        gap_type_schema = schema["properties"]["gaps"]["items"]["properties"]["gap_type"]
        assert "enum" in gap_type_schema, "gap_type must be a controlled enum"
        allowed = set(gap_type_schema["enum"])
        assert {"methodological", "empirical", "theoretical", "cross-domain"} <= allowed


# ── Pipeline terminal outcome mapping ─────────────────────────────────


class TestPipelineOutcomeEnum:
    """Freezes the typed terminal outcomes Commit 3 introduces."""

    def test_outcome_enum_members(self):
        members = {m.value for m in PipelineOutcome}
        assert {
            "running", "succeeded", "no_research_gap",
            "failed_output_contract", "failed_execution",
        } <= members

    def test_outcome_defaults_to_running(self):
        from backend.pipeline.result import PipelineResult
        result = PipelineResult()
        assert result.outcome == PipelineOutcome.RUNNING
        assert result.terminal_stage is None
        assert result.terminal_reason is None

    def test_outcome_is_string_serializable(self):
        # StrEnum: each member equals its string value.
        assert PipelineOutcome.NO_RESEARCH_GAP == "no_research_gap"
        assert PipelineOutcome.FAILED_OUTPUT_CONTRACT == "failed_output_contract"


# ── Pipeline-level terminalization (stage wiring) ─────────────────────


class TestGapStageTerminalization:
    """Freezes how GapAnalysisStage maps analyzer outcomes to pipeline
    terminal outcomes and downstream not_reached states.

    These assert against the real stage; the heavy orchestration loop is
    covered by Commit 7. Here we prove the stage's own contract.
    """

    def _make_stage(self, analyzer) -> tuple:
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import GapAnalysisStage, StageContext
        hooks = MagicMock()
        # dispatch_sync_safe is async in production (HookDispatcher).
        hooks.dispatch_sync_safe = AsyncMock()
        stage = GapAnalysisStage(
            gap_analyzer=analyzer,
            goal_manager=None,
            hooks=hooks,
            memory=None,
        )
        ctx = StageContext(result=PipelineResult(), all_papers=_make_papers())
        return stage, ctx

    def test_valid_gaps_continue(self):
        analyzer = MagicMock()
        analyzer.analyze = AsyncMock(
            return_value=([ResearchGap(title="G", description="d", gap_type="methodological",
                                       confidence=0.8)], _cluster_report_with(0))
        )
        stage, ctx = self._make_stage(analyzer)
        proceed = _run(stage.execute(ctx))
        assert proceed is True
        assert ctx.result.outcome == PipelineOutcome.RUNNING

    def test_no_gap_halts_with_no_research_gap(self):
        analyzer = MagicMock()
        analyzer.analyze = AsyncMock(return_value=([], _cluster_report_with(0)))
        stage, ctx = self._make_stage(analyzer)
        proceed = _run(stage.execute(ctx))
        assert proceed is False
        assert ctx.result.outcome == PipelineOutcome.NO_RESEARCH_GAP
        assert ctx.result.terminal_stage == "gap_analysis"

    def test_output_contract_failure_halts(self):
        analyzer = MagicMock()
        analyzer.analyze = AsyncMock(side_effect=GapAnalysisOutputContractError("bad"))
        stage, ctx = self._make_stage(analyzer)
        proceed = _run(stage.execute(ctx))
        assert proceed is False
        assert ctx.result.outcome == PipelineOutcome.FAILED_OUTPUT_CONTRACT
        assert ctx.result.terminal_stage == "gap_analysis"

    def test_execution_failure_halts(self):
        analyzer = MagicMock()
        analyzer.analyze = AsyncMock(side_effect=GapAnalysisExecutionError("down"))
        stage, ctx = self._make_stage(analyzer)
        proceed = _run(stage.execute(ctx))
        assert proceed is False
        assert ctx.result.outcome == PipelineOutcome.FAILED_EXECUTION
        assert ctx.result.terminal_stage == "gap_analysis"


# ── Downstream not_reached after terminalization ──────────────────────


class TestDownstreamNotReached:
    """Freezes the requirement that, after a gap-analysis terminal outcome,
    later stages are recorded as not_reached (orchestrator-level behavior)."""

    def test_stage_status_enum_has_execution_failed(self):
        # Commit 3 adds the execution_failed stage status.
        from backend.pipeline.result import StageReport
        # Construct a report with the new status to prove it is a valid value.
        rep = StageReport(name="gap_analysis", status="execution_failed")
        assert rep.status == "execution_failed"
        rep2 = StageReport(name="gap_analysis", status="contract_violation")
        assert rep2.status == "contract_violation"

    def test_coordinator_marks_later_stages_not_reached_after_terminal(self):
        """Orchestrator-level: when gap_analysis returns False (terminalized),
        the real RunCoordinator must mark all later stages not_reached and
        return False — proving the wiring between the stage's typed outcome
        and the orchestration loop (Commit 3 exit gate).
        """
        from types import SimpleNamespace

        from backend.pipeline.execution.run_state import RunCheckpoint
        from backend.pipeline.orchestrator.run_coordinator import RunCoordinator
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import PipelineStage, StageContext
        from backend.pipeline.strategies.models import StageConfig, StrategyConfig

        class _StubLifecycle:
            doom_detected = False

            async def post_stage_common(self, *a, **kw):
                pass

            async def post_stage_specific(self, *a, **kw):
                return "continue"

        class _StubCompaction:
            async def prepare_context(self, ctx, stage_name):
                return ctx

        class _StubPersistence:
            def advance_stage(self, *a, **kw):
                pass

            def save_checkpoint(self, *a, **kw):
                pass

        class _StubProcessor:
            def persist_stage_report(self, *a, **kw):
                pass

            async def persist_stage_context(self, *a, **kw):
                pass

        class _StubServices:
            cross_stage_ctx = None
            governance_policy = None

        settings = SimpleNamespace(heartbeat_enabled=False)

        class _FakeOrchestrator:
            def __init__(self):
                self._provider = None
                self._strategy_config = StrategyConfig(
                    name="test",
                    stages={
                        "gap_analysis": StageConfig(enabled=True),
                        "idea_generation": StageConfig(enabled=True),
                    },
                )
                self._strategy_name = "test"
                self._lifecycle = _StubLifecycle()
                self._compaction = _StubCompaction()
                self._persistence = _StubPersistence()
                self._processor = _StubProcessor()
                self._services = _StubServices()
                self._settings = settings
                self._model_manager = None
                self._operation_executor = None
                self._mm_stage_aliases = {}
                self._task_router = None
                self._resolve_user_model = None
                self._should_stop = lambda: False
                self._STAGE_ORDER = ["gap_analysis", "idea_generation"]
                self._last_stage_retries = 0

            async def _execute_stage_with_retry(self, stage, ctx, checkpoint):
                return await stage.execute(ctx)

            def _record_stage(self, stage_name, t0):
                pass

        class _TerminalGapStage(PipelineStage):
            name = "gap_analysis"

            async def execute(self, ctx: StageContext) -> bool:
                from backend.pipeline.result import PipelineOutcome
                ctx.result.outcome = PipelineOutcome.NO_RESEARCH_GAP
                ctx.result.terminal_stage = "gap_analysis"
                ctx.result.terminal_reason = "no gaps identified"
                return False

        class _ShouldNotRunStage(PipelineStage):
            name = "idea_generation"
            ran = False

            async def execute(self, ctx: StageContext) -> bool:
                _ShouldNotRunStage.ran = True
                return True

        fake_orch = _FakeOrchestrator()
        coordinator = RunCoordinator(fake_orch)

        result = PipelineResult()
        ctx = StageContext(result=result)
        checkpoint = RunCheckpoint.create_new(
            run_id="run_term", stage_names=["gap_analysis", "idea_generation"],
        )

        completed = _run(coordinator.execute_stage_loop(
            stages=[_TerminalGapStage(), _ShouldNotRunStage()],
            ctx=ctx,
            result=result,
            checkpoint=checkpoint,
            run_id="run_term",
            domain="test",
            db_run_id=None,
        ))

        # The loop returns False (halted) and the later stage never ran.
        assert completed is False
        assert _ShouldNotRunStage.ran is False
        # The typed terminal outcome is preserved on the result.
        assert result.outcome == PipelineOutcome.NO_RESEARCH_GAP
        assert result.terminal_stage == "gap_analysis"
        # gap_analysis executed; idea_generation was marked not_reached.
        statuses = {r.name: r.status for r in result.stage_report}
        assert statuses.get("gap_analysis") == "executed"
        assert statuses.get("idea_generation") == "not_reached"
