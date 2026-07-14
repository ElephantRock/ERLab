# 🐘 Elephant Rock — Product Definition

> **Status: v0 hypothesis — not a decree.**
> This document is the frontend's counterpart to `SOUL.md`. Where `SOUL.md`
> defines our *research philosophy*, this defines our *user and the interface
> that serves them*. Every claim marked **[H]** is a hypothesis to validate
> against 3–5 real researchers before this document hardens into v1. Until
> then, treat it as the strongest available starting point — better than no
> arbiter, but not yet ground truth.
>
> **How to use this document:** when a UI decision is disputed, cite the
> section and principle that resolves it. If no section resolves it, the
> document has a gap and should be amended. The point is to have *an* arbiter
> that is written down, not to have written the perfect one.

---

## Who We Serve

### The Primary User **[H]**
A **researcher doing original work** who uses Elephant Rock as an augmented
ideation and analysis tool — to discover gaps they hadn't seen, generate
directions they wouldn't have pursued, and produce proposals rigorous enough
to evaluate honestly.

They are not looking for answers. They are looking for **better questions,
backed by evidence, that they can judge and refine.**

### What They Do Here
They **read, judge, and refine** research artifacts — proposals primarily,
gaps and ideas secondarily. Their core act is **editorial judgment**: deciding
which generated directions are worth their time, which are not, and why.

This is a reading-and-thinking workflow, not a monitoring workflow. The
interface must be calibrated to sustained attention on prose, not to glancing
at telemetry.

### The Anti-User — Who We Are **Not** Building For
- **Not an SRE / ops engineer** monitoring a system. Telemetry exists
  (costs, traces, run health) but it is *secondary support*, not the product.
- **Not a casual chatbot user** wanting instant answers. The researcher
  tolerates a 25-minute run because rigor takes time.
- **Not us, looking at our own machine.** The interface is not a trophy case
  for the pipeline's sophistication. It is a tool for someone else's work.

### Secondary Users (supported, never first-class)
- **The reviewer / governance approver** — audits quality, approves or denies.
- **The administrator** — watches cost, model health, operations.
These users get reachable, functional surfaces — but they never set the tone.

---

## The Primary Task

> **Read a generated proposal, judge whether it is worth pursuing, and either
> refine it toward rigor or reject it with cause.**

Everything else — launching runs, monitoring progress, browsing gaps,
governing, auditing — exists to feed, support, or follow this task. When two
UI elements compete for the same real estate, the one closer to this task
wins.

---

## The Core Loop

```
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. DIRECT    — Launch a run on a domain, choose a strategy. │
   │                 (Secondary. Should take < 1 minute.)        │
   │                                                              │
   │ 2. MONITOR   — Watch progress without anxiety.              │
   │                 (Secondary. Must not demand attention.)     │
   │                                                              │
   │ 3. TRIAGE    — Scan the batch; pick which ideas to examine. │
   │                 (Dense is fine here — this is scanning.)    │
   │                                                              │
   │ 4. READ      — Examine a proposal in depth.                 │
   │                 ★ THE CENTER. Typography & space live here. │
   │                                                              │
   │ 5. JUDGE     — Assess novelty, feasibility, integrity.      │
   │                 Use scores + provenance + citations.        │
   │                                                              │
   │ 6. REFINE    — Fix sections, regenerate, give feedback.     │
   │                 The machine is directable, not a black box. │
   │                                                              │
   │ 7. GOVERN    — Approve, deny, or export the survivors.      │
   └─────────────────────────────────────────────────────────────┘
```

**Reading and judging (4–5) are the center.** Steps 1–3 feed it; 6–7 follow
it. The interface's information architecture, density, and tone are all
derived from keeping these two steps at the center.

---

## Interface Principles

Derived from the primary task, not from aesthetic preference. Each principle
exists because the researcher's judgment depends on it.

### 1. Reading Is the Center
The proposal body is the largest, calmest, most carefully typeset surface in
the product. Its type scale, line height, and measure are calibrated to
sustained reading of 2,000+ words. Every other surface calibrates *against*
it — not the other way around.

We reject: type sizes below readable thresholds (`text-[8px]`, `text-[9px]`)
on any human-read text; telemetry-style labels (`font-mono uppercase
tracking-widest`) as section headers; density that serves glanceability over
reading.

### 2. Trust Must Be Earned Visibly **[H]**
Because `SOUL.md` forbids fabricated citations and inflated scores, the
interface's job is to make that honesty **inspectable**. Every quantitative
claim, every citation, every score is one click away from its evidence: the
source paper, the supporting chunk, the axis breakdown.

Scores are never flat numbers. A novelty score links to its four axes and
closest prior work. A feasibility score links to its six dimensions. A "0.5
unverifiable" is shown *as* uncertain, never dressed up as confident.

### 3. The Machine Proposes; the Human Decides
Scores, rankings, and quality gates **inform** the researcher's judgment.
They never replace it. The interface presents the machine's assessment as
input to a decision, not as the decision itself. A proposal marked "low
novelty" can still be pursued; the interface must not make that pursuit feel
like defiance.

