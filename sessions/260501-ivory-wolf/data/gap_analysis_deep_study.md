# Elephant Rock — Deep Gap Analysis Study

**Date:** 2026-05-02  
**Scope:** Every file touching the gap lifecycle — models, analyzer, clustering, pipeline stage, API routes, frontend components, DB persistence, tests, and 12 cross-cutting integrations.

---

## 1. The Gap Lifecycle — End to End

A "gap" in Elephant Rock is an identified underexplored research area that emerges from analyzing academic literature. Gaps are the central artifact connecting the **literature intake** stages to the **idea generation** stage. The full lifecycle is:

```
Papers Ingested → Clustering → LLM Gap Detection → Truth Revision →
  → Faithfulness Check → Knowledge Graph Write → Goal Creation →
  → Memory Storage → Cross-Stage Context Save → DB Persistence →
  → API Exposure → Frontend Display → Gap→Idea Traceability →
  → Self-Improvement Feedback
```

---

## 2. Core Data Model

### 2.1 Pipeline Model (`backend/pipeline/gap_analysis/models.py`)

```python
class ResearchGap(BaseModel):
    title: str                        # Human-readable gap title
    description: str                  # Detailed explanation of what's missing
    gap_type: str                     # "methodological" | "empirical" | "theoretical" | "cross-domain"
    related_clusters: list[int]       # Which TF-IDF clusters this gap relates to
    potential_impact: str             # Textual description of impact if addressed
    confidence: float = 0.5           # 0.0-1.0, LLM-assessed confidence this is a genuine gap
    truth: TruthValue                 # OpenNARS truth calculus (frequency + confidence + evidence_count)

class ClusterInfo(BaseModel):
    cluster_id: int
    label: str                        # Auto-generated from top TF-IDF terms (e.g., "transformer / attention / BERT")
    paper_count: int
    top_terms: list[str]              # Top TF-IDF terms in the cluster
    avg_citations: float | None       # Average citation count of papers in cluster

class ClusterReport(BaseModel):
    clusters: list[ClusterInfo]
    total_papers: int
```

### 2.2 Database Model (`backend/db/models.py`)

```python
class ResearchGapDB(Base):
    __tablename__ = "research_gaps"
    id: int PK
    title: Text
    description: Text
    gap_type: String(50)              # methodological, empirical, theoretical, cross-domain
    confidence: Float                 # 0.0-1.0
    potential_impact: Text
    pipeline_run_id: int FK → pipeline_runs.id  # Which run produced this gap
    pipeline_run: relationship        # Back-populates PipelineRun.gaps
    created_at: DateTime
    # Indexes: pipeline_run_id, confidence
```

### 2.3 Frontend Type (`frontend/src/api/types.ts`)

```typescript
interface ResearchGap {
    id: number;
    title: string;
    description: string;
    gap_type: string;
    confidence: number;
    potential_impact: string;
    idea_count: number;               // Count of ideas whose source_gap_ids includes this gap's title
}
```

---

## 3. Gap Analysis Pipeline Stage

### 3.1 Stage Implementation (`backend/pipeline/stages.py:166-260`)

`GapAnalysisStage` is Stage 4 of the 9-stage pipeline. It receives `StageContext` with `all_papers` from the previous stages and produces `result.gaps` and `result.cluster_report`.

**Execution Flow:**

```
1. Recall prior gaps from memory (semantic recall with domain + "research gaps" query)
2. Call GapAnalyzer.analyze(papers, domain, max_gaps, prior_gaps)
3. Store gaps in result.gaps + cluster_report
4. Write gap entities to Knowledge Graph (entity_type=CONCEPT, with truth values)
5. Run faithfulness check (verify gap claims against source papers)
6. Create research goals from gaps via GoalManager
7. Dispatch "gap.found" hook for each gap
8. Return True (continue pipeline)
```

**Subsystem Integration Table:**

| Subsystem | Integration Point | What It Does |
|:---|:---|:---|
| GapAnalyzer | Core analysis engine | Clusters papers → LLM identifies gaps → Truth revision |
| KnowledgeGraph | Entity write | Each gap becomes a CONCEPT entity with truth value |
| FaithfulnessChecker | Claim verification | LLM checks if gap descriptions contradict source papers |
| GoalManager | Goal creation | Each gap becomes a `ResearchGoal` with priority = confidence |
| Hooks | Event dispatch | `gap.found` event per gap (title, confidence, gap_type) |
| Memory | Prior gap recall | Queries semantic memory for previously seen gaps in this domain |
| CrossStageContext | Output save | Saves gap data for consumption by downstream stages |
| Provider Override | Model routing | Supports per-stage model override from TaskRouter |

