"""
Confirmatory E2E runner — v1.0.3 stage-attribution and session-binding protocol.

Runs the full deep_research pipeline against z.ai (glm-5.2) with explicit
run-id and session-id binding, preflight validation, durable run-ID reservation
through RunService, attempt-isolated session storage, post-execution binding
verification, session-finalization reconciliation against the cost ledger, and
terminal-paper-outcome validation.

The runner does NOT call ``register_run()`` or ``complete_run()`` — both
belong to the production orchestrator/lifecycle. The runner only verifies
their persisted results.

Testable structure: ``validate_preflight``, ``derive_attempt_session_dir``,
``validate_terminal_outcome``, and ``run_confirmatory`` are importable pure
functions so tests can inject fakes without network calls.
"""
import os
# These MUST be set before any backend imports — the shell env var
# EROCK_EMBEDDING_MODEL has a stale value that overrides .env
os.environ["EROCK_EMBEDDING_MODEL"] = "text-embedding-qwen3-embedding-0.6b"
os.environ["EROCK_EMBEDDING_BASE_URL"] = "http://100.64.0.2:1234"
os.environ.setdefault("EROCK_DATABASE_URL", "sqlite:///./data/elephant_rock.db")

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Frozen research input (must not change between confirmatory runs).
FROZEN_DOMAIN = "transformer attention mechanisms for low-resource language translation"

# Frozen pipeline parameters.
FROZEN_PARAMS: dict = {
    "generation_rounds": 1,
    "ideas_per_round": 1,
    "max_gaps": 3,
    "export_format": "markdown",
}


class PreflightError(Exception):
    """Raised when the preflight validation rejects the run/session identity."""


class TerminalOutcomeError(RuntimeError):
    """Raised when the pipeline result does not contain a valid terminal paper."""


@dataclass
class ConfirmatoryConfig:
    """Configuration for a confirmatory run, resolved before execution."""

    run_id: str
    session_id: str
    domain: str = FROZEN_DOMAIN
    # Optional overrides from the acceptance case manifest. When None,
    # the frozen defaults (deep_research, FROZEN_PARAMS) are used,
    # preserving backward compatibility.
    strategy: str | None = None
    research_question: str | None = None
    generation_rounds: int | None = None
    ideas_per_round: int | None = None
    max_gaps: int | None = None
    export_format: str | None = None
    experiment_spec_id: str | None = None

    def summary(self) -> dict:
        """Credential-free machine-readable summary."""
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "domain": self.domain,
        }


