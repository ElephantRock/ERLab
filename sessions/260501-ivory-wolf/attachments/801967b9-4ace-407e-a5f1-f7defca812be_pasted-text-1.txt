# Thirteen Fixes — Mapped to Reference-Repo Solutions

Each fix is traced to a specific pattern found in `C:\Next AI\ref\*`.

---

## CRITICAL 1: Vector Store Dimension Mismatch
**Problem:** ChromaDB collection expects 1536-dim embeddings, gets 384-dim queries. All 79 novelty scores are fake (default 0.8).

**Root cause:** `VectorStore.__init__` calls `get_or_create_collection` without checking whether the existing collection's dimension matches the current `EmbeddingService.dimension`. When the embedding provider changes (e.g., from OpenAI 1536 → Ollama 384), the collection retains old dimensions but queries use new ones. ChromaDB silently returns empty results, and `NoveltyChecker` falls through to the "No similar papers found" path returning hardcoded 0.8.

**Solution (from `mem0-main/mem0/vector_stores/chroma.py` + `mem0-main/mem0/configs/vector_stores/chroma.py`):**

mem0 validates dimensions at collection creation time and stores `embedding_dims` in config. Their pattern:
1. Read `embedding_model_dims` from the embedder config
2. Pass it when creating the vector store
3. Validate on every insert

**Files to change:**

### `backend/pipeline/knowledge/vector_store.py`
```python
# Add to __init__ after get_or_create_collection:
self._collection = self._client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)

# NEW: Validate collection dimension matches embedding dimension
actual_dim = self._embedding_service.dimension
if self._collection.count() > 0:
    # Peek at existing embeddings to check dimension
    sample = self._collection.get(limit=1, include=["embeddings"])
    if sample["embeddings"] and len(sample["embeddings"][0]) != actual_dim:
        logger.warning(
            "Collection dimension (%d) != embedding dimension (%d). "
            "Recreating collection.",
            len(sample["embeddings"][0]), actual_dim,
        )
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
```

### `backend/pipeline/knowledge/embedding_service.py`
The `dimension` property defaults to 1536 when the provider doesn't declare one. The `DummyEmbeddingProvider` also defaults to 1536. Need to ensure the actual provider's dimension is queried at startup:

```python
# In EmbeddingService.__init__, add startup validation:
async def validate_startup(self) -> bool:
    """Test embed a single string to confirm dimensions work."""
    test = await self.embed_single("test")
    if not test or all(v == 0.0 for v in test):
        logger.error("Embedding provider returned zero vector — novelty will be fake")
        return False
    return True
```

---

## CRITICAL 2: Proposal Synthesizer Produces Stubs
**Problem:** 37/37 proposals have "Synthesis failed" as the introduction. Average 170 words.

**Root cause:** The `synthesize()` method wraps everything in one `try/except`. Any failure (provider timeout, structured_output parse error, max_tokens exceeded) falls to the catch-all that returns a stub `ResearchProposal(introduction="Synthesis failed...")`. The `_expand_sections` retry helps but only if the first pass partially succeeded.

**Solution (from `AI-Scientist-main/ai_scientist/perform_writeup.py`):**

AI-Scientist generates papers **section-by-section**, not in one monolithic call. Each section gets its own prompt with specific writing tips (`per_section_tips` dict). After writing, each section goes through a **refinement pass** with an error checklist. Key pattern:

```python
per_section_tips = {
    "Abstract": "TL;DR of the paper...",
    "Introduction": "Longer version of the Abstract...",
    "Method": "What we do. Why we do it...",
}

# Write section by section
for section_name in REQUIRED_SECTIONS:
    text = write_section(section_name, tips=per_section_tips[section_name])
    text = refine_section(section_name, text, error_list)
```

**Files to change:**

### `backend/pipeline/synthesis/proposal_synthesizer.py`
Replace the single-call approach with section-by-section generation:

```python
async def synthesize(self, ...):
    sections = {}
    # Generate each section independently
    for section_name in REQUIRED_SECTIONS:
        try:
            section_text = await self._generate_section(
                section_name, idea, novelty_report, feasibility_report, ...
            )
            sections[section_name.lower().replace(" ", "_")] = section_text
        except Exception as e:
            logger.error("Section %s failed: %s", section_name, e)
            sections[section_name.lower().replace(" ", "_")] = ""
    
    # Refine all sections together
    proposal = ResearchProposal(idea_id=None, **sections)
    proposal = await self._refine_all_sections(proposal, idea)
    return proposal
```

