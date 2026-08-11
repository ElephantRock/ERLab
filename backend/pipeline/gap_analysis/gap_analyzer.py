"""Gap analysis — identify underexplored research areas."""

import logging

from pydantic import ValidationError

from backend.pipeline.gap_analysis.cluster_service import ClusterService
from backend.pipeline.gap_analysis.contracts import (
    GapAnalysisExecutionError,
    GapAnalysisOutputContractError,
    GapAnalysisPayload,
    GapCandidatePayload,
    gap_analysis_schema,
)
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

# Re-export the contract errors so existing imports
# (``from backend.pipeline.gap_analysis.gap_analyzer import
# GapAnalysisOutputContractError``) keep working. The canonical home is
# :mod:`backend.pipeline.gap_analysis.contracts`.
__all__ = [
    "GapAnalysisOutputContractError",
    "GapAnalysisExecutionError",
    "GapAnalyzer",
    "_title_similarity",
]

logger = logging.getLogger(__name__)

GAP_ANALYSIS_PROMPT = """You are an expert AI/NLP research analyst. Analyze the following research landscape
and identify {max_gaps} significant research gaps.

## Current Research Clusters:
{cluster_summary}

## Sample Papers:
{paper_summaries}

## CITATION INTEGRITY (MANDATORY)
You MUST only reference papers that are listed in the Sample Papers section above.
Do NOT invent, fabricate, or hallucinate any paper titles, authors, or years.
If you mention a paper, it MUST appear in the Sample Papers list.
If you are unsure whether a paper exists in the provided list, do not cite it.
Instead, describe the gap in general terms without naming a specific paper.

For each gap, provide:
1. A concise title
2. A detailed description of what's missing or underexplored
3. The gap type: methodological, empirical, theoretical, or cross-domain
4. Which clusters it relates to (use only cluster IDs listed above)
5. The potential impact if addressed
6. Your confidence in this being a genuine gap (0.0 to 1.0)

Respond with a JSON object matching the provided schema with a "gaps" array. \
Each gap object must have keys: title, description, gap_type, related_clusters, potential_impact, confidence."""

# Provider/transport exceptions that, after retry exhaustion, classify as an
# execution failure rather than an output-contract failure. Imported lazily
# inside ``analyze`` to avoid hard wiring optional gateway symbols.


def _contract_error(reason: str, **safe_fields) -> GapAnalysisOutputContractError:
    """Build an output-contract error carrying only safe structural fields.

    Raw provider output must never be embedded in the message or logged.
    """
    extras = " ".join(f"{k}={v}" for k, v in safe_fields.items())
    msg = f"stage=gap_analysis failure_category=output_contract reason={reason}"
    if extras:
        msg = f"{msg} {extras}"
    logger.error("Gap analysis output contract failure: %s", msg)
    return GapAnalysisOutputContractError(msg)


