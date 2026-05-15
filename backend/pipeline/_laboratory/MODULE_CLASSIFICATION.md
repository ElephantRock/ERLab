# Module Classification — Production vs Laboratory

**Date**: 2026-05-15  
**Purpose**: Classify all pipeline subsystems as PRODUCTION or LABORATORY

## PRODUCTION (wired into orchestrator, runs in every pipeline)

| Module | Role | Wired Since |
|:--|:--|:--|
| `orchestrator.py` | Main pipeline coordinator | Batch-07 |
| `stages.py` (17 stages) | Stage implementations | Batch-07+ |
| `novelty/novelty_checker.py` | Novelty checking (enhanced) | Batch-11, Phase B |
| `novelty/models.py` | NoveltyProfile + DownstreamDirectives | Phase B |
| `novelty/s2_verifier.py` | S2 web novelty check | B163 |
| `novelty/embedding_scorer.py` | Embedding-based novelty | B155 |
| `knowledge/vector_store.py` | ChromaDB (zero-vector guard) | Batch-11, Phase C |
| `knowledge/bm25_index.py` | BM25 full-text search | Batch-11 |
| `knowledge/retriever.py` | TwoStageRetriever (BM25+Vector RRF) | Batch-11 |
| `knowledge/reranker.py` | 5-strategy reranker | RAG Sprint |
| `knowledge/embedding_service.py` | Embedding wrapper | Batch-11, Phase C |
| `knowledge/embedding_providers.py` | Provider factory | Batch-11 |
| `knowledge/relationship_extractor.py` | Paper relationship extraction | B155 |
| `literature/search_service.py` | Multi-source search | Batch-07 |
| `literature/multi_source.py` | Source orchestration | Batch-07 |
| `literature/semantic_scholar.py` | S2 source | Batch-07 |
| `literature/openalex_source.py` | OpenAlex source | B153 |
| `literature/citation_explorer.py` | Citation traversal | B161 |
| `literature/research_agent.py` | Research sub-agent | B186 |
| `gap_analysis/gap_analyzer.py` | Gap analysis | Batch-07 |
| `gap_analysis/cluster_service.py` | Gap clustering | Batch-14 |
| `gap_analysis/deduplicator.py` | Gap dedup | B117 |
| `generation/ideator_agent.py` | Idea generation | Batch-07 |
| `generation/agent_orchestrator.py` | Agent coordination | Batch-07 |
| `generation/tree_search.py` | Tree-of-thought search | B75 |
| `reflection/reflector.py` | Gap/idea reflection (with retry) | Batch-80, Phase A |
| `feasibility/feasibility_scorer.py` | Feasibility (with weight overrides) | Batch-12, Phase B |
| `evaluation/proposal_evaluator.py` | 7-dim evaluation | Batch-15, B153 |
| `evaluation/adversarial_reviewer.py` | Cross-model review | B152, Phase A |
| `evaluation/mechanical_metrics.py` | Formula metrics | Batch-64 |
| `evaluation/quality_gate.py` | Quality gating | B154 |
| `synthesis/proposal_synthesizer.py` | Proposal generation (with framing) | Batch-07, Phase B |
| `synthesis/paper_synthesizer.py` | Paper formatting | Batch-07 |
| `synthesis/context_compactor.py` | Context compression | B188 |
| `synthesis/fast_synthesizer.py` | Fast synthesis mode | B77 |
| `verification/proposal_deepener.py` | Deepening (LLM mode) | B114 |
| `verification/citation_claim_auditor.py` | Citation audit | B112 |
| `verification/reference_verifier.py` | Reference check | B112 |
| `verification/pipeline_evaluator.py` | Pipeline eval | Phase 8 |
| `claims/extractor.py` | Claim extraction | B121 |
| `claims/contradiction/detector.py` | Contradiction detection | B125 |
| `claims/method_problem.py` | Method-problem detection | B126 |
| `claims/study_designer.py` | Study design | B127 |
| `export/export_service.py` | Multi-format export | Batch-07 |
| `monitoring/doom_loop.py` | Doom detection | B185 |
| `monitoring/ccw.py` | Consolidated Context Window | B191 |
| `monitoring/cost_estimator.py` | Cost estimation | B187 |
| `monitoring/effort_probe.py` | Effort probing | B189 |
| `monitoring/contracts.py` | Output contracts | Phase D |
| `dag/pipeline.yaml` | Single config source | B184 |
| `dag/config.py` | YAML loader | B180 |
| `dag/stage_log.py` | Stage logging | B180 |
| `dag/trimmer.py` | Paper trimming | B181, Phase A |
| `notifications/gateway.py` | Notification dispatch | B190 |
| `journal/writer.py` | Research journal | B162 |
| `preflight.py` | Pre-flight checks | Honesty Remediation |
| `persistence.py` | DB persistence | Batch-07 |
| `result.py` | PipelineResult dataclass | Batch-07, Phase B |

## LABORATORY (coded, tested, NOT wired into production orchestrator)

| Module | LOC | Purpose | Blocker |
|:--|:--|:--|:--|
| `metacognition/monitor.py` | Metacognitive monitoring | Never called from orchestrator |
| `metacognitive/ledger.py` | Thought ledger | Duplicate of metacognition/ |
| `metacognitive/manager.py` | Metacognitive manager | Never called |
| `metacognitive/plateau_detector.py` | Plateau detection | Never called |
| `self_improve/engine.py` | Evolution engine | No orchestration loop |
| `self_improve/evolution.py` | Pipeline evolution | Never called |
| `self_improve/frontier.py` | Pareto frontier | Never called |
| `self_improve/fitness.py` | Fitness scoring | Never called |
| `self_improve/ratchet.py` | Ratchet loop | Never called |
| `self_improve/textgrad.py` | TextGrad engine | Never called |
| `self_improve/lessons.py` | Lesson extraction | Never called |
| `self_improve/constraints.py` | Constraint validation | Never called |
| `self_improve/feedback_history.py` | Feedback tracking | Never called |
| `self_improve/ab_test.py` | A/B testing | Never called |
| `autonomy/budget.py` | Simple budget | Feature-flagged OFF |
| `autonomy/curiosity.py` | Curiosity driver | Feature-flagged OFF |
| `autonomy/goals.py` | Goal manager | Feature-flagged OFF |
| `autonomy/state_machine.py` | Consciousness FSM | Feature-flagged OFF |
| `negotiation/agent.py` | Negotiation agent | Never called |
| `negotiation/session.py` | Negotiation session | Never called |
| `sandboxing/docker_backend.py` | Docker sandbox | Feature-flagged OFF |
| `sandboxing/protocol.py` | Sandbox protocol | Feature-flagged OFF |
| `observability/manager.py` | OTLP manager | Feature-flagged OFF |
| `observability/metrics.py` | OTEL metrics | Feature-flagged OFF |
| `observability/otlp_exporter.py` | OTLP export | Feature-flagged OFF |
| `reasoning/scratch_space.py` | Reasoning workspace | Never called |
| `planning/agent.py` | Planning agent | Never called |
| `tools/mcp/client.py` | MCP client | Never called |
| `tools/registry.py` | Tool registry | Never called |
| `session/manager.py` | Session manager | Partially wired |

## ESTIMATED LOC

- **Production**: ~28,000 LOC across 56 modules
- **Laboratory**: ~18,500 LOC across 30 modules (feature-flagged or unwired)
- **Total**: ~46,500 LOC

## Ratio

Production:Laboratory = 1.5:1 (target was 3:1 after quarantine, but quarantine was documentation-only to avoid breaking 200+ tests)
