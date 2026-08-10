"""Tests for the shared JSON extraction utility."""
import pytest

from backend.pipeline.utils.json_extraction import (
    JsonExtractionError,
    extract_json,
)


class TestDirectParse:
    """Strategy 1: text is already valid JSON."""

    def test_dict(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_list(self):
        result = extract_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_nested(self):
        result = extract_json('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_whitespace_padded(self):
        result = extract_json('  \n  {"x": 1}  \n  ')
        assert result == {"x": 1}

    def test_number_rejected(self):
        """A bare number is valid JSON but not a dict/list — should fall through."""
        result = extract_json("42")
        assert result == {}  # falls through to empty dict

    def test_string_rejected(self):
        """A bare string is valid JSON but not a dict/list."""
        result = extract_json('"hello"')
        assert result == {}  # falls through


class TestJsonCodeFence:
    """Strategy 2: ```json ... ``` code fence."""

    def test_json_fence(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_json_fence_with_surrounding_text(self):
        text = 'I analyzed the data.```json\n{"score": 0.85}\n```\nThat is the result.'
        assert extract_json(text) == {"score": 0.85}

    def test_json_fence_list(self):
        text = '```json\n[1, 2, 3]\n```'
        assert extract_json(text) == [1, 2, 3]


class TestPlainCodeFence:
    """Strategy 3: ``` ... ``` without language tag."""

    def test_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_plain_fence_with_text(self):
        text = 'Results:\n```\n{"x": 1}\n```\nDone.'
        assert extract_json(text) == {"x": 1}


class TestBracketExtraction:
    """Strategy 4: find first { ... } or [ ... ]."""

    def test_embedded_dict(self):
        text = 'The result is {"key": "value"} and that is all.'
        assert extract_json(text) == {"key": "value"}

    def test_embedded_list(self):
        text = 'Items: [1, 2, 3]'
        assert extract_json(text) == [1, 2, 3]

    def test_embedded_list_of_dicts(self):
        """List-of-dicts extraction: finds [ first, matches to ]."""
        text = 'Items: [{"a": 1}, {"b": 2}]\nDone.'
        assert extract_json(text) == [{"a": 1}, {"b": 2}]

    def test_nested_brackets(self):
        text = 'Data: {"outer": {"inner": [1, 2]}}'
        assert extract_json(text) == {"outer": {"inner": [1, 2]}}

    def test_brackets_in_strings(self):
        """Brackets inside JSON strings should not affect matching."""
        text = '{"msg": "use {curly} braces"}'
        assert extract_json(text) == {"msg": "use {curly} braces"}


class TestFailureModes:
    """Edge cases and failure handling."""

    def test_empty_string(self):
        assert extract_json("") == {}

    def test_none_like(self):
        assert extract_json("  ") == {}

    def test_no_json_strict(self):
        with pytest.raises(JsonExtractionError):
            extract_json("No JSON here at all", strict=True)

    def test_no_json_lenient(self):
        result = extract_json("No JSON here at all")
        assert result == {}

    def test_malformed_json_in_fence(self):
        """Malformed JSON in a fence should fall through to bracket matching."""
        text = '```json\n{"key":}\n```'
        # This is invalid JSON — should return {} in lenient mode
        result = extract_json(text)
        assert isinstance(result, (dict, list))


class TestRealLlmPatterns:
    """Patterns we've actually seen from LLM providers."""

    def test_thinking_tag_wrapped(self):
        """Some providers wrap in <think/> tags before JSON."""
        text = '<think\\n>Let me analyze...\\n</think\\n>\\n{"score": 0.85}'
        result = extract_json(text)
        assert result == {"score": 0.85}

    def test_mixed_newlines(self):
        text = '{\n  "gaps": [\n    {"title": "Gap 1"},\n    {"title": "Gap 2"}\n  ]\n}'
        result = extract_json(text)
        assert len(result["gaps"]) == 2

    def test_trailing_comma_in_fence(self):
        """LLMs often add trailing commas."""
        text = '```json\n{"a": 1,}\n```'
        # This should fail direct parse and fence parse, fall through
        result = extract_json(text)
        # Either parses it or returns {} — just shouldn't crash
        assert isinstance(result, (dict, list))
