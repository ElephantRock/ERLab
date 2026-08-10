"""Phase 10 / 10B — structured claim-level repair findings.

Extends the existing claim_alignment evaluator to emit specific section-level
findings that identify exactly what needs to be repaired and where.

Each finding binds to:
  canonical section name + section hash + exact claim text/hash
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from backend.pipeline.evaluation.paper_sections import parse_paper


@dataclass(frozen=True)
class ClaimRepairFinding:
    """A single claim-level repair finding."""

    section: str  # canonical section name: "abstract", "conclusion", etc.
    section_hash: str  # SHA-256 of the section's full text
    claim_text: str  # the specific defective claim text
    claim_hash: str  # SHA-256 of the claim text
    finding_type: str  # one of the supported types below
    severity: str  # blocker | material_concern | minor_concern
    claimed_method: str | None  # the unexecuted method being credited
    executed_method: str  # the spec's actual method
    required_action: str  # what the revision must do
    supporting_result_markers: tuple[str, ...]  # RESULT markers this claim should cite
    supporting_source_markers: tuple[str, ...]  # SOURCE markers in the section


# Supported finding types
FINDING_TYPES = {
    "unexecuted_method_attribution",
    "incorrect_central_method",
    "unsupported_contribution_claim",
    "unsupported_conclusion",
    "metric_direction_misinterpretation",
}


def derive_repair_findings(
    paper_md: str,
    spec_method: str,
    spec_dataset: str,
    spec_baseline: str = "",
    spec_comparison: str = "",
    claim_alignment_result: Any = None,
) -> list[ClaimRepairFinding]:
    """Derive structured repair findings from a blocked paper.

    This function examines the paper's sections and the claim_alignment
    result to produce specific, actionable findings. No provider calls.

    Args:
        paper_md: The paper to analyze.
        spec_method: The experiment spec's analysis method.
        spec_dataset: The experiment spec's dataset name.
        spec_baseline: The spec's baseline method.
        spec_comparison: The spec's comparison model.
        claim_alignment_result: The ClaimAlignmentResult from evaluate_claim_alignment.

    Returns:
        List of ClaimRepairFinding objects, one per defective claim.
    """
    findings: list[ClaimRepairFinding] = []
    parsed = parse_paper(paper_md)

    # Extract method terms
    method_lower = spec_method.lower()
    executed_terms = []
    if "logistic regression" in method_lower:
        executed_terms.append("logistic regression")
    if "linear regression" in method_lower:
        executed_terms.append("linear regression")

    baseline_terms = []
    if spec_baseline:
        bl = spec_baseline.lower()
        if "majority" in bl:
            baseline_terms.append("majority")
        if "mean" in bl:
            baseline_terms.append("mean")

    # Detect unexecuted methods in title, abstract, and conclusion
    for section_name in ["title", "abstract", "conclusion"]:
        section = parsed.get_section(section_name)
        if not section:
            continue

        section_text = section.full_text
        section_lower = section_text.lower()

        # Detect unexecuted method patterns
        unexecuted_patterns = [
            (r'\bquantum\b', "quantum"),
            (r'\bvariational quantum\b', "variational quantum"),
            (r'\bgraph neural network\b', "graph neural network"),
            (r'\bgnn\b', "GNN"),
            (r'\bphysics.informed neural network\b', "physics-informed neural network"),
            (r'\bpinn\b', "PINN"),
            (r'\bwavelet\b', "wavelet"),
            (r'\bspectral\b', "spectral"),
        ]

        detected_methods = []
        for pattern, name in unexecuted_patterns:
            if re.search(pattern, section_lower):
                detected_methods.append(name)

        if not detected_methods:
            continue

        # Check if background-labeled
        background_patterns = [
            r'(?i)background', r'(?i)as background', r'(?i)for context',
            r'(?i)while .* (have|has) been', r'(?i)in contrast',
        ]
        is_background = any(re.search(p, section_text[:300]) for p in background_patterns)

        if is_background:
            continue  # background is allowed

        # Find specific claim sentences with the unexecuted method
        sentences = re.split(r'(?<=[.!?])\s+', section_text)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            has_unexecuted = any(re.search(p, sentence_lower) for p, _ in unexecuted_patterns)
            # A claim is any sentence that either uses claim language OR
            # appears in the abstract/conclusion (which are inherently claim sections)
            has_claim = bool(re.search(
                r'(?i)(we\s+demonstrat|demonstrates?\s+that|we\s+show|outperform|'
                r'significantly|results?\s+show|we\s+present|we\s+propose|'
                r'quantum|method|algorithm|approach)',
                sentence
            )) or len(sentence.strip()) > 5  # any non-trivial sentence in abstract/conclusion

            if has_unexecuted and has_claim:
                # Extract RESULT/SOURCE markers in this sentence
                result_markers = tuple(re.findall(r'\[RESULT-\d+\]', sentence))
                source_markers = tuple(re.findall(r'\[SOURCE-\d+\]', sentence))

                claim_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()

                # Determine severity
                if section_name == "abstract":
                    severity = "blocker"
                    finding_type = "incorrect_central_method"
                    action = (
                        f"Replace this claim with one that centers the executed method "
                        f"({spec_method}) and dataset ({spec_dataset}). "
                        f"The {detected_methods[0]} method must be labeled as background."
                    )
                else:
                    severity = "blocker"
                    finding_type = "unsupported_conclusion"
                    action = (
                        f"Attribute the results to the executed method ({spec_method}), "
                        f"not to {detected_methods[0]}."
                    )

                findings.append(ClaimRepairFinding(
                    section=section_name,
                    section_hash=section.hash,
                    claim_text=sentence.strip(),
                    claim_hash=claim_hash,
                    finding_type=finding_type,
                    severity=severity,
                    claimed_method=detected_methods[0],
                    executed_method=spec_method,
                    required_action=action,
                    supporting_result_markers=result_markers,
                    supporting_source_markers=source_markers,
                ))

    return findings
