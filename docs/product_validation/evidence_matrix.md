# Evidence Matrix — Per-Participant Capture Template

> **Purpose:** structured capture for each interview, so synthesis
> (`interview_protocol.md`) works *by question across participants* rather
> than *by participant*. One copy of this template per participant.
>
> **Filled:** during the session (rough) → from the recording (verbatim
> quotes + intensity). **Synthesized in:** the per-question rollup that
> drives the PRODUCT.md v1 amendment.

## Participant metadata (fill once)

| Field | Value |
|---|---|
| ID | P1 (P2, P3, …) |
| Date | YYYY-MM-DD |
| Domain | (e.g. NLP, comp-bio, ML theory) |
| Role | (PhD student / postdoc / PI / industry researcher / research manager) |
| Career stage | (early / mid / senior) |
| Tools used (last 12mo) | (Elicit, Semantic Scholar, Consensus, …) |
| Incentive | ($ / equivalent / unpaid) |
| Consent to record | Y / N |
| Closest to PRODUCT.md "primary user"? | Yes / Partial / No (if No, note why — still usable, just weighted lower) |

---

## Per-question capture

For each of the 6 `[H]` questions: the **answer in the participant's
terms**, a **verbatim quote**, an **intensity rating**, and a **verdict
signal**. The verdict is preliminary — final synthesis is cross-participant.

### [H-Q1] Primary user — researcher vs. research manager?

| Field | Capture |
|---|---|
| Behavioral evidence (what they described doing) | |
| Verbatim quote (≤25 words) | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ individual researcher / ▢ manager-triage / ▢ mixed |
| Triangulation notes | (e.g. "PI but still reads deeply — mixed") |

### [H-Q2] Desktop vs. mobile context

| Field | Capture |
|---|---|
| Deep-reading device(s) | |
| Scanning/triage device(s) | |
| Verbatim quote | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ desktop-primary / ▢ tablet-mobile matters / ▢ mobile-triage-only |

### [H-Q3] Trust in scores

| Field | Capture |
|---|---|
| How they treat scores (last encounter) | |
| Unprompted "how was this calculated?" | Y / N |
| Verbatim quote | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ scores-as-input / ▢ scores-as-noise / ▢ scores-as-authority |

### [H-Q4] Run length / strategy preference

| Field | Capture |
|---|---|
| Expected wait time for a search/analysis | |
| Stated abandonment threshold (if any) | |
| Verbatim quote | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ deep-run tolerant / ▢ many-fast preferred / ▢ mixed |

### [H-Q5] Governance frequency

| Field | Capture |
|---|---|
| Does a formal sign-off step exist in their workflow? | |
| Frequency | ▢ per-idea / ▢ per-milestone / ▢ rare-none |
| Collaborative? | solo / multi-approver |
| Verbatim quote | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ daily-gate / ▢ rare-audit / ▢ collaborative-review |

### [H-Q6] Compare vs. one-at-a-time

| Field | Capture |
|---|---|
| How they evaluated multiple directions last time | |
| Tool-supported comparison? (ever) | Y / N |
| Verbatim quote | |
| Intensity | ▢ casual / ▢ considered / ▢ vivid |
| Signal | ▢ serial / ▢ side-by-side-frequent / ▢ mental-compare |

---

## Artifact-reaction segment (UI walkthrough)

Not scored against the 6 questions — calibration only. Capture frictions
that surface *unprompted* (the highest-signal kind).

| Surface | Unprompted friction / comment | Severity (their framing) |
|---|---|---|
| Dashboard | | |
| Idea-detail (reading surface) | | |
| Pipeline-new | | |
| Other | | |

## Closing "what didn't I ask?"

| Verbatim | Flag as new `[H]` candidate? |
|---|---|

## Interviewer's one-line summary

> (e.g. "P3 is the target user — vivid individual-researcher, desktop-
> primary, treats scores as input but distrusts them until proven, deep-run
> tolerant, evaluates serially. Confirms Q1/Q2/Q4; complicates Q3.")

---

## Synthesis rollup (filled after all participants)

This section is appended **once**, after all sessions, in a single
consolidated copy — not per participant. For each `[H]` question:

```
[H-Qn]  Verdict:  confirmed / revised / refuted / inconclusive

  P1: <signal> — <quote>
  P2: <signal> — <quote>
  …

  Reasoning: <why this verdict, citing strongest evidence not vote-count>
  PRODUCT.md amendment (if revised): <new wording>
  Follow-up question (if inconclusive): <next-round prompt>
```

The rollup is what feeds `decision_rules.md` → the PRODUCT.md v1
amendment proposal.
