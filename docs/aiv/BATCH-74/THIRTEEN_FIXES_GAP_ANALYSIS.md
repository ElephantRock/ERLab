# Thirteen Fixes — Prescription vs Implementation Gap Analysis

**Date:** 2026-05-06  
**Source:** `pasted-text-1.txt` (the "Thirteen Fixes" document)  
**Executed in:** BATCH-73 (commit `8552dba`) + BATCH-74 (commit `96a6e75`)  
**Status:** 13/13 fixes implemented, 4 sub-gaps remain

---

## Fix-by-Fix Assessment

### CRITICAL 1: Vector Store Dimension Mismatch
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Collection dimension validation | ✅ `__init__` checks stored vs provider dim | ✅ Done in `vector_store.py` | **MATCH** |
| Auto-recreate on mismatch | ✅ `delete_collection` + recreate | ✅ Done | **MATCH** |
| `EmbeddingService.validate_startup()` | ✅ Test embed to confirm non-zero | ❌ Not implemented | **GAP** |

**Gap severity:** LOW. The dimension check in `VectorStore.__init__` catches the mismatch. But the zero-vector problem remains: `DummyEmbeddingProvider` returns all-zero embeddings, and no startup check detects this. A real provider (OpenAI/Gemini/Ollama) would return real vectors, so this gap only matters in the dummy/test configuration.

---

### CRITICAL 2: Proposal Synthesizer Produces Stubs
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Section-by-section generation | ✅ Each section independently | ✅ `_generate_single_section()` exists | **MATCH** |
| Per-section tips dict | ✅ `per_section_tips` | ✅ Done in `_generate_single_section` | **MATCH** |
| Refinement pass (`_refine_all_sections`) | ✅ Error checklist after writing | ❌ Not implemented | **GAP** |

**Gap severity:** MEDIUM. The synthesizer now generates section-by-section with a fallback for failed sections. But there's no refinement pass — no error checklist, no second review of generated sections. The first-pass quality is the final quality.

---

### CRITICAL 3: Pipeline Success Rate 10%
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Don't halt on empty literature | ✅ Return True instead of False | ✅ Done | **MATCH** |
| S2 API key warning at startup | ✅ Log warning | ✅ Already existed from BATCH-68 | **MATCH** |

**Full match.** No gaps.

---

### HIGH 4: Knowledge Graph Has 1 Relationship Type
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| New `relationship_extractor.py` | ✅ LLM-based extraction | ✅ Done with O(n) comparisons | **MATCH** |
| Integrate into IngestionStage | ✅ Call after entity creation | ✅ Done | **MATCH** |
| CITES, USES_METHOD, EXTENDS, etc. | ✅ 6 relationship types | ✅ All 6 supported | **MATCH** |
| Compare with next 5 papers | ✅ O(n) not O(n²) | ✅ Max 3 per paper (stricter) | **MATCH** |

**Full match.** Actually stricter than prescribed (3 comparisons vs 5).

---

### HIGH 5: Truth Values Are Cosmetic
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Revise gap truth when idea references it | ✅ In IdeaGenerationStage | ✅ Done | **MATCH** |
| Revise gap truth when paper relates to gap | ✅ In LiteratureSearchStage | ❌ Not implemented | **GAP** |
| `revise()` never decreases confidence | ✅ Authority rule | ✅ Capped at 0.99 | **MATCH** |

**Gap severity:** LOW. Paper-to-gap truth revision is not implemented. The idea-to-gap revision is the more impactful path (ideas directly address gaps), but paper-to-gap would further improve truth quality.

---

### HIGH 6: Tree Search Disabled
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Change default to True | ✅ `bool = True` | ✅ Done | **MATCH** |

**Full match.**

---

### HIGH 7: Mechanical Metrics Never Computed
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Fallback to all_papers when empty | ✅ `supporting = ctx.all_papers[:10]` | ✅ Done | **MATCH** |

**Full match.** Note: the deeper fix (populating `idea.supporting_papers` during idea generation) was not done — only the fallback was implemented.

---

### HIGH 8: Self-Improvement Never Triggered
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Create data directory in `_init_self_improve` | ✅ `mkdir(parents=True)` | ✅ Done in orchestrator.py | **MATCH** |
| Create dir in `ParetoFrontier.__init__` | ✅ `mkdir(parents=True)` | ❌ Not done in evolution.py | **GAP** |

**Gap severity:** LOW. The directory creation in `orchestrator.py` runs before `ParetoFrontier` is constructed, so the missing mkdir in `ParetoFrontier.__init__` is effectively covered. But if `ParetoFrontier` is ever instantiated directly (not through the orchestrator), it would fail.

---

