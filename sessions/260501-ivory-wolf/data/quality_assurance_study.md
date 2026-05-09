# Automated Quality Assurance Study — Gap Analysis for Elephant Rock

**Date**: 2026-05-09  
**Source**: "Quality Assurance Without Human Review" — 7 methods for automated claim verification  
**Scope**: Map each technique to existing Elephant Rock modules, identify gaps, prioritize

---

## Gap Analysis Summary

```
┌──────────────────────────────┬───────────┬────────────────────────────────────────┐
│ Technique                    │ Status    │ What We Have                          │
├──────────────────────────────┼───────────┼────────────────────────────────────────┤
│ 1. Cross-Model Consensus     │ 🟡 PARTIAL│ AdversarialDebate exists but unused   │
│ 2. Source-Anchored Quotes    │ 🔴 MISSING│ No quote verification at all          │
│ 3. Consistency Checking      │ 🟢 EXISTS │ ContradictionDetector + numeric check │
│ 4. Staged Confidence         │ 🔴 MISSING│ Binary quality_score only             │
│ 5. Adversarial Verification  │ 🟡 PARTIAL│ ContradictionDetector is adversarial  │
│ 6. Temporal Decay            │ 🔴 MISSING│ No trust decay mechanism              │
│ 7. Provenance Tracking       │ 🟡 PARTIAL│ Governance audit exists but not for   │
│                              │           │ claims                                │
└──────────────────────────────┴───────────┴────────────────────────────────────────┘
```

---

## Detailed Analysis Per Technique

### 1. Cross-Model Consensus — 🟡 PARTIAL

**What the reference proposes**: Run the same verification through two different models (7B + 14B). If both agree → high confidence. If they disagree → flag as uncertain.

**What we have**: `backend/pipeline/evaluation/adversarial_debate.py` — a 3-agent debate system (optimist, skeptic, contrarian) with weighted consensus scoring. But it's **not wired into any pipeline stage** — it exists as a standalone module that nobody calls.

**Gap**: The debate system exists but isn't used for wiki verification, claim verification, or contradiction detection. We verify with a single model only.

**Priority**: MEDIUM — useful but doubles LLM cost. Only valuable for high-stakes claims (paper draft, study design inputs).

---

### 2. Source-Anchored Quote Verification — 🔴 MISSING ⭐

**What the reference proposes**: Force the LLM to quote the exact source text supporting a claim. Then verify the quote actually exists in the source via substring matching. If the LLM can't produce a real quote → claim is unsupported or hallucinated.

**What we have**: Our WikiVerifier asks "is this claim supported?" but **never requires a quote** and **never validates evidence against the source**. The LLM can say "supported" without producing verifiable evidence.

**Why this is the #1 gap**: This is the single most effective technique for catching hallucinations:
- 30-40% of fabricated claims are caught by quote verification alone
- It's deterministic (string matching, no LLM judgment needed for the verification step)
- It creates an evidence trail for provenance

**Implementation**: Modify `_verify_claim_with_llm()` to:
1. Request `"supporting_quote"` in the JSON response
2. Verify `supporting_quote in source_text` (with fuzzy matching for whitespace)
3. If quote is fabricated → mark as UNSUPPORTED with high confidence

**Priority**: **HIGH** — 30-40% hallucination catch rate for a simple string match.

---

### 3. Consistency Checking — 🟢 EXISTS

**What the reference proposes**: Check claims against other claims in the same paper (intra-paper) and against established results from other papers (cross-paper). Flag statistical outliers.

**What we have**: `ContradictionDetector` pairs RESULT claims with same dataset+metric and checks for contradictions. This covers intra-paper and cross-paper consistency.

**What's missing**: The reference's cross-paper consistency check uses **known mean ± standard deviation** from the database to detect outliers (>3σ). Our detector only pairs individual claims, not aggregate statistics.

**Priority**: LOW — our ContradictionDetector already covers the core case.

---

### 4. Staged Confidence (Progressive Trust) — 🔴 MISSING ⭐

**What the reference proposes**: Claims accumulate trust through verification stages:
- Keyword overlap → 0.0-0.3
- Single LLM → 0.3-0.6
- Source-anchored quote → 0.6-0.8
- Cross-model consensus → 0.8-0.9
- Cross-paper consistency → 0.9-1.0

