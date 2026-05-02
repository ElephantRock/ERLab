# Elephant Rock — Deep Subsystem Analysis

**Companion to:** `comprehensive_study_report_v2.md`  
**Date:** 2026-05-02  
**Scope:** Every pipeline subsystem, agent architecture, and advanced feature — read from source code.

---

## 1. Multi-Agent Idea Generation (`backend/pipeline/generation/`)

The core innovation of Elephant Rock is its multi-agent ideation loop — a structured debate between three specialized agents that produces higher-quality research ideas than single-prompt generation.

### 1.1 AgentOrchestrator

The `AgentOrchestrator` coordinates a multi-round Ideator → Critic → Refiner loop with sophisticated control flow:

**Initialization:**
- Three agents: `IdeatorAgent`, `CriticAgent`, `RefinerAgent`
- `ImpasseDetector` for stuck-state detection
- `StrategyTracker` for data-driven strategy selection
- `WorkingContext` for inter-round context compression
- Temperature overrides from evolved parameters

**Loop Structure (per round):**
1. **Strategy Selection**: Rule-based for first 5 rounds, then data-driven from StrategyTracker
2. **Impasse Resolution**: Apply pending resolution from previous round (constraint injection, strategy switch, perspective change)
3. **Ideator**: Generate N raw ideas from gaps + literature context
4. **Critic**: Evaluate ideas with strategy-aware critique
5. **Loop Detection**: If critiques repeat, force META_REFLECTION strategy
6. **Refiner**: Strengthen ideas based on critiques
7. **Convergence Check**: Either Borda tournament or standard convergence
8. **Plateau Check**: Detect score stagnation
9. **Impasse Detection**: Identify stuck states and queue resolutions
10. **Context Compression**: Compress inter-round context to fit token limits

**Termination Conditions:**
- All rounds complete
- Convergence detected (ideas stop improving)
- Plateau detected (critiques show no actionable improvements)
- Borda convergence (incumbent wins 2+ consecutive tournaments)

### 1.2 IdeatorAgent

- Uses Jinja2 template (`prompts/ideator_system.md`) for structured prompting
- RAG augmentation: when a `TwoStageRetriever` is available, retrieves additional papers per gap from vector store
- Builds context from gaps (title, description, potential_impact) and top-20 papers
- Generates ideas via `structured_output` with a JSON schema enforcing title, problem_statement, proposed_method
- Accepts prior_critique text to avoid repeating previous mistakes
- Temperature: 0.8 (creative but structured)

### 1.3 CriticAgent

- Evaluates ideas using configurable strategies (see below)
- Produces structured Critique with: strengths, weaknesses, prior_art_concerns, feasibility_concerns, suggestions
- Each critique includes an overall_assessment summary

### 1.4 RefinerAgent

- Takes raw ideas + critiques and produces strengthened versions
- Includes round_num context to adapt refinement depth
- Produces ResearchIdea objects with scores, domain, and source_gap_ids

### 1.5 Critic Strategies

The system uses metacognitive strategy selection for the Critic agent:
- **Rule-based** (first 5 rounds): Selected based on round number and convergence state
- **Data-driven** (5+ rounds): `StrategyTracker` recommends based on accumulated `StrategyOutcome` records (strategy, round_num, idea_count, avg_score)

### 1.6 Convergence Detection

Two convergence modes:

**Standard Convergence:**
- Compares refined ideas against previous round's ideas
- Checks if ideas are semantically similar (converging on solution)
- Detects when further rounds would yield diminishing returns

**Borda Tournament Convergence** (autoreason pattern from ICLR 2026):
- Three versions compete: incumbent (A), adversarial revision (B), synthesis (AB)
- Fresh judge agents rank them blindly with randomized labels (eliminates positional bias)
- Borda count aggregation determines winner
- Convergence when incumbent wins k=2 consecutive rounds
- "Do nothing" is always a first-class option — prevents scope creep

### 1.7 Impasse Detection & Resolution (Soar + OpenHands Pattern)

Four impasse types detected:

| Impasse | Detection Method | Resolution |
|:---|:---|:---|
| DUPLICATE_IDEAS | Jaccard similarity > 0.8 on title words | Inject random constraint (e.g., "must use contrastive learning") |
| IDENTICAL_CRITIQUES | Weakness set overlap > 70% | Switch to META_REFLECTION strategy |
| SCORE_PLATEAU | Score std_dev < 0.02 over 3 rounds | Increase temperature by 0.1 |
| LOW_DIVERSITY | Average pairwise title similarity > 0.5 | Change perspective (e.g., "cognitive science angle") |

