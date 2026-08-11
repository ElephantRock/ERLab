"""Tests for P1B.2: embedding snapshot integrity (Decision 1C).

Covers the frozen replay-must-fail conditions and required snapshot contents
from the P1B.1-P1B.3 authorization (Decision 1C).

Replay MUST fail (not silently regenerate) when:
  - candidate text hash differs
  - query text hash differs
  - binding evidence differs
  - dimension differs
  - normalization contract differs
  - vector artifact fingerprint differs
  - benchmark fingerprint differs

The snapshot must contain: snapshot schema version, benchmark version and
fingerprint, capability binding ID, generation capability-check ID,
provider/model/deployment evidence, embedding contract version, dimension
and numeric representation, normalization posture, query/candidate IDs and
canonical text hashes, exact vectors, per-vector fingerprints, complete
snapshot fingerprint, created timestamp.
"""

from __future__ import annotations

import json
from datetime import UTC

import pytest

from backend.ranking.embedding_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    SnapshotBindingEvidence,
    SnapshotIntegrityError,
    SnapshotItem,
    canonical_text_hash,
    clear_snapshot_dir,
    load_snapshot,
    vector_fingerprint,
    write_snapshot,
)

BENCH_VER = "discovery_ranking_v2+retrieval_ranking_v2"
BENCH_FP = "a" * 64


def _mk_item(item_id: str, role: str, text: str, dim: int = 4) -> SnapshotItem:
    vec = tuple(float(i + 1) / 10 for i in range(dim))
    return SnapshotItem(
        item_id=item_id,
        item_role=role,
        canonical_text=text,
        text_hash=canonical_text_hash(text),
        vector=vec,
        vector_fingerprint=vector_fingerprint(vec),
    )


def _binding(**overrides) -> SnapshotBindingEvidence:
    base = dict(
        capability_binding_id="b" * 64,
        capability_check_id="c" * 64,
        generation_runtime_fingerprint="f" * 64,
        provider_kind="lmstudio",
        provider_model="voyage-4-nano",
        provider_revision="rev1",
        endpoint_identity="http://host:1234",
        deployment_id=None,
        embedding_contract_version="embedding_v1",
        dimension=4,
        normalization_policy="l2",
    )
    base.update(overrides)
    return SnapshotBindingEvidence(**base)


def _items():
    return [
        _mk_item("q1", "query", "query one"),
        _mk_item("c1", "candidate", "doc one"),
        _mk_item("c2", "candidate", "doc two"),
    ]


@pytest.fixture
def fresh_snapshot_dir(tmp_path):
    """A fresh empty dir for snapshot write/load round-trips."""
    return tmp_path / "snap"


