"""Tests for context offload store."""

import pytest

from backend.pipeline.compaction.offload import ContextOffloadStore


@pytest.fixture
def store(tmp_path):
    return ContextOffloadStore(str(tmp_path / "offload"))


class TestContextOffloadSave:
    def test_save_creates_file(self, store):
        path = store.save("run_1", 0, [{"role": "user", "content": "hello"}])
        assert path.endswith(".jsonl")

    def test_save_with_metadata(self, store):
        path = store.save("run_1", 0, [{"role": "user", "content": "hi"}], metadata={"stage": "gen"})
        assert path


class TestContextOffloadLoad:
    def test_load_returns_messages(self, store):
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        store.save("run_1", 0, msgs)
        loaded = store.load("run_1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "hello"

    def test_load_empty_run(self, store):
        loaded = store.load("nonexistent_run")
        assert loaded == []

    def test_load_multiple_chunks_ordered(self, store):
        store.save("run_1", 2, [{"role": "user", "content": "third"}])
        store.save("run_1", 0, [{"role": "user", "content": "first"}])
        store.save("run_1", 1, [{"role": "user", "content": "second"}])
        loaded = store.load("run_1")
        assert [m["content"] for m in loaded] == ["first", "second", "third"]


class TestContextOffloadDelete:
    def test_delete_removes_chunks(self, store):
        store.save("run_1", 0, [{"role": "user", "content": "hello"}])
        count = store.delete("run_1")
        assert count == 1
        assert store.load("run_1") == []

    def test_delete_nonexistent(self, store):
        count = store.delete("nonexistent")
        assert count == 0


class TestContextOffloadList:
    def test_list_empty(self, store):
        assert store.list_offloads() == []

    def test_list_with_runs(self, store):
        store.save("run_a", 0, [{"role": "user", "content": "a"}])
        store.save("run_b", 0, [{"role": "user", "content": "b"}])
        store.save("run_b", 1, [{"role": "user", "content": "b2"}])
        offloads = store.list_offloads()
        run_ids = {o["run_id"] for o in offloads}
        assert run_ids == {"run_a", "run_b"}
        run_b = next(o for o in offloads if o["run_id"] == "run_b")
        assert run_b["chunk_count"] == 2