We reject: any UI that implies the machine has decided for the user;
auto-dismissal of "low-quality" work without an explicit human action.

### 4. The Machine Is Directable
Refinement is a first-class action, not an advanced feature. Fix a section,
regenerate with feedback, re-run scoring, re-run a stage, adjust a strategy
— the controls that `SOUL.md` calls "constructive criticism" are always
within reach of the artifact they act on.

We reject: burying refine/govern/export under "Advanced" navigation;
read-only views of artifacts that the pipeline can re-generate.

### 5. Density Serves the Step
Density is contextual, not uniform. **Triage (step 3)** may be dense — the
researcher is scanning. **Reading (step 4)** must breathe — they are
thinking. The same density in both is a failure of either the scan or the
read.

### 6. Honesty in State, Not Decoration
Status indicators reflect real state, or they do not exist. We do not show a
pulsing green "system ready" dot that is hardcoded on, because training users
to ignore indicators is a quiet form of dishonesty. If something is
unverified, it says unverified. If data failed to load, it says so. An empty
state is never dressed up as success.

We reject: decorative status; silent error swallowing; "Local GPU" labels
that don't reflect actual config.

---

## Scope

### In the Product (primary surfaces)
- The reading workspace (proposal + supporting evidence/provenance/scores).
- Run configuration and live progress.
- Triage / browsing of ideas, gaps, proposals.
- Refinement actions (fix, regenerate, feedback, refine scores).
- Governance (approve/deny, audit timeline).
- Export (Markdown, LaTeX, PDF).

### In the Product (secondary, functional-not-tonal)
- Costs, traces, memory, operations, model config, sessions, autonomous,
  plugins, knowledge graph. These exist for power users and debugging. They
  are **reachable from navigation but do not set the visual tone** of the
  primary surfaces.

### Explicitly Out of Scope as a *Primary* Experience
- Real-time ops monitoring as a dashboard-first experience.
- Mobile as a *primary* creation/review context **[H — validate]**. Mobile
  must reach every route (it currently doesn't), but the reading workspace
  is designed for desktop; mobile is triage + monitoring + governance only.

---

## Anti-Patterns We Reject

These are the failure modes the current interface falls into. Naming them
makes the principles enforceable.

- **The Ops Dashboard Trap** — `SYS_OK`, pulsing green dots, `font-mono`
  status footers, 8px elapsed timers. This is not a server room.
- **The Flat Score** — a single pill showing `0.82 High` with no axis
  breakdown, no closest prior work, no comparison. Scores are the product;
  flattening them flattens the product.
- **The Mirror** — UI that reproduces the backend's conceptual structure
  (Studio / Research / System / Advanced) instead of organizing around the
  researcher's workflow (Direct / Triage / Read / Refine / Govern).
- **The Trophy Case** — surfaces that exist to display the pipeline's
  sophistication rather than to serve a decision the researcher is making.
- **The Static Marketing Hero** — generic copy that occupies the most
  valuable real estate on every visit, regardless of who's looking.
- **The Decorative Indicator** — any status element that doesn't reflect
  real state. If it isn't truthful, it doesn't ship.
- **The Orphan Route** — a real page with no navigation path to it.
- **The Unreachable Mobile Route** — a route a mobile user cannot reach
  except by typing a URL.

---

## Our Commitment

Every screen, every component, every type size in this interface exists to
serve a researcher's editorial judgment — to help them read more carefully,
judge more rigorously, and refine more constructively than they could alone.

Where the interface and the machine's sophistication compete for attention,
the interface recedes. Where the interface and the researcher's judgment
compete for authority, the researcher wins.

This is the contract between Elephant Rock and the person who uses it.

---

## Open Questions to Validate Before v1 **[H]**

These assumptions are load-bearing and currently untested. Each should be
checked against 3–5 real researchers before this document hardens:

1. **Is the primary user a researcher doing original work**, or a research
   manager / lab lead triaging directions for a team? (Changes whether
   "triage" or "read" is the center.)
2. **Is desktop the primary context**, or do researchers review proposals on
   tablets/phones more than we assume?
3. **Do researchers trust AI-generated scores enough to act on them**, or do
   they treat all scores as suspect until they've read the evidence? (Sets
   how prominent score breakdowns must be vs. the raw proposal text.)
4. **Is the 25-minute run acceptable**, or is the real workflow many short
   `fast_scan` runs rather than one deep one? (Changes whether monitoring
   deserves more or less prominence.)
5. **Is governance (human approval) a daily act or a rare audit?** (Sets
   whether it's a primary nav item or a secondary surface.)
6. **Do researchers want to compare proposals side-by-side**, or do they
   evaluate one at a time? (The current interface assumes the latter;
   comparison may be a missing primary pattern.)

Until these are answered, this document is a hypothesis. A hypothesis with
an arbiter's role is still better than no arbiter — but it must be revised
when the evidence comes in.