class TestSnapshotRoundTrip:
    def test_write_then_load_round_trips(self, fresh_snapshot_dir):
        write_snapshot(
            fresh_snapshot_dir,
            benchmark_version=BENCH_VER,
            benchmark_fingerprint=BENCH_FP,
            binding=_binding(),
            items=_items(),
        )
        snap = load_snapshot(
            fresh_snapshot_dir,
            expected_benchmark_fingerprint=BENCH_FP,
            expected_benchmark_version=BENCH_VER,
        )
        assert snap.benchmark_version == BENCH_VER
        assert snap.benchmark_fingerprint == BENCH_FP
        assert snap.dimension == 4
        assert len(snap.queries()) == 1
        assert len(snap.candidates()) == 2
        # per-item access
        assert snap.get("c1") is not None
        assert snap.get("nope") is None

    def test_files_written(self, fresh_snapshot_dir):
        write_snapshot(
            fresh_snapshot_dir,
            benchmark_version=BENCH_VER,
            benchmark_fingerprint=BENCH_FP,
            binding=_binding(),
            items=_items(),
        )
        assert (fresh_snapshot_dir / "snapshot.json").exists()
        assert (fresh_snapshot_dir / "snapshot.fingerprint").exists()

    def test_snapshot_fingerprint_is_deterministic(self, fresh_snapshot_dir, tmp_path):
        d1 = tmp_path / "s1"
        d2 = tmp_path / "s2"
        write_snapshot(d1, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        write_snapshot(d2, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        s1 = load_snapshot(d1, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        s2 = load_snapshot(d2, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        assert s1.snapshot_fingerprint == s2.snapshot_fingerprint

    def test_refuses_to_overwrite_existing_snapshot(self, fresh_snapshot_dir):
        write_snapshot(
            fresh_snapshot_dir,
            benchmark_version=BENCH_VER,
            benchmark_fingerprint=BENCH_FP,
            binding=_binding(),
            items=_items(),
        )
        with pytest.raises(SnapshotIntegrityError, match="refusing to overwrite"):
            write_snapshot(
                fresh_snapshot_dir,
                benchmark_version=BENCH_VER,
                benchmark_fingerprint=BENCH_FP,
                binding=_binding(),
                items=_items(),
            )

    def test_clear_then_rewrite_allowed(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        clear_snapshot_dir(fresh_snapshot_dir)
        # second write should succeed now
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())


class TestSnapshotRequiredContents:
    """Decision 1C: the snapshot must contain every required field."""

    def test_schema_version_present(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        assert payload["snapshot_schema_version"] == SNAPSHOT_SCHEMA_VERSION

    def test_benchmark_version_and_fingerprint_present(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        assert payload["benchmark_version"] == BENCH_VER
        assert payload["benchmark_fingerprint"] == BENCH_FP

    def test_capability_binding_evidence_present(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        for f in (
            "capability_binding_id", "capability_check_id",
            "generation_runtime_fingerprint", "provider_kind", "provider_model",
            "embedding_contract_version", "endpoint_identity",
            "dimension", "normalization_policy",
        ):
            assert payload.get(f), f"missing/empty binding field: {f}"

    def test_per_item_text_hash_and_vector_fingerprint(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        for it in payload["items"]:
            assert "item_id" in it
            assert "item_role" in it
            assert "text_hash" in it and len(it["text_hash"]) == 64
            assert "vector" in it
            assert "vector_fingerprint" in it and len(it["vector_fingerprint"]) == 64

    def test_created_timestamp_present(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        assert payload["created_at"]
        # ISO 8601 contains a 'T'
        assert "T" in payload["created_at"]

    def test_snapshot_fingerprint_field_present(self, fresh_snapshot_dir):
        write_snapshot(fresh_snapshot_dir, benchmark_version=BENCH_VER,
                       benchmark_fingerprint=BENCH_FP, binding=_binding(), items=_items())
        payload = json.loads((fresh_snapshot_dir / "snapshot.json").read_text())
        assert len(payload["snapshot_fingerprint"]) == 64
        sidecar = (fresh_snapshot_dir / "snapshot.fingerprint").read_text().strip()
        assert payload["snapshot_fingerprint"] == sidecar


class TestReplayMustFailConditions:
    """Decision 1C: replay MUST FAIL (never silently regenerate) when …"""

    def _write_and_mutate(self, tmp_path, mutate):
        d = tmp_path / "snap"
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        mutate(d)
        return d

    def test_missing_snapshot_json_fails(self, tmp_path):
        d = tmp_path / "snap"
        d.mkdir()
        with pytest.raises(SnapshotIntegrityError, match="missing"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_missing_sidecar_fingerprint_fails(self, tmp_path):
        d = tmp_path / "snap"
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        (d / "snapshot.fingerprint").unlink()
        with pytest.raises(SnapshotIntegrityError, match="missing"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_benchmark_fingerprint_mismatch_fails(self, tmp_path):
        d = tmp_path / "snap"
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        with pytest.raises(SnapshotIntegrityError, match="benchmark_fingerprint mismatch"):
            load_snapshot(d, expected_benchmark_fingerprint="z" * 64, expected_benchmark_version=BENCH_VER)

    def test_benchmark_version_mismatch_fails(self, tmp_path):
        d = tmp_path / "snap"
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        with pytest.raises(SnapshotIntegrityError, match="benchmark_version mismatch"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version="other")

    def test_tampered_vector_rejected(self, tmp_path):
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["items"][1]["vector"][0] = 999.0
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError, match="vector_fingerprint mismatch"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_vector_fingerprint_field_rejected(self, tmp_path):
        """Tampering the vector_fingerprint field itself is caught by recompute."""
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["items"][0]["vector_fingerprint"] = "0" * 64
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_text_hash_caught_via_snapshot_fingerprint(self, tmp_path):
        """Changing a text_hash invalidates the snapshot_fingerprint recompute."""
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["items"][0]["text_hash"] = "f" * 64
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError, match="snapshot_fingerprint mismatch|sidecar"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_binding_id_caught_via_snapshot_fingerprint(self, tmp_path):
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["capability_binding_id"] = "x" * 64
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError, match="snapshot_fingerprint mismatch|sidecar"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_dimension_caught(self, tmp_path):
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["dimension"] = 99
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError, match="dimension"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_normalization_caught_via_snapshot_fingerprint(self, tmp_path):
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["normalization_policy"] = "none"
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises(SnapshotIntegrityError, match="snapshot_fingerprint mismatch|sidecar"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_tampered_sidecar_fingerprint_rejected(self, tmp_path):
        d = tmp_path / "snap"
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items())
        (d / "snapshot.fingerprint").write_text("0" * 64)
        with pytest.raises(SnapshotIntegrityError, match="sidecar fingerprint mismatch"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_incomplete_binding_evidence_rejected(self, tmp_path):
        d = tmp_path / "snap"
        # missing provider_model
        bad_binding = _binding(provider_model="")
        write_snapshot(d, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=bad_binding, items=_items())
        with pytest.raises(SnapshotIntegrityError, match="incomplete binding evidence"):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)

    def test_no_silent_regeneration_of_missing_vector(self, tmp_path):
        """If an item's vector is removed, load must fail, not regenerate."""
        def mutate(d):
            payload = json.loads((d / "snapshot.json").read_text())
            payload["items"][1].pop("vector")
            (d / "snapshot.json").write_text(json.dumps(payload, indent=2))
        d = self._write_and_mutate(tmp_path, mutate)
        with pytest.raises((SnapshotIntegrityError, KeyError, TypeError)):
            load_snapshot(d, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)


class TestSnapshotFingerprintStability:
    def test_different_text_produces_different_fingerprint(self, tmp_path):
        d1 = tmp_path / "s1"
        d2 = tmp_path / "s2"
        items1 = _items()
        items2 = [
            _mk_item("q1", "query", "DIFFERENT query"),
            _mk_item("c1", "candidate", "doc one"),
            _mk_item("c2", "candidate", "doc two"),
        ]
        write_snapshot(d1, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP, binding=_binding(), items=items1)
        write_snapshot(d2, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP, binding=_binding(), items=items2)
        s1 = load_snapshot(d1, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        s2 = load_snapshot(d2, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        assert s1.snapshot_fingerprint != s2.snapshot_fingerprint

    def test_item_order_does_not_change_fingerprint(self, tmp_path):
        """Fingerprint must be order-independent (items are sorted in payload)."""
        d1 = tmp_path / "s1"
        d2 = tmp_path / "s2"
        items = _items()
        write_snapshot(d1, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP, binding=_binding(), items=items)
        write_snapshot(d2, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP, binding=_binding(), items=list(reversed(items)))
        s1 = load_snapshot(d1, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        s2 = load_snapshot(d2, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        assert s1.snapshot_fingerprint == s2.snapshot_fingerprint

    def test_created_at_excluded_from_fingerprint(self, tmp_path, monkeypatch):
        """Different creation timestamps must not change the fingerprint."""
        from datetime import datetime, timedelta
        d1 = tmp_path / "s1"
        d2 = tmp_path / "s2"
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = t1 + timedelta(days=365)
        write_snapshot(d1, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items(), created_at=t1)
        write_snapshot(d2, benchmark_version=BENCH_VER, benchmark_fingerprint=BENCH_FP,
                       binding=_binding(), items=_items(), created_at=t2)
        s1 = load_snapshot(d1, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        s2 = load_snapshot(d2, expected_benchmark_fingerprint=BENCH_FP, expected_benchmark_version=BENCH_VER)
        assert s1.snapshot_fingerprint == s2.snapshot_fingerprint
        assert s1.created_at != s2.created_at  # timestamp differs, fp doesn't