### 3.2 Gap→Idea Traceability

When the AgentOrchestrator generates ideas from gaps, each idea gets `source_gap_ids = [gap.title for gap in gaps]` (set in `agent_orchestrator.py`). This flows through:

1. `ResearchIdea.source_gap_ids: list[str]` (pipeline model)
2. `Idea.source_gap_ids: Text` (DB model, stored as JSON `["Gap A", "Gap B"]`)
3. `IdeaDetail.source_gap_ids` (API response, parsed from JSON)
4. Frontend displays "Source Research Gaps" section with amber dots

The reverse query — "how many ideas address this gap?" — is done via `crud.count_ideas_for_gap()` which uses a parameterized `LIKE` query on the `source_gap_ids` JSON text column.

---

## 4. GapAnalyzer — The Core Engine

### 4.1 Two-Phase Architecture

```
Phase 1: Clustering (deterministic)
  Papers → Embeddings/TF-IDF → UMAP 2D reduction → HDBSCAN clustering → TF-IDF cluster labeling

Phase 2: Gap Identification (LLM-powered)
  Cluster summary + Paper summaries → LLM structured output → JSON gaps → Truth revision
```

### 4.2 Clustering Pipeline (`cluster_service.py`)

| Step | Algorithm | Fallback |
|:---|:---|:---|
| Embedding extraction | Paper.embedding (if available) | TF-IDF on title+abstract (500 features) |
| Dimensionality reduction | UMAP (2D, cosine metric, 15 neighbors) | First 2 dimensions |
| Clustering | HDBSCAN (min_cluster_size=3, euclidean) | KMeans (n = max(2, papers/3), max 10) |
| Cluster labeling | Top TF-IDF terms (100 features, English stopwords) | `"Cluster {id}"` |
| Citation stats | Average citation_count per cluster | `None` |

**Minimum threshold**: < 3 papers → clustering skipped entirely, returns empty `ClusterReport`.

### 4.3 Gap Identification Prompt

The LLM receives:
- **Cluster summary**: Formatted list of clusters with labels, paper counts, and average citations
- **Paper summaries**: Top 30 papers with year, title, and first 200 chars of abstract
- **Instruction**: Identify N gaps with title, description, gap_type, related_clusters, potential_impact, confidence

**Structured output schema** enforces JSON array with required fields: title, description, gap_type, potential_impact, confidence.

### 4.4 Truth Revision

When `prior_gaps` are provided (from memory recall):

```
For each new gap:
  1. Compare title similarity (Jaccard word overlap) against all prior gaps
  2. If similarity > 0.8 with any prior gap:
     a. Keep the prior gap's title (stability)
     b. Revise truth: prior.truth.revise(new_observation)
     c. new_observation = TruthValue.from_observation(frequency=new_gap.confidence)
  3. If no match:
     a. Create fresh TruthValue.from_observation(frequency=new_gap.confidence)
```

