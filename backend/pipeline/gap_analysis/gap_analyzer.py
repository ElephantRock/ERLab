"""Gap analysis — identify underexplored research areas."""

import json
import logging

from backend.pipeline.utils.json_extraction import extract_json

from backend.pipeline.gap_analysis.cluster_service import ClusterService
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

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
4. Which clusters it relates to
5. The potential impact if addressed
6. Your confidence in this being a genuine gap (0.0 to 1.0)
7. Specific paper references from the Sample Papers list that support this gap (use only papers listed above)

Respond with a JSON array of objects with keys: title, description, gap_type, related_clusters, potential_impact, confidence"""

_REQUIRED_GAP_FIELDS = frozenset({
    "title", "description", "gap_type", "related_clusters",
    "potential_impact", "confidence",
})


class GapAnalysisOutputContractError(RuntimeError):
    """Raised when nonempty gap-analysis output violates the expected schema."""


def _normalize_gap_payload(
    raw_response: str,
    parsed: object,
) -> list[dict]:
    """Normalize and validate a parsed gap-analysis payload.

    Contract:
    - valid explicit empty payload → []
    - valid gap payload → list[dict] with required fields
    - anything incompatible → GapAnalysisOutputContractError
    """
    response_nonempty = bool(raw_response and raw_response.strip())
    parsed_type = type(parsed).__name__

    if isinstance(parsed, list):
        gap_list = parsed
    elif isinstance(parsed, dict):
        if "gaps" in parsed:
            gaps_value = parsed["gaps"]
            if not isinstance(gaps_value, list):
                logger.error(
                    "Gap analysis output contract failure: "
                    "stage=gap_analysis failure_category=output_contract "
                    "reason=gaps_value_not_list response_nonempty=%s parsed_type=%s",
                    response_nonempty, parsed_type,
                )
                raise GapAnalysisOutputContractError(
                    f"stage=gap_analysis failure_category=output_contract "
                    f"reason=gaps_value_not_list parsed_type={parsed_type}"
                )
            gap_list = gaps_value
        elif _REQUIRED_GAP_FIELDS.issubset(parsed.keys()):
            gap_list = [parsed]
        else:
            missing = sorted(_REQUIRED_GAP_FIELDS - set(parsed.keys()))
            logger.error(
                "Gap analysis output contract failure: "
                "stage=gap_analysis failure_category=output_contract "
                "reason=dict_missing_gaps_key response_nonempty=%s parsed_type=%s "
                "missing_keys=%s",
                response_nonempty, parsed_type, missing,
            )
            raise GapAnalysisOutputContractError(
                f"stage=gap_analysis failure_category=output_contract "
                f"reason=dict_missing_gaps_key parsed_type={parsed_type} "
                f"missing_keys={missing}"
            )
    else:
        logger.error(
            "Gap analysis output contract failure: "
            "stage=gap_analysis failure_category=output_contract "
            "reason=unparseable_type response_nonempty=%s parsed_type=%s",
            response_nonempty, parsed_type,
        )
        raise GapAnalysisOutputContractError(
            f"stage=gap_analysis failure_category=output_contract "
            f"reason=unparseable_type parsed_type={parsed_type}"
        )

    for idx, item in enumerate(gap_list):
        if not isinstance(item, dict):
            logger.error(
                "Gap analysis output contract failure: "
                "stage=gap_analysis failure_category=output_contract "
                "reason=gap_item_not_object response_nonempty=%s parsed_type=%s item_index=%d",
                response_nonempty, parsed_type, idx,
            )
            raise GapAnalysisOutputContractError(
                f"stage=gap_analysis failure_category=output_contract "
                f"reason=gap_item_not_object item_index={idx} parsed_type={parsed_type}"
            )
        missing_keys = sorted(_REQUIRED_GAP_FIELDS - set(item.keys()))
        if missing_keys:
            logger.error(
                "Gap analysis output contract failure: "
                "stage=gap_analysis failure_category=output_contract "
                "reason=missing_required_fields response_nonempty=%s parsed_type=%s "
                "item_index=%d missing_keys=%s",
                response_nonempty, parsed_type, idx, missing_keys,
            )
            raise GapAnalysisOutputContractError(
                f"stage=gap_analysis failure_category=output_contract "
                f"reason=missing_required_fields item_index={idx} "
                f"missing_keys={missing_keys}"
            )

    return gap_list


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two titles."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


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

        Returns (gaps, cluster_report).

        Raises:
            GapAnalysisOutputContractError: if the nonempty provider response
                violates the expected gap schema.
        """
        cluster_report = await self._cluster_service.cluster_papers(papers)
        cluster_summary = self._format_clusters(cluster_report)
        paper_summaries = self._format_paper_summaries(papers[:20])
        prompt = GAP_ANALYSIS_PROMPT.format(
            max_gaps=max_gaps,
            cluster_summary=cluster_summary,
            paper_summaries=paper_summaries,
        )

        try:
            llm = provider or self._provider
            if receipts is not None:
                from backend.pipeline.operations.provider_conformance import build_receipt_from_provider
                receipts.append(build_receipt_from_provider(llm))
            raw_response = await llm.complete(
                messages=[
                    {"role": "system", "content": f"You are a {domain} research analyst. Respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )

            if not raw_response or not raw_response.strip():
                logger.error(
                    "Gap analysis output contract failure: "
                    "stage=gap_analysis failure_category=output_contract "
                    "reason=blank_response response_nonempty=false parsed_type=N/A"
                )
                raise GapAnalysisOutputContractError(
                    "stage=gap_analysis failure_category=output_contract "
                    "reason=blank_response"
                )

            parsed = extract_json(raw_response)

            if not parsed or (isinstance(parsed, dict) and not parsed and raw_response.strip()):
                logger.error(
                    "Gap analysis output contract failure: "
                    "stage=gap_analysis failure_category=output_contract "
                    "reason=unparseable_json response_nonempty=true parsed_type=empty_dict"
                )
                raise GapAnalysisOutputContractError(
                    "stage=gap_analysis failure_category=output_contract "
                    "reason=unparseable_json"
                )

            raw_gaps = _normalize_gap_payload(raw_response, parsed)

            gaps = []
            for g in raw_gaps:
                import re as _re
                clusters_raw = g.get("related_clusters", [])
                clusters_normalized: list[int] = []
                for c in clusters_raw:
                    if isinstance(c, int):
                        clusters_normalized.append(c)
                    elif isinstance(c, str):
                        match = _re.search(r"\d+", c)
                        if match:
                            clusters_normalized.append(int(match.group()))
                    elif isinstance(c, (float,)):
                        clusters_normalized.append(int(c))

                new_gap = ResearchGap(
                    title=g.get("title", "Untitled Gap"),
                    description=g.get("description", ""),
                    gap_type=g.get("gap_type", "unknown"),
                    related_clusters=clusters_normalized,
                    potential_impact=g.get("potential_impact", ""),
                    confidence=min(1.0, max(0.0, float(g.get("confidence", 0.5)))),
                )

                if prior_gaps:
                    matched = False
                    for prior in prior_gaps:
                        sim = _title_similarity(new_gap.title, prior.title)
                        if sim > 0.8:
                            new_observation = TruthValue.from_observation(
                                frequency=new_gap.confidence,
                            )
                            new_gap = ResearchGap(
                                title=prior.title,
                                description=new_gap.description,
                                gap_type=new_gap.gap_type,
                                related_clusters=new_gap.related_clusters,
                                potential_impact=new_gap.potential_impact,
                                confidence=new_gap.confidence,
                                truth=prior.truth.revise(new_observation),
                            )
                            matched = True
                            logger.info(
                                "Revised truth for gap '%s': %s",
                                prior.title,
                                new_gap.truth,
                            )
                            break
                    if not matched:
                        new_gap = ResearchGap(
                            **new_gap.model_dump(exclude={"truth"}),
                            truth=TruthValue.from_observation(
                                frequency=new_gap.confidence,
                            ),
                        )
                else:
                    new_gap = ResearchGap(
                        **new_gap.model_dump(exclude={"truth"}),
                        truth=TruthValue.from_observation(
                            frequency=new_gap.confidence,
                        ),
                    )

                gaps.append(new_gap)

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

        except GapAnalysisOutputContractError:
            raise
        except Exception as e:
            logger.error(
                "Gap analysis LLM call failed: %s. "
                "Returning 0 gaps with failure state (not an empty success).",
                e, exc_info=True,
            )
            return [], cluster_report

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
