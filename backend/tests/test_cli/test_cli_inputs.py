"""Tests for CLI _build_research_idea helper and option parsing (P12)."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("chromadb", MagicMock())

from backend.cli.main import _build_research_idea


def test_build_research_idea_with_explicit_fields():
    """When method and contributions are provided, use them directly."""
    provider = MagicMock()

    idea = _build_research_idea(
        text="Research on transformer attention mechanisms",
        provider=provider,
        method="Multi-head attention with sparse routing",
        contributions="Improved efficiency and accuracy",
    )

    assert idea.proposed_method == "Multi-head attention with sparse routing"
    assert idea.expected_contributions == "Improved efficiency and accuracy"
    assert idea.problem_statement == "Research on transformer attention mechanisms"
    # Provider should NOT have been called since both fields were provided
    assert provider.generate.call_count == 0


def test_build_research_idea_uses_llm_fallback():
    """When method/contributions are None, the function calls the LLM provider."""
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=json.dumps({
            "title": "LLM Generated Title",
            "proposed_method": "LLM generated method",
            "expected_contributions": "LLM generated contributions",
        })
    )

    idea = _build_research_idea(
        text="Research on transformer attention mechanisms",
        provider=provider,
        method=None,
        contributions=None,
    )

    assert provider.generate.call_count == 1
    assert idea.proposed_method == "LLM generated method"
    assert idea.expected_contributions == "LLM generated contributions"
