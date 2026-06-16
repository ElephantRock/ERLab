"""Shared test fixtures for Elephant Rock Research tests."""

import pytest

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import IdeaCandidate, ResearchIdea
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider
from backend.providers.resilience.circuit_breaker import CircuitBreaker
from backend.providers.resilience.retry import RetryConfig
from backend.providers.secrets import KeyVault


class FakeLLMProvider(LLMProvider):
    """Deterministic mock LLM provider for testing."""

    def __init__(self, responses: dict | None = None):
        self._responses = responses or {}
        self._call_log: list[dict] = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._call_log.append({"method": "complete", "messages": messages})
        return self._responses.get("complete", "Test response")

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        self._call_log.append({"method": "complete_stream", "messages": messages})
        yield "Test"

    async def structured_output(self, messages, schema, temperature=0.3, **kwargs) -> dict:
        self._call_log.append(
            {
                "method": "structured_output",
                "messages": messages,
                "schema": schema,
            }
        )
        return self._responses.get("structured_output", {})

    async def embed(self, texts) -> list[list[float]]:
        self._call_log.append({"method": "embed", "texts": texts})
        return [[0.1] * 10 for _ in texts]

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model"


@pytest.fixture
def fake_provider():
    return FakeLLMProvider()


@pytest.fixture
def sample_papers():
    return [
        Paper(id="p1", source="test", title="Test Paper 1", abstract="Abstract 1", year=2024),
        Paper(id="p2", source="test", title="Test Paper 2", abstract="Abstract 2", year=2023),
    ]


@pytest.fixture
def sample_gaps():
    return [
        ResearchGap(
            title="Test Gap 1",
            description="A test research gap",
            gap_type="methodological",
            confidence=0.8,
        ),
        ResearchGap(
            title="Test Gap 2",
            description="Another test gap",
            gap_type="empirical",
            confidence=0.6,
        ),
    ]


@pytest.fixture
def sample_ideas():
    return [
        ResearchIdea(
            title="Idea A",
            problem_statement="Problem A",
            proposed_method="Method A",
            expected_contributions="Contrib A",
            novelty_rationale="Novel A",
            evaluation_approach="Eval A",
            round_generated=1,
            score=0.8,
        ),
        ResearchIdea(
            title="Idea B",
            problem_statement="Problem B",
            proposed_method="Method B",
            expected_contributions="Contrib B",
            novelty_rationale="Novel B",
            evaluation_approach="Eval B",
            round_generated=1,
            score=0.5,
        ),
        ResearchIdea(
            title="Idea C",
            problem_statement="Problem C",
            proposed_method="Method C",
            expected_contributions="Contrib C",
            novelty_rationale="Novel C",
            evaluation_approach="Eval C",
            round_generated=2,
            score=0.9,
        ),
    ]


@pytest.fixture
def sample_candidates():
    return [
        IdeaCandidate(
            title="Candidate A",
            problem_statement="Problem A",
            proposed_method="Method A",
        ),
        IdeaCandidate(
            title="Candidate B",
            problem_statement="Problem B",
            proposed_method="Method B",
        ),
    ]


class FlakyLLMProvider(FakeLLMProvider):
    """Provider that fails N times before succeeding."""

    def __init__(self, fail_count: int = 3, responses: dict | None = None):
        super().__init__(responses)
        self._fail_count = fail_count
        self._attempt = 0

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._attempt += 1
        if self._attempt <= self._fail_count:
            raise ConnectionError(f"Simulated failure {self._attempt}/{self._fail_count}")
        return await super().complete(messages, temperature, max_tokens)


@pytest.fixture
def flaky_provider():
    return FlakyLLMProvider(fail_count=3)


@pytest.fixture
def circuit_breaker():
    return CircuitBreaker(failure_threshold=3, reset_timeout=0.5)


@pytest.fixture
def retry_config():
    return RetryConfig(
        max_retries=5,
        base_delay=0.01,
        max_delay=0.05,
        jitter=0.0,
        cooldown_delay=0.05,
    )


@pytest.fixture
def key_vault(tmp_path):
    vault = KeyVault(
        master_password="test-master-password",
        persist_path=str(tmp_path / "vault.json"),
    )
    vault.add_key("openai", "sk-test-key-1")
    vault.add_key("openai", "sk-test-key-2")
    vault.add_key("openai", "sk-test-key-3")
    return vault