Different downstream actions require different trust levels:
- Display in artifact: trust ≥ 0.0
- Gap analysis: trust ≥ 0.6
- Study design: trust ≥ 0.8
- Paper draft: trust ≥ 0.95

**What we have**: A single `quality_score` (0.0-1.0) on WikiEntry that's just `verified/total` claims. No staged progression, no downstream trust gates.

**Why this matters**: Without staged confidence, low-trust claims propagate to gap analysis and study design, poisoning downstream outputs.

**Priority**: **HIGH** — prevents garbage-in-garbage-out across the pipeline.

---

### 5. Adversarial Verification — 🟡 PARTIAL

**What the reference proposes**: Two-pass verification: first ask "is this supported?", then ask "is there evidence AGAINST this claim?" This catches confirmation bias (LLMs agree too readily).

**What we have**: ContradictionDetector finds contradictory claims across papers. WikiVerifier asks "is this supported?" but never asks the adversarial question.

**Gap**: We never ask "what evidence contradicts this claim?" — we only ask "what evidence supports it?" These are different questions. A claim can have supporting evidence AND contradicting evidence simultaneously.

**Priority**: MEDIUM — useful but doubles verification cost. Can be selective (only run when standard confidence < 0.8).

---

### 6. Temporal Decay — 🔴 MISSING

**What the reference proposes**: Claims from older papers that haven't been independently verified lose trust over time. Corroborated claims get a trust boost.

**What we have**: No trust decay mechanism at all. A claim from 2020 with no corroboration has the same trust as a claim from 2026 confirmed by 3 papers.

**Priority**: LOW — only matters for long-running deployments with accumulated claim databases. Our DB has 1,223 papers and 196 gaps, but temporal analysis isn't critical yet.

---

### 7. Provenance Tracking — 🟡 PARTIAL

**What the reference proposes**: Every claim carries its full verification history (which stages it passed, what evidence was found, what confidence at each stage). Machine-readable + human-readable audit trail.

**What we have**: `backend/pipeline/governance/events.py` has cryptographic audit trails for governance decisions. But nothing tracks claim-level verification history.

**Priority**: LOW — nice for debugging but not blocking quality.

---

## Recommended Implementation Priority

### HIGH (Implement Now)

| # | Technique | Module to Modify | Effort | Impact |
|:--|:----------|:-----------------|:-------|:-------|
| 1 | **Source-Anchored Quotes** | `wiki/verifier.py` | 2 hrs | 30-40% hallucination catch |
| 2 | **Staged Confidence** | `wiki/verifier.py` + `claims/models.py` | 3 hrs | Prevents low-trust propagation |

### MEDIUM (Next Sprint)

| # | Technique | Module to Modify | Effort | Impact |
|:--|:----------|:-----------------|:-------|:-------|
| 3 | **Adversarial Verification** | `wiki/verifier.py` | 2 hrs | Catches confirmation bias |
| 4 | **Wire AdversarialDebate** | `evaluation/adversarial_debate.py` → pipeline stages | 2 hrs | Existing code, just connect |

### LOW (Future)

| # | Technique | Module to Modify | Effort | Impact |
|:--|:----------|:-----------------|:-------|:-------|
| 5 | **Temporal Decay** | New module `claims/trust.py` | 4 hrs | Long-term self-correction |
| 6 | **Provenance Tracking** | `claims/models.py` | 3 hrs | Auditability |

---

## What We Should NOT Adopt

1. ❌ **Full multi-model consensus on every claim** — Too expensive (2-3x LLM cost). Use selectively for low-confidence claims only.
2. ❌ **Temporal decay as a pipeline gate** — We don't have enough historical data yet. Implement later when claim DB is larger.
3. ❌ **Cross-paper statistical outlier detection** — Our ContradictionDetector already handles the pairwise case. Adding aggregate statistics is over-engineering at this stage.

---

## Key Insight from the Document

> "You don't need a human to judge truth. You need multiple independent mechanical checks that converge on a trust score. When four different methods agree, the claim is almost certainly correct."

This is the philosophy we should adopt: **mechanical verification layers**, not smarter prompts. String matching for quote verification is 100x more reliable than asking the LLM "are you sure?"

The two highest-value additions:
1. **Source anchoring** (string match catches 30-40% of fabrications with zero false positives)
2. **Staged confidence** (prevents low-trust claims from reaching study design and paper drafts)
