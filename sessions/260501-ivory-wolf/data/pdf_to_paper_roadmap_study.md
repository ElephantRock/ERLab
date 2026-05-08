# Architecture Study: PDF → Published Paper Roadmap vs Elephant Rock

## Executive Summary

The proposed roadmap is a **10-phase system** from arXiv PDF to publishable paper.
Elephant Rock already covers **Phases 1, 6 (partial), and 9 (partial)** — about 40% of the vision.
The remaining 60% is **claim extraction, wiki generation, curation, study design, experiment execution, and paper drafting**.

---

## Phase-by-Phase Comparison

### Phase 0: Foundation — Elephant Rock ✅ HAS THIS
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| PostgreSQL + pgvector | SQLite + ChromaDB (simpler but functional) |
| FastAPI backend | ✅ Full FastAPI with 18+ route modules |
| Electron desktop UI | React SPA (web-based, not Electron) |
| Object storage for PDFs | `data/` directory structure |

**Gap**: PostgreSQL vs SQLite is an upgrade for production scale, but not critical for research.

---

### Phase 1: Paper Ingestion — Elephant Rock ✅ HAS THIS
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| arXiv API fetch | ✅ `arxiv_source.py` |
| PDF download | ✅ `pdf_service.py` |
| PDF → structured text | ✅ `markitdown` + section parsing |
| Semantic chunking | ✅ `embedding_service.py` + `vector_store.py` |
| Embedding & indexing | ✅ ChromaDB with 768-dim vectors |
| Multi-source search | ✅ OpenAlex, Semantic Scholar, CrossRef, PubMed |

**Gap**: No *daily automated* ingestion — pipeline runs are on-demand. Missing a scheduler.

---

### Phase 2: Curation & Filtering — Elephant Rock ⚠️ PARTIAL
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Rule engine (must_include/exclude) | ❌ No user-defined rule system |
| Semantic similarity filtering | ✅ `relevance_filter.py` |
| Author/venue prestige scoring | ❌ Not implemented |
| Citation velocity tracking | ❌ Not implemented |
| LLM relevance scoring | ✅ `relevance_filter.py` uses LLM scoring |
| Max papers per day limit | ❌ Not configurable |

**Gap**: Need a user-configurable curation rules engine with explicit include/exclude filters.

---

### Phase 3: Wiki Generation — Elephant Rock ❌ DOES NOT HAVE
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Comprehensive JSON wiki schema | ❌ No wiki generation |
| Method extraction (architecture, training, loss) | ❌ Only high-level gap analysis |
| Key insights extraction | ❌ Not implemented |
| Experiment results extraction (tables, metrics) | ❌ Not implemented |
| Limitations extraction | ⚠️ Gap analysis touches on this |
| Future work extraction | ⚠️ Gap analysis touches on this |
| Code/resource links | ❌ Not extracted |
| Novelty assessment per-paper | ❌ Only novelty checking against corpus |
| Quality verification of wiki claims | ❌ Not implemented |

**This is the single biggest gap.** The proposed wiki schema is extremely detailed — 30+ fields covering every aspect of a paper. Elephant Rock's pipeline currently treats papers as abstract containers and never deeply parses their internal structure.

---

### Phase 4: Claim Extraction — Elephant Rock ❌ DOES NOT HAVE
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Method claims (architecture, training, constraints) | ❌ |
| Result claims (dataset, metric, value, baseline) | ❌ |
| Limitation claims (type, severity) | ❌ |
| Future work claims (specificity, difficulty) | ❌ |
| Comparative claims (improves_on, contradicts) | ❌ |
| Cross-paper claim matching | ❌ |

**Critical gap.** Claims are the foundation for contradiction detection, scale gap detection, and method-problem gap detection. Without structured claims, the advanced gap detectors cannot work.

---

### Phase 5: Artifact Generation — Elephant Rock ❌ DOES NOT HAVE
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Interactive artifact document | ❌ |
| Agent enrichment (connections, experiments) | ❌ |
| Connection finding (builds_on, contradicts) | ⚠️ `contradiction.py` exists but not integrated |
| Experiment suggestion | ❌ |
| Related papers agent | ⚠️ Vector similarity exists |
| Incremental agent updates | ❌ |

---

### Phase 6: Gap Detection — Elephant Rock ⚠️ PARTIAL (stronger in some ways)
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Method-problem gap detector | ❌ No claim-based detection |
| Contradiction detector | ⚠️ `contradiction.py` exists, not wired to gap pipeline |
| Scale gap detector | ❌ No scaling law extrapolation |
| LLM-based gap scoring | ✅ `gap_analyzer.py` with confidence scores |
| Clustering-based gaps | ✅ `cluster_service.py` with UMAP + HDBSCAN |
| Gold standard evaluation | ✅ `gold_standards.py` + `pipeline_evaluator.py` |
| Cross-run deduplication | ✅ `deduplicator.py` |
| Multi-domain known gaps | ✅ 4 domains × 8 gaps |

**Elephant Rock is stronger at evaluation but weaker at detection diversity.** The roadmap proposes 3 specialized detectors (method-problem, contradiction, scale) that Elephant Rock doesn't have. But Elephant Rock has quality metrics (Cohen's Kappa, gold standard recall) that the roadmap doesn't mention.

