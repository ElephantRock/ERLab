# Decision Rules — Answers → Consequences

> **Purpose:** make the validation *actionable*. For each of the 6 `[H]`
> questions, this maps every plausible answer to its concrete consequence
> on PRODUCT.md, INTERFACE_CONTRACT.md, and Phases 1–5. With flip
> thresholds, so synthesis produces engineering decisions, not just findings.
>
> **How to use:** after synthesis (`evidence_matrix.md` rollup), find each
> question's verdict and apply the matching rule. The rules are written so
> that an inconclusive verdict has a safe default — Phase 1/2 never blocks
> on "we need more data" for a question that doesn't gate them.

## Verdict vocabulary

- **Confirmed** — evidence agrees with PRODUCT.md v0. Remove the `[H]`.
- **Revised** — evidence disagrees in a specifiable way. PRODUCT.md is
  amended; downstream artifacts follow.
- **Refuted** — evidence clearly contradicts. Major amendment; may block
  the affected phase until resolved.
- **Inconclusive** — evidence mixed or thin. Apply the **safe default**
  (specified per question) and flag for a follow-up round. Do not block
  unless the question is load-bearing for the next phase.

## Flip thresholds

A verdict is **Confirmed/Refuted** when:
- ≥3 of 5 participants agree on the signal *and* at least one is "vivid"
  intensity, **or**
- the disagreeing participants are clearly farther from the target-user
  profile (per `evidence_matrix.md` "closest to primary user?").

Otherwise **Inconclusive**. (Triangulation over vote-counting, per
`interview_protocol.md`.)

A **Revision** is when there's clear signal *for a different answer than
v0*, not just "v0 is wrong." If you can't write the new wording, it's
inconclusive, not revised.

---

## [H-Q1] Primary user — researcher vs. research manager?

**The biggest lever. Affects: which loop step is the CENTER.**

### If Confirmed (individual researcher)
- PRODUCT.md §"Primary User" keeps "researcher doing original work."
- READ stays the center; TRIAGE is secondary.
- ScoreReport: single-artifact, prominent axis breakdown (judgment support).
- IA: READ group (reached via triage), as `INTERFACE_CONTRACT.md §5` spec.

### If Revised (research manager / lab lead triaging for a team)
- PRODUCT.md §"Primary User" becomes "research manager evaluating
  directions for a team."
- **TRIAGE becomes the center**, not READ. The manager scans many,
  delegates deep reads, decides portfolio fit.
- ScoreReport: becomes *comparative* by default — managers rank, they
  don't read. The ScoreReport primitive (CONTRACT §6) must support
  multi-idea comparison as a first-class mode, not a "future" add-on.
- IA: TRIAGE is the landing page; READ is delegated/subordinate.
- **Impact: INTERFACE_CONTRACT §5 (IA) and §6 (ScoreReport) must be
  re-derived. Phase 1 and Phase 2 scope swap.**

### If Inconclusive
- **Safe default: Confirmed (researcher).** PRODUCT.md v0 was written
  from the codebase's own workflow evidence; absent refutation, keep it.
- Flag Q1 for a follow-up round targeting more manager-profile recruits.
- Do **not** block Phase 1 on Q1 if inconclusive — the IA can ship in the
  researcher-centered form and be revised if Q1 flips later (the contract
  is v0; an IA refactor is cheaper than building comparison-first wrongly).

### Load-bearing for which phases?
**Phase 1 (IA), Phase 2 (reading surface + ScoreReport).** This is the
question most worth resolving before those phases commit.

---

## [H-Q2] Desktop vs. mobile

**Affects: reading-surface responsiveness, mobile nav scope.**

### If Confirmed (desktop-primary, mobile = triage/monitoring)
- PRODUCT.md §"Scope" keeps "reading workspace is designed for desktop;
  mobile is triage + monitoring + governance only."
- Reading surface: desktop-optimized; responsive but not mobile-first.
- Mobile nav: the Phase 1 mobile sheet exposes all routes (fixing the
  13-orphan symptom), but the reading surface degrades gracefully rather
  than being redesigned for thumb-use.

### If Revised (tablet/mobile matters for reading)
- PRODUCT.md §"Scope" is amended: reading surface is responsive-first.
- Reading-surface type scale must re-flow at breakpoints; the `text-prose-*`
  tokens (CONTRACT §3) gain mobile variants.
