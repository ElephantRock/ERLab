"""Tests for the TokenCounter."""

from backend.providers.token_counter import TokenCounter, TokenSnapshot


class TestTokenSnapshot:
    def test_total_tokens(self):
        snap = TokenSnapshot(input_tokens=100, output_tokens=50, call_count=1)
        assert snap.total_tokens == 150

    def test_default_values(self):
        snap = TokenSnapshot()
        assert snap.input_tokens == 0
        assert snap.output_tokens == 0
        assert snap.call_count == 0
        assert snap.total_tokens == 0


class TestTokenCounter:
    def test_record_accumulates(self):
        counter = TokenCounter()
        counter.record(input_tokens=100, output_tokens=50)
        counter.record(input_tokens=200, output_tokens=75)
        snap = counter.snapshot()
        assert snap.input_tokens == 300
        assert snap.output_tokens == 125
        assert snap.call_count == 2
        assert snap.total_tokens == 425

    def test_snapshot_does_not_clear(self):
        counter = TokenCounter()
        counter.record(input_tokens=100, output_tokens=50)
        snap1 = counter.snapshot()
        snap2 = counter.snapshot()
        assert snap1.total_tokens == snap2.total_tokens

    def test_reset_clears_state(self):
        counter = TokenCounter()
        counter.record(input_tokens=100, output_tokens=50)
        counter.reset()
        snap = counter.snapshot()
        assert snap.input_tokens == 0
        assert snap.output_tokens == 0
        assert snap.call_count == 0

    def test_record_after_reset(self):
        counter = TokenCounter()
        counter.record(input_tokens=100, output_tokens=50)
        counter.reset()
        counter.record(input_tokens=50, output_tokens=25)
        snap = counter.snapshot()
        assert snap.total_tokens == 75
        assert snap.call_count == 1

    def test_multiple_resets(self):
        counter = TokenCounter()
        for i in range(3):
            counter.record(input_tokens=100 * (i + 1), output_tokens=50)
            counter.reset()
        snap = counter.snapshot()
        assert snap.total_tokens == 0