Resolutions are queued and applied in the next round, creating a feedback loop that breaks the agent out of repetitive patterns.

---

## 2. Knowledge Systems

### 2.1 Knowledge Graph (`backend/pipeline/knowledge/graph.py`)

An entity-centric knowledge graph with Hebbian-like edge consolidation:

**Entities:**
- Typed: papers, authors, methods, datasets, concepts
- Carry `TruthValue` (frequency, confidence, evidence_count)
- Content-hash deduplication — same content gets truth revision instead of duplication
- Entity resolution for canonical ID mapping

**Relationships:**
- Typed: cites, uses_method, extends, contradicts, etc.
- Bidirectional adjacency index for O(1) neighbor lookup
- Incoming set index for fast reverse traversal

**Advanced Features:**
- Versioning: Optional `ChangeBuffer` + `VersionLog` for tracking entity evolution
- Activation spreading: Relevance propagation via `ActivationPipeline`
- Reactive streams: `StreamRegistry` for real-time graph update subscriptions
- Graph embeddings: `GraphEmbeddingIndex` for similarity-based entity search
- Graph walks: BFS traversal with configurable max_hops for subgraph extraction
- Community detection: Identifies clusters of related entities

### 2.2 TruthValue System (`backend/pipeline/knowledge/truth.py`)

OpenNARS-inspired epistemic truth maintenance:

```
TruthValue = { frequency, confidence, evidence_count, propagation_debt }
```

- **frequency**: P(proposition is true | evidence) — how well-supported the assertion is
- **confidence**: P(evidence is sufficient) — how much evidence we have
- **expectation**: `frequency * confidence` — combined quality metric
- **revision**: Weighted average of frequency values when new evidence arrives (not overwrite!)
- **decay**: Temporal confidence decay at configurable rate
- **propagation_debt**: Tracks how much truth changed, flagging downstream consumers as stale

This means the knowledge graph doesn't just store facts — it stores beliefs with uncertainty quantification, and updates them principledly as new evidence arrives.

### 2.3 Graph RAG Retriever (`backend/pipeline/knowledge/graph_rag_retriever.py`)

Three-source retrieval fusion:

1. **BM25** (lexical matching from TwoStageRetriever)
2. **Semantic** (embedding-based similarity from TwoStageRetriever)
3. **Graph** (entity-centric graph walks from KnowledgeGraph)

Sources are fused via **weighted Reciprocal Rank Fusion (RRF)**:
- Base results get weight 1.0
- Graph results get configurable weight (default 0.3)
- Score = sum(weight_i / (k + rank_i)) across sources

The graph retrieval path:
1. Query → entity extraction → entity embedding similarity search
2. Entity IDs → BFS graph walks (max 2 hops)
3. Walk entities → paper relationships → document retrieval
4. Results merged with base retrieval via RRF

---

## 3. Self-Improvement Engine (`backend/pipeline/self_improve/`)

10 files implementing a complete self-improvement system:

| File | Purpose |
|:---|:---|
| `engine.py` | EvolutionEngine — wraps PipelineEvolver with per-stage outcome tracking |
| `evolution.py` | PipelineEvolver — parameter mutation with PARAM_RANGES constraints |
| `ab_test.py` | A/B testing framework for parameter variants |
| `fitness.py` | Fitness scoring from novelty + feasibility + user ratings |
| `constraints.py` | Parameter boundary constraints |
| `feedback_history.py` | User feedback aggregation |
| `frontier.py` | Frontier-based exploration of parameter space |
| `lessons.py` | Learned lessons extraction from outcomes |
| `ratchet.py` | Quality ratchet — never degrade below historical best |

**EvolutionEngine Features:**
- Per-stage outcome recording with metadata (stage, score, params, issues)
- Time-decayed digests: exponential decay weighting recent outcomes more heavily
- Prompt overlay generation: LLM synthesizes improvement suggestions from accumulated data
- History-aware parameter proposal: biases toward addressing low-scoring stages
- Automatic nudge: if idea_generation avg score < 0.4, increases ideas_per_round and generation_rounds

---

## 4. Autonomous Research (`backend/pipeline/autonomy/`)

### 4.1 Consciousness State Machine

PUMA-inspired 5-state machine:

```
IDLE ──idle_timeout──> EXPLORING ──new_high_confidence_gap──> FOCUSED
  ↑                       │                                    │
  │                       │ (no_gaps_found)                    │
  │                       ↓                                    ↓
  └──consolidation_complete── DREAMING <──analysis_complete── CONTEMPLATING
```

