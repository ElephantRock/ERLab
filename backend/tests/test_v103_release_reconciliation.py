"""v1.0.3 regression freeze for release-truth reconciliation.

These tests intentionally describe the approved v1.0.3 contracts before the
production repairs are applied.  They freeze only the six observed blockers:

* every concrete provider accepts and attributes stage/run_id usage context;
* cost views and persistence are scoped to one run;
* session terminalization consumes the CostTracker summary contract;
* structured-output calls use the usage-enabled provider boundary;
* incomplete accounting cannot be labelled reconciled;
* package and README release identities agree on v1.0.3.

No external provider calls are made.
"""
from __future__ import annotations

import inspect
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.orchestrator.stage_lifecycle import StageLifecycle
from backend.pipeline.persistence import PipelinePersistence
from backend.providers.anthropic_provider import AnthropicProvider
from backend.providers.base import CostEvent
from backend.providers.gemini_provider import GeminiProvider
from backend.providers.litellm_provider import LiteLLMProvider
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openai_provider import OpenAIProvider
from backend.providers.provider_factory import CostTracker

PROVIDER_CLASSES = (
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    LiteLLMProvider,
)


@pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES, ids=lambda cls: cls.__name__)
def test_complete_with_usage_context_contract_is_uniform(provider_cls):
    """Every concrete provider must honor the base usage-context signature."""
    params = inspect.signature(provider_cls.complete_with_usage).parameters
    assert "stage" in params
    assert "run_id" in params


@pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES, ids=lambda cls: cls.__name__)
def test_complete_with_usage_attributes_cost_to_stage_and_run(provider_cls):
    """Provider usage callbacks must preserve the actual stage and run identity."""
    source = inspect.getsource(provider_cls.complete_with_usage)
    assert "stage=stage" in source
    assert "run_id=run_id" in source


@pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES, ids=lambda cls: cls.__name__)
def test_structured_output_with_usage_context_contract_is_uniform(provider_cls):
    """Structured calls are billable and require the same attribution contract."""
    params = inspect.signature(provider_cls.structured_output_with_usage).parameters
    assert "stage" in params
    assert "run_id" in params


def _event(run_id: str, input_tokens: int, output_tokens: int) -> CostEvent:
    return CostEvent(
        provider="openai",
        model="test-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stage="test_stage",
        run_id=run_id,
    )


def test_cost_tracker_exposes_run_scoped_views(tmp_path):
    """A tracker may be process-lived, but every accounting view is run-scoped."""
    tracker = CostTracker()
    tracker.record(_event("run_a", 10, 5))
    tracker.record(_event("run_b", 20, 10))

    summary_a = tracker.summary(run_id="run_a")
    summary_b = tracker.summary(run_id="run_b")

    assert summary_a["event_count"] == 1
    assert summary_a["total_tokens"] == 15
    assert summary_b["event_count"] == 1
    assert summary_b["total_tokens"] == 30

    ledger_a = tmp_path / "run_a.jsonl"
    tracker.persist(str(ledger_a), run_id="run_a")
    records = [json.loads(line) for line in ledger_a.read_text(encoding="utf-8").splitlines()]
    assert [record["run_id"] for record in records] == ["run_a"]


