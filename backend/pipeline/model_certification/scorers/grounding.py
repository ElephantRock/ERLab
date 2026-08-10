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

v0.2 corpus-backed scoring:
When gold.claims contains corpus-backed support_label entries, the scorer
uses those to compute precise metrics instead of heuristic extraction.
"""

from __future__ import annotations

import re

from backend.pipeline.model_certification.eval_case import GoldAnswer, StageEvalCase

# Known fabricated citation patterns
_FABRICATION_INDICATORS = {
    "doi:10.0000", "doi:10.9999", "arxiv:0000", "(n.d.)",
    "fabricated", "example.com", "doi:10.fake",
}

# Valid corpus-backed support labels
_VALID_SUPPORT_LABELS = {
    "supported", "weakly_supported", "unsupported",
    "wrong_citation", "fabricated_citation", "contradicted",
}


def compute_grounding_metrics(
    raw_output: str,
    parsed_output: dict | None,
    case: StageEvalCase,
    gold: GoldAnswer | None = None,
) -> dict[str, float]:
    """Compute grounding metrics for an output.

    Separates citation existence from claim support.
    Uses corpus-backed gold when available, heuristic extraction otherwise.
    """
    if not case.requires_grounding:
        return {}

    text = raw_output or ""

    # ── Corpus-backed path ──
    if gold and gold.claims and _is_corpus_backed(gold):
        return _compute_corpus_backed_metrics(text, parsed_output, gold)

    # ── Heuristic path (legacy cases without corpus) ──
    return _compute_heuristic_metrics(text, parsed_output, gold)


def _is_corpus_backed(gold: GoldAnswer) -> bool:
    """Check if gold answer has corpus-backed claim labels."""
    if not gold.claims:
        return False
    return any(
        c.get("support_label") in _VALID_SUPPORT_LABELS
        for c in gold.claims
    )


def _compute_corpus_backed_metrics(
    text: str,
    parsed_output: dict | None,
    gold: GoldAnswer,
) -> dict[str, float]:
    """Compute metrics using corpus-backed gold labels.

    Matches model output against gold claims by checking if the model
    correctly identifies each claim's support status.
    """
    gold_claims = gold.claims
    corpus_source_ids = set()
    for s in gold.corpus_sources:
        if isinstance(s, dict):
            corpus_source_ids.add(s.get("source_id", ""))
        elif isinstance(s, str):
            corpus_source_ids.add(s)

    text_lower = text.lower()

    # Classify gold claims
    supported_count = 0
    unsupported_count = 0
    wrong_citation_count = 0
    fabricated_count = 0
    contradicted_count = 0
    total = len(gold_claims)

    for gc in gold_claims:
        label = gc.get("support_label", "unsupported")

        # Check if model output correctly handles this claim
        claim_text = gc.get("text", gc.get("rationale", ""))
        claim_id = gc.get("claim_id", "")

        # Check if the model identified the issue
        if _model_correctly_identified(text, parsed_output, gc, label, corpus_source_ids):
            if label == "supported":
                supported_count += 1
            elif label == "fabricated_citation":
                fabricated_count += 1
            elif label == "wrong_citation":
                wrong_citation_count += 1
            elif label == "contradicted":
                contradicted_count += 1
            elif label == "unsupported":
                unsupported_count += 1
            elif label == "weakly_supported":
                supported_count += 1  # counts as partially supported
        else:
            # Model missed or misidentified this
            if label == "supported":
                unsupported_count += 1  # model didn't make a supported claim
            elif label == "fabricated_citation":
                fabricated_count += 1  # still counts as fabricated in output
            elif label == "wrong_citation":
                wrong_citation_count += 1
            elif label == "contradicted":
                contradicted_count += 1
            elif label == "unsupported":
                unsupported_count += 1

    # Total citations in model output
    model_citations = _extract_all_citations(text, parsed_output)
    total_citations = max(len(model_citations), 1)

    # Citation precision: real corpus sources cited / total citations
    real_cited = sum(1 for c in model_citations if _is_real_corpus_source(c, corpus_source_ids))
    citation_precision = real_cited / total_citations

    # Fabrication rate: citations NOT in corpus / total citations
    fabricated_citations = sum(1 for c in model_citations if not _is_real_corpus_source(c, corpus_source_ids))
    fabrication_rate = fabricated_citations / total_citations

    # Claim support rate: correctly supported claims / total gold claims
    claim_support_rate = supported_count / max(total, 1)

    # Unsupported claim rate
    unsupported_rate = unsupported_count / max(total, 1)

    # Contradiction handling score
    contradiction_cases = [gc for gc in gold_claims if gc.get("support_label") == "contradicted"]
    if contradiction_cases:
        contradiction_score = contradicted_count / len(contradiction_cases)
    else:
        contradiction_score = 1.0  # No contradictions to handle = perfect

    return {
        "claim_support_rate": round(claim_support_rate, 3),
        "unsupported_claim_rate": round(unsupported_rate, 3),
        "citation_precision": round(citation_precision, 3),
        "citation_fabrication_rate": round(fabrication_rate, 3),
        "contradiction_handling_score": round(contradiction_score, 3),
    }


def _model_correctly_identified(
    text: str,
    parsed_output: dict | None,
    gold_claim: dict,
    label: str,
    corpus_source_ids: set[str],
) -> bool:
    """Check if model output correctly handled a gold claim.

    For supported claims: model should cite the correct source.
    For unsupported/wrong/fabricated: model should flag the issue.
    For contradicted: model should note the contradiction.
    """
    text_lower = text.lower()
    supporting = gold_claim.get("supporting_sources", [])
    cited = gold_claim.get("cited_sources", [])
    claim_text = gold_claim.get("text", gold_claim.get("rationale", ""))
    claim_text_lower = claim_text.lower() if claim_text else ""

    if label == "supported":
        # Model should mention the supporting source
        for src in supporting:
            if src.lower() in text_lower:
                return True
        # Also check if claim topic appears
        if claim_text_lower and any(kw in text_lower for kw in _extract_key_phrases(claim_text)):
            return True
        return False

    elif label == "fabricated_citation":
        # Model should flag the citation as fabricated/non-existent
        for src in cited:
            # If the fabricated source appears in output, model didn't flag it
            if src.lower() in text_lower:
                return False  # Model included fabricated citation without flagging
        # Or model explicitly mentions fabrication
        fabricate_indicators = ["fabricat", "not in corpus", "non-existent", "does not exist", "not found", "not available", "invalid"]
        if any(ind in text_lower for ind in fabricate_indicators):
            return True
        # Check parsed output for support_label
        if parsed_output and isinstance(parsed_output, (dict, list)):
            items = parsed_output if isinstance(parsed_output, list) else parsed_output.get("claims", [parsed_output])
            for item in items:
                if isinstance(item, dict):
                    sl = item.get("support_label", "").lower()
                    if "fabricat" in sl or sl in ("fabricated_citation", "non_existent"):
                        return True
        return False

    elif label == "wrong_citation":
        # Model should identify the citation mismatch
        correct_sources = gold_claim.get("supporting_sources", [])
        wrong_sources = gold_claim.get("cited_sources", [])
        # Check if model notes the mismatch
        mismatch_indicators = ["wrong", "mismatch", "incorrect", "does not support", "not support", "misattribut", "better support", "correct source"]
        if any(ind in text_lower for ind in mismatch_indicators):
            return True
        # Check parsed output
        if parsed_output and isinstance(parsed_output, (dict, list)):
            items = parsed_output if isinstance(parsed_output, list) else parsed_output.get("claims", [parsed_output])
            for item in items:
                if isinstance(item, dict):
                    sl = item.get("support_label", "").lower()
                    if "wrong" in sl or "mismatch" in sl:
                        return True
        return False

    elif label == "contradicted":
        # Model should acknowledge the contradiction
        contra_indicators = ["contradict", "conflict", "inconsisten", "opposite", "however", "but the source", "limitation"]
        if any(ind in text_lower for ind in contra_indicators):
            return True
        return False

    elif label == "unsupported":
        # Model should flag as unsupported
        unsup_indicators = ["unsupported", "no evidence", "not supported", "overclaim", "exaggerat", "cannot be verified"]
        if any(ind in text_lower for ind in unsup_indicators):
            return True
        # Check parsed output
        if parsed_output and isinstance(parsed_output, (dict, list)):
            items = parsed_output if isinstance(parsed_output, list) else parsed_output.get("claims", [parsed_output])
            for item in items:
                if isinstance(item, dict):
                    sl = item.get("support_label", "").lower()
                    if "unsupported" in sl:
                        return True
        return False

    elif label == "weakly_supported":
        return True  # Partial credit

    return False


def _extract_key_phrases(text: str) -> list[str]:
    """Extract key phrases (3+ word sequences) from text for matching."""
    words = text.lower().split()
    phrases = []
    for n in range(4, 2, -1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            if len(phrase) > 10:
                phrases.append(phrase)
    return phrases[:10]


def _extract_all_citations(text: str, parsed_output: dict | None) -> list[str]:
    """Extract all citation references from model output."""
    citations = []

    # From parsed output
    if parsed_output:
        if isinstance(parsed_output, list):
            items = parsed_output
        elif isinstance(parsed_output, dict):
            items = parsed_output.get("claims", [parsed_output])
            for key in ("citations", "sources", "references"):
                vals = parsed_output.get(key, [])
                if isinstance(vals, list):
                    citations.extend(str(v) for v in vals)
        else:
            items = []

        for item in items:
            if isinstance(item, dict):
                for key in ("citation", "source", "reference", "cited_source", "correct_source", "supporting_source"):
                    val = item.get(key)
                    if val:
                        if isinstance(val, list):
                            citations.extend(str(v) for v in val)
                        elif str(val) not in citations:
                            citations.append(str(val))

    # From text: P1, P2, PX, [S1], [S2], [SOURCE-1] patterns
    source_patterns = re.findall(r'\b(P\w+|S\w+)\b', text)
    citations.extend(source_patterns)
    bracket_patterns = re.findall(r'\[([A-Z]+[-\w]*)\]', text)
    citations.extend(bracket_patterns)

    return list(set(citations)) if citations else []


def _is_real_corpus_source(citation: str, corpus_ids: set[str]) -> bool:
    """Check if a citation matches a real corpus source."""
    cite_upper = citation.upper().strip()
    for sid in corpus_ids:
        if cite_upper == sid.upper():
            return True
    # Check partial matches
    cite_lower = citation.lower()
    for sid in corpus_ids:
        if sid.lower() in cite_lower or cite_lower in sid.lower():
            return True
    return False


def _compute_heuristic_metrics(
    text: str,
    parsed_output: dict | None,
    gold: GoldAnswer | None,
) -> dict[str, float]:
    """Legacy heuristic path for cases without corpus-backed gold."""
    claims = _extract_claims(parsed_output, text)
    citations = _extract_citations(parsed_output, text)

    total_claims = max(len(claims), 1)
    total_citations = max(len(citations), 1)

    # Citation precision: real sources / total sources
    real_citations = 0
    fabricated = 0
    for cite in citations:
        cite_lower = cite.lower()
        is_fabricated = any(ind in cite_lower for ind in _FABRICATION_INDICATORS)
        if is_fabricated:
            fabricated += 1
        else:
            if gold and gold.expected_keys:
                gold_cites_lower = [k.lower() for k in gold.expected_keys]
                if any(g in cite_lower for g in gold_cites_lower) or len(cite.strip()) > 5 and "http" not in cite_lower:
                    real_citations += 1
                else:
                    fabricated += 1
            else:
                if len(cite.strip()) > 3:
                    real_citations += 1
                else:
                    fabricated += 1

    citation_precision = real_citations / total_citations
    fabrication_rate = fabricated / total_citations

    # Claim support
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
            cite_keys = _extract_cite_keys(claim)
            if cite_keys:
                has_real = any(
                    ck.lower() in rc.lower()
                    for ck in cite_keys
                    for rc in citations[:real_citations]
                )
                if has_real:
                    if gold and gold.expected_fields:
                        claim_topic = gold.expected_fields.get("topic", "")
                        if claim_topic and claim_topic.lower() in claim_lower or has_evidence_text:
                            supported += 1
                        else:
                            supported += 0  # Wrong context
                    else:
                        supported += 1
                else:
                    unsupported += 1
            else:
                supported += 1
        else:
            unsupported += 1

    claim_support_rate = supported / total_claims
    unsupported_claim_rate = unsupported / total_claims

    # Contradiction handling
    contradiction_handling = 0.5
    if gold and gold.expected_fields:
        conflicts = gold.expected_fields.get("contradictions", [])
        if conflicts:
            text_lower = text.lower()
            acked = sum(1 for c in conflicts if isinstance(c, str) and c.lower() in text_lower)
            contradiction_handling = acked / len(conflicts)
        else:
            contradiction_handling = 1.0

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
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
    return sentences[:20]


def _extract_citations(parsed_output, text):
    """Extract citation strings from output."""
    citations = []
    if parsed_output and "citations" in parsed_output:
        cites = parsed_output["citations"]
        if isinstance(cites, list):
            citations = [str(c) for c in cites]
    if not citations:
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
        brackets = re.findall(r'\[[\d,\s\-]+\]', text)
        citations = brackets if brackets else []
    return citations


def _extract_cite_keys(claim_text):
    """Extract citation keys like [1], [2] from a claim."""
    return re.findall(r'\[\d+\]', claim_text)