| State | Action | Description |
|:---|:---|:---|
| IDLE | Wait | No active work, waiting for triggers |
| EXPLORING | Broad search | Literature search across domains |
| FOCUSED | Run pipeline | Full pipeline on identified gaps |
| CONTEMPLATING | Analyze results | Extract insights from pipeline output |
| DREAMING | Consolidate | Memory consolidation + world model update |

Each state records time in state and full transition history.

### 4.2 Curiosity Driver

PUMA's CuriosityDrive with boredom mechanism:
- Tracks explored topics
- When idle too long, suggests underexplored adjacent domains
- Generates diverse search queries for suggested topics
- Uses LLM to synthesize exploration suggestions from topic history

### 4.3 Goal & Dependency Management

- Goal tracking with dependency graphs
- Budget management per autonomous cycle
- Hook system for lifecycle events (cycle start/complete)

---

## 5. Sandbox System (`backend/pipeline/sandboxing/`)

Three backend implementations for isolated code execution:

| Backend | Isolation | Use Case |
|:---|:---|:---|
| `DockerBackend` | Full container isolation | Production |
| `SubprocessBackend` | Process-level isolation | Development |
| `NoopBackend` | No isolation | Testing |

**Configuration:**
- `SandboxConfig`: timeout (30s), max output (100KB), memory limit (256MB), network (disabled), environment vars, allowed commands
- `SandboxSession`: Persistent session for multi-execution reuse with context manager pattern

**Protocol-based design** — no inheritance required, just duck-typing with `SandboxBackend` Protocol.

---

## 6. Negotiation System (`backend/pipeline/negotiation/`)

Multi-agent negotiation framework:

**NegotiationAgent** capabilities:
- **Propose**: Generate a proposal on a topic (with prior proposal context)
- **Critique**: Evaluate a proposal with severity rating (high/medium/low)
- **Rebut**: Defend or revise a proposal against critique
- **Vote**: Score proposals 0.0-1.0 with reasoning
- **Synthesize**: Merge the best elements of competing proposals

**NegotiationSession** manages multi-round negotiation:
- Tracks proposals, critiques, and votes across rounds
- Consensus detection via `consensus.py`
- Configurable convergence criteria

---

## 7. Metacognitive Monitoring (`backend/pipeline/metacognition/`)

Self-monitoring system inspired by python_actr, Soar, and det-acp:

**Signal Types:**
| Signal | Trigger | Severity |
|:---|:---|:---|
| QUALITY_DROP | Score delta > threshold (0.3) | proportional to delta |
| STAGNATION | No improvement for N rounds (3) | 0.5 |
| ANOMALY | Score > 2 std deviations from mean | computed |
| BUDGET_EXCEEDED | Cost over budget | computed |
| CONVERGENCE_STALL | No convergence in N rounds (5) | 0.7 |

**Configurable thresholds** via `MonitoringThresholds` — all tunable without code changes.

---

## 8. Tool System (`backend/pipeline/tools/`)

OpenAI Agents-inspired tool registry:

```python
@tool(description="Search arXiv for papers")
async def literature_search(query: str, max_results: int = 10) -> list[dict]:
    ...
```

**Features:**
- `@tool` decorator for declarative registration
- Auto-schema extraction from function signatures
- OpenAI function-calling schema generation
- Guardrail integration (tool-level safety checks)
- Timeout enforcement with asyncio.wait_for
- Trust levels: "trusted" vs "untrusted" (different execution policies)
- Output size limits for untrusted tools
- Audit logging via ToolAuditLog
- MCP (Model Context Protocol) integration for external tool servers
- Tool matching and scoring for agent tool selection

**MCP Integration** (`backend/pipeline/tools/mcp/`):
- Client/transport for MCP server communication
- Server registry for tool discovery
- Adapter pattern bridging MCP tools to internal ToolRegistry
- Manager for MCP server lifecycle

---

## 9. Streaming & Observability

### 9.1 StreamManager (`backend/pipeline/streaming/`)

Real-time event streaming for frontend progress updates:

**Event Types:**
- `STAGE_START` / `STAGE_COMPLETE` — pipeline stage lifecycle
- `IDEA_GENERATED` / `IDEA_SCORED` — idea events
- `TOOL_CALL` — tool execution events
- `LLM_CHUNK` — streaming LLM output
- `ERROR` / `PROGRESS` / `HEARTBEAT` / `DONE`