def test_two_sequential_run_ledgers_are_disjoint(tmp_path):
    """Persisting run B must never inherit run A's events or budget total."""
    tracker = CostTracker()
    tracker.record(_event("run_a", 100, 50))
    tracker.record(_event("run_b", 200, 100))

    persistence = PipelinePersistence()
    persistence.persist_cost_ledger(
        run_id="run_a",
        tracker=tracker,
        cost_persist_dir=str(tmp_path),
        cost_cap_usd=100.0,
    )
    persistence.persist_cost_ledger(
        run_id="run_b",
        tracker=tracker,
        cost_persist_dir=str(tmp_path),
        cost_cap_usd=100.0,
    )

    ledger_a = [
        json.loads(line)
        for line in (tmp_path / "run_a_cost_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    ledger_b = [
        json.loads(line)
        for line in (tmp_path / "run_b_cost_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    summary_a = json.loads(
        (tmp_path / "run_a_cost_summary.json").read_text(encoding="utf-8")
    )
    summary_b = json.loads(
        (tmp_path / "run_b_cost_summary.json").read_text(encoding="utf-8")
    )

    assert [record["run_id"] for record in ledger_a] == ["run_a"]
    assert [record["run_id"] for record in ledger_b] == ["run_b"]
    assert summary_a["record_count"] == 1
    assert summary_a["total_tokens"] == 150
    assert summary_b["record_count"] == 1
    assert summary_b["total_tokens"] == 300


class _Hooks:
    async def dispatch_sync_safe(self, _name, _payload):
        return None


class _SessionManager:
    def __init__(self) -> None:
        self.completed: tuple | None = None

    def complete_run(self, session_id, run_id, *, tokens_used, cost_usd):
        self.completed = (session_id, run_id, tokens_used, cost_usd)


class _Services:
    def __init__(self) -> None:
        self.hooks = _Hooks()
        self.session_manager = _SessionManager()

    def __getattr__(self, _name):
        return None


class _Processor:
    def evaluate_pipeline(self, _result, _ctx):
        return None

    def collect_warnings(self, _result):
        return None


class _Persistence:
    def mark_run_completed(self, _db_run_id):
        return None

    def mark_run_failed(self, _db_run_id, _reason):
        return None

    def persist_cost_ledger(self, **_kwargs):
        return None

    def persist_proposals(self, _result, _db_run_id):
        return None


@pytest.mark.anyio
async def test_session_enabled_terminalization_uses_tracker_summary(tmp_path):
    """A completed session run must not read nonexistent tracker properties."""
    services = _Services()
    tracker = CostTracker()
    tracker.record(_event("run_session", 10, 5))
    lifecycle = StageLifecycle(
        services=services,
        settings=SimpleNamespace(
            cost_persist_dir=str(tmp_path),
            budget_max_cost_usd=100.0,
            run_artifacts_enabled=False,
        ),
        persistence=_Persistence(),
        integration=None,
        processor=_Processor(),
        provider=object(),
        cost_tracker=tracker,
    )
    result = SimpleNamespace(
        proposals=[object()],
        ideas=[],
        gaps=[],
        novelty_reports={},
    )

    await lifecycle.post_pipeline_finalize(
        result=result,
        ctx=SimpleNamespace(),
        run_id="run_session",
        domain="test",
        strategy="deep_research",
        params={},
        db_run_id=None,
        session_id="session_1",
        ideas_per=1,
        rounds=1,
    )

    assert services.session_manager.completed is not None
    session_id, run_id, tokens_used, cost_usd = services.session_manager.completed
    assert (session_id, run_id) == ("session_1", "run_session")
    assert tokens_used == 15
    assert cost_usd > 0


def test_gateway_schema_branch_uses_usage_enabled_provider_path():
    """The production schema branch must not bypass structured usage receipts."""
    source = inspect.getsource(PipelineOrchestrator.__init__)
    assert "structured_output_with_usage" in source
    assert (
        "return await inner_provider.structured_output(messages, schema, temperature)"
        not in source
    )


def test_cost_summary_can_represent_partial_accounting():
    """A nonempty ledger alone is insufficient to claim full reconciliation."""
    source = inspect.getsource(PipelinePersistence.persist_cost_ledger)
    assert '"partial"' in source
    assert (
        '"reconciled" if summary.get("event_count", 0) > 0 else "no_events"'
        not in source
    )


def test_release_identity_is_v1_0_3_everywhere():
    """The package built from the release branch must identify the same release."""
    repo_root = Path(__file__).resolve().parents[2]
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert pyproject["project"]["version"] == "1.0.3"
    assert "**v1.0.3**" in readme[:500]
