"""
Confirmatory E2E runner — v1.0.3 stage-attribution and session-binding protocol.

Runs the full deep_research pipeline against z.ai (glm-4.6) with explicit
run-id and session-id binding, preflight validation, durable run-ID reservation
through RunService, post-execution binding verification, and session-
finalization reconciliation against the cost ledger.

The runner does NOT call ``register_run()`` or ``complete_run()`` — both
belong to the production orchestrator/lifecycle. The runner only verifies
their persisted results.

Testable structure: ``validate_preflight`` and ``run_confirmatory`` are
importable pure functions so tests can inject fakes without network calls.
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


@dataclass
class ConfirmatoryConfig:
    """Configuration for a confirmatory run, resolved before execution."""

    run_id: str
    session_id: str
    domain: str = FROZEN_DOMAIN

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
    """
    # ── 1. Preflight ──
    validate_preflight(config)

    # ── 1b. Build effective settings with session management enabled ──
    # The confirmatory protocol requires session finalization. The default
    # configuration has session_enabled=False, which would leave the
    # orchestrator's session_manager as None — preventing lifecycle-owned
    # registration and finalization. Override it explicitly here.
    from backend.config import get_settings

    base_settings = get_settings()
    effective_settings = base_settings.model_copy(
        update={"session_enabled": True}
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
    # Pass the same effective_settings so the orchestrator's ServiceRegistry
    # initializes its own SessionManager on the same directory. The runner and
    # the production lifecycle independently open the same public session store.
    if orchestrator_factory is None:
        from backend.pipeline.orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(strategy="deep_research", settings=effective_settings)
    else:
        orchestrator = orchestrator_factory(settings=effective_settings)

    # ── 4b. Verify the orchestrator's production-facing session boundary ──
    # The orchestrator must have opened a session manager on the same store.
    # If session_enabled was lost or ignored, session_manager will be None and
    # the lifecycle will never register or finalize the run.
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
    result = await orchestrator.run(
        domain=config.domain,
        generation_rounds=FROZEN_PARAMS["generation_rounds"],
        ideas_per_round=FROZEN_PARAMS["ideas_per_round"],
        max_gaps=FROZEN_PARAMS["max_gaps"],
        export_format=FROZEN_PARAMS["export_format"],
        run_id=config.run_id,
        session_id=resolved_session_id,
    )

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
    }


def _generate_id(prefix: str) -> str:
    """Generate a unique run or session ID."""
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


async def main():
    parser = argparse.ArgumentParser(description="Confirmatory E2E pipeline runner")
    parser.add_argument("--run-id", default=None, help="Explicit run ID (auto-generated if omitted)")
    parser.add_argument("--session-id", default=None, help="Explicit session ID (auto-generated if omitted)")
    parser.add_argument("--domain", default=FROZEN_DOMAIN, help="Research domain (frozen for confirmatory runs)")
    args = parser.parse_args()

    run_id = args.run_id or _generate_id("run")
    session_id = args.session_id or _generate_id("session")

    config = ConfirmatoryConfig(
        run_id=run_id,
        session_id=session_id,
        domain=args.domain,
    )

    print("=" * 60)
    print("CONFIRMATORY E2E — deep_research strategy")
    print("Provider: z.ai (glm-4.6)")
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