This means gaps that reappear across multiple pipeline runs accumulate evidence — their truth `confidence` increases (more evidence = higher confidence in the gap's existence), while their truth `frequency` converges toward the LLM's repeated assessment.

### 4.5 Title Similarity

Simple Jaccard similarity on lowercased word sets:

```python
def _title_similarity(a: str, b: str) -> float:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    return len(intersection) / len(union)
```

Threshold for matching: > 0.8 (very high overlap required).

---

## 5. Faithfulness Checking

### 5.1 Purpose

After gaps are identified, the `FaithfulnessChecker` verifies that each gap's description doesn't contradict the source literature. This catches LLM hallucinations where the model might claim "no methods exist for X" when papers clearly describe such methods.

### 5.2 Process

```
For each gap:
  1. Build claim = "{gap.title}: {gap.description[:300]}"
  2. Build source text = top 10 papers (title + first 200 chars of abstract)
  3. Ask LLM: "Is this claim faithful to the sources?" (temperature=0.1 for determinism)
  4. Structured output: {is_faithful: bool, contradiction_type: str, explanation: str}
  5. If unfaithful → log warning with gap title and explanation
```

**Fail-closed**: If the LLM call fails, the check returns `is_faithful=True` (default in `FaithfulnessReport`), avoiding false blocking of valid gaps.

---

## 6. Knowledge Graph Integration

Each identified gap is written to the Knowledge Graph as a `CONCEPT` entity:

```python
gap_entity = KnowledgeEntity(
    id=f"gap:{gap.title[:60]}",
    entity_type=EntityType.CONCEPT,
    name=gap.title,
    properties={
        "gap_type": gap.gap_type,
        "description": gap.description[:200],
        "potential_impact": gap.potential_impact,
    },
    truth=TruthValue(frequency=gap.confidence, confidence=0.6),
)
```

The graph is saved immediately after gap analysis, making gaps available for:
- Graph RAG retrieval (entity-centric search)
- Graph visualization (Knowledge Graph page)
- World model dependency tracking
- Relationship linking (gaps connected to papers, methods, concepts)

---

## 7. Goal Management from Gaps

The `GoalManager.create_from_gaps()` converts each gap into a `ResearchGoal`:

```python
ResearchGoal(
    title=f"Investigate: {gap.title}",
    description=gap.description,
    priority=gap.confidence,       # Gap confidence becomes goal priority
    status=GoalStatus.PROPOSED,
)
```

If a `GoalDependencyTracker` is configured, each goal gets a dependency registered:
```
condition: "gap '{title}' confidence > 0.3"
```

Goals can be:
- **Decomposed** into sub-goals: "Literature search for {title}", "Generate ideas for {title}", "Evaluate feasibility of {title}"
- **Prioritized** by confidence score
- **Conflict-checked** against the knowledge graph
- **Retracted** if severity="high" conflicts are detected

---

## 8. Autonomous Mode Gap Handling

In autonomous mode, the consciousness state machine uses gaps as transition triggers:

```
EXPLORING state:
  Run pipeline with broad search queries
  If result.gaps found → transition("new_high_confidence_gap") → FOCUSED state
  If no gaps found → transition("no_gaps_found") → IDLE state
```

This means the autonomous agent only enters deep research mode (FOCUSED) when it discovers genuine research gaps during broad exploration.

---

## 9. Self-Improvement Gap Parameters

The evolution engine manages `max_gaps` as an evolvable parameter:

| Parameter | Range | Default |
|:---|:---|:---|
| `max_gaps` | 3-10 | 5 |

**Evolution behavior** (from `engine.py`):
- If `gap_analysis` stage average score < 0.4, `max_gaps` is nudged toward the upper bound (+1)
- If the idea generation stage score < 0.4, both `ideas_per_round` and `generation_rounds` increase

This means the system adapts its gap exploration breadth based on how useful previous gaps proved to be.

---

## 10. API Layer

### 10.1 Endpoints

| Method | Path | Parameters | Response |
|:---|:---|:---|:---|
| GET | `/gaps/` | `run_id?`, `limit=20`, `offset=0` | `{gaps: [...], total: N, run_id: ID}` |
| GET | `/gaps/{gap_id}` | — | `{gap: {...}}` |

### 10.2 Default Run Resolution

When `run_id` is omitted, the API automatically resolves to the **latest completed pipeline run**:

```python
latest = session.execute(
    select(PipelineRun)
    .where(PipelineRun.status == "completed")
    .order_by(PipelineRun.id.desc())
    .limit(1)
).scalar_one_or_none()
```

### 10.3 Gap Response Shape

```json
{
    "id": 1,
    "title": "Limited cross-domain evaluation of NLP methods",
    "description": "Most NLP methods are evaluated only on English...",
    "gap_type": "methodological",
    "confidence": 0.85,
    "potential_impact": "High — would enable multilingual AI systems",
    "idea_count": 3,
    "pipeline_run_id": 1,
    "created_at": "2026-05-02T14:30:00"
}
```

The `idea_count` field is computed at query time by calling `count_ideas_for_gap()` for each gap.

---

## 11. Frontend Layer

### 11.1 Gaps Explorer Page (`/gaps`)

- Fetches gaps from `/gaps/` API
- Displays as sorted list (confidence descending)
- Each gap rendered as `GapCard` component
- Pagination: 20 per page
- Empty state: "No research gaps found. Run a pipeline to discover gaps."
- Click-through: idea_count badge → navigates to `/ideas?search={gap.title}`

### 11.2 GapCard Component

| Element | Rendering |
|:---|:---|
| Title | `text-sm font-medium` |
| Description | `text-xs text-muted-foreground line-clamp-2` |
| Gap Type Badge | `Badge variant="outline"` (e.g., "methodological") |
| Potential Impact | `text-xs text-muted-foreground` |
| Idea Count | Amber pill button: "3 ideas" → click navigates to ideas filtered by gap title |
| Confidence % | Text + progress bar, color-coded (green ≥0.8, emerald ≥0.6, amber ≥0.3, red <0.3) |

### 11.3 Gap Traceability in Idea Detail

When viewing an idea, the "Source Research Gaps" section shows:
- Bulleted list of gap titles with amber dots
- Each gap title is the string from `source_gap_ids` JSON

---

## 12. Persistence Layer

### 12.1 Write Path

After the `gap_analysis` stage completes, the orchestrator calls:
```python
self._persistence.persist_gaps(result, db_run_id)
```

Which creates a `ResearchGapDB` row per gap with all fields linked to the pipeline run.

### 12.2 Read Path

For pipeline resume/reconstruction:
```python
self._persistence.load_gaps(db_run_id)
```

Reconstructs `ResearchGap` objects from DB rows (loses `truth` and `related_clusters` in the reconstruction — a known gap).

---

## 13. Cross-Stage Context

After gap analysis completes, the orchestrator saves:
```python
[{"title": g.title, "description": g.description, "confidence": g.confidence, "gap_type": g.gap_type}]
```

This is consumed by downstream stages (idea generation, feasibility scoring, proposal synthesis) via `cross_stage_ctx.load_prior_context()`.

---

## 14. Test Coverage

### 14.1 Backend Tests

| Test File | Coverage |
|:---|:---|
| `test_pipeline/test_gap_analysis.py` | Title similarity, cluster formatting, paper summary formatting, happy path, prior gap truth revision, LLM failure fallback, confidence sorting |
| `test_pipeline/test_traceability.py` | source_gap_ids propagation from gaps to ideas, default empty, critique/refinement history |
| `test_db/test_batch14_task01.py` | Search filters, sort by score/min_score, count_ideas_for_gap, SQL injection safety, source_gap_ids persistence, null score handling |
| `test_memory/test_gap_closures.py` | Prior gap recall from memory, quality gate fail-closed, auto-promotion, deletion, decay trigger |

### 14.2 Frontend Tests

| Test File | Coverage |
|:---|:---|
| `pages/__tests__/gaps-explorer.test.tsx` | Renders gap list, shows empty state |
| `components/gaps/__tests__/gap-card.test.tsx` | Renders title/description/type, confidence %, confidence bar width |

---

## 15. Gap Types Taxonomy

The system recognizes four gap types (determined by the LLM):

| Type | Description | Example |
|:---|:---|:---|
| **methodological** | Missing or inadequate research methods | "Limited cross-domain evaluation of NLP methods" |
| **empirical** | Lack of experimental evidence or data | "No benchmarks exist for low-resource language pairs" |
| **theoretical** | Gaps in theoretical understanding | "No formal framework connects attention mechanisms to information theory" |
| **cross-domain** | Opportunities at domain boundaries | "Computer vision techniques not applied to genomic sequence analysis" |

---

## 16. Identified Gaps in the Gap System Itself

### 16.1 Data Loss in Persistence

| Issue | Detail |
|:---|:---|
| **Truth not persisted** | `ResearchGap.truth` (TruthValue) is lost when converting to/from `ResearchGapDB`. The DB model has no `truth` columns. |
| **Related clusters lost** | `ResearchGap.related_clusters` is not stored in the DB model. |
| **Cluster report ephemeral** | `ClusterReport` is not persisted — lost after the pipeline run. |

### 16.2 Query Limitations

| Issue | Detail |
|:---|:---|
| **Gap search is title-only** | `count_ideas_for_gap()` uses `LIKE` on the JSON text column — fragile if gap titles have special characters or vary slightly |
| **No gap search/filter in API** | The `/gaps/` endpoint has no search, type filter, or confidence range filter |
| **No cross-run gap dedup** | Each run creates fresh gap rows — no deduplication against gaps from prior runs |
| **No gap detail edit** | Gaps are immutable once created — no way to correct or enrich gap descriptions |

### 16.3 Frontend Limitations

| Issue | Detail |
|:---|:---|
| **No gap search** | The Gaps Explorer has no search input (unlike Ideas Browser) |
| **No gap type filter** | No dropdown to filter by methodological/empirical/theoretical/cross-domain |
| **No confidence range filter** | No slider to filter by confidence score |
| **No gap detail page** | No `/gaps/:id` route — clicking a gap card does nothing |
| **No gap-to-paper navigation** | Can't see which papers contributed to a gap's identification |
| **No clustering visualization** | The ClusterReport is never exposed to the frontend |

### 16.4 Pipeline Integration Gaps

| Issue | Detail |
|:---|:---|
| **No gap feedback mechanism** | Users can rate ideas (1-5 stars) but can't rate gaps (is this gap real? useful?) |
| **No gap merging** | If multiple runs produce similar gaps, there's no deduplication or merging |
| **No gap lifecycle tracking** | A gap can't transition from "identified" → "being investigated" → "addressed" |
| **No gap-to-proposal direct link** | Gaps link to ideas, but not to the proposals that might address them |
| **No cluster evolution tracking** | No way to see how clusters change across runs as new papers are added |

### 16.5 Missing Feature Opportunities

| Opportunity | Description |
|:---|:---|
| **Gap Dashboard** | Aggregated view: gap type distribution, confidence histogram, trends over runs |
| **Gap Comparison** | Side-by-side comparison of gaps across runs to see how the landscape evolves |
| **Gap Export** | Export gaps as structured data (CSV, JSON, BibTeX) |
| **Gap Prioritization UI** | Drag-and-drop ranking, mark as "investigating", assign to team members |
| **Cluster Visualization** | Interactive scatter plot of the UMAP-reduced paper clusters with gap labels |
| **Gap Similarity Search** | Find similar gaps across runs using embedding similarity |
| **Gap Notifications** | Alert when a new gap is detected with high confidence |
| **Gap Closure Tracking** | When ideas score high on a gap, track progress toward "closing" the gap |

---

## 17. Gap System Metrics

| Metric | Value |
|:---|:---|
| Core pipeline files | 3 (models.py, gap_analyzer.py, cluster_service.py) |
| Pipeline stage integration | 1 stage, 8 subsystem connections |
| DB columns | 7 (title, description, gap_type, confidence, potential_impact, pipeline_run_id, created_at) |
| DB indexes | 2 (pipeline_run_id, confidence) |
| API endpoints | 2 (list, get) |
| Frontend pages | 1 (Gaps Explorer) |
| Frontend components | 1 (GapCard) |
| Frontend tests | 5 test cases |
| Backend tests | ~25 test cases across 4 test files |
| Gap types | 4 (methodological, empirical, theoretical, cross-domain) |
| Clustering algorithms | 3 (UMAP + HDBSCAN + KMeans fallback) |
| Cross-cutting integrations | 12 (KG, goals, memory, faithfulness, hooks, SSE, self-improve, etc.) |
| Evolvable parameters | 1 (max_gaps: 3-10) |
| Truth maintenance | OpenNARS evidential revision with Jaccard title matching |

---

## 18. Recommendations

### 18.1 High Priority

1. **Persist Truth Values**: Add `truth_frequency`, `truth_confidence`, `truth_evidence_count` columns to `ResearchGapDB` to prevent data loss
2. **Persist Cluster Reports**: Add a `cluster_report_json` column to `PipelineRun` for cross-run cluster comparison
3. **Add Gap Search/Filter to API**: Support `search`, `gap_type`, `min_confidence` query parameters
4. **Add Gap Search to Frontend**: Mirror the Ideas Browser search/filter/sort pattern
5. **Create Gap Detail Page**: `/gaps/:id` route showing full description, related papers, linked ideas, cluster membership

### 18.2 Medium Priority

6. **Gap Feedback**: Add a 1-5 rating + notes to gaps (like idea feedback)
7. **Gap Deduplication**: Jaccard similarity check before persisting — merge with existing gap if similarity > 0.8
8. **Gap Lifecycle States**: Add `status` column: `identified → investigating → addressed`
9. **Cluster Visualization**: Add UMAP scatter plot to the frontend (showing papers as dots, gaps as labels)
10. **Gap Type Distribution Chart**: Add to dashboard showing methodological vs empirical vs theoretical vs cross-domain

### 18.3 Low Priority

11. **Gap Export**: CSV/JSON export of gaps
12. **Gap Comparison View**: Side-by-side across runs
13. **Gap Notifications**: Alert on high-confidence new gaps
14. **Gap Closure Tracking**: Progress metric based on idea scores linked to the gap
15. **Related Clusters Column**: Add `related_clusters` JSON column to DB

---

*Study complete. 100+ files examined. Gap lifecycle traced from paper ingestion through clustering, LLM identification, truth revision, faithfulness checking, knowledge graph integration, goal creation, memory storage, persistence, API exposure, frontend display, and self-improvement feedback.*