def _validate_payload(payload: object, cluster_report: ClusterReport) -> list[GapCandidatePayload]:
    """Validate the provider payload through the typed contract.

    Defense in depth:
        Provider response → Pydantic validation → semantic cluster validation.

    A blank/None/non-dict payload, a non-list ``gaps`` value, or any field-
    level violation raises :class:`GapAnalysisOutputContractError`. Returns
    the validated gap candidates (possibly empty).
    """
    response_nonempty = payload is not None and not (
        isinstance(payload, str) and not payload.strip()
    )
    parsed_type = type(payload).__name__

    # Blank / missing payload.
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        raise _contract_error(
            "blank_response", response_nonempty=False, parsed_type=parsed_type,
        )
    # Structurally incompatible top-level type.
    if not isinstance(payload, (dict, list)):
        raise _contract_error(
            "unparseable_type", response_nonempty=response_nonempty, parsed_type=parsed_type,
        )

    # Pydantic validation against the canonical typed model. This enforces
    # required fields, controlled gap_type enum, confidence bounds, unique
    # nonnegative cluster ids, extra-field rejection, and string stripping.
    try:
        validated = GapAnalysisPayload.model_validate(payload)
    except ValidationError as exc:
        # Extract a coarse reason from the first error for safe diagnostics.
        try:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", []))
            reason = first.get("type", "validation_error")
        except Exception:  # pragma: no cover - defensive
            reason = "validation_error"
            loc = "unknown"
        raise _contract_error(
            reason,
            response_nonempty=response_nonempty,
            parsed_type=parsed_type,
            field=loc,
        ) from exc

    # Semantic validation: every referenced cluster must exist in the actual
    # ClusterReport produced for this run. When clustering produced no clusters
    # (degenerate input), there is no valid id to reference, so this check is
    # skipped — gaps must not be rejected solely because clustering found none.
    valid_cluster_ids = {c.cluster_id for c in cluster_report.clusters}
    if valid_cluster_ids:
        for idx, gap in enumerate(validated.gaps):
            for cid in gap.related_clusters:
                if cid not in valid_cluster_ids:
                    raise _contract_error(
                        "invalid_cluster_id",
                        response_nonempty=response_nonempty,
                        item_index=idx,
                        cluster_id=cid,
                        valid_clusters=sorted(valid_cluster_ids),
                    )

    return validated.gaps


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two titles."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _build_research_gap(
    candidate: GapCandidatePayload,
    prior_gaps: list[ResearchGap] | None,
) -> ResearchGap:
    """Construct a ResearchGap from a validated candidate, revising truth
    against any prior matching gap."""
    new_gap = ResearchGap(
        title=candidate.title,
        description=candidate.description,
        gap_type=candidate.gap_type.value,
        related_clusters=list(candidate.related_clusters),
        potential_impact=candidate.potential_impact,
        confidence=candidate.confidence,
    )

    if prior_gaps:
        for prior in prior_gaps:
            if _title_similarity(new_gap.title, prior.title) > 0.8:
                new_observation = TruthValue.from_observation(frequency=new_gap.confidence)
                revised = ResearchGap(
                    **new_gap.model_dump(exclude={"truth"}),
                    truth=prior.truth.revise(new_observation),
                )
                logger.info("Revised truth for gap '%s': %s", prior.title, revised.truth)
                return revised
        return ResearchGap(
            **new_gap.model_dump(exclude={"truth"}),
            truth=TruthValue.from_observation(frequency=new_gap.confidence),
        )

    return ResearchGap(
        **new_gap.model_dump(exclude={"truth"}),
        truth=TruthValue.from_observation(frequency=new_gap.confidence),
    )