- **Impact: Phase 2 scope grows** (responsive retype, not just desktop).

### If Inconclusive
- **Safe default: Confirmed.** Desktop-primary is the cheaper default and
  matches the artifact (prose reads poorly on phones regardless). The
  reading surface ships desktop-first; responsive hardening becomes a
  Phase 2.5 if Q2 later flips.
- Do not block any phase.

### Load-bearing for which phases?
**Phase 2 (reading surface) only.** Phase 1 (IA + mobile sheet) proceeds
regardless — every route must be reachable on mobile whether or not the
reading surface is mobile-optimized.

---

## [H-Q3] Trust in scores

**Affects: ScoreReport prominence, axis-breakdown default state.**

### If Confirmed (scores as input; verify-then-trust)
- ScoreReport as `INTERFACE_CONTRACT §6` specifies: summary + always-
  reachable breakdown, confidence rendered visibly.
- PRODUCT.md §2 ("trust must be earned visibly") reaffirmed.

### If Revised (scores as noise — researchers read prose first, ignore scores until they've read)
- Scores **shrink**. The pill survives in triage but the reading surface
  de-emphasizes scores: the right-hand rail leads with *provenance and
  citations*, not score breakdowns. Axis breakdown moves to an opt-in
  drawer, not default-visible.
- PRODUCT.md §2 wording shifts: "scores inform judgment" → "evidence
  informs judgment; scores are a secondary index."
- **Impact: Phase 2 reading-surface layout changes; ScoreReport stays but
  is demoted in the rail order.**

### If Revised (scores as authority — rare but high-responsibility)
- The honesty commitment becomes *more* load-bearing, not less. Uncertainty
  must be unmissable. ScoreReport renders confidence as the *dominant*
  visual property, not a sublabel.
- PRODUCT.md anti-fabrication emphasis strengthens.

### If Inconclusive
- **Safe default: Confirmed (scores-as-input).** It's the balanced design
  and matches `SOUL.md`'s honesty framing.
- Ship ScoreReport as specified; the opt-in drawer (Revised path) is a
  trivial Phase 2.5 adjustment if Q3 flips.

### Load-bearing for which phases?
**Phase 2 (reading surface, ScoreReport).** Not Phase 1.

---

## [H-Q4] Run length / strategy preference

**Affects: default strategy, monitoring prominence, "resume watching."**

### If Confirmed (deep-run tolerant)
- Default strategy stays `deep_research`; monitoring stays secondary
  (PRODUCT.md §"Core Loop": "monitoring must not demand attention").
- The contextual hero's "resume watching" is a real action.

### If Revised (many-fast preferred)
- Default strategy flips to `fast_scan`. The 16-stage `deep_research`
  becomes the opt-in, not the default.
- **Monitoring becomes more prominent** — users iterating every 2–3 min
  *watch* the progress, they don't context-switch away.
- PRODUCT.md §"Core Loop" step 2 (MONITOR) rewrites from "must not demand
  attention" to "must support tight feedback loops."
- **Impact: Phase 4 (direct + monitor) scope changes; the run-detail view
  becomes a primary surface, not a secondary one.**

### If Inconclusive
- **Safe default: Confirmed.** "Rigor takes time" is the brand promise
  (SOUL.md); defaulting to fast_scan undercuts it.
- Phase 4 ships monitoring-as-secondary; if Q4 flips, monitoring
  prominence is a Phase 4.5 bump.

### Load-bearing for which phases?
**Phase 4 (direct + monitor).** Not Phase 1 or 2.

---

## [H-Q5] Governance frequency

**Affects: whether GOVERN is a primary nav group.**

### If Confirmed (daily/gate-like)
- GOVERN stays a primary nav group (CONTRACT §5 IA spec).
- Approval UI stays simple (approve/deny + amendment), per current design.

### If Revised (rare/milestone audit)
- **GOVERN drops out of primary nav** → into the SECONDARY group.
- The Core Loop's step 7 (GOVERN) is no longer a daily act; it becomes a
  milestone act reached via the artifact, not via nav.
- **Impact: INTERFACE_CONTRACT §5 IA is amended.** Phase 1 scope shrinks
  (one fewer primary nav group to design); the freed real estate goes to
  READ or REFINE.

### If Revised (collaborative — multi-approver)
- Approval UI complexity grows: assignment, delegation, multi-party state.
- Governance becomes a more substantial Phase 1 surface, not a smaller one.

