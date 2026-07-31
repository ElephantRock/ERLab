"""Phase 8 / 8R.6 — claim-level experiment-alignment gate.

Evaluates whether a paper's central narrative faithfully identifies the
experiment that produced its evidence. This goes beyond lexical term-presence
checking: it examines the abstract, contribution statement, and conclusion to
determine whether the paper *centers* the executed method or *frames the
contribution around an unexecuted method*.

Classification of claimed methods:
    executed                  — the spec's declared analysis method
    baseline                  — the spec's declared baseline
    background                — explicitly labeled as background/motivation
    proposed_but_not_evaluated — described as a contribution but not in the spec
    future_work               — labeled as future work
    unrelated                 — neither in the spec nor connected to the experiment

A paper is BLOCKED when:
    * the abstract centers an unexecuted method
    * the contribution statement credits an unexecuted method
    * observed results are attributed to a model absent from the manifest
    * the registered experiment is presented as ancillary while another method
      is claimed as the demonstrated contribution
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ClaimAlignmentResult:
    """Result of the claim-level alignment evaluation."""

    passed: bool
    finding: str  # no_concern | minor_concern | material_concern | blocker
    reason: str
    abstract_centers_executed: bool = True
    contribution_centers_executed: bool = True
    unexecuted_method_in_abstract: str = ""
    unexecuted_method_in_conclusion: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "finding": self.finding,
            "reason": self.reason,
            "abstract_centers_executed": self.abstract_centers_executed,
            "contribution_centers_executed": self.contribution_centers_executed,
            "unexecuted_method_in_abstract": self.unexecuted_method_in_abstract,
            "unexecuted_method_in_conclusion": self.unexecuted_method_in_conclusion,
        }


# ── Helpers ─────────────────────────────────────────────────────────

def _extract_section(paper_md: str, section_names: list[str], max_chars: int = 1000) -> str:
    """Extract a paper section by heading name."""
    for name in section_names:
        # Match ## heading or ### heading or plain "Name:"
        pattern = rf'(?i)#{{1,3}}\s*{re.escape(name)}[:\s]*(.*?)(?:\n#{{1,3}}|\Z)'
        m = re.search(pattern, paper_md, re.DOTALL)
        if m:
            return m.group(1).strip()[:max_chars]
        # Also try "Name:" without heading markers
        pattern2 = rf'(?i)\b{re.escape(name)}[:\s]+(.*?)(?:\n#{{1,3}}|\n\n[A-Z]|\Z)'
        m2 = re.search(pattern2, paper_md, re.DOTALL)
        if m2:
            return m2.group(1).strip()[:max_chars]
    return ""


def _extract_abstract(paper_md: str) -> str:
    """Extract the abstract section."""
    return _extract_section(paper_md, ["abstract"], 800)


def _extract_conclusion(paper_md: str) -> str:
    """Extract the conclusion section."""
    return _extract_section(paper_md, ["conclusion", "conclusions", "summary"], 800)


def _extract_contribution_statements(paper_md: str) -> str:
    """Extract contribution/key-contributions/main-contributions sections."""
    text = _extract_section(paper_md, ["contributions", "key contributions", "our contributions"], 800)
    if not text:
        # Try to find "Our contributions are" or "We contribute" inline
        for pattern in [r'(?i)our contributions? (?:are|include)[:\s]*(.*?)(?:\n#{1,3}|\Z)',
                        r'(?i)we contribute[:\s]*(.*?)(?:\n#{1,3}|\Z)',
                        r'(?i)main contributions[:\s]*(.*?)(?:\n#{1,3}|\Z)']:
            m = re.search(pattern, paper_md, re.DOTALL)
            if m:
                text = m.group(1).strip()[:800]
                break
    return text


def _classify_method_mention(text: str, executed_method_terms: list[str],
                              baseline_terms: list[str]) -> str:
    """Classify what method a text passage centers.

    Returns: 'executed' | 'baseline' | 'unexecuted' | 'unknown'
    """
    if not text:
        return 'unknown'
    text_lower = text.lower()

    # Check if executed method terms are present
    has_executed = any(t in text_lower for t in executed_method_terms)
    has_baseline = any(t in text_lower for t in baseline_terms)

    # Check for common unexecuted-method framing patterns
    unexecuted_indicators = [
        r'\bquantum\b', r'\bvariational quantum\b', r'\bvqls\b', r'\bvqe\b',
        r'\bquantum circuit\b', r'\bquantum neural\b', r'\bquantum computing\b',
        r'\bgraph neural network\b', r'\bgnn\b',
        r'\btransformer\b', r'\battention mechanism\b',
        r'\bphysics.informed neural network\b', r'\bpinn\b',
        r'\breinforcement learning\b', r'\bdeep learning\b',
        r'\bconvolutional neural\b', r'\bcnn\b',
        r'\bdiffusion model\b', r'\bgenerative adversarial\b',
        r'\bwavelet\b', r'\bspectral\b',
    ]
    unexecuted_hits = []
    for pattern in unexecuted_indicators:
        if re.search(pattern, text_lower):
            unexecuted_hits.append(pattern.replace(r'\b', '').replace(r'.', ' ').strip())

    # Check if the unexecuted method is explicitly labeled as background
    background_indicators = [
        r'(?i)background[:\s]', r'(?i)as background', r'(?i)for context',
        r'(?i)related work', r'(?i)in contrast to', r'(?i)unlike',
        r'(?i)while .* (have|has) been (proposed|used|explored)',
        r'(?i)inspired by', r'(?i)drawing on',
    ]
    is_background = any(re.search(p, text[:200]) for p in background_indicators)

    if unexecuted_hits and not is_background:
        # The text mentions advanced methods without labeling them as background
        # Check if the executed method is also mentioned in the same passage
        if has_executed:
            # Both present — need to determine which is centered
            # If the first 200 chars mention the unexecuted method more prominently
            first_200 = text_lower[:200]
            unexecuted_in_start = any(re.search(p, first_200) for p in unexecuted_indicators)
            executed_in_start = any(t in first_200 for t in executed_method_terms)
            if unexecuted_in_start and not executed_in_start:
                return 'unexecuted'
            return 'executed'
        return 'unexecuted'

    if has_executed:
        return 'executed'
    if has_baseline:
        return 'baseline'
    return 'unknown'


def evaluate_claim_alignment(
    paper_md: str,
    spec_method: str,
    spec_dataset: str,
    spec_baseline: str = "",
    spec_comparison: str = "",
) -> ClaimAlignmentResult:
    """Evaluate whether the paper's central narrative matches the experiment.

    This is the claim-level structural check (8R.6). It examines the abstract,
    contribution statement, and conclusion to determine if the paper centers
    the executed method or frames the contribution around an unexecuted method.

    Args:
        paper_md: The full paper markdown.
        spec_method: The spec's declared analysis method (e.g. "logistic regression").
        spec_dataset: The spec's declared dataset name.
        spec_baseline: The spec's declared baseline method.
        spec_comparison: The spec's declared comparison model.

    Returns:
        ClaimAlignmentResult with passed/finding/reason.
    """
    # Build method terms for matching
    method_lower = spec_method.lower()
    executed_terms = []
    if "logistic regression" in method_lower:
        executed_terms.append("logistic regression")
    if "linear regression" in method_lower:
        executed_terms.append("linear regression")
    # Also check for the comparison method
    if spec_comparison:
        comp_lower = spec_comparison.lower()
        if "logistic regression" in comp_lower and "logistic regression" not in executed_terms:
            executed_terms.append("logistic regression")
        if "linear regression" in comp_lower and "linear regression" not in executed_terms:
            executed_terms.append("linear regression")

    baseline_terms = []
    if spec_baseline:
        baseline_lower = spec_baseline.lower()
        if "majority" in baseline_lower:
            baseline_terms.append("majority")
        if "mean" in baseline_lower:
            baseline_terms.append("mean")

    # Extract paper regions
    abstract = _extract_abstract(paper_md)
    conclusion = _extract_conclusion(paper_md)
    contributions = _extract_contribution_statements(paper_md)

    # Phase 10 correction A: extract and classify the title
    title = ""
    title_match = re.match(r'^#\s+(.+)', paper_md.strip())
    if title_match:
        title = title_match.group(1).strip()
    title_class = _classify_method_mention(title, executed_terms, baseline_terms) if title else 'unknown'

    # Classify each region
    abstract_class = _classify_method_mention(abstract, executed_terms, baseline_terms)
    conclusion_class = _classify_method_mention(conclusion, executed_terms, baseline_terms)
    contrib_class = _classify_method_mention(contributions, executed_terms, baseline_terms) if contributions else 'unknown'

    # Determine the dominant unexecuted method name
    unexecuted_abstract = ""
    unexecuted_conclusion = ""
    for region_name, region_text in [("abstract", abstract), ("conclusion", conclusion)]:
        if region_text:
            region_lower = region_text.lower()
            for pattern, name in [
                (r'\bquantum\b', "quantum"), (r'\bvariational quantum\b', "variational quantum"),
                (r'\bgraph neural network\b', "graph neural network"), (r'\bgnn\b', "GNN"),
                (r'\bphysics.informed neural network\b', "physics-informed neural network"),
                (r'\bpinn\b', "PINN"),
                (r'\bwavelet\b', "wavelet"), (r'\bspectral\b', "spectral"),
            ]:
                if re.search(pattern, region_lower):
                    if region_name == "abstract":
                        unexecuted_abstract = name
                    else:
                        unexecuted_conclusion = name
                    break

    # ── Blocking conditions ────────────────────────────────────────
    issues = []

    # Phase 10 correction A: title centered on unexecuted method is a blocker
    if title_class == 'unexecuted':
        title_unexecuted = ""
        title_lower = title.lower() if title else ""
        for pattern, name in [
            (r'\bquantum\b', "quantum"),
            (r'\bgraph neural network\b', "GNN"),
            (r'\bphysics.informed neural network\b', "PINN"),
        ]:
            if re.search(pattern, title_lower):
                title_unexecuted = name
                break
        issues.append(
            f"Title centers an unexecuted method ({title_unexecuted or 'advanced architecture'}). "
            f"The title must name the executed method or dataset. "
            f"Current title: '{title[:60]}'"
        )

    if abstract_class == 'unexecuted':
        issues.append(
            f"Abstract centers an unexecuted method ({unexecuted_abstract or 'advanced architecture'}) "
            f"instead of the spec's executed method ({spec_method}). "
            f"The abstract must name the executed dataset and method as the paper's central contribution."
        )

    if contrib_class == 'unexecuted':
        issues.append(
            f"Contribution statement credits an unexecuted method. "
            f"The central contribution must be bounded to the executed analysis ({spec_method})."
        )

    if conclusion_class == 'unexecuted':
        issues.append(
            f"Conclusion attributes results to an unexecuted method ({unexecuted_conclusion or 'advanced architecture'}). "
            f"Observed results must be attributed to the executed method ({spec_method})."
        )

    # Check dataset presence in abstract — pass if the core name token is present
    abstract_lower = abstract.lower()
    dataset_core = spec_dataset.lower().replace("_", " ").split()[0]  # e.g. "wine" from "wine_quality"
    dataset_present = (
        spec_dataset.lower() in abstract_lower
        or spec_dataset.lower().replace("_", " ") in abstract_lower
        or dataset_core in abstract_lower
    )
    if not dataset_present and abstract:
        issues.append(
            f"Abstract does not mention the experiment's dataset ({spec_dataset})."
        )

    if issues:
        # Determine severity
        has_title_issue = title_class == 'unexecuted'
        has_abstract_issue = abstract_class == 'unexecuted'
        has_contrib_issue = contrib_class == 'unexecuted'
        has_conclusion_issue = conclusion_class == 'unexecuted'

        # Title, abstract, and contribution issues are blockers — they are
        # the paper's central narrative identity. A quantum title on a
        # logistic-regression paper is a fundamental misalignment.
        if has_title_issue or has_abstract_issue or has_contrib_issue:
            finding = "blocker"
            passed = False
        elif has_conclusion_issue:
            finding = "material_concern"
            passed = False
        else:
            finding = "minor_concern"
            passed = True  # dataset missing but method correct — minor

        return ClaimAlignmentResult(
            passed=passed,
            finding=finding,
            reason="; ".join(issues),
            abstract_centers_executed=(abstract_class == 'executed'),
            contribution_centers_executed=(contrib_class != 'unexecuted'),
            unexecuted_method_in_abstract=unexecuted_abstract,
            unexecuted_method_in_conclusion=unexecuted_conclusion,
        )

    # All clear
    return ClaimAlignmentResult(
        passed=True,
        finding="no_concern",
        reason=(
            f"Abstract and conclusion center the executed method ({spec_method}) "
            f"and dataset ({spec_dataset}). No unexecuted method is presented "
            f"as the paper's central contribution."
        ),
        abstract_centers_executed=True,
        contribution_centers_executed=True,
    )
