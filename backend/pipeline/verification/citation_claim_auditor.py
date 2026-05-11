"""Citation Claim Auditor: Verifies citations and quantitative claims against sources.

Three verification axes:
  (1) Citation Existence — does [SOURCE-X] point to a real source?
  (2) Citation Context — is the claim attributed to that source accurate?
  (3) Quantitative Accuracy — are numbers/metrics faithful to source text?

HB-02: Graceful fallback on LLM failure — returns status="skipped".
HB-03: [SOURCE-X] indices validated against actual source count.
HB-04: Trust score clamped to [0.0, 1.0].
HB-05: Partial results on timeout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SOURCE_X_PATTERN = re.compile(r'\[SOURCE-(\d+)\]')

_QUANTITATIVE_PATTERN = re.compile(
    r'(?:\d+\.?\d*\s*%'
    r'|\d+\.?\d*\s*(?:accuracy|precision|recall|F1|score|improvement|gain|reduction)'
    r'|(?:accuracy|precision|recall|F1|score)\s*(?:of|:)?\s*\d+\.?\d*)',
    re.IGNORECASE,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "citation_audit.md"


@dataclass
class CitationAuditItem:
    """Result of auditing a single [SOURCE-X] citation."""

    ref_index: int                          # The X in [SOURCE-X]
    ref_exists: bool                        # Does the source paper exist?
    claim_text: str                         # Text surrounding the citation
    context_verified: bool                  # LLM says claim matches source
    context_justification: str             # LLM's reasoning
    quantitative_claims: list[dict]         # Extracted numbers/metrics
    quantitative_verified: bool            # All numbers match source
    trust_contribution: float              # 0.0-1.0 for this citation


@dataclass
class CitationAuditReport:
    """Full audit report for a single proposal."""

    proposal_id: int
    total_citations: int
    verified_citations: int
    fabricated_citations: int
    context_mismatches: int
    quantitative_errors: int
    trust_score: float                      # 0.0-1.0, mean of item contributions
    items: list[CitationAuditItem]
    model_used: str
    status: str                             # "complete" | "partial" | "skipped"

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "total_citations": self.total_citations,
            "verified_citations": self.verified_citations,
            "fabricated_citations": self.fabricated_citations,
            "context_mismatches": self.context_mismatches,
            "quantitative_errors": self.quantitative_errors,
            "trust_score": round(self.trust_score, 4),
            "items": [
                {
                    "ref_index": item.ref_index,
                    "ref_exists": item.ref_exists,
                    "claim_text": item.claim_text,
                    "context_verified": item.context_verified,
                    "context_justification": item.context_justification,
                    "quantitative_claims": item.quantitative_claims,
                    "quantitative_verified": item.quantitative_verified,
                    "trust_contribution": round(item.trust_contribution, 4),
                }
                for item in self.items
            ],
            "model_used": self.model_used,
            "status": self.status,
        }


class CitationClaimAuditor:
    """Audits proposal citations and quantitative claims against source papers.

    Usage:
        auditor = CitationClaimAuditor(provider)
        report = await auditor.audit(proposal_text, source_papers)
        if report.trust_score < 0.5:
            logger.warning("Low trust score: %.2f", report.trust_score)
    """

    def __init__(self, provider=None, timeout: float = 60.0) -> None:
        self._provider = provider
        self._timeout = timeout
        self._prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load the citation audit prompt template."""
        try:
            if _PROMPT_PATH.exists():
                return _PROMPT_PATH.read_text(encoding="utf-8")
        except Exception:
            pass
        # Fallback inline prompt
        return (
            "Verify whether the following claim accurately represents the source paper. "
            "Respond in JSON: {context_verified, context_justification, "
            "quantitative_claims, quantitative_verified, trust_contribution}"
        )

    async def audit(
        self,
        proposal_text: str,
        source_papers: list[str],
        proposal_id: int = 0,
    ) -> CitationAuditReport:
        """Audit all [SOURCE-X] citations in proposal text.

        Args:
            proposal_text: The full proposal/paper markdown text.
            source_papers: List of source paper text strings (indexed from 1).
            proposal_id: Proposal index for the report.

        Returns:
            CitationAuditReport with per-citation results and aggregate trust score.
        """
        source_count = len(source_papers)
        ref_indices = self._extract_source_refs(proposal_text)

        if not ref_indices:
            return CitationAuditReport(
                proposal_id=proposal_id,
                total_citations=0,
                verified_citations=0,
                fabricated_citations=0,
                context_mismatches=0,
                quantitative_errors=0,
                trust_score=1.0,
                items=[],
                model_used=getattr(self._provider, "default_model", "none")
                    if self._provider else "none",
                status="complete",
            )

        items: list[CitationAuditItem] = []
        fabricated = 0
        context_mismatches = 0
        quantitative_errors = 0
        verified = 0
        is_partial = False

        for ref_idx in ref_indices:
            # HB-03: Validate index against source count
            if ref_idx > source_count or ref_idx < 1:
                item = CitationAuditItem(
                    ref_index=ref_idx,
                    ref_exists=False,
                    claim_text=self._extract_claim_context(proposal_text, ref_idx),
                    context_verified=False,
                    context_justification=f"Source index {ref_idx} exceeds available sources ({source_count})",
                    quantitative_claims=[],
                    quantitative_verified=False,
                    trust_contribution=0.0,
                )
                items.append(item)
                fabricated += 1
                continue

            # Valid reference — use LLM for context verification
            claim_text = self._extract_claim_context(proposal_text, ref_idx)
            source_text = source_papers[ref_idx - 1]
            quant_claims = self._extract_quantitative_claims(claim_text)

            try:
                item = await asyncio.wait_for(
                    self._verify_citation_context(
                        ref_idx, claim_text, source_text, quant_claims,
                    ),
                    timeout=self._timeout / max(len(ref_indices), 1),
                )
            except asyncio.TimeoutError:
                # HB-05: Partial results on timeout
                item = CitationAuditItem(
                    ref_index=ref_idx,
                    ref_exists=True,
                    claim_text=claim_text,
                    context_verified=False,
                    context_justification="Verification timed out",
                    quantitative_claims=quant_claims,
                    quantitative_verified=False,
                    trust_contribution=0.5,
                )
                is_partial = True
            except Exception as e:
                # LLM failure for this citation — non-fatal
                logger.warning(
                    "Context verification failed for [SOURCE-%d] (non-fatal): %s",
                    ref_idx, e,
                )
                item = CitationAuditItem(
                    ref_index=ref_idx,
                    ref_exists=True,
                    claim_text=claim_text,
                    context_verified=False,
                    context_justification=f"Verification error: {e}",
                    quantitative_claims=quant_claims,
                    quantitative_verified=False,
                    trust_contribution=0.5,
                )

            items.append(item)

            if item.context_verified:
                verified += 1
            else:
                context_mismatches += 1
            if not item.quantitative_verified and quant_claims:
                quantitative_errors += 1

        # HB-04: Trust score = mean of item contributions, clamped [0.0, 1.0]
        trust_score = self._compute_trust_score(items)

        return CitationAuditReport(
            proposal_id=proposal_id,
            total_citations=len(ref_indices),
            verified_citations=verified,
            fabricated_citations=fabricated,
            context_mismatches=context_mismatches,
            quantitative_errors=quantitative_errors,
            trust_score=trust_score,
            items=items,
            model_used=getattr(self._provider, "default_model", "none")
                if self._provider else "none",
            status="partial" if is_partial else "complete",
        )

    @staticmethod
    def _extract_source_refs(text: str) -> list[int]:
        """Extract unique [SOURCE-X] indices from text, sorted."""
        indices = set()
        for match in _SOURCE_X_PATTERN.finditer(text):
            indices.add(int(match.group(1)))
        return sorted(indices)

    @staticmethod
    def _extract_claim_context(text: str, ref_index: int, window: int = 200) -> str:
        """Extract the text surrounding a [SOURCE-X] citation."""
        pattern = re.compile(rf'\[SOURCE-{ref_index}\]')
        match = pattern.search(text)
        if not match:
            return ""
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        return text[start:end].strip()

    @staticmethod
    def _extract_quantitative_claims(text: str) -> list[dict]:
        """Extract quantitative claims (numbers, percentages, metrics) from text."""
        claims = []
        seen = set()
        for match in _QUANTITATIVE_PATTERN.finditer(text):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                claims.append({"value": value, "raw": match.group(0)})
        return claims

    @staticmethod
    def _compute_trust_score(items: list[CitationAuditItem]) -> float:
        """Compute mean trust contribution, clamped to [0.0, 1.0] (HB-04)."""
        if not items:
            return 1.0
        raw = sum(item.trust_contribution for item in items) / len(items)
        return max(0.0, min(1.0, raw))

    async def _verify_citation_context(
        self,
        ref_index: int,
        claim_text: str,
        source_text: str,
        quant_claims: list[dict],
    ) -> CitationAuditItem:
        """Use LLM to verify a citation's context against source text."""
        if not self._provider:
            # No provider — skip LLM verification, assume valid
            return CitationAuditItem(
                ref_index=ref_index,
                ref_exists=True,
                claim_text=claim_text,
                context_verified=True,
                context_justification="No LLM provider — assumed valid",
                quantitative_claims=quant_claims,
                quantitative_verified=True,
                trust_contribution=1.0,
            )

        user_message = (
            f"## Claim to verify:\n\n{claim_text}\n\n"
            f"## Source paper text:\n\n{source_text[:3000]}\n\n"
            f"## Quantitative claims found: "
            f"{json.dumps(quant_claims) if quant_claims else 'None'}\n\n"
            f"Respond in JSON format."
        )

        try:
            response = await self._provider.complete(
                messages=[
                    {"role": "system", "content": self._prompt_template},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception as e:
            # LLM call failed — return conservative item
            return CitationAuditItem(
                ref_index=ref_index,
                ref_exists=True,
                claim_text=claim_text,
                context_verified=False,
                context_justification=f"LLM error: {e}",
                quantitative_claims=quant_claims,
                quantitative_verified=False,
                trust_contribution=0.5,
            )

        # Parse LLM response
        try:
            result = self._parse_llm_response(response)
        except Exception:
            result = {
                "context_verified": False,
                "context_justification": "Failed to parse LLM response",
                "quantitative_claims": quant_claims,
                "quantitative_verified": False,
                "trust_contribution": 0.5,
            }

        return CitationAuditItem(
            ref_index=ref_index,
            ref_exists=True,
            claim_text=claim_text,
            context_verified=result.get("context_verified", False),
            context_justification=result.get("context_justification", ""),
            quantitative_claims=result.get("quantitative_claims", quant_claims),
            quantitative_verified=result.get("quantitative_verified", False),
            trust_contribution=float(result.get("trust_contribution", 0.5)),
        )

    @staticmethod
    def _parse_llm_response(response: str) -> dict:
        """Parse JSON from LLM response, handling markdown code fences."""
        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return json.loads(text)


def create_skipped_report(proposal_id: int = 0, reason: str = "") -> CitationAuditReport:
    """Create a skipped report for when the entire audit must be skipped (HB-02)."""
    return CitationAuditReport(
        proposal_id=proposal_id,
        total_citations=0,
        verified_citations=0,
        fabricated_citations=0,
        context_mismatches=0,
        quantitative_errors=0,
        trust_score=0.0,
        items=[],
        model_used="none",
        status="skipped",
    )
