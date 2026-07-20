# P1 Closeout — Ranking Quality

## 1. Entry state

HEAD: `40709c9`, 4490 passed, 25 skipped, clean tree.

## 2. Ranking-surface audit

Three ranking surfaces identified:
1. **TrimmerStage** — keyword-overlap heuristic + `[:20]` (dominant quality bottleneck)
2. **SearchService** — source-priority deduplication (not relevance)
3. **TwoStageRetriever** — proper hybrid BM25+semantic+RRF (scores transient)

## 3. Current baseline behavior

The legacy `legacy_lexical_top20_v1` policy reproduces the TrimmerStage
keyword-overlap behavior. Evaluated on the frozen benchmark:

```
macro nDCG@10: < 1.0 (lexical traps reduce quality)
macro Precision@5: < 1.0
```

The benchmark includes lexical traps (high term overlap, grade=0) that
the legacy policy ranks poorly.

## 4. Benchmark construction

- 9 discovery cases, 3 retrieval cases
- 3 domains: machine learning, biomedical, NLP
- 0-3 graded relevance judgments
- 3 splits: calibration, development, held_out
- Deterministic fingerprint
- Note: synthetic benchmark — narrower than real user data

## 5. Candidate policies

- `legacy_lexical_top20_v1` — keyword overlap (baseline)
- `hybrid_rrf_v1` — reciprocal-rank fusion of lexical + semantic

## 6. Quality metrics

Metrics framework: nDCG@5, nDCG@10, MRR@10, Precision@5, Recall@20.

The legacy baseline has been evaluated. The hybrid RRF policy is
implemented and ready for evaluation with semantic scores from the
verified embedding runtime.

## 7. Production wiring status

**NOT YET WIRED.** The ranking contracts, policies, and evaluation
framework exist but have not replaced TrimmerStage in production.
Production still uses the keyword-overlap heuristic.

This is a deliberate sequencing decision per the P1 plan: no production
algorithm switch should occur before P1.7 establishes that the candidate
policy meets the frozen acceptance thresholds.

## 8. Known limitations

- Benchmark is synthetic (9 discovery + 3 retrieval cases)
- No inter-annotator agreement (single-annotator synthetic judgments)
- Hybrid RRF policy not yet evaluated with real semantic scores
- Production TrimmerStage not yet replaced
- No durable ranking execution evidence in DB (migration not created)
- Frontend TS baseline (101 errors) remains open

## 9. Infrastructure vs quality status

```
ranking infrastructure       COMPLETE
benchmark framework          COMPLETE
policy evaluation            COMPLETE (legacy baseline measured)
production activation        NOT STARTED
quality improvement proven   NOT YET
```

## 10. P2 entry posture

P2 (query planning) can proceed in parallel with P1 production wiring.
The ranking framework is ready for production integration.
