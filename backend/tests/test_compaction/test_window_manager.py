"""Tests for ContextWindowManager."""

import pytest

from backend.pipeline.compaction.window_manager import CHARS_PER_TOKEN, ContextWindowManager


class FakeProvider:
    default_model = "gpt-4o"

    async def complete(self, messages, **kwargs):
        return "summary"


def make_messages(count: int, chars_per_msg: int = 1000) -> list[dict]:
    return [{"role": "user", "content": "x" * chars_per_msg} for _ in range(count)]


@pytest.fixture
def manager():
    return ContextWindowManager(FakeProvider(), trigger_fraction=0.85, offload_dir="./data/test_offload")


class TestEstimateTokens:
    def test_basic(self):
        msgs = [{"role": "user", "content": "a" * 400}]
        assert ContextWindowManager._estimate_total_tokens(msgs) == 100


class TestShouldTrigger:
    def test_over_threshold(self):
        assert ContextWindowManager._should_trigger(110_000, 128_000, 0.85)

    def test_under_threshold(self):
        assert not ContextWindowManager._should_trigger(100_000, 128_000, 0.85)


class TestTruncateToolOutputs:
    def test_truncates_long_tool_output(self, manager):
        msgs = [
            {"role": "tool", "content": "x" * 5000},
            {"role": "user", "content": "short"},
        ]
        result = manager._truncate_tool_outputs(msgs)
        assert len(result[0]["content"]) < 5000
        assert "[...truncated]" in result[0]["content"]
        assert result[1]["content"] == "short"

    def test_no_truncation_under_limit(self, manager):
        msgs = [{"role": "tool", "content": "short output"}]
        result = manager._truncate_tool_outputs(msgs)
        assert result[0]["content"] == "short output"

    def test_non_tool_messages_unchanged(self, manager):
        msgs = [{"role": "user", "content": "x" * 5000}]
        result = manager._truncate_tool_outputs(msgs)
        assert len(result[0]["content"]) == 5000


class TestCheckAndCompress:
    def test_no_compression_under_threshold(self, manager):
        # 10 messages * 1000 chars = 2500 tokens, well under 85% of 128k
        msgs = make_messages(10, 1000)
        result = manager.check_and_compress(msgs)
        assert result == msgs
        assert manager._compressions_done == 0

    def test_truncation_reduces_tokens(self, manager):
        # 5 tool messages * 5000 chars each = 6250 tokens, under threshold
        # but trigger first, then truncation should help
        big_tool_msgs = [{"role": "tool", "content": "x" * 600_000}] * 5
        result = manager.check_and_compress(big_tool_msgs)
        # After truncation each is ~2000 chars, total ~2500 tokens, under threshold
        assert manager._compressions_done == 1

    def test_offload_triggered(self, manager):
        # 2000 messages * 100 chars = 50k tokens, over 85% of 8k (llama3)
        # But we're using gpt-4o which is 128k. Need much more.
        # Use 2000 msgs * 300 chars = 150k tokens > 108k threshold
        msgs = make_messages(2000, 300)
        result = manager.check_and_compress(msgs, model_name="gpt-4o", run_id="test_run")
        assert len(result) < len(msgs)
        assert manager._compressions_done == 1


class TestGetUsageReport:
    def test_report(self, manager):
        msgs = make_messages(10, 400)  # 1000 tokens
        report = manager.get_usage_report(msgs, model_name="gpt-4o")
        assert report["current_tokens"] == 1000
        assert report["context_size"] == 128_000
        assert report["utilization_pct"] < 1.0
        assert report["compressions_done"] == 0


class TestCleanup:
    def test_cleanup(self, manager, tmp_path):
        manager._offload = __import__(
            "backend.pipeline.compaction.offload",
            fromlist=["ContextOffloadStore"],
        ).ContextOffloadStore(str(tmp_path / "offload"))
        manager._offload.save("test_run", 0, [{"role": "user", "content": "hi"}])
        count = manager.cleanup("test_run")
        assert count == 1