class GapAnalyzer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._cluster_service = ClusterService()

    async def analyze(
        self,
        papers: list[Paper],
        domain: str = "AI/NLP",
        max_gaps: int = 5,
        prior_gaps: list[ResearchGap] | None = None,
        *,
        provider: LLMProvider | None = None,
        receipts: list | None = None,
    ) -> tuple[list[ResearchGap], ClusterReport]:
        """Identify research gaps from a collection of papers.

        Returns ``(gaps, cluster_report)``. ``gaps`` may be empty when the
        provider correctly identifies no gaps — that case is distinguishable
        from failure (which raises).

        Raises:
            GapAnalysisOutputContractError: the provider returned a
                structurally non-conforming payload (bad type, missing/blank
                fields, out-of-range confidence, unknown cluster id, extra
                fields).
            GapAnalysisExecutionError: the provider/transport layer failed
                after the gateway retry policy was exhausted.
        """
        cluster_report = await self._cluster_service.cluster_papers(papers)
        cluster_summary = self._format_clusters(cluster_report)
        paper_summaries = self._format_paper_summaries(papers[:20])
        prompt = GAP_ANALYSIS_PROMPT.format(
            max_gaps=max_gaps,
            cluster_summary=cluster_summary,
            paper_summaries=paper_summaries,
        )

        llm = provider or self._provider
        if receipts is not None:
            from backend.pipeline.operations.provider_conformance import build_receipt_from_provider
            receipts.append(build_receipt_from_provider(llm))

        # Defense in depth, layer 1: route through structured_output() with the
        # canonical typed schema as the provider constraint. The gateway retry
        # policy applies here; we do not add an analyzer-level retry loop.
        schema = gap_analysis_schema()
        messages = [
            {"role": "system", "content": f"You are a {domain} research analyst. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            payload = await llm.structured_output(
                messages=messages,
                schema=schema,
                temperature=0.3,
                max_tokens=4096,
            )
        except GapAnalysisOutputContractError:
            raise
        except Exception as exc:
            # Provider/transport failure after retry exhaustion → classified as
            # an execution failure. NEVER swallowed into an empty gap list.
            logger.error(
                "Gap analysis provider call failed: %s failure_category=execution",
                type(exc).__name__,
            )
            raise GapAnalysisExecutionError(
                f"stage=gap_analysis failure_category=execution "
                f"provider_error={type(exc).__name__}"
            ) from exc

        # Defense in depth, layers 2-3: Pydantic validation + semantic cluster
        # validation. Raises GapAnalysisOutputContractError on any violation.
        candidates = _validate_payload(payload, cluster_report)

        gaps = [_build_research_gap(c, prior_gaps) for c in candidates]

        try:
            from backend.config import get_settings
            _s = get_settings()
            if getattr(_s, "abandonment_tracking_enabled", True):
                from backend.pipeline.research.abandonment import AbandonmentTracker
                tracker = AbandonmentTracker(
                    getattr(_s, "abandonment_tracking_path", "./data/abandoned_directions.jsonl")
                )
                if tracker.count() > 0:
                    before = len(gaps)
                    gaps = [g for g in gaps if not tracker.is_abandoned(g.title)]
                    excluded_count = before - len(gaps)
                    if excluded_count:
                        logger.info(
                            "Abandonment tracking: excluded %d gaps",
                            excluded_count,
                        )
        except Exception as e:
            logger.debug("Abandonment exclusion failed (non-fatal): %s", e)

        sorted_gaps = sorted(gaps, key=lambda g: g.confidence, reverse=True)

        try:
            from backend.pipeline.research.incumbent import IncumbentFrontierSelector
            selector = IncumbentFrontierSelector()
            directions = selector.select(sorted_gaps, papers)
            for direction in directions:
                direction.gap.is_incumbent = direction.is_incumbent
                direction.gap.frontier_rank = direction.frontier_rank
                direction.gap.evidence_strength = direction.evidence_strength
            incumbent_count = sum(1 for d in directions if d.is_incumbent)
            frontier_count = sum(1 for d in directions if d.frontier_rank is not None)
            logger.info(
                "Incumbent/Frontier: %d incumbent, %d frontier, %d background",
                incumbent_count, frontier_count,
                len(directions) - incumbent_count - frontier_count,
            )
        except Exception as e:
            logger.debug("Incumbent classification failed (non-fatal): %s", e)

        return sorted_gaps, cluster_report

    @staticmethod
    def _format_clusters(report: ClusterReport) -> str:
        lines = []
        for c in report.clusters:
            lines.append(
                f"- Cluster {c.cluster_id} ({c.label}): {c.paper_count} papers, "
                f"avg citations: {c.avg_citations:.1f}"
                if c.avg_citations
                else f"- Cluster {c.cluster_id} ({c.label}): {c.paper_count} papers"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_paper_summaries(papers: list[Paper]) -> str:
        lines = []
        for i, p in enumerate(papers[:30], 1):
            abstract = (p.abstract or "")[:150]
            authors_str = ""
            if hasattr(p, "authors") and p.authors:
                if isinstance(p.authors, list):
                    names = []
                    for a in p.authors[:3]:
                        if hasattr(a, "name"):
                            names.append(a.name)
                        else:
                            names.append(str(a))
                    authors_str = ", ".join(names)
                    if len(p.authors) > 3:
                        authors_str += " et al."
                else:
                    authors_str = str(p.authors)
            year_str = str(p.year) if p.year else "N/A"
            author_line = f" Authors: {authors_str}" if authors_str else ""
            lines.append(f"{i}. [{year_str}] {p.title}{author_line}\n   {abstract}...")
        return "\n".join(lines) if lines else "(No papers provided)"