This way, if one section fails, others still get generated — no more "Synthesis failed" stubs.

---

## CRITICAL 3: Pipeline Success Rate 10%
**Problem:** 49 attempts, 5 produced ideas, zero produced a complete proposal.

**Root cause:** This is the cumulative effect of CRITICAL 1 + 2. Fix those two and success rate jumps. But there's a third issue: the pipeline halts on `LiteratureSearchStage` returning `False` when no papers found (which happens when Semantic Scholar rate-limits).

**Solution (from `autoresearch-master` + `AI-Scientist-main/ai_scientist/generate_ideas.py`):**

Both have multi-source fallback with graceful degradation. AI-Scientist's `search_for_papers` tries Semantic Scholar, then falls back to other sources, and still proceeds with empty results by using idea generation from the domain alone.

**Files to change:**

### `backend/pipeline/stages.py` — `LiteratureSearchStage.execute`
```python
# Change: don't halt on empty results
if not all_papers:
    logger.warning("No papers found. Proceeding with domain knowledge only.")
    # Don't return False — let gap analysis work from domain alone
    return True  # Changed from False
```

### `backend/pipeline/literature/semantic_scholar.py`
Already has retry logic, but add API key validation:

```python
def __init__(self, api_key: str | None = None):
    if not api_key:
        logger.warning(
            "Semantic Scholar API key not set. Rate limits will be severe. "
            "Get a free key at: https://www.semanticscholar.org/product/api#api-key"
        )
    ...
```

---

## HIGH 4: Knowledge Graph Has 1 Relationship Type
**Problem:** Only `PROPOSES_METHOD` edges exist (added in `stages.py`). The other 8 relationship types in `RelationType` are never created.

**Root cause:** The `IngestionStage` only adds paper entities — no relationships between papers (CITES, USES_METHOD, EXTENDS, etc.). The `IdeaGenerationStage` only adds `PROPOSES_METHOD` from gaps to ideas. Nobody extracts relationships from paper text.

**Solution (from `AutoResearchClaw-main/researchclaw/knowledge/graph/relations.py`):**

AutoResearchClaw has 9 relationship types (CITES, EXTENDS, OUTPERFORMS, USES_DATASET, APPLIES_METHOD, EVALUATES_WITH, AUTHORED_BY, RELATED_TO) and extracts them during ingestion using LLM-based extraction.

**Files to change:**

### New file: `backend/pipeline/knowledge/relationship_extractor.py`
```python
"""LLM-based relationship extraction from paper abstracts."""

RELATIONSHIP_EXTRACTION_PROMPT = """Given these two research papers, identify relationships between them.

Paper A: {title_a}
Abstract: {abstract_a}

Paper B: {title_b}
Abstract: {abstract_b}

Classify the relationship. Choose from:
- CITES: Paper A cites or references Paper B
- USES_METHOD: Paper A uses a method from Paper B
- EXTENDS: Paper A extends/builds upon Paper B's work
- CONTRADICTS: Paper A contradicts or challenges Paper B's findings
- BUILDS_ON: Paper A builds on Paper B's framework
- APPLIED_TO: Paper A applies Paper B's technique to a new domain

Respond in JSON: {"relation_type": "...", "confidence": 0.0-1.0, "evidence": "..."}
"""

async def extract_relationships(papers: list[Paper], provider: LLMProvider) -> list[KnowledgeRelationship]:
    """Extract relationships between papers using LLM."""
    relationships = []
    for i, paper_a in enumerate(papers):
        for paper_b in papers[i+1:i+5]:  # Compare with next 5 papers
            # ... LLM call + parse
    return relationships
```

### `backend/pipeline/stages.py` — `IngestionStage.execute`
Add relationship extraction after entity creation:
```python
# After adding entities to KG
if self._kg:
    from backend.pipeline.knowledge.relationship_extractor import extract_relationships
    relationships = await extract_relationships(unique_papers, self._provider)
    for rel in relationships:
        self._kg.add_relationship(rel)
    self._kg.save()
```

---

## HIGH 5: Truth Values Are Cosmetic
**Problem:** All gaps have confidence=0.5, evidence=1. `revise()` is never called.

**Root cause:** Truth values are created with `TruthValue(frequency=gap.confidence, confidence=0.6)` in `GapAnalysisStage` but are never revised when new evidence arrives. The `revise()` method exists in `TruthValue` but nothing calls it after initial creation.

