"""Grounding scorer — citation-level evidence quality.

For stages with requires_grounding=True, computes:
  claim_support_rate       — claims supported by cited evidence / total
  unsupported_claim_rate   — claims without any evidence / total
  citation_precision       — real cited sources / total cited sources
  citation_fabrication_rate — fabricated citations / total citations
  contradiction_handling_score — how well conflicting evidence is handled

HARD GATES:
  citation_fabrication_rate > 0.00 → stage not approved for grounded use
  unsupported_claim_rate > 0.20   → stage degraded or not approved

Implementation caution: citation_precision and claim_support_rate are SEPARATE.
A real citation used in the wrong context hurts claim_support_rate
even when citation_precision is high.
"""

from __future__ import annotations

from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


# Known fabricated citation patterns
_FABRICATION_INDICATORS = {
    "doi:10.0000", "doi:10.9999", "arxiv:0000", "(n.d.)",
    "fabricated", "example.com", "doi:10.fake",
}


def compute_grounding_metrics(
    raw_output: str,
    parsed_output: dict | None,
    case: StageEvalCase,
    gold: GoldAnswer | None = None,
) -> dict[str, float]:
    """Compute grounding metrics for an output.

    Separates citation existence from claim support.
    """
    if not case.requires_grounding:
        return {}

    text = raw_output or ""

    # Extract claims and citations from output
    claims = _extract_claims(parsed_output, text)
    citations = _extract_citations(parsed_output, text)

    total_claims = max(len(claims), 1)
    total_citations = max(len(citations), 1)

    # --- Citation precision: real sources / total sources ---
    real_citations = 0
    fabricated = 0
    for cite in citations:
        cite_lower = cite.lower()
        is_fabricated = any(ind in cite_lower for ind in _FABRICATION_INDICATORS)
        if is_fabricated:
            fabricated += 1
        else:
            # Check against gold known real citations
            if gold and gold.expected_keys:
                gold_cites_lower = [k.lower() for k in gold.expected_keys]
                if any(g in cite_lower for g in gold_cites_lower):
                    real_citations += 1
                elif len(cite.strip()) > 5 and "http" not in cite_lower:
                    # Not in gold but looks real enough
                    real_citations += 1
                else:
                    fabricated += 1
            else:
                # No gold — assume non-fabricated-looking citations are real
                if len(cite.strip()) > 3:
                    real_citations += 1
                else:
                    fabricated += 1

    citation_precision = real_citations / total_citations
    fabrication_rate = fabricated / total_citations

    # --- Claim support: claims backed by cited evidence / total ---
    # A claim is "supported" if it references a real citation
    supported = 0
    unsupported = 0
    for claim in claims:
        claim_lower = claim.lower()
        has_cite_ref = any(
            cite_key in claim_lower
            for cite_key in _extract_cite_keys(claim)
        )
        has_evidence_text = any(
            marker in claim_lower
            for marker in ("found that", "showed", "demonstrated", "reported",
                           "according to", "evidence", "data from")
        )
        if has_cite_ref or has_evidence_text:
            # Check if the citation is a real one
            cite_keys = _extract_cite_keys(claim)
            if cite_keys:
                # Cross-reference: does this claim's citation exist in real citations?
                has_real = False
                for ck in cite_keys:
                    for rc in citations[:real_citations]:
                        if ck.lower() in rc.lower():
                            has_real = True
                            break
                if has_real:
                    # Real citation used — but does it actually support the claim?
                    # v0.2 heuristic: check if claim topic overlaps with citation topic
                    if gold and gold.expected_fields:
                        claim_topic = gold.expected_fields.get("topic", "")
                        if claim_topic and claim_topic.lower() in claim_lower:
                            supported += 1
                        elif has_evidence_text:
                            supported += 1  # evidence text suggests proper use
                        else:
                            # Real citation but potentially wrong context
                            supported += 0  # NOT supported — wrong context
                    else:
                        supported += 1
                else:
                    unsupported += 1
            else:
                supported += 1  # has evidence text without explicit citation
        else:
            unsupported += 1

    claim_support_rate = supported / total_claims
    unsupported_claim_rate = unsupported / total_claims

    # --- Contradiction handling: check if conflicting evidence is acknowledged ---
    contradiction_handling = 0.0
    if gold and gold.expected_fields:
        conflicts = gold.expected_fields.get("contradictions", [])
        if conflicts:
            text_lower = text.lower()
            acked = sum(1 for c in conflicts if isinstance(c, str) and c.lower() in text_lower)
            contradiction_handling = acked / len(conflicts)
        else:
            contradiction_handling = 1.0
    else:
        contradiction_handling = 0.5  # neutral

    return {
        "claim_support_rate": round(claim_support_rate, 3),
        "unsupported_claim_rate": round(unsupported_claim_rate, 3),
        "citation_precision": round(citation_precision, 3),
        "citation_fabrication_rate": round(fabrication_rate, 3),
        "contradiction_handling_score": round(contradiction_handling, 3),
    }


def _extract_claims(parsed_output, text):
    """Extract claim texts from output."""
    if parsed_output and "claims" in parsed_output:
        claims = parsed_output["claims"]
        if isinstance(claims, list):
            return [str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in claims]
    # Fallback: split by sentences
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
    return sentences[:20]  # cap at 20


def _extract_citations(parsed_output, text):
    """Extract citation strings from output."""
    citations = []
    if parsed_output and "citations" in parsed_output:
        cites = parsed_output["citations"]
        if isinstance(cites, list):
            citations = [str(c) for c in cites]
    if not citations:
        # Also check individual claim citations
        if parsed_output and "claims" in parsed_output:
            claims = parsed_output["claims"]
            if isinstance(claims, list):
                for c in claims:
                    if isinstance(c, dict):
                        for key in ("citation", "source", "reference", "paper_id"):
                            val = c.get(key)
                            if val and str(val) not in citations:
                                citations.append(str(val))
    if not citations:
        # Fallback: extract [N] style references
        import re
        brackets = re.findall(r'\[[\d,\s\-]+\]', text)
        citations = brackets if brackets else []
    return citations


def _extract_cite_keys(claim_text):
    """Extract citation keys like [1], [2] from a claim."""
    import re
    return re.findall(r'\[\d+\]', claim_text)
