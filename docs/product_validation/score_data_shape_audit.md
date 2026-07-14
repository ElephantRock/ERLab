# Score Data-Shape Audit

> **Purpose:** map every score-related payload to the fields a future
> `<ScoreReport>` (INTERFACE_CONTRACT §6) will need. Validation-independent:
> score inspectability is required by PRODUCT.md §2 regardless of who the
> user is.
>
> **Headline finding:** the constraint is **persistence, not rendering**. The
> backend computes rich score data (confidence, closest prior work, axis
> evidence) but the persistence layer strips most of it before it reaches
> the frontend. A `<ScoreReport>` rollout is gated as much by persisting the
> richness as by building the component.

## 1. The three layers — and where they diverge

| Layer | Novelty | Feasibility | Ensemble review |
|---|---|---|---|
| **Backend computes** | `NoveltyProfile` (rich: 4 axes + per-axis confidence/evidence, `overall_confidence`, `closest_prior_work`, `differentiations`, `search_coverage`, `strategic_direction`) | `FeasibilityReport` (6 axes + weights + reasoning + risks + timeline) | `EnsembleReview` (3 perspectives + risk flags) |
| **Persisted to DB** | 4 axis scores + `novelty_arguments` only | 4 of 6 axes + reasoning + timeline | full (in `proposal_sections.ensemble_review`) |
| **Frontend types** | `Record<string, unknown>` (untyped blob) | `Record<string, unknown>` (untyped blob) | `EnsembleReview` interface (typed) |
| **Rendered** | 4 axis bars + arguments text | 4 of 6 axis bars (2 missing from persistence) | full breakdown |

The novelty report loses the most: confidence, closest prior work, axis
evidence, and the "unverifiable" signal are all computed and all dropped.

## 2. Frontend types — what's actually declared

### `IdeaSummary` (card-level) — `api/types.ts:103-119`
```ts
novelty_score: number | null;        // 0.0–1.0
feasibility_score: number | null;    // 0–10  (NOTE: different scale)
overall_score: number | null;        // 0.0–1.0
quality_summary?: QualitySummary | null;   // { passed, total, has_issues }
governance_status?: "approved"|"denied"|"needs_changes"|null;
reference_count?: number; cited_count?: number; supporting_count?: number;
```

### `IdeaDetail` — `api/types.ts:151-170`
```ts
novelty_report: Record<string, unknown> | null;     // ← untyped blob
feasibility_report: Record<string, unknown> | null;  // ← untyped blob
mechanical_metrics: Record<string, number> | null;
proposal_sections: Record<string, unknown> | null;   // carries ensemble_review
quality_checks: QualityCheckResult[] | null;
remediation_hints: RemediationHint[] | null;
citation_audit: CitationAuditEntry[] | null;
```

### `EnsembleReview` — `api/types.ts:139-149` (the only fully-typed score)
```ts
overall_score: number;
methodology: PerspectiveReview | null;
novelty: PerspectiveReview | null;
clarity: PerspectiveReview | null;
consensus_strengths: string[]; critical_weaknesses: string[];
actionable_suggestions: string[]; summary: string; risk_flags?: string[];
```

### There is NO `NoveltyReport` / `NoveltyProfile` / `FeasibilityReport` TS interface
Those names are backend (Python) classes. Frontend views
(`novelty-report-view.tsx`, `feasibility-report-view.tsx`) define their own
ad-hoc string-key arrays as the de-facto type. This is the first thing a
`<ScoreReport>` rollout must fix.

## 3. ScoreReport-needs × data-availability matrix

✔ = reaches frontend · ⚠ = backend computes but **stripped before persist** · ✗ = absent

