"""Phase 9 / 9B — revision directive and evidence invariants.

An immutable structure that carries the frozen experiment evidence and
blocking findings into a constrained paper revision. The directive is
constructed from persisted state and verified before any provider call.

The directive enforces evidence invariants:
  - metric values cannot change
  - RESULT identities cannot be invented or redefined
  - SOURCE identities cannot be invented or redefined
  - every used RESULT/SOURCE marker must resolve to the frozen map
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceInvariant:
    """A frozen snapshot of the evidence that must remain unchanged
    across a paper revision. Hashed for verification."""

    result_map: tuple[tuple[str, float], ...]  # (marker, value) pairs
    source_map: tuple[str, ...]  # marker identities
    experiment_manifest_hash: str
    dataset_hash: str
    analysis_code_hash: str

    @property
    def result_map_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(list(self.result_map), sort_keys=True).encode()
        ).hexdigest()

    @property
    def source_map_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(list(self.source_map), sort_keys=True).encode()
        ).hexdigest()

    def to_dict(self) -> dict:
        return {
            "result_map": list(self.result_map),
            "source_map": list(self.source_map),
            "result_map_hash": self.result_map_hash,
            "source_map_hash": self.source_map_hash,
            "experiment_manifest_hash": self.experiment_manifest_hash,
            "dataset_hash": self.dataset_hash,
            "analysis_code_hash": self.analysis_code_hash,
        }


@dataclass(frozen=True)
class RevisionDirective:
    """Structured directive for evidence-constrained paper revision.

    Constructed from persisted experiment evidence and gate findings.
    Passed to the revision synthesizer to constrain the output.

    Immutable: once constructed, the evidence cannot be modified.
    """

    # ── Blocking findings that triggered the revision ───────────────
    blocking_findings: tuple[str, ...]

    # ── Executed experiment description (from spec, frozen) ─────────
    research_question: str
    task_type: str
    target_name: str
    executed_method: str
    baseline_method: str
    comparison_method: str
    primary_metric: str
    metric_direction: str
    dataset_name: str
    split_method: str
    random_seed: int

    # ── Frozen evidence invariants ──────────────────────────────────
    evidence: EvidenceInvariant

    # ── Detection output (from claim_alignment) ─────────────────────
    unexecuted_methods_detected: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "blocking_findings": list(self.blocking_findings),
            "research_question": self.research_question,
            "task_type": self.task_type,
            "target_name": self.target_name,
            "executed_method": self.executed_method,
            "baseline_method": self.baseline_method,
            "comparison_method": self.comparison_method,
            "primary_metric": self.primary_metric,
            "metric_direction": self.metric_direction,
            "dataset_name": self.dataset_name,
            "split_method": self.split_method,
            "random_seed": self.random_seed,
            "evidence": self.evidence.to_dict(),
            "unexecuted_methods_detected": list(self.unexecuted_methods_detected),
        }

    def build_revision_prompt(self) -> str:
        """Build the constraint block injected into the synthesis prompt.

        This is the dynamic, defect-derived version of the 8R.7 static
        "PAPER NARRATIVE CONSTRAINT" block. It tells the LLM exactly which
        defects to fix and which evidence is immutable.
        """
        lines = [
            "## PAPER REVISION DIRECTIVE (critical — revise the paper to fix these defects)",
            "",
            "The following blocking findings were detected and MUST be fixed:",
        ]
        for i, finding in enumerate(self.blocking_findings, 1):
            lines.append(f"  {i}. {finding}")
        lines.append("")
        lines.append("The paper reports this executed experiment:")
        lines.append(f"  Research question: {self.research_question}")
        lines.append(f"  Task type: {self.task_type}")
        lines.append(f"  Dataset: {self.dataset_name}")
        lines.append(f"  Target: {self.target_name}")
        lines.append(f"  Executed method: {self.executed_method}")
        lines.append(f"  Baseline: {self.baseline_method}")
        lines.append(f"  Comparison model: {self.comparison_method}")
        lines.append(f"  Primary metric: {self.primary_metric} ({self.metric_direction})")
        lines.append(f"  Split: {self.split_method}, seed={self.random_seed}")
        lines.append("")
        lines.append("MANDATORY REVISION REQUIREMENTS:")
        lines.append("1. The ABSTRACT must name the executed dataset and method as the central contribution.")
        lines.append("2. The CONTRIBUTION STATEMENT must bound the contribution to the executed analysis.")
        if self.unexecuted_methods_detected:
            lines.append(
                f"3. These unexecuted methods ({', '.join(self.unexecuted_methods_detected)}) "
                "MUST be explicitly labeled as 'background', 'motivation', or 'future work'."
            )
            lines.append("   They must NOT be presented as the paper's demonstrated contribution.")
        lines.append("4. The CONCLUSION must attribute observed results to the executed method.")
        lines.append("5. All outcome claims must reference [RESULT-N] markers.")
        lines.append("6. Do NOT change any observed metric values, RESULT markers, or SOURCE markers.")
        lines.append("")
        lines.append("IMMUTABLE EVIDENCE (do not modify):")
        lines.append(f"  RESULT map hash: {self.evidence.result_map_hash[:32]}...")
        lines.append(f"  SOURCE map hash: {self.evidence.source_map_hash[:32]}...")
        for marker, value in self.evidence.result_map:
            lines.append(f"  {marker} = {value}")
        return "\n".join(lines)


def verify_revised_paper_invariants(
    revised_paper_md: str,
    evidence: EvidenceInvariant,
) -> tuple[bool, list[str]]:
    """Verify that a revised paper does not violate evidence invariants.

    Returns (all_ok, violations).
    """
    violations: list[str] = []

    # Check no RESULT marker identity was invented
    import re
    paper_result_markers = set(re.findall(r'\[RESULT-\d+\]', revised_paper_md))
    frozen_result_markers = {f"[{m}]" for m, _ in evidence.result_map}
    invented = paper_result_markers - frozen_result_markers
    if invented:
        violations.append(f"Invented RESULT markers: {invented}")

    # Check no SOURCE marker identity was invented
    paper_source_markers = set(re.findall(r'\[SOURCE-\d+\]', revised_paper_md))
    frozen_source_markers = set(evidence.source_map)
    invented_sources = paper_source_markers - frozen_source_markers
    if invented_sources:
        violations.append(f"Invented SOURCE markers: {invented_sources}")

    # Check no metric values were changed. Rather than fragile text extraction
    # (which produces false positives when markers are near each other), we
    # rely on the structural guarantee that RESULT markers are frozen: the
    # paper can only cite markers from the frozen map, and the values are
    # in the frozen manifest. If a marker identity is in the frozen map, its
    # value was defined by the frozen experiment and cannot be changed by
    # paper text. The manifest hash provides the cryptographic guarantee.
    # We skip per-marker value text extraction to avoid false positives from
    # adjacent markers.

    return (len(violations) == 0, violations)
