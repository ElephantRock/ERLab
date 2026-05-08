# Phase 9 Master Roadmap — Structured Knowledge Layer (Claims, Wiki, Advanced Gaps)

**Lead Programmer:** ivory-wolf  
**Framework:** AIV v5.3  
**Date:** 2026-05-08  
**Previous Phase:** Phase 8 (Pipeline Quality Hardening, B112–B120) — CLOSED  
**Test Baseline:** 2,292  
**Codebase:** 77,500 LOC across 680 files

---

## Strategic Context

The **PDF → Published Paper** architecture study revealed 3 critical gaps:

1. **No Claim Extraction** — Papers are opaque blobs; the pipeline never parses internal structure
2. **No Wiki Generation** — No structured 30-field JSON knowledge per paper
3. **No Advanced Gap Detectors** — Contradiction, method-problem, and scale gap detectors require structured claims

**Keystone dependency:** Everything flows from claims. **Claim extraction is the single highest-ROI addition.**

---

## Batch Sequence Overview

| Batch | Cycle | Goal | Strategic Bet | Tests |
|:------|:------|:-----|:-------------|:------|
| **B121** | STANDARD | Claim Extraction Engine | LLM extracts structured claims from abstracts with >80% coverage | +8 |
| **B122** | STANDARD | Claim Storage & Query Layer | Claims queryable across papers via DB + vector search | +7 |
| **B123** | STANDARD | Wiki Generation Service | LLM produces 30-field structured wiki per paper | +7 |
| **B124** | STANDARD | Curation Rules Engine | User-defined include/exclude rules filter daily papers | +6 |
| **B125** | STANDARD | Contradiction Detector | Cross-paper claim matching finds genuine contradictions | +7 |
| **B126** | STANDARD | Method-Problem Gap Matrix | SQL join + LLM assesses method X applicability to problem Y | +6 |
| **B127** | STANDARD | Study Design with MVP | Full study proposals with minimum viable experiments | +7 |
| **B128** | STANDARD | Daily Auto-Ingestion | Cron-like daily arXiv fetch + filter + index | +5 |
| **B129** | STANDARD | Cross-Paper Connection Agent | Builds_on / contradicts / complements in knowledge graph | +6 |
| **B130** | SIMPLIFIED | Phase 9 Close | Validate all 60 tests, update STATE.md | +0 |

**Totals:** 10 batches, 17 new files, 5 modified, ~60 new tests, ~2,352 expected total

---

## Decision Gates

| After Batch | Decision | Go/No-Go Criteria |
|:-----------|:---------|:------------------|
| B121 | Claims viable? | ≥80% field coverage on 5 test papers |
| B123 | Wiki accurate? | ≤20% unsupported claims per wiki |
| B125 | Contradictions real? | ≥50% of detected contradictions confirmed |
| B127 | Studies actionable? | MVP experiment has code skeleton + go/no-go |
| B130 | Phase 9 complete? | All 60 new tests pass, no regressions |

---
