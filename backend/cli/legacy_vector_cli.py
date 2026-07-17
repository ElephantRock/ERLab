"""Legacy vector migration operator CLI (P0.3.5 final).

Thin adapter over the production services. Does not duplicate scanning,
mapping, planning, indexing, drift, or reconciliation logic.

Commands:
  inventory-legacy   scan + map + plan (no reindex unless --execute)
  reindex-legacy     execute governed reindex for planned targets
  resume-legacy      continue nonterminal inventory run
  verify-legacy      rescan + reconcile + atomically publish complete
  report-legacy      generate JSON/human report from ledger
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.db.database import _get_engine, get_session
from backend.pipeline.legacy_vector_inventory import (
    ChromaLegacyInventoryBackend,
    LegacyVectorInventoryBackend,
    create_inventory_run,
    execute_reindex_targets,
    plan_reindex_targets,
    reconcile_inventory_aggregates,
    run_mapping_phase,
    scan_legacy_collection,
    verify_source_drift,
)
from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

logger = logging.getLogger(__name__)


# ── Report contract ──────────────────────────────────────────────────


class LegacyVectorMigrationReport:
    """Machine-readable report from persisted ledger evidence."""
    report_schema_version: str = "legacy_vector_migration_report_v1"

    def __init__(self, session, inventory_run_id: int):
        from backend.db.models import (
            LegacyVectorInventoryRun,
            LegacyVectorReindexTarget,
        )
        run = session.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == inventory_run_id
            )
        ).scalar_one()

        self.inventory_run_id = inventory_run_id
        self.inventory_status = run.status
        self.collection_name = run.collection_name
        self.source_snapshot_fingerprint = run.source_snapshot_fingerprint or ""
        self.target_embedding_profile_id = run.target_embedding_profile_id
        self.source_record_count = run.source_record_count or 0
        self.mapped_record_count = run.mapped_record_count or 0
        self.ambiguous_record_count = run.ambiguous_record_count or 0
        self.unmapped_record_count = run.unmapped_record_count or 0
        self.invalid_record_count = run.invalid_record_count or 0
        self.identity_conflict_count = run.identity_conflict_count or 0
        self.distinct_target_count = run.distinct_target_paper_count or 0
        self.newly_indexed_target_count = run.newly_indexed_target_count or 0
        self.already_indexed_target_count = run.already_indexed_target_count or 0
        self.content_unavailable_target_count = run.content_unavailable_target_count or 0
        self.failed_target_count = run.reindex_failed_target_count or 0
        self.duplicate_target_record_count = run.duplicate_target_record_count or 0
        self.source_snapshot_verified = None  # Set by verify command
        self.target_profile_verification_status = "unverified"
        self.reconciliation_passed = None
        self.ownership_mutation_detected = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# ── Command implementations ──────────────────────────────────────────


def cmd_inventory_legacy(args: argparse.Namespace) -> int:
    """Scan + map + plan targets. Optionally execute reindex."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # Validate profile
    from backend.db.models import EmbeddingProfile
    s = Session()
    try:
        profile = s.execute(
            select(EmbeddingProfile).where(EmbeddingProfile.profile_id == args.target_profile)
        ).scalar_one_or_none()
        if profile is None:
            print(f"Error: target profile {args.target_profile[:12]}... not found", file=sys.stderr)
            return 2
    finally:
        s.close()

    # Create inventory run
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=args.target_profile)
        s.commit()
    finally:
        s.close()

    print(f"Inventory run {run_id} created")

    # Scan
    import chromadb
    from backend.config import get_settings
    settings = get_settings()
    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    legacy_backend = ChromaLegacyInventoryBackend(chroma_client)

    fp = scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    print(f"Scanned {legacy_backend.count_records()} records, fingerprint: {fp[:16]}...")

    # Map
    run_mapping_phase(Session, inventory_run_id=run_id)
    print(f"Mapping complete")

    # Plan targets
    target_count = plan_reindex_targets(
        Session, inventory_run_id=run_id,
        embedding_profile_id=args.target_profile,
    )
    print(f"Planned {target_count} distinct targets")

    if args.dry_run:
        print("Dry run complete — no governed vectors created")
        return 0

    # Execute reindex
    if args.execute:
        return _execute_reindex(Session, run_id, args.target_profile)

    print("Use 'erlab vectors reindex-legacy' to execute governed reindexing")
    return 0