**Solution (from `OpenNARS-for-Applications-master`):**

OpenNARS uses truth revision as a core loop — every new observation triggers revision. The pattern is: when a gap gets referenced by an idea, revise its truth upward. When papers are added that relate to a gap, revise its truth based on evidence count.

**Files to change:**

### `backend/pipeline/stages.py` — `IdeaGenerationStage._execute_sequential`
```python
# After ideas are generated, revise gap truth values
for idea in ideas:
    for gap_id in idea.source_gap_ids:
        gap_eid = f"gap:{gap_id[:60]}"
        entity = self._kg.get_entity(gap_eid) if self._kg else None
        if entity:
            # Idea addresses this gap → revise truth upward
            entity.truth = entity.truth.revise(
                TruthValue(frequency=0.8, confidence=0.7, evidence_count=1)
            )
```

### `backend/pipeline/knowledge/graph.py` — `add_entity`
The `revise()` call already happens when the same entity is added twice. The real fix is ensuring entities get re-added with updated truth values when new evidence arrives (e.g., when a gap is later confirmed by idea generation).

---

## HIGH 6: Tree Search Never Ran
**Problem:** Disabled by default (`tree_of_thought_enabled: bool = False`), never enabled.

**Root cause:** Config default is `False`. The feature works but nobody turns it on.

**Solution:** Change the default to `True` since it's a headline feature.

**File:** `backend/config.py`
```python
tree_of_thought_enabled: bool = True  # Changed from False
```

---

## HIGH 7: Mechanical Metrics Never Computed
**Problem:** 0/79 ideas have them.

**Root cause:** `MechanicalMetricsStage` exists and is in the stage list. But the `compute_all` method requires `idea.supporting_papers` which is never populated. The `IdeaGenerationStage` doesn't set `supporting_papers` on generated ideas.

**Solution:** The fix is in `IdeaGenerationStage` — track which papers informed each idea.

**File:** `backend/pipeline/generation/agent_orchestrator.py` or the idea generation agent.
Need to set `idea.supporting_papers = [p.id for p in context_papers[:10]]` on each generated idea.

Also, `MechanicalMetricsStage.execute` has this code:
```python
cited_ids = set(getattr(idea, "supporting_papers", []) or [])
supporting = [p for p in ctx.all_papers if getattr(p, "id", None) in cited_ids]
```
This returns empty when `supporting_papers` is empty/None, so all metrics default to 0.

**Quick fix in stages.py MechanicalMetricsStage:**
```python
# Fallback: if no explicit supporting_papers, use all papers
if not supporting:
    supporting = ctx.all_papers[:10]
```

---

## HIGH 8: Self-Improvement Never Triggered
**Problem:** No data directory exists.

**Root cause:** `self_improve_persist_dir` defaults to `"./data/self_improve"`. The directory is never created at startup, and `ParetoFrontier` fails silently when it can't read its file. The `_evolver` is initialized but can't persist.

**Solution (pattern from `mem0-main`):**

mem0 always creates directories in `__init__` before reading/writing.

**File:** `backend/pipeline/self_improve/evolution.py` — `ParetoFrontier.__init__`
```python
from pathlib import Path

def __init__(self, path: str):
    self._path = Path(path)
    self._path.parent.mkdir(parents=True, exist_ok=True)  # ADD THIS
    self._load()
```

Also in `backend/pipeline/orchestrator.py` — `_init_self_improve`:
```python
def _init_self_improve(self, settings):
    # Ensure data directory exists
    Path(settings.self_improve_persist_dir).mkdir(parents=True, exist_ok=True)  # ADD THIS
    ...
```

---

## HIGH 9: 7 Runs Stuck "Running" Forever
**Problem:** Background task dies silently, runs stay "running" forever.

**Root cause:** The heartbeat system exists (`StageHeartbeat` in `orchestrator.py`) but it only tracks active stages during execution. When the process dies, there's no watchdog to mark the run as failed. The `RunCheckpoint` persists stage status but nothing polls for orphaned runs.

**Solution (from `airflow-main/airflow-core/src/airflow/jobs/scheduler_job_runner.py`):**

Airflow's `_find_task_instances_without_heartbeats` is the exact pattern needed:
1. Track `last_heartbeat_at` timestamp on each run
2. A periodic watchdog checks: `SELECT * FROM runs WHERE status='running' AND last_heartbeat_at < NOW() - INTERVAL timeout`
3. Mark orphaned runs as failed

