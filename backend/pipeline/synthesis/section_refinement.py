"""Section refinement service — regenerate individual proposal sections.

This service is the single entry point for mutations to proposal sections.
It wraps the ProposalSynthesizer, applies citation sanitization, records
revisions, and updates the proposal atomically.

Key invariants:
- Every mutation creates an append-only ProposalSectionRevision row
- Mutations are atomic (single DB transaction)
- Optimistic concurrency via expected_current_hash
- Double hash check: before LLM generation AND inside the transaction
- Model receipt required for user-triggered refinement
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Proposal, ProposalSectionRevision
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer

logger = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    """SHA-256 hash of text, returned as hex string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ConcurrencyConflict(Exception):
    """Raised when expected_current_hash doesn't match the section's actual hash.

    This means another tab/request modified the section between the client
    reading it and submitting the refinement request.
    """

    pass


class ReceiptRequired(Exception):
    """Raised when the provider cannot produce a ModelReceipt for refinement.

    User-triggered refinement is a model-backed mutation and must carry
    a verifiable receipt. Compatibility-mode providers (bool returns)
    cannot be used for section refinement.
    """

    pass


@dataclass
class SectionRefinementResult:
    """Typed result of a section refinement or rollback."""

    revision_id: int
    section_key: str
    previous_text: str
    new_text: str
    previous_hash: str
    section_hash: str
    quality_checks_before: list[dict]
    quality_checks_after: list[dict]
    model_receipt: dict | None = None