**Features:**
- Per-run asyncio.Queue for SSE delivery
- Deduplication window (1s default) to suppress rapid duplicate events
- Broadcast mode for run_id-less events
- Cancel stream with DONE event
- SSE formatter: `data: {json}\n\n`

### 9.2 Observability Manager (`backend/pipeline/observability/`)

- Hierarchical traces with span nesting (PIPELINE → STAGE → OPERATION)
- In-memory metrics with optional OTLP export
- Per-span attributes and status tracking

---

## 10. Evaluation System (`backend/pipeline/evaluation/`)

11 files implementing comprehensive evaluation:

| File | Purpose |
|:---|:---|
| `scorer.py` | Multi-dimensional scoring (novelty, feasibility, impact, soundness) |
| `quality_gate.py` | Configurable thresholds with composite scoring |
| `geval.py` | GEval framework implementation |
| `pipeline_evaluator.py` | End-to-end pipeline evaluation |
| `adversarial_debate.py` | Adversarial debate evaluation |
| `ensemble_review.py` | Multi-reviewer ensemble scoring |
| `deepeval_adapter.py` | DeepEval framework adapter |
| `normalizers.py` | Score normalization across dimensions |
| `cost.py` | Cost-aware evaluation |
| `cache.py` | Evaluation result caching |

**Quality Gate Configuration:**
```
Default thresholds:
  Novelty:    >= 0.3 (weight 0.3)
  Feasibility: >= 0.4 (weight 0.3)
  Impact:     >= 0.3 (weight 0.2)
  Soundness:  >= 0.5 (weight 0.2, REQUIRED)
  Composite:  >= 0.4
  Mode:       "any" (composite + no required failures)
```

Recommendations: "proceed" / "retry_with_feedback" / "discard"

---

## 11. Compaction System (`backend/pipeline/compaction/`)

Context window management across 9 files:

| File | Purpose |
|:---|:---|
| `agent_context.py` | WorkingContext compression between agent rounds |
| `budget_manager.py` | Token budget allocation across stages |
| `window_manager.py` | Sliding window for conversation history |
| `summarizer.py` | LLM-based context summarization |
| `paper_selector.py` | Select most relevant papers within token budget |
| `model_profiles.py` | Token limits per model (GPT-4: 128K, Claude: 200K, etc.) |
| `middleware.py` | Middleware for automatic context trimming |
| `offload.py` | Context offloading to external storage |
| `prompts.py` | Compaction-specific prompt templates |

---

## 12. Persistence & Execution

### 12.1 PipelinePersistence (`backend/pipeline/persistence.py`)

Handles all database writes during pipeline execution:
- Creates run records with status tracking
- Persists papers (with source_id dedup), gaps, ideas
- Updates pipeline run status and stage progress
- Checkpoint save/load for durable execution
- Cost recording per run
- Warning collection for non-fatal errors

### 12.2 RunCheckpoint & Heartbeat

- `RunCheckpoint`: Tracks per-stage state (pending/running/completed/failed)
- `StageHeartbeat`: Background asyncio.Task sending periodic heartbeats (default 30s)
- External watchdogs can detect hung stages via stale heartbeat timestamps
- Checkpoint enables resume-after-crash at the stage level

---

## 13. Reasoning & Skills

### 13.1 Scratch Space (`backend/pipeline/reasoning/scratch_space.py`)

A working memory for chain-of-thought reasoning — agents can store intermediate results and retrieve them in subsequent steps.

### 13.2 Skills System (`backend/pipeline/skills/`)

Dynamic skill registration and proposal:
- `SkillRegistry`: Register named skills with descriptions
- `ProposerGenerator`: Generate skill proposals based on task requirements
- Skill models for structured skill definitions

---

## 14. Frontend Advanced Features

### 14.1 Dashboard Analytics

Lazy-loaded chart components:
- `ScoreDistributionChart`: Histogram of idea scores
- `DomainBreakdownChart`: Ideas grouped by research domain
- `RunStatusChart`: Pipeline run status distribution

### 14.2 Autonomous Page

Full autonomous cycle management UI:
- Start form with domain + max_runs configuration
- Consciousness state badge visualization
- Scheduler controls (start/stop with status)
- Evolution status display (enabled, overlays generated, recent outcomes)
- Cycle history with progress tracking
- Stop confirmation dialog (HB-01 pattern)

### 14.3 SSE Streaming (Frontend)

`sseFetch()` in `frontend/src/api/client.ts`:
- Uses `fetch()` with `ReadableStream` (not EventSource)
- Authorization via headers (not query params — security improvement)
- Manual SSE parsing: splits on `\n\n`, extracts `data:` lines
- AbortController for cleanup
- Error handling with abort exclusion