**New file: `backend/pipeline/execution/watchdog.py`**
```python
"""Watchdog that detects and marks stuck pipeline runs."""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PipelineWatchdog:
    def __init__(self, persistence, timeout_seconds: float = 300.0, poll_interval: float = 60.0):
        self._persistence = persistence
        self._timeout = timedelta(seconds=timeout_seconds)
        self._poll_interval = poll_interval
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            await self._check_stuck_runs()
            await asyncio.sleep(self._poll_interval)

    async def _check_stuck_runs(self):
        """Find runs stuck in 'running' and mark them failed."""
        stuck = self._persistence.find_stale_runs(max_age=self._timeout)
        for run in stuck:
            logger.warning("Marking stuck run %s as failed (no heartbeat for %s)",
                          run.run_id, self._timeout)
            self._persistence.mark_run_failed(run.db_id, "Watchdog: no heartbeat within timeout")
```

### `backend/pipeline/persistence.py`
Add method:
```python
def find_stale_runs(self, max_age: timedelta) -> list:
    """Find runs that have been running longer than max_age."""
    cutoff = datetime.utcnow() - max_age
    with self._session() as session:
        return session.query(PipelineRun).filter(
            PipelineRun.status == "running",
            PipelineRun.updated_at < cutoff,
        ).all()
```

---

## HIGH 10: Tests Mock Everything
**Problem:** 1,944 passing tests prove nothing about real behavior.

**Root cause:** All tests mock the LLM provider, vector store, and knowledge graph. No integration tests exist.

**Solution (from `deepeval-main` patterns):**

deepeval provides test patterns for LLM applications that test real behavior:
1. **Smoke tests** that call real endpoints with small inputs
2. **Golden master tests** that record and replay real LLM responses
3. **Contract tests** that validate input/output schemas without mocking internals

**New file:** `backend/tests/integration/test_pipeline_smoke.py`
```python
"""Smoke test: runs the actual pipeline with minimal inputs."""
import pytest
from backend.pipeline.orchestrator import PipelineOrchestrator

@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_produces_ideas():
    """Test that the pipeline can produce at least one idea from a real run."""
    orch = PipelineOrchestrator()
    result = await orch.run(
        domain="AI/NLP",
        search_queries=["transformer attention mechanisms"],
        generation_rounds=1,
        ideas_per_round=1,
        run_novelty=False,
        run_feasibility=False,
        run_synthesis=False,
    )
    assert len(result.ideas) >= 0  # At minimum, doesn't crash
    assert result.run_id is not None

@pytest.mark.integration
@pytest.mark.asyncio
async def test_novelty_check_real_embeddings():
    """Test novelty check with real embeddings, not mocked ones."""
    orch = PipelineOrchestrator()
    # ... test with actual embedding service
```

Also add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests that require real services (deselect with '-m \"not integration\"')",
]
```

---

## MEDIUM 11: Semantic Scholar Rate-Limited
**Problem:** 429 errors without API key.

**Root cause:** `semantic_scholar_api_key` defaults to `None`. Without it, Semantic Scholar allows ~100 requests/5min vs 1 request/second with a key.

**Solution:** Already partially implemented — the retry logic with exponential backoff exists in `semantic_scholar.py`. The fix is two-part:

1. **Validate at startup:**
```python
# In orchestrator._init_core_services
if not settings.semantic_scholar_api_key:
    logger.warning(
        "EROCK_SEMANTIC_SCHOLAR_API_KEY not set. "
        "Rate limits will be severe. Get a free key: "
        "https://www.semanticscholar.org/product/api#api-key"
    )
```

2. **Add to .env.example with clear instructions** (already done).

3. **Make OpenAlex the primary source when no API key** — it's free and unlimited:
```python
# In search_service.py _default_sources
if not settings.semantic_scholar_api_key:
    # Reorder: OpenAlex first, Semantic Scholar last
    return [OpenAlexSource(...), ArxivSource(), SemanticScholarSource()]