class ProposalSectionRefinementService:
    """Service for regenerating individual proposal sections with revision tracking."""

    def __init__(self, synthesizer: ProposalSynthesizer):
        self._synthesizer = synthesizer

    # -- Refine --

    async def refine_section(
        self,
        session: Session,
        proposal: Proposal,
        section_key: str,
        idea,  # ResearchIdea
        novelty_report=None,
        feasibility_report=None,
        literature: str = "",
        *,
        expected_current_hash: str,
        trigger: str = "user_manual",
        trigger_detail: dict | None = None,
        provider=None,
    ) -> SectionRefinementResult:
        """Regenerate a single section with full revision tracking.

        Raises:
            ConcurrencyConflict: If expected_current_hash doesn't match.
            ReceiptRequired: If the provider cannot produce a ModelReceipt.
        """
        sections = json.loads(proposal.sections_json) if proposal.sections_json else {}
        current_text = sections.get(section_key, "")

        # ── Pre-check: hash before expensive LLM generation ──
        current_hash = _sha256(current_text)
        if current_hash != expected_current_hash:
            raise ConcurrencyConflict(
                f"Section '{section_key}' was modified. "
                f"Expected hash {expected_current_hash[:12]}... but got {current_hash[:12]}..."
            )

        # ── Quality checks BEFORE ──
        from backend.api.quality_checks import compute_quality_checks

        qc_before = compute_quality_checks({section_key: current_text}) or []

        # ── Generate new section text via PUBLIC synthesizer API ──
        new_text = await self._synthesizer.generate_section(
            section_key=section_key,
            idea=idea,
            novelty_report=novelty_report,
            feasibility_report=feasibility_report,
            literature=literature,
        )

        # ── Require model receipt ──
        # Extract receipt from provider if available
        receipt_dict = None
        active_provider = provider or self._synthesizer._provider
        if hasattr(active_provider, "last_receipt") and active_provider.last_receipt:
            r = active_provider.last_receipt
            receipt_dict = {
                "requested_model": r.requested_model,
                "served_model": r.served_model,
                "provider": r.provider,
                "endpoint": r.endpoint,
                "timestamp": r.timestamp,
                "context_length": r.context_length,
            }
        if receipt_dict is None:
            raise ReceiptRequired(
                "Provider cannot produce a ModelReceipt. "
                "Section refinement requires a verifiable model receipt."
            )

        # ── Sanitize citations on the new text ──
        new_text = self._sanitize_section(new_text)

        # ── Quality checks AFTER ──
        qc_after = compute_quality_checks({section_key: new_text}) or []

        new_hash = _sha256(new_text)

        # ── Atomic transaction ──
        return self._commit_revision(
            session=session,
            proposal=proposal,
            section_key=section_key,
            new_text=new_text,
            new_hash=new_hash,
            previous_text=current_text,
            previous_hash=current_hash,
            source="section_refine",
            trigger=trigger,
            trigger_detail=trigger_detail,
            receipt_dict=receipt_dict,
            qc_after=qc_after,
            qc_before=qc_before,
            # Second hash check inside transaction
            expected_hash_in_tx=current_hash,
        )

    # -- Restore (Rollback) --

    async def restore_version(
        self,
        session: Session,
        proposal: Proposal,
        section_key: str,
        target_revision_id: int,
        *,
        expected_current_hash: str,
    ) -> SectionRefinementResult:
        """Restore a section to the text captured in a specific revision.

        Creates a new revision with source='rollback' so the audit trail
        is unbroken.

        Raises:
            ConcurrencyConflict: If expected_current_hash doesn't match.
            NotFoundError: If the target revision doesn't exist.
        """
        from backend.api.errors import NotFoundError

        # Find the target revision
        target = session.execute(
            select(ProposalSectionRevision).where(
                ProposalSectionRevision.id == target_revision_id,
                ProposalSectionRevision.proposal_id == proposal.id,
                ProposalSectionRevision.section_key == section_key,
            )
        ).scalar_one_or_none()
        if not target:
            raise NotFoundError(
                f"Revision {target_revision_id} not found for section '{section_key}'"
            )

        sections = json.loads(proposal.sections_json) if proposal.sections_json else {}
        current_text = sections.get(section_key, "")

        # ── Pre-check hash ──
        current_hash = _sha256(current_text)
        if current_hash != expected_current_hash:
            raise ConcurrencyConflict(
                f"Section '{section_key}' was modified. "
                f"Expected hash {expected_current_hash[:12]}... but got {current_hash[:12]}..."
            )

        from backend.api.quality_checks import compute_quality_checks

        qc_before = compute_quality_checks({section_key: current_text}) or []
        qc_after = compute_quality_checks({section_key: target.section_text}) or []

        # ── Atomic transaction ──
        return self._commit_revision(
            session=session,
            proposal=proposal,
            section_key=section_key,
            new_text=target.section_text,
            new_hash=target.section_hash,
            previous_text=current_text,
            previous_hash=current_hash,
            source="rollback",
            trigger="user_restore",
            trigger_detail={"target_revision_id": target_revision_id},
            receipt_dict=None,
            qc_after=qc_after,
            qc_before=qc_before,
            expected_hash_in_tx=current_hash,
        )

    # -- Internal: atomic commit with double hash check --

    def _commit_revision(
        self,
        session: Session,
        proposal: Proposal,
        section_key: str,
        new_text: str,
        new_hash: str,
        previous_text: str,
        previous_hash: str,
        source: str,
        trigger: str,
        trigger_detail: dict | None,
        receipt_dict: dict | None,
        qc_after: list[dict],
        qc_before: list[dict],
        expected_hash_in_tx: str,
    ) -> SectionRefinementResult:
        """Create revision + update proposal atomically.

        Double-checks the hash inside the transaction to catch
        modifications that happened during LLM generation.
        """
        # ── Reload sections from DB (inside transaction) ──
        session.refresh(proposal)
        sections = json.loads(proposal.sections_json) if proposal.sections_json else {}
        tx_current_text = sections.get(section_key, "")
        tx_current_hash = _sha256(tx_current_text)

        # ── Second hash check inside transaction ──
        if tx_current_hash != expected_hash_in_tx:
            raise ConcurrencyConflict(
                f"Section '{section_key}' changed during processing. "
                f"Aborting to prevent clobbering concurrent edit."
            )

        # ── Create revision row (append-only) ──
        revision = ProposalSectionRevision(
            proposal_id=proposal.id,
            section_key=section_key,
            section_text=new_text,
            section_hash=new_hash,
            previous_text=previous_text,
            previous_hash=previous_hash,
            source=source,
            trigger=trigger,
            trigger_detail=json.dumps(trigger_detail) if trigger_detail else None,
            model_receipt_json=json.dumps(receipt_dict) if receipt_dict else None,
            quality_checks_json=json.dumps(qc_after) if qc_after else None,
        )
        session.add(revision)

        # ── Update sections_json ──
        sections[section_key] = new_text
        proposal.sections_json = json.dumps(sections)

        # ── Recompute content_md ──
        proposal.content_md = self._recompute_markdown(sections)

        # ── Commit ──
        session.commit()

        logger.info(
            "Section '%s' revised: source=%s trigger=%s revision_id=%s",
            section_key, source, trigger, revision.id,
        )

        return SectionRefinementResult(
            revision_id=revision.id,
            section_key=section_key,
            previous_text=previous_text,
            new_text=new_text,
            previous_hash=previous_hash,
            section_hash=new_hash,
            quality_checks_before=qc_before,
            quality_checks_after=qc_after,
            model_receipt=receipt_dict,
        )

    # -- Internal helpers --

    @staticmethod
    def _sanitize_section(text: str) -> str:
        """Run citation sanitization on a single section's text."""
        from backend.db.database import get_session
        from backend.db.models import Paper as DBPaper
        from backend.pipeline.literature.models import Author
        from backend.pipeline.literature.models import Paper as PipelinePaper

        # Build a minimal proposal for the sanitizer
        class FakeProposal:
            sections: dict

        fake = FakeProposal()
        fake.sections = {"_target": text}

        # Use the static sanitizer with the actual corpus
        try:
            with get_session() as db_session:
                db_papers = db_session.execute(select(DBPaper)).scalars().all()
                corpus = []
                for dbp in db_papers:
                    try:
                        authors_data = json.loads(dbp.authors) if dbp.authors else []
                        author_objs = [Author(name=a) for a in authors_data[:5]]
                    except Exception:
                        author_objs = []
                    pp = PipelinePaper(
                        id=dbp.source_id or str(dbp.id),
                        source=dbp.source or "unknown",
                        title=dbp.title or "",
                        abstract=dbp.abstract or "",
                        authors=author_objs,
                        year=dbp.year,
                        venue=dbp.venue,
                        keywords=[],
                    )
                    corpus.append(pp)

            # Sanitize only the target section
            sanitized = ProposalSynthesizer._sanitize_citations(fake, corpus)
            return sanitized.sections.get("_target", text)
        except Exception as e:
            logger.warning("Citation sanitization failed for section (non-fatal): %s", e)
            return text

    @staticmethod
    def _recompute_markdown(sections: dict) -> str:
        """Recompute content_md from sections dict."""
        from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

        proposal = ResearchProposal(**sections)
        return proposal.to_markdown()