---

### Phase 7: Study Generation — Elephant Rock ⚠️ PARTIAL
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Gap → study proposal | ✅ Idea generation from gaps (IdeatorAgent) |
| Hypothesis formulation | ✅ Ideas include problem/method/contributions |
| Experimental design | ⚠️ `EvaluationPlanGenerator` in plan_generator.py |
| MVP experiment definition | ❌ |
| Go/no-go criteria | ❌ |
| Risk assessment | ✅ Feasibility scoring |
| Timeline/resource estimation | ✅ Ideas include timeline |
| Publication strategy | ❌ |

**Gap**: Elephant Rock generates ideas but not full study proposals with MVP experiments and go/no-go criteria.

---

### Phase 8: Experiment Execution — Elephant Rock ❌ DOES NOT HAVE
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Docker-sandboxed execution | ❌ |
| GPU resource allocation | ❌ |
| Experiment result collection | ❌ |
| Go/no-go analysis agent | ❌ |
| Incremental paper updates from results | ❌ |

**This is a major new subsystem.** Elephant Rock is a research *discovery* platform, not a research *execution* platform.

---

### Phase 9: Paper Generation — Elephant Rock ⚠️ PARTIAL
| Proposed | Elephant Rock Status |
|:---------|:---------------------|
| Complete paper draft from study | ✅ `ProposalSynthesizer` generates 10-section proposals |
| LaTeX export | ✅ `md_to_latex.py` + `latex_exporter.py` |
| BibTeX references | ✅ `bibtex_exporter.py` |
| Section-by-section refinement | ✅ `_refine_sections()` in synthesizer |
| Math notation (LaTeX) | ✅ Prompt instructs LaTeX math |
| Incremental updates | ❌ No update from experiment results |
| Paper quality checklist | ⚠️ `_check_section()` verifies word counts |
| Wiki-based reference extraction | ❌ |

Elephant Rock generates proposals that *read like papers* but aren't grounded in actual experimental results — they're LLM-synthesized from gaps + literature.

---

## Gap Priority Matrix

| Gap | Impact | Effort | Priority |
|:----|:-------|:-------|:---------|
| **Claim Extraction** (Phase 4) | HIGH — enables all advanced gaps | MEDIUM | **P0** |
| **Wiki Generation** (Phase 3) | HIGH — structured paper knowledge | MEDIUM | **P0** |
| **Contradiction Detector** (Phase 6) | MEDIUM — unique gap type | LOW (code exists) | **P1** |
| **Curation Rules Engine** (Phase 2) | MEDIUM — personalized filtering | LOW | **P1** |
| **Method-Problem Gap Detector** (Phase 6) | HIGH — cross-domain transfer gaps | MEDIUM | **P1** |
| **Study Design with MVP** (Phase 7) | HIGH — actionable experiments | MEDIUM | **P2** |
| **Daily Auto-Ingestion** (Phase 1) | MEDIUM — always-current library | LOW | **P2** |
| **Scale Gap Detector** (Phase 6) | LOW — niche but valuable | HIGH | **P3** |
| **Experiment Execution** (Phase 8) | HIGH — full execution platform | VERY HIGH | **P3** |
| **Paper Draft from Results** (Phase 9) | MEDIUM — incremental improvement | HIGH | **P3** |

---

## What Elephant Rock Has That This Roadmap Doesn't

1. **Tree Search idea generation** (beam search, multi-round ideation)
2. **Novelty checking with embeddings** (vector similarity against corpus)
3. **Feasibility scoring** (timeline, risk, resource estimation)
4. **Closed-book citation policy** (SOURCE-X indexing, sanitization)
5. **Reference verification** (trust scores, hallucination stripping)
6. **Proposal deepening** (architecture, toy examples, failure modes, success criteria)
7. **Pipeline quality evaluation** (gap recall, precision, Cohen's Kappa)
8. **Gold standard evaluation** (4 domains × 8 known gaps)
9. **Cross-run gap deduplication**
10. **Hybrid model routing** (local thinking + cloud generation)
11. **4 pipeline strategies** (fast_scan, deep_research, academic_proposal, literature_review)
12. **Journal writer** (research log with sensitive pattern filtering)
13. **Knowledge graph** (1,404 entities, 804 relationships)
14. **World model** (tracks beliefs about research domains)
15. **2,292 tests** across 120+ batches

---

## Honest Assessment

The roadmap is **architecturally sound** and covers the full research lifecycle. But it has significant overlap with Elephant Rock in Phases 1, 6, and 9, and the **real delta is in Phases 3-5 and 8**:

- **Wiki + Claims** (Phases 3-4) = the structured knowledge layer Elephant Rock lacks
- **Artifact generation** (Phase 5) = the interactive research notebook
- **Experiment execution** (Phase 8) = the execution sandbox

The highest-ROI additions for Elephant Rock would be:
1. **Claim extraction** — turns papers from opaque blobs into queryable knowledge
2. **Wiki generation** — structured paper summaries for the knowledge graph
3. **Contradiction detector** — code exists (`contradiction.py`), just needs wiring
4. **Method-problem gap matrix** — once claims exist, this is a SQL join + LLM assessment
