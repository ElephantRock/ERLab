"""Approval manager for human-in-the-loop governance gates.

Provides async pause/resume for pipeline stages that require
human approval (GATE policy action). Uses asyncio.Event for
non-blocking waits.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class PendingApproval:
    """A governance gate awaiting human decision."""

    decision_id: str
    stage: str
    reason: str
    rule_name: str
    created_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    amendment: str | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)


class ApprovalManager:
    """Manages pending governance approvals with async pause/resume."""

    def __init__(self, timeout_seconds: float = 3600):
        self._pending: dict[str, PendingApproval] = {}
        self._timeout = timeout_seconds

    async def request_approval(
        self, stage: str, reason: str, rule_name: str
    ) -> PendingApproval:
        """Create a pending approval and wait for resolution."""
        decision_id = str(uuid.uuid4())[:8]
        approval = PendingApproval(
            decision_id=decision_id,
            stage=stage,
            reason=reason,
            rule_name=rule_name,
        )
        self._pending[decision_id] = approval
        logger.info(
            "Approval requested: %s for stage '%s' (rule: %s)",
            decision_id, stage, rule_name,
        )

        try:
            await asyncio.wait_for(approval._event.wait(), timeout=self._timeout)
        except asyncio.TimeoutError:
            approval.status = ApprovalStatus.EXPIRED
            logger.warning("Approval %s expired", decision_id)

        self._pending.pop(decision_id, None)
        return approval

    def approve(self, decision_id: str) -> bool:
        """Approve a pending decision. Returns True if found."""
        approval = self._pending.get(decision_id)
        if not approval or approval.status != ApprovalStatus.PENDING:
            return False
        approval.status = ApprovalStatus.APPROVED
        approval._event.set()
        logger.info("Approval %s granted", decision_id)
        return True

    def deny(self, decision_id: str, amendment: str | None = None) -> bool:
        """Deny a pending decision. Returns True if found."""
        approval = self._pending.get(decision_id)
        if not approval or approval.status != ApprovalStatus.PENDING:
            return False
        approval.status = ApprovalStatus.DENIED
        approval.amendment = amendment
        approval._event.set()
        logger.info("Approval %s denied", decision_id)
        return True

    def get_pending(self) -> list[dict]:
        """List all pending approvals (for API endpoint)."""
        return [
            {
                "decision_id": a.decision_id,
                "stage": a.stage,
                "reason": a.reason,
                "rule_name": a.rule_name,
                "created_at": a.created_at.isoformat(),
                "status": a.status.value,
            }
            for a in self._pending.values()
            if a.status == ApprovalStatus.PENDING
        ]

    async def deny_with_resubmission(
        self,
        decision_id: str,
        amendment: str,
        stage: str,
        reason: str = "",
        rule_name: str = "",
    ) -> PendingApproval | None:
        """Deny with amendment, then auto-resubmit a new approval request.

        The amendment text is carried forward into the new request so
        the next human reviewer can see the feedback from the previous denial.
        """
        denied = self.deny(decision_id, amendment=amendment)
        if not denied:
            return None

        combined_reason = f"{reason} [AMENDMENT: {amendment}]" if reason else f"Resubmitted with amendment: {amendment}"
        return await self.request_approval(
            stage=stage,
            reason=combined_reason,
            rule_name=rule_name or "resubmission",
        )