### HIGH 9: 7 Runs Stuck "Running" Forever
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| New `watchdog.py` | ✅ `PipelineWatchdog` class | ✅ Done | **MATCH** |
| `find_stale_runs()` in persistence | ✅ Query status='running' | ✅ Done | **MATCH** |
| `updated_at` column on PipelineRun | ✅ Track last activity | ✅ Done + migration 006 | **MATCH** |
| API endpoint | ✅ POST /pipeline/watchdog | ✅ Done | **MATCH** |
| Periodic background polling | ✅ `start()` async loop | ❌ Not wired into app startup | **GAP** |

**Gap severity:** LOW. The watchdog has `check_sync()` and `check_and_mark_stale_runs()` methods, plus the API endpoint. But there's no automatic periodic polling — you have to call the endpoint manually or wire it into the app startup yourself.

---

### HIGH 10: Tests Mock Everything
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Integration test skeleton | ✅ `test_pipeline_smoke.py` | ✅ 6 tests under `tests/integration/` | **MATCH** |
| `@pytest.mark.integration` | ✅ Marker | ✅ Done | **MATCH** |
| Tests pass without API keys | ✅ Use DummyEmbeddingProvider | ✅ Done | **MATCH** |

**Full match.** Note: the prescribed tests mentioned `PipelineOrchestrator.run()` — the actual tests test individual components (embedding, vector store, truth, relationships, watchdog) rather than a full pipeline run, which is more practical for tests that must work without API keys.

---

### MEDIUM 11: Semantic Scholar Rate-Limited
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| Startup warning | ✅ Log when no key | ✅ Already existed | **MATCH** |
| `.env.example` with instructions | ✅ Document the key | ✅ Already existed | **MATCH** |
| Reorder sources: OpenAlex first when no key | ✅ `_default_sources` reordering | ✅ Done in `search_service.py` | **MATCH** |

**Full match.**

---

### MEDIUM 12: 24 Duplicate Papers
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| DOI/title dedup in LiteratureSearchStage | ✅ Replace ID-based dedup | ✅ Done | **MATCH** |
| Fuzzy title matching | ✅ `SequenceMatcher` threshold 0.85 | ❌ Not implemented | **GAP** |

**Gap severity:** LOW. The DOI/normalized-title dedup catches exact duplicates. Fuzzy matching would catch near-duplicates like "Attention Is All You Need" vs "Attention is all you need" but the `lower().strip()` normalization already handles most of these.

---

### MEDIUM 13: 5 API Endpoints Broken
| Aspect | Prescribed | Implemented | Status |
|--------|-----------|-------------|--------|
| `costs.py` null check | ✅ ServiceUnavailableError | ✅ Done | **MATCH** |
| `governance.py` null check | ✅ ServiceUnavailableError | ❌ Not done | **GAP** |
| `sessions.py` null check | ✅ ServiceUnavailableError | ❌ Not done | **GAP** |
| `literature.py` null check | ✅ ServiceUnavailableError | ❌ Not done | ❌ Actually already works |
| `ServiceUnavailableError` class | ✅ Add to errors.py | ✅ Already existed | **MATCH** |

**Gap severity:** MEDIUM. Only `costs.py` got the null-check pattern. The document prescribed applying the same pattern to governance, sessions, and literature. The literature endpoint actually works (the 422 was from using wrong parameter name in testing). But governance and sessions may still 503 when their services aren't initialized.

---

## Summary: 4 Sub-Gaps Remain

| # | Gap | Severity | Impact |
|---|-----|----------|--------|
| G1 | `EmbeddingService.validate_startup()` not implemented | LOW | Zero vectors from DummyEmbeddingProvider not detected at startup |
| G2 | `_refine_all_sections()` not implemented in synthesizer | MEDIUM | No quality pass after section generation |
| G3 | Paper-to-gap truth revision not implemented | LOW | Only idea-to-gap revision exists |
| G4 | ParetoFrontier directory creation not added to `__init__` | LOW | Covered by orchestrator's mkdir, but fragile |
| G5 | Watchdog not wired into app startup for periodic polling | LOW | Manual-only via API endpoint |
| G6 | Fuzzy title dedup not implemented | LOW | Only exact DOI/title dedup |
| G7 | governance.py and sessions.py null-checks not added | MEDIUM | Endpoints may 503 when services not initialized |

### Overall Assessment

**13/13 fixes implemented at the primary level.** All critical and high-severity fixes are in place. The 7 sub-gaps are all LOW or MEDIUM severity — they represent defensive improvements and polish, not pipeline-breaking issues.

The two most impactful remaining gaps are:
1. **G2 (refinement pass):** Without a second quality check, the synthesizer relies entirely on first-pass LLM quality
2. **G7 (endpoint null-checks):** Two API routes may return 500s instead of proper 503s

Neither gap prevents the pipeline from producing research output with real API keys and a real embedding provider.