---

## 15. Advanced Generation Features

### 15.1 Additional Generation Modules

| File | Purpose |
|:---|:---|
| `agent_handlers.py` | Handler functions for agent event processing |
| `dag_executor.py` | DAG-based execution for dependent generation tasks |
| `buffered_taxonomy.py` | Buffered taxonomy for idea categorization |
| `context_isolator.py` | Isolate context per agent to prevent cross-contamination |
| `error_taxonomy.py` | Classify generation errors for targeted recovery |
| `forest.py` | Tree-of-forests idea exploration |
| `mechanical_checks.py` | Fast deterministic quality checks (no LLM needed) |
| `reasoning_graph.py` | Graph-based reasoning for idea evaluation |
| `topology.py` | Topology analysis for idea space mapping |
| `tot_adapter.py` | Tree-of-Thought adapter for deep reasoning |
| `tool_calling.py` | Tool calling integration for idea generation |
| `verifier.py` | Output verification and validation |

---

## 16. Cross-Cutting Concerns

### 16.1 Hooks System

Lifecycle event dispatching:
- `pipeline.start` / `pipeline.complete`
- `pipeline.stage.complete`
- `impasse.detected` / `impasse.resolved`
- `dispatch_sync_safe`: Non-blocking dispatch that catches errors

### 16.2 Session Management (`backend/pipeline/session/`)

- Group pipeline runs by session_id
- Session-level budget tracking
- Session metadata and tags
- Query across sessions for historical analysis

### 16.3 Memory Consolidation (`backend/pipeline/memory/consolidation.py`)

- Transfer episodic memories to semantic memory
- Extract patterns from repeated experiences
- Build generalized knowledge from specific run outcomes

---

## 17. Architecture Patterns Summary

| Pattern | Implementation | Files |
|:---|:---|:---|
| **Multi-Agent Debate** | Ideator → Critic → Refiner loop | `generation/agent_orchestrator.py` |
| **Borda Tournament** | Blind judge ranking with positional bias elimination | `generation/borda.py` |
| **Impasse-Driven Learning** | Soar-style impasse detection and resolution | `generation/impasse.py` |
| **Truth Maintenance** | OpenNARS evidential truth calculus | `knowledge/truth.py` |
| **Hebbian Consolidation** | Edge strength increases with co-activation | `knowledge/graph.py` |
| **Curiosity-Driven Exploration** | PUMA boredom mechanism | `autonomy/curiosity.py` |
| **Metacognitive Monitoring** | python_actr/Soar self-monitoring | `metacognition/monitor.py` |
| **Quality Ratchet** | Never degrade below historical best | `self_improve/ratchet.py` |
| **Evolutionary Optimization** | Parameter mutation with fitness scoring | `self_improve/evolution.py` |
| **Tool Registry** | OpenAI Agents @tool decorator pattern | `tools/registry.py` |
| **Protocol-Based Design** | Python Protocol for sandbox backends | `sandboxing/protocol.py` |
| **Lazy Loading** | React.lazy for chart components | `pages/dashboard.tsx` |
| **SSE via Fetch** | Header-based auth (not query params) | `api/client.ts` |
| **Durable Execution** | Checkpoint + heartbeat for crash recovery | `execution/` |

---

## 18. Theoretical Foundations

The platform draws from multiple AI research traditions:

| Tradition | Inspiration | Application |
|:---|:---|:---|
| **OpenNARS** | Evidential truth calculus | TruthValue for knowledge graph |
| **Soar** | Impasse-driven learning | ImpasseDetector in agent loop |
| **PUMA** | Consciousness state machine, curiosity drive | Autonomous mode |
| **python_actr** | Self-monitoring | MetacognitiveMonitor |
| **autoreason (ICLR 2026)** | Borda tournament convergence | Idea refinement convergence |
| **OpenHands** | Stuck detection | Impasse resolution strategies |
| **det-acp** | Policy-gated intervention | Governance integration |
| **Tree-of-Thought** | Multi-path reasoning | tot_adapter.py |
| **Graph RAG** | Graph-augmented retrieval | Three-source RRF fusion |
| **Hebbian Learning** | Co-activation strengthens connections | Knowledge graph edge consolidation |

---

*Analysis complete. All 32 pipeline subsystem directories examined from source code.*
*Total subsystem files analyzed: 200+ Python modules across generation, knowledge, autonomy, self-improvement, sandboxing, negotiation, metacognition, tools, evaluation, compaction, session, streaming, observability, and execution.*