### If Inconclusive
- **Safe default: Confirmed (daily).** It's the higher-information default;
  demoting GOVERN based on inconclusive evidence risks hiding a primary
  workflow. If Q5 flips to "rare," demotion is a trivial Phase 1.5 change.

### Load-bearing for which phases?
**Phase 1 (IA).** This is the question that most directly shapes the nav.

---

## [H-Q6] Compare side-by-side vs. one-at-a-time

**The highest-impact question. May add a whole new primary surface.**

### If Confirmed (one-at-a-time / serial)
- PRODUCT.md v0 holds. ScoreReport stays single-artifact.
- No comparison surface is built. This is the cheapest outcome.

### If Revised (side-by-side comparison is a real, frequent pattern)
- **A new primary surface enters the contract: `<CompareView>`.** Triage
  gets a compare mode (select 2–3 ideas, see them side by side); the
  reading surface gets a "compare with" action.
- ScoreReport must support the multi-idea case natively (already
  anticipated in CONTRACT §6: "comparison-ready"), but it moves from
  "designed-for" to "must-ship."
- PRODUCT.md §"Core Loop" gains a COMPARE step between TRIAGE and READ.
- **Impact: Phase 1 (IA adds compare entry) and Phase 3 (triage gains
  compare mode) scope grows. A new primitive is added to the contract.**

### If Revised (mental compare only — they compare in their head, not in-tool)
- Low-fidelity compare support suffices: a "pin" action + a lightweight
  compare page showing pinned items' scores side by side. Not a full
  split-pane reading surface.
- Smaller scope than the side-by-side case, but still new work.

### If Inconclusive
- **Safe default: Confirmed (serial).** Building comparison-first on
  inconclusive evidence risks over-building. The "pin + compare" low-
  fidelity path is a cheap Phase 3.5 addition if Q6 later flips.
- This is the one question where the safe default is *most* tempting to
  override — comparison is a common researcher need and the current UI's
  absence is conspicuous. Resist: build it when the evidence is there.

### Load-bearing for which phases?
**Phase 1 (IA), Phase 3 (triage), and potentially the contract itself**
(if comparison becomes a primary surface, CONTRACT gains a §7).

---

## Cross-cutting: which questions gate which phases?

| | Q1 user | Q2 desktop | Q3 scores | Q4 run | Q5 governance | Q6 compare |
|---|---|---|---|---|---|---|
| **Phase 1 (IA)** | ⚠️ | — | — | — | ⚠️ | ⚠️ |
| **Phase 2 (reading)** | ⚠️ | ⚠️ | ⚠️ | — | — | — |
| **Phase 3 (triage)** | — | — | — | — | — | ⚠️ |
| **Phase 4 (direct+monitor)** | — | — | — | ⚠️ | — | — |
| **Phase 5 (long tail + lint flip)** | — | — | — | — | — | — |

⚠️ = load-bearing (the answer changes the phase's scope/design).
— = not load-bearing (phase proceeds regardless).

**Reading the matrix:**
- Phase 5 never blocks — it's mechanical migration + lint flip.
- Phase 1 is gated by Q1/Q5/Q6 (the three IA-shaping questions).
- Phase 2 is gated by Q1/Q2/Q3 (the three reading-surface questions).

**Implication for sequencing:** if validation is time-constrained,
prioritize resolving Q1, Q5, Q6 (Phase 1's gates) before Q2, Q3, Q4
(Phase 2's gates). Phase 1 ships first, so its gates matter first.

## Safe-default summary (if validation slips)

If interviews can't be run before Phase 1 *must* start, apply all safe
defaults and proceed — but mark every `[H]` as **provisionally affirmed**,
not confirmed, and revisit at the first opportunity. The safe defaults
exist precisely so the work doesn't stall; they are not a substitute for
validation, but they are a principled fallback.

| Q | Safe default | Confidence in default |
|---|---|---|
| Q1 | Individual researcher (READ is center) | High — matches codebase evidence |
| Q2 | Desktop-primary | High — prose reads poorly on phones |
| Q3 | Scores-as-input | Medium — balanced design |
| Q4 | Deep-run tolerant | Medium-high — matches SOUL.md brand |
| Q5 | Governance is daily | Medium — higher-info default |
| Q6 | Serial evaluation (no compare) | Medium — cheapest; don't over-build |

The defaults with "Medium" confidence are the ones most worth validating
before their gating phase commits.