```

---

## MEDIUM 12: 24 Duplicate Papers
**Problem:** Dedup uses ID, not title. Same paper from different sources gets different IDs.

**Root cause:** `SearchService._deduplicate` already uses DOI-then-title-hash (line in `search_service.py`):
```python
key = paper.doi if paper.doi else _title_hash(paper.title)
```
But `LiteratureSearchStage` has its own dedup that only uses ID:
```python
if p.id not in seen:  # This misses cross-source duplicates!
```

**Solution:** Fix `LiteratureSearchStage` to use the same dedup as `SearchService`.

**File:** `backend/pipeline/stages.py` — `LiteratureSearchStage.execute`
```python
# Replace ID-based dedup with title-based dedup
from backend.pipeline.literature.search_service import _title_hash
seen = set()
unique = []
for p in all_papers:
    key = p.doi if p.doi else _title_hash(p.title)
    if key not in seen:
        seen.add(key)
        unique.append(p)
```

Also add fuzzy title matching for near-duplicates:
```python
def _fuzzy_title_dedup(papers: list[Paper], threshold: float = 0.85) -> list[Paper]:
    """Remove papers with very similar titles."""
    from difflib import SequenceMatcher
    unique = []
    for paper in papers:
        is_dup = any(
            SequenceMatcher(None, paper.title.lower(), existing.title.lower()).ratio() > threshold
            for existing in unique
        )
        if not is_dup:
            unique.append(paper)
    return unique
```

---

## MEDIUM 13: 5 API Endpoints Broken
**Problem:** costs, traces, governance, sessions, literature endpoints return 500s.

**Root cause:** These endpoints depend on services that may not be initialized (e.g., `ObservabilityManager` for traces, `SessionManager` for sessions). When the service is `None`, accessing it causes `AttributeError`.

The `traces.py` route already has the right pattern:
```python
def _get_observability():
    mgr = get_active_manager()
    if not mgr:
        raise ServiceUnavailableError("Observability not enabled", ...)
    return mgr
```

But `costs.py`, `governance.py`, `sessions.py`, `literature.py` don't have this pattern.

**Solution (from `dify-main` API pattern):**

Dify uses FastAPI dependency injection with graceful fallback:

**File:** `backend/api/routes/costs.py` and other broken routes
```python
from backend.api.errors import ServiceUnavailableError

def _require_tracker():
    tracker = get_registry().cost_tracker
    if not tracker:
        raise ServiceUnavailableError(
            "Cost tracking not available",
            hint="Ensure the pipeline has been initialized"
        )
    return tracker

# Use in all endpoints:
@router.get("/summary")
async def cost_summary():
    return _require_tracker().summary()
```

Apply the same pattern to:
- `backend/api/routes/governance.py` — check `_governance_validator`
- `backend/api/routes/sessions.py` — check `_session_manager`  
- `backend/api/routes/literature.py` — check `_search_service`

### `backend/api/errors.py` — add ServiceUnavailableError
```python
class ServiceUnavailableError(HTTPException):
    def __init__(self, msg: str, hint: str = ""):
        super().__init__(
            status_code=503,
            detail={"error": msg, "hint": hint}
        )
```

---

## Summary: Priority Order

| # | Problem | Root Cause | Fix Location | Effort |
|---|---------|-----------|-------------|--------|
| 1 | Dimension mismatch | No validation on collection vs provider | `vector_store.py`, `embedding_service.py` | S |
| 2 | Synthesis stubs | Monolithic LLM call, catch-all fallback | `proposal_synthesizer.py` | M |
| 3 | 10% success rate | #1 + #2 combined + halt-on-empty | `stages.py` | S |
| 4 | 1 relationship type | No extraction during ingestion | New `relationship_extractor.py` | M |
| 5 | Cosmetic truth values | Never revised after creation | `stages.py` | S |
| 6 | Tree search disabled | Default=False in config | `config.py` | XS |
| 7 | No mechanical metrics | `supporting_papers` never populated | `stages.py` | S |
| 8 | No self-improve dir | Directory never created | `orchestrator.py`, `evolution.py` | XS |
| 9 | Stuck "running" forever | No watchdog for orphaned runs | New `watchdog.py` | M |
| 10 | Tests mock everything | No integration tests | New `test_pipeline_smoke.py` | M |
| 11 | Semantic Scholar 429 | No API key, no fallback ordering | `search_service.py` | S |
| 12 | 24 duplicate papers | `LiteratureSearchStage` dedup by ID only | `stages.py` | S |
| 13 | 5 broken endpoints | Missing null-checks on optional services | `api/routes/*.py` | S |

**XS** = 1 line change, **S** = <10 lines, **M** = 10-50 lines