| Need | `IdeaSummary` | `novelty_report` | `feasibility_report` | `EnsembleReview` | `mechanical_metrics` |
|---|---|---|---|---|---|
| Summary score | ✔ | ✔ (pipeline) / ✔ (refine) | ✔ (refine only) | ✔ | ✗ (5 sub-metrics, no composite) |
| **Confidence** | ✗ | ⚠ `overall_confidence` dropped | ✗ | ✗ | ✗ |
| Per-axis scores | ✗ | ✔ 4 axes (0–1) | ✔ 4 of 6 (0–10) | ✔ 3 perspectives | ✔ 5 metrics |
| **Axis weights** | ✗ | ✗ (applied server-side, not persisted) | ✗ (server-side) | ✗ | ✗ |
| **Closest prior work** | ✗ | ⚠ `closest_prior_work` dropped | ✗ | ✗ | ✗ |
| Supporting evidence | ✔ `supporting_papers` + `ResolvedReference.match_confidence` | ⚠ `axes[].evidence_found` dropped | ✔ `reasoning` | ✔ strengths/weaknesses | ✗ |
| **Unverifiable signal** | ✗ | ⚠ `overall_confidence=0.2` + blind-spots flag dropped | ✗ | ✗ | ✗ |

**The critical absence:** there is no frontend field that signals "this
score is unverifiable / low-confidence." The backend computes exactly this
(the no-results branch sets confidence 0.2 and arguments "unverifiable"),
but the confidence number is dropped on persist. PRODUCT.md §2 ("a 0.5
unverifiable is shown *as* uncertain") cannot be implemented without a
persistence change.

## 4. Every score render site

| Component / location | What it renders | What it ignores |
|---|---|---|
| `ScoreBadge` (`:9-18`) | `score` + label pill | confidence, axes, weights, evidence |
| `idea-card.tsx:87-105` | overall_score text + novelty/feasibility via ScoreBadge | quality_summary detail, confidence |
| `idea-list-item.tsx:41-45` | overall_score as % | novelty, feasibility entirely |
| `idea-detail.tsx:146-162` | 3 ScoreBadges + QC pill | confidence, axis breakdown (deferred to tabs) |
| `NoveltyReportView` (`:8-13`) | 4 axis ScoreBars + arguments markdown | **confidence, closest prior work, overall, weights** |
| `FeasibilityReportView` (`:9-16`) | 4 of 6 axis bars + timeline/risks/reasoning | overall, weights, 2 missing axes |
| `idea-detail.tsx:398-419` (Metrics tab) | each mechanical metric as `toFixed(3)` | labels beyond key-name, provenance |
| `proposal-review-panel.tsx:128-227` | **full EnsembleReview breakdown** (overall + 3 perspectives + strengths/weaknesses + risks + suggestions) | per-perspective `suggestions` |
| `evidence-panel.tsx:133,208` | `match_confidence` as "% confidence", gap `confidence` as "% conf." | report-level evidence summary |
| `dashboard.tsx:290-294,518-537` | focus-idea "Novelty: NN%"; 3-cell grid | overall/feasibility in focus widget |
| `score-distribution.tsx` | bucketed bar chart (Low/Mod/High/VeryHigh) | per-idea detail |
| `gap-card.tsx:59-64`, `knowledge-graph/*` | gap/entity `confidence` as bar+% | (different domain — knowledge graph) |

**The richest existing score component is `proposal-review-panel.tsx`** —
it's the closest thing to the target `<ScoreReport>` and the natural
template.

## 5. Gap analysis

### A. Backend computes, persistence strips → needs persistence change
| Field | Backend source | Why lost |
|---|---|---|
| `overall_confidence` | `NoveltyProfile` (`novelty/models.py:76`) | `persistence.py` `nov_dict` copies only axes + arguments |
| `axes[].confidence`, `.evidence_found`, `.reasoning` | `AxisAssessment` (`models.py:40-46`) | Not copied |
| `closest_prior_work: List[PriorWorkMatch]` | `NoveltyProfile` (`models.py:78`) | Not copied |
| `differentiations`, `search_coverage`, `blind_spots_identified` | `NoveltyProfile` (`models.py:79-80`) | Not copied |
| `strategic_direction` | `NoveltyProfile` (`models.py:74`) | Not copied |
| `feas_dict` missing `novelty_grounding`, `impact_potential`, `overall_score`, `key_risks` | `FeasibilityReport` (`feasibility_scorer.py:39-68`) | `persistence.py:327-334` copies 4 of 6 axes only |

The refine endpoint (`backend/api/routes/ideas.py:464-465`) is even more
aggressive: stores only `{"overall_score": ...}` for both reports. **Data
shape differs between pipeline-run ideas and refined ideas.**

### B. Reaches frontend, not rendered
- `score_guide` (`IdeaListResponse.score_guide`) — fetched, never displayed.
- `EnsembleReview.risk_flags` — rendered; but `PerspectiveReview.suggestions` per-perspective is not.
- `mechanical_metrics` — raw `toFixed(3)`, no labels/provenance.
- `match_confidence` on references — rendered per-reference but not as a report-level evidence-strength summary.

### C. Absent entirely → needs backend + schema
- **Axis weights.** No `weight` field anywhere. Feasibility weights
  (`data 20% / compute 15% / methods 20% / eval 20% / novelty 10% / impact 15%`)
  live only in the LLM prompt (`feasibility_scorer.py:33`) and in
  `DownstreamDirectives.feasibility_weight_overrides` (per strategic
  direction, not persisted). A `<ScoreReport>` showing weights needs either
  persistence or client-side default-weight constants.
- **Report-level confidence** for feasibility and ensemble review. Only
  novelty has it, and even that is dropped.
- **Cross-idea comparison payload.** No endpoint returns a normalized
  comparison view.

### D. Shape divergence to flag for `<ScoreReport>` design
- **Three axis sets** today: novelty (4, 0–1), feasibility (6, 0–10),
  ensemble (3 perspectives, 0–1). Scales are inconsistent;
  `score-utils.ts:18-32` normalizes feasibility `/10` ad hoc.
- `overall_score` is 0–1 everywhere it exists, but feasibility axes are
  0–10 — a single `<ScoreReport>` must normalize internally.

## 6. Existing comparison affordances (for the Q6 decision)

- **Sorting:** `ideas-browser.tsx:24-29` `SORT_OPTIONS` = date/score/novelty/feasibility.
- **Threshold filter:** min-score slider `0–1 step 0.1` (semantically targets `overall_score`).
- **Distribution chart:** bucketed, not pairwise.
- **No side-by-side.** No component compares two ideas directly.
  `RelatedIdea.overall_score` is fetched for gap-detail but only listed.
- **No normalize/compare endpoint** in `api/ideas.ts`.

## 7. Files to touch for a `<ScoreReport>` rollout

| Layer | File | Change |
|---|---|---|
| Types | `api/types.ts` | Replace the four `Record<string, unknown>` with real interfaces mirroring `backend/pipeline/novelty/models.py` + `feasibility_scorer.py` |
| Persistence | `backend/pipeline/persistence.py:240-342` | Persist `overall_confidence`, per-axis confidence/evidence, `closest_prior_work`, the 2 missing feasibility axes |
| Persistence | `backend/api/routes/ideas.py:459-466` | Stop stripping refined reports to `{overall_score}` only |
| Backend (optional) | `feasibility_scorer.py` / `DownstreamDirectives` | Persist axis weights |
| Rendering | `components/ideas/novelty-report-view.tsx`, `feasibility-report-view.tsx`, `proposal-review-panel.tsx`, `score-badge.tsx`, `lib/score-utils.ts` | Consolidate into `<ScoreReport>` |
| Comparison | `pages/ideas-browser.tsx` + new surface | Add side-by-side (gated on Q6 validation) |

## 8. Implication for Phase 2

`<ScoreReport>` cannot ship its full value in Phase 2 on the current
persistence shape. Two paths:
1. **Phase 2 ships the rendering primitive** consuming whatever richness
   exists today (4 novelty axes, 4 of 6 feasibility axes, full ensemble
   review), with confidence/evidence fields degrading gracefully to
   "unknown" when absent. The persistence gap is closed in a parallel
   backend task.
2. **Phase 2 blocks** on the persistence change.

Path 1 is consistent with PRODUCT.md's "fail-open but annotate" philosophy
and the contract's `confidence?` optional field — render what's there,
mark what's missing honestly. Path 2 is purer but couples frontend Phase 2
to a backend schema migration. Recommend path 1; flag the persistence gap
as a tracked debt item with its own phase.
