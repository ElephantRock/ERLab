"""Automated contradiction detection for the knowledge graph.

Scans the KG for conflicting assertions using three strategies:
1. Verify truth propagation on existing CONTRADICTS relations
2. Find entity pairs with conflicting truth values on same topic
3. LLM-based logical contradiction detection on entity properties

Resolves contradictions using OpenNARS-style truth-value revision.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ContradictionReport(BaseModel):
    """Detected contradiction between two entities."""

    entity_a_id: str
    entity_b_id: str
    contradiction_type: str  # "logical" | "temporal" | "empirical"
    severity: float = 0.0
    evidence: str = ""
    resolution: str = ""  # "truth_revision" | "flag_for_review" | "merge"


class ContradictionScanner:
    """Automated contradiction scanning on KnowledgeGraph updates."""

    def __init__(
        self,
        kg: Any,
        provider: Any = None,
        scan_interval: int = 10,
    ) -> None:
        self._kg = kg
        self._provider = provider
        self._scan_interval = scan_interval
        self._update_count = 0

    async def scan(self) -> list[ContradictionReport]:
        """Full KG scan for contradictions using all strategies."""
        reports: list[ContradictionReport] = []

        # Strategy 1: Check existing CONTRADICTS relations for unpropagated truth
        reports.extend(self._scan_contradicts_relations())

        # Strategy 2: Find entity pairs with conflicting truth values
        reports.extend(self._scan_conflicting_truth())

        # Strategy 3: LLM-based logical contradiction detection
        if self._provider:
            llm_reports = await self._scan_llm_contradictions()
            reports.extend(llm_reports)

        return reports

    async def scan_on_update(self, entity_id: str) -> list[ContradictionReport]:
        """Targeted scan after a specific entity update."""
        self._update_count += 1
        if self._update_count % self._scan_interval != 0:
            return []
        return await self.scan()

    async def resolve_contradiction(self, report: ContradictionReport) -> None:
        """Apply truth-value revision for a detected contradiction."""
        from backend.pipeline.knowledge.truth import TruthValue

        entity_a = self._kg.get_entity(report.entity_a_id)
        entity_b = self._kg.get_entity(report.entity_b_id)

        if not entity_a or not entity_b:
            return

        if report.resolution == "truth_revision":
            # Weaken confidence on both entities
            if hasattr(entity_a, 'truth') and entity_a.truth:
                entity_a.truth = TruthValue(
                    frequency=entity_a.truth.frequency,
                    confidence=entity_a.truth.confidence * 0.8,
                    evidence_count=entity_a.truth.evidence_count,
                )
            if hasattr(entity_b, 'truth') and entity_b.truth:
                entity_b.truth = TruthValue(
                    frequency=1.0 - entity_b.truth.frequency,
                    confidence=entity_b.truth.confidence * 0.8,
                    evidence_count=entity_b.truth.evidence_count,
                )
            logger.info(
                "Resolved contradiction: %s <-> %s (truth revision)",
                report.entity_a_id[:8], report.entity_b_id[:8],
            )

    def _scan_contradicts_relations(self) -> list[ContradictionReport]:
        """Check existing CONTRADICTS edges for unpropagated truth."""
        from backend.pipeline.knowledge.relationships import RelationType

        reports = []
        for rel in getattr(self._kg, '_relationships', []):
            if rel.relation_type == RelationType.CONTRADICTS:
                source = self._kg.get_entity(rel.source_id)
                target = self._kg.get_entity(rel.target_id)
                if source and target:
                    source_conf = getattr(source, 'truth', None)
                    target_conf = getattr(target, 'truth', None)
                    if source_conf and target_conf:
                        # High confidence on both sides is a contradiction signal
                        if source_conf.confidence > 0.5 and target_conf.confidence > 0.5:
                            severity = min(source_conf.confidence, target_conf.confidence)
                            reports.append(ContradictionReport(
                                entity_a_id=rel.source_id,
                                entity_b_id=rel.target_id,
                                contradiction_type="logical",
                                severity=severity,
                                evidence=f"Both entities have high confidence despite CONTRADICTS relation",
                                resolution="truth_revision",
                            ))
        return reports

    def _scan_conflicting_truth(self) -> list[ContradictionReport]:
        """Find entity pairs with conflicting truth values on overlapping topics."""
        reports = []
        entities = list(getattr(self._kg, '_entities', {}).values())

        # Group by entity_type
        by_type: dict[str, list] = {}
        for entity in entities:
            etype = getattr(entity, 'entity_type', 'unknown')
            by_type.setdefault(etype, []).append(entity)

        # Within each type, check for conflicting frequency values
        for etype, group in by_type.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, min(i + 5, len(group))):
                    a, b = group[i], group[j]
                    a_truth = getattr(a, 'truth', None)
                    b_truth = getattr(b, 'truth', None)
                    if not a_truth or not b_truth:
                        continue

                    # Conflict: one entity has high frequency, other has low
                    freq_diff = abs(a_truth.frequency - b_truth.frequency)
                    if freq_diff > 0.6 and a_truth.confidence > 0.3 and b_truth.confidence > 0.3:
                        severity = freq_diff * min(a_truth.confidence, b_truth.confidence)
                        reports.append(ContradictionReport(
                            entity_a_id=a.id if hasattr(a, 'id') else str(i),
                            entity_b_id=b.id if hasattr(b, 'id') else str(j),
                            contradiction_type="empirical",
                            severity=severity,
                            evidence=f"Conflicting truth: freq={a_truth.frequency:.2f} vs {b_truth.frequency:.2f}",
                            resolution="flag_for_review",
                        ))
        return reports[:10]  # Cap to avoid explosion

    async def _scan_llm_contradictions(self) -> list[ContradictionReport]:
        """Use LLM to detect logical contradictions between entity descriptions."""
        if not self._provider:
            return []

        reports = []
        entities = list(getattr(self._kg, '_entities', {}).values())

        # Sample pairs for LLM checking (avoid O(n^2) cost)
        import random
        if len(entities) < 2:
            return []

        pairs = []
        indices = list(range(len(entities)))
        for _ in range(min(5, len(entities))):
            if len(indices) >= 2:
                pair = random.sample(indices, 2)
                pairs.append((entities[pair[0]], entities[pair[1]]))

        for a, b in pairs:
            a_name = getattr(a, 'name', str(a)[:50])
            b_name = getattr(b, 'name', str(b)[:50])
            a_desc = getattr(a, 'description', getattr(a, 'properties', {}))
            b_desc = getattr(b, 'description', getattr(b, 'properties', {}))

            try:
                result = await self._provider.structured_output(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are detecting contradictions between research claims. "
                                "Determine if these two claims logically contradict each other."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Claim A ({a_name}): {str(a_desc)[:300]}\n\n"
                                f"Claim B ({b_name}): {str(b_desc)[:300]}\n\n"
                                "Do these contradict?"
                            ),
                        },
                    ],
                    schema={
                        "type": "object",
                        "properties": {
                            "is_contradiction": {"type": "boolean"},
                            "explanation": {"type": "string"},
                        },
                    },
                    temperature=0.1,
                )

                if result.get("is_contradiction"):
                    reports.append(ContradictionReport(
                        entity_a_id=a.id if hasattr(a, 'id') else "",
                        entity_b_id=b.id if hasattr(b, 'id') else "",
                        contradiction_type="logical",
                        severity=0.7,
                        evidence=result.get("explanation", "LLM detected contradiction"),
                        resolution="flag_for_review",
                    ))
            except Exception as e:
                logger.warning("LLM contradiction scan failed for pair: %s", e)

        return reports