def validate_preflight(config: ConfirmatoryConfig) -> None:
    """Validate run-id and session-id before orchestrator construction.

    Rejects blank, malformed, or unsafe identifiers.
    Raises ``PreflightError`` on any failure — the caller must not continue.
    """
    if not config.run_id or not config.run_id.strip():
        raise PreflightError("run_id is blank")
    if not config.session_id or not config.session_id.strip():
        raise PreflightError("session_id is blank")
    _UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f;`$]')
    for label, value in (("run_id", config.run_id), ("session_id", config.session_id)):
        if _UNSAFE.search(value):
            raise PreflightError(f"{label} contains unsafe characters: {value!r}")


def derive_attempt_session_dir(base_dir: str, run_id: str) -> Path:
    """Derive an attempt-specific session directory from the base and run ID.

    Required properties:
    - same run_id + same base → same derived path
    - different run_id → different derived path
    - derived path is a child of the configured base
    - derived path never equals the configured base
    """
    attempt_dir = Path(base_dir) / "confirmatory" / run_id
    base_resolved = Path(base_dir).resolve()
    attempt_resolved = attempt_dir.resolve()
    # Reject path escape or equality with base.
    if attempt_resolved == base_resolved:
        raise PreflightError(
            f"derived attempt session dir equals the base: {attempt_dir}"
        )
    if not str(attempt_resolved).startswith(str(base_resolved)):
        raise PreflightError(
            f"derived attempt session dir escapes the base: {attempt_dir}"
        )
    return attempt_dir


def _resolve_session(
    session_manager: Any,
    session_id: str,
) -> str:
    """Resolve a session using only the public session-manager API.

    No supplied session ID: create a fresh session, capture its ID, activate it.
    Supplied session ID: require it to exist and be in an actionable state.

    Returns the resolved (immutable) session ID.
    Raises ``PreflightError`` if the session is missing or in a terminal state.
    """
    from backend.pipeline.session.models import SessionState

    session = session_manager.get(session_id)
    if session is None:
        # Create a new session and use its generated ID.
        session = session_manager.create(name="confirmatory-e2e")
        session_id = session.id

    state = getattr(session, "state", None)
    if isinstance(state, SessionState):
        state = state.value

    if state in ("created",):
        session_manager.activate(session_id)
    elif state in ("paused",):
        session_manager.resume(session_id)
    elif state in ("active",):
        pass  # use unchanged
    elif state in ("ended", "expired", "cleaned_up"):
        raise PreflightError(
            f"session_id={session_id!r} is in terminal state {state!r}"
        )

    return session_id


def validate_terminal_outcome(result: Any, run_id: str) -> dict:
    """Validate that the pipeline result contains a valid terminal paper.

    Checks (in order):
    1. Explicit failed/aborted/error/cancelled terminal status → reject.
    2. At least one proposal with ``metadata['full_paper']['paper_markdown']``
       that is a nonblank string → accept.
    3. Otherwise → reject.

    Returns a safe diagnostics dict with structural facts only.

    Raises ``TerminalOutcomeError`` if no valid terminal paper is found.
    """
    # ── 1. Check explicit failed terminal status ──
    terminal_status = getattr(result, "status", None)
    status_str = None
    if terminal_status is not None:
        status_str = terminal_status.value if hasattr(terminal_status, "value") else str(terminal_status)
        status_lower = status_str.lower().strip()
        if status_lower in ("failed", "aborted", "error", "cancelled", "canceled"):
            raise TerminalOutcomeError(
                f"Terminal outcome for run_id={run_id!r} has explicit failed "
                f"status: {status_str!r}"
            )

    # ── 2. Check for at least one completed paper ──
    proposals = getattr(result, "proposals", None)
    proposal_count = 0
    completed_paper_count = 0

    if proposals is not None:
        # Support dict[int, Proposal] and list[Proposal] representations.
        if isinstance(proposals, dict):
            proposal_iter = proposals.values()
        elif isinstance(proposals, (list, tuple)):
            proposal_iter = proposals
        else:
            proposal_iter = []
        for proposal in proposal_iter:
            proposal_count += 1
            metadata = getattr(proposal, "metadata", None)
            if metadata is None:
                continue
            # metadata may be a JSON string or a dict.
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    continue
            if not isinstance(metadata, dict):
                continue
            full_paper = metadata.get("full_paper")
            if not isinstance(full_paper, dict):
                continue
            paper_md = full_paper.get("paper_markdown", "")
            if isinstance(paper_md, str) and paper_md.strip():
                completed_paper_count += 1

    if completed_paper_count == 0:
        raise TerminalOutcomeError(
            f"Terminal outcome for run_id={run_id!r} produced no completed paper. "
            f"proposals={proposal_count}, completed_papers={completed_paper_count}"
        )

    return {
        "run_id": run_id,
        "terminal_status": status_str if terminal_status is not None else None,
        "proposal_count": proposal_count,
        "completed_paper_count": completed_paper_count,
    }


async def run_confirmatory(
    config: ConfirmatoryConfig,
    orchestrator_factory: Any = None,
    session_manager: Any = None,
    run_service: Any = None,
    cost_tracker: Any = None,
) -> dict:
    """Execute the confirmatory pipeline with identity binding and verification.

    This function is the testable boundary: tests inject fake factories and
    managers to prove the binding protocol without network calls.

    The runner does NOT call ``register_run()`` or ``complete_run()`` — both
    belong to the production orchestrator/lifecycle. The runner only verifies
    their persisted results.

    Returns:
        A credential-free machine-readable summary dict.

    Raises:
        PreflightError: if identity validation or session resolution fails.
        RuntimeError: if post-execution binding or session reconciliation fails.
        TerminalOutcomeError: if no valid terminal paper is found.
    """
    # ── 1. Preflight ──
    validate_preflight(config)

    # ── 1b. Build effective settings with attempt-isolated session store ──
    from backend.config import get_settings

    base_settings = get_settings()
    base_session_dir = base_settings.session_data_dir
    attempt_session_dir = derive_attempt_session_dir(base_session_dir, config.run_id)

    # Reject an already-existing attempt directory (don't delete or reuse).
    if attempt_session_dir.exists():
        raise PreflightError(
            f"attempt session directory already exists: {attempt_session_dir}"
        )

    effective_settings = base_settings.model_copy(
        update={
            "session_enabled": True,
            "session_data_dir": str(attempt_session_dir),
        }
    )
    session_data_dir = effective_settings.session_data_dir

    # ── 2. Resolve session ──
    if session_manager is None:
        from backend.pipeline.session.manager import SessionManager
        session_manager = SessionManager(data_dir=session_data_dir)

    resolved_session_id = _resolve_session(session_manager, config.session_id)

    # ── 3. Reserve the run identity through RunService ──
    if run_service is None:
        from backend.api.run_service import get_run_service
        run_service = get_run_service()

    try:
        bound_run_id = run_service.create_run(
            domain=config.domain,
            strategy="deep_research",
            session_id=resolved_session_id,
            config=FROZEN_PARAMS,
            run_id_override=config.run_id,
        )
    except Exception as e:
        raise PreflightError(
            f"RunService.create_run failed for run_id={config.run_id!r}: {e}"
        ) from e

    if bound_run_id != config.run_id:
        raise PreflightError(
            f"RunService bound run_id={bound_run_id!r} but requested {config.run_id!r}"
        )

    # ── 4. Construct orchestrator with effective settings ──
    _strategy = config.strategy or "deep_research"
    if orchestrator_factory is None:
        from backend.pipeline.orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(strategy=_strategy, settings=effective_settings)
    else:
        orchestrator = orchestrator_factory(settings=effective_settings)

    # ── 4b. Verify the orchestrator's production-facing session boundary ──
    services = getattr(orchestrator, "services", None)
    if services is None:
        services = getattr(orchestrator, "_services", None)
    orchestrator_sessions = (
        getattr(services, "session_manager", None)
        if services is not None
        else None
    )
    if orchestrator_sessions is None:
        raise PreflightError(
            "orchestrator session management is not enabled"
        )
    if orchestrator_sessions.get(resolved_session_id) is None:
        raise PreflightError(
            f"resolved session {resolved_session_id!r} is not visible to the "
            f"orchestrator session store"
        )

    # ── 5. Execute pipeline with explicit identities ──
    # Resolve parameters: case overrides take precedence over frozen defaults.
    _gen_rounds = config.generation_rounds or FROZEN_PARAMS["generation_rounds"]
    _ideas = config.ideas_per_round or FROZEN_PARAMS["ideas_per_round"]
    _gaps = config.max_gaps or FROZEN_PARAMS["max_gaps"]
    _export = config.export_format or FROZEN_PARAMS["export_format"]

    run_kwargs: dict[str, Any] = dict(
        domain=config.domain,
        generation_rounds=_gen_rounds,
        ideas_per_round=_ideas,
        max_gaps=_gaps,
        export_format=_export,
        run_id=config.run_id,
        session_id=resolved_session_id,
    )
    if config.research_question:
        run_kwargs["research_question"] = config.research_question
    if config.experiment_spec_id:
        run_kwargs["experiment_spec_id"] = config.experiment_spec_id

    result = await orchestrator.run(**run_kwargs)

    # ── 6. Verify binding ──
    result_run_id = getattr(result, "run_id", None)
    binding_verified = result_run_id == config.run_id
    if not binding_verified:
        raise RuntimeError(
            f"Binding verification failed: result.run_id={result_run_id!r} "
            f"!= requested run_id={config.run_id!r}"
        )

    # ── 7. Verify exactly one lifecycle-owned session record ──
    if cost_tracker is None:
        cost_tracker = getattr(orchestrator, "_cost_tracker", None)

    summary = cost_tracker.summary(run_id=config.run_id) if cost_tracker else {
        "total_tokens": 0, "total_cost_usd": 0.0, "event_count": 0,
    }

    final_session = session_manager.get(resolved_session_id)
    matching = []
    if final_session:
        for record in final_session.runs:
            if getattr(record, "run_id", None) == config.run_id:
                matching.append(record)

    if len(matching) != 1:
        raise RuntimeError(
            f"Expected exactly one session run record for run_id={config.run_id!r}, "
            f"found {len(matching)}"
        )

    run_record = matching[0]
    record_status = getattr(run_record, "status", None)
    record_tokens = getattr(run_record, "tokens_used", 0)
    record_cost = getattr(run_record, "cost_usd", 0.0)
    record_completed = getattr(run_record, "completed_at", None)

    session_reconciled = (
        record_status == "completed"
        and record_completed is not None
        and record_tokens == summary.get("total_tokens", 0)
        and abs(record_cost - summary.get("total_cost_usd", 0.0)) < 1e-6
    )

    if not session_reconciled:
        raise RuntimeError(
            f"Session reconciliation failed for run_id={config.run_id!r}: "
            f"status={record_status!r}, tokens={record_tokens} vs {summary.get('total_tokens')}, "
            f"cost={record_cost} vs {summary.get('total_cost_usd')}"
        )

    # ── 8. Validate terminal research outcome ──
    outcome_diag = validate_terminal_outcome(result, config.run_id)

    return {
        "run_id": config.run_id,
        "session_id": resolved_session_id,
        "result.run_id": result_run_id,
        "event_count": summary.get("event_count", 0),
        "total_tokens": summary.get("total_tokens", 0),
        "total_cost_usd": round(summary.get("total_cost_usd", 0.0), 6),
        "session_tokens": record_tokens,
        "session_cost_usd": round(record_cost, 6),
        "binding_verified": binding_verified,
        "session_reconciled": session_reconciled,
        "session_enabled": True,
        "session_data_dir": str(session_data_dir),
        "terminal_outcome_verified": True,
        "completed_paper_count": outcome_diag["completed_paper_count"],
        # The raw PipelineResult for callers that need to evaluate gates
        # (evaluate_gates reads .outcome, .stage_report, .proposals, etc.).
        # Existing callers that only access summary dict keys are unaffected.
        "_pipeline_result": result,
    }


def _generate_id(prefix: str) -> str:
    """Generate a unique run or session ID."""
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


async def main():
    parser = argparse.ArgumentParser(description="Confirmatory E2E pipeline runner")
    parser.add_argument("--run-id", default=None, help="Explicit run ID (auto-generated if omitted)")
    parser.add_argument("--session-id", default=None, help="Explicit session ID (auto-generated if omitted)")
    parser.add_argument("--domain", default=FROZEN_DOMAIN, help="Research domain (frozen for confirmatory runs)")
    # Acceptance mode (Phase A2): manifest-driven, verdict-classified.
    parser.add_argument("--acceptance-case", default=None,
                        help="Path to a LivePaperAcceptanceCase JSON manifest. "
                             "When set, runs in acceptance mode (preflight + verdict + evidence).")
    parser.add_argument("--evidence-dir", default=None,
                        help="Directory for the immutable evidence bundle (acceptance mode).")
    args = parser.parse_args()

    # ── Acceptance mode ──
    if args.acceptance_case:
        if not args.evidence_dir:
            print("--evidence-dir is required with --acceptance-case")
            sys.exit(3)
        from backend.acceptance.runner import run_acceptance
        report, _ev = await run_acceptance(
            case_path=args.acceptance_case,
            evidence_dir=args.evidence_dir,
            run_id=args.run_id,
            session_id=args.session_id,
        )
        print(f"ACCEPTANCE VERDICT: {report.verdict.value.upper()} (exit {report.exit_code})")
        for g in report.failed_gates:
            print(f"  FAILED GATE: {g.gate} ({g.reason_code})")
        sys.exit(report.exit_code)

    run_id = args.run_id or _generate_id("run")
    session_id = args.session_id or _generate_id("session")

    config = ConfirmatoryConfig(
        run_id=run_id,
        session_id=session_id,
        domain=args.domain,
    )

    print("=" * 60)
    print("CONFIRMATORY E2E — deep_research strategy")
    print("Provider: z.ai (glm-5.2)")
    print("=" * 60)
    print(f"run_id:     {config.run_id}")
    print(f"session_id: {config.session_id}")
    print(f"domain:     {config.domain}")
    print()

    try:
        summary = await run_confirmatory(config)
        print()
        print("=" * 60)
        print("CONFIRMATORY SUMMARY")
        print("=" * 60)
        for k, v in summary.items():
            print(f"  {k}: {v}")
    except PreflightError as e:
        print(f"PREFLIGHT FAILED: {e}")
        sys.exit(1)
    except TerminalOutcomeError as e:
        print(f"TERMINAL OUTCOME FAILED: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Pipeline error: {type(e).__name__}: {str(e)[:300]}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