def cmd_reindex_legacy(args: argparse.Namespace) -> int:
    """Execute governed reindex for planned targets."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return _execute_reindex(Session, args.inventory_run_id, _get_profile_for_run(Session, args.inventory_run_id))


def cmd_resume_legacy(args: argparse.Namespace) -> int:
    """Continue a nonterminal inventory run."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # Check run state
    from backend.db.models import LegacyVectorInventoryRun
    s = Session()
    try:
        run = s.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == args.inventory_run_id
            )
        ).scalar_one_or_none()
        if run is None:
            print(f"Error: inventory run {args.inventory_run_id} not found", file=sys.stderr)
            return 2
        if run.status == "complete":
            print(f"Inventory run {args.inventory_run_id} already complete")
            return 0
        if run.status not in ("scanned", "reindexing", "failed"):
            print(f"Error: cannot resume from status {run.status!r}", file=sys.stderr)
            return 3
        profile_id = run.target_embedding_profile_id
    finally:
        s.close()

    return _execute_reindex(Session, args.inventory_run_id, profile_id)


def cmd_verify_legacy(args: argparse.Namespace) -> int:
    """Rescan + reconcile + atomically publish complete."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    from backend.db.models import LegacyVectorInventoryRun
    s = Session()
    try:
        run = s.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == args.inventory_run_id
            )
        ).scalar_one_or_none()
        if run is None:
            print(f"Error: inventory run {args.inventory_run_id} not found", file=sys.stderr)
            return 2
    finally:
        s.close()

    # Rescan source
    import chromadb
    from backend.config import get_settings
    settings = get_settings()
    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    legacy_backend = ChromaLegacyInventoryBackend(chroma_client)

    if not verify_source_drift(Session, legacy_backend, inventory_run_id=args.inventory_run_id):
        print("Error: source snapshot drift detected", file=sys.stderr)
        _mark_failed(Session, args.inventory_run_id, "source_snapshot_drift")
        return 4

    # Reconcile
    valid, detail = reconcile_inventory_aggregates(Session, inventory_run_id=args.inventory_run_id)
    if not valid:
        print(f"Error: reconciliation failed: {detail}", file=sys.stderr)
        _mark_failed(Session, args.inventory_run_id, "reconciliation_failed", detail)
        return 5

    # Publish complete
    s = Session()
    try:
        s.execute(
            __import__("sqlalchemy").update(LegacyVectorInventoryRun)
            .where(LegacyVectorInventoryRun.id == args.inventory_run_id)
            .values(status="complete", completed_at=datetime.now(timezone.utc))
        )
        s.commit()
    finally:
        s.close()

    print(f"Inventory run {args.inventory_run_id} verified and complete")
    return 0


def cmd_report_legacy(args: argparse.Namespace) -> int:
    """Generate report from persisted ledger."""
    engine = _get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    s = Session()
    try:
        report = LegacyVectorMigrationReport(s, args.inventory_run_id)
    finally:
        s.close()

    if args.format == "json":
        print(report.to_json())
    else:
        print(f"Inventory Run:     {report.inventory_run_id}")
        print(f"Status:            {report.inventory_status}")
        print(f"Source Fingerprint:{report.source_snapshot_fingerprint[:16]}...")
        print(f"Source Records:    {report.source_record_count}")
        print(f"  Mapped:          {report.mapped_record_count}")
        print(f"  Ambiguous:       {report.ambiguous_record_count}")
        print(f"  Unmapped:        {report.unmapped_record_count}")
        print(f"  Invalid:         {report.invalid_record_count}")
        print(f"  Conflicts:       {report.identity_conflict_count}")
        print(f"Targets:           {report.distinct_target_count}")
        print(f"  Newly Indexed:   {report.newly_indexed_target_count}")
        print(f"  Already Indexed: {report.already_indexed_target_count}")
        print(f"  Unavailable:     {report.content_unavailable_target_count}")
        print(f"  Failed:          {report.failed_target_count}")
        print(f"  Duplicates:      {report.duplicate_target_record_count}")

    return 0


# ── Helpers ──────────────────────────────────────────────────────────


def _execute_reindex(Session, run_id: int, profile_id: str) -> int:
    """Execute governed reindex using the runtime."""
    runtime = build_governed_vector_runtime_from_settings(_get_engine())
    if runtime is None:
        print("Error: cannot build governed vector runtime", file=sys.stderr)
        return 5

    class _EmbeddingAdapter:
        def __init__(self, svc):
            self._svc = svc
        async def embed_single(self, text):
            result = await self._svc.embed_texts([text])
            return result[0] if result else []

    counts = __import__("asyncio").run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=runtime.backend,
        embedding_provider=_EmbeddingAdapter(
            __import__("backend.pipeline.knowledge.embedding_service", fromlist=["EmbeddingService"]).EmbeddingService(
                __import__("backend.providers.provider_factory", fromlist=["create_provider"]).create_provider()
            )
        ),
        profile_dict=runtime.profile_dict,
        embedding_profile_id=profile_id,
    ))

    print(f"Reindex: {counts['indexed']} indexed, {counts['already_indexed']} already-indexed, "
          f"{counts['failed']} failed, {counts['content_unavailable']} unavailable")
    return 0 if counts["failed"] == 0 else 5


def _get_profile_for_run(Session, run_id: int) -> str:
    from backend.db.models import LegacyVectorInventoryRun
    s = Session()
    try:
        run = s.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == run_id
            )
        ).scalar_one()
        return run.target_embedding_profile_id
    finally:
        s.close()


def _mark_failed(Session, run_id: int, code: str, detail: str = "") -> None:
    from backend.db.models import LegacyVectorInventoryRun
    from sqlalchemy import update
    s = Session()
    try:
        s.execute(
            update(LegacyVectorInventoryRun)
            .where(LegacyVectorInventoryRun.id == run_id)
            .values(status="failed", failure_code=code, failure_detail=detail[:500],
                    completed_at=datetime.now(timezone.utc))
        )
        s.commit()
    finally:
        s.close()


# ── CLI parser ───────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erlab vectors", description="Vector maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("inventory-legacy", help="Scan + map + plan legacy collection")
    p_inv.add_argument("--target-profile", required=True, help="Embedding profile ID")
    p_inv.add_argument("--dry-run", action="store_true", help="No governed vector writes")
    p_inv.add_argument("--execute", action="store_true", help="Also execute reindex")
    p_inv.set_defaults(func=cmd_inventory_legacy)

    p_re = sub.add_parser("reindex-legacy", help="Execute governed reindex")
    p_re.add_argument("--inventory-run-id", type=int, required=True)
    p_re.set_defaults(func=cmd_reindex_legacy)

    p_res = sub.add_parser("resume-legacy", help="Continue nonterminal run")
    p_res.add_argument("--inventory-run-id", type=int, required=True)
    p_res.set_defaults(func=cmd_resume_legacy)

    p_ver = sub.add_parser("verify-legacy", help="Rescan + reconcile + publish complete")
    p_ver.add_argument("--inventory-run-id", type=int, required=True)
    p_ver.set_defaults(func=cmd_verify_legacy)

    p_rep = sub.add_parser("report-legacy", help="Generate report")
    p_rep.add_argument("--inventory-run-id", type=int, required=True)
    p_rep.add_argument("--format", choices=["json", "text"], default="text")
    p_rep.set_defaults(func=cmd_report_legacy)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
