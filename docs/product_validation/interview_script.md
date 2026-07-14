# Interview Script — the 6 `[H]` Questions

> **Purpose:** behavioral prompts for the 6 load-bearing hypotheses in
> `PRODUCT.md`. Each question maps to a PRODUCT.md `[H]` and to a
> `decision_rules.md` consequence.
>
> **Rule:** every prompt opens with **behavioral recall**, not preference.
> "Tell me about the last time…" beats "do you like…" every time. If a
> participant can't recall a specific instance, that's data (the behavior
> may be rarer than assumed) — note it and move on; don't coach them into
> a hypothetical.

## Format per question

```
[H-Qn]  PRODUCT.md claim under test

  OPENER (behavioral recall — 2-3 min)
    The non-leading entry prompt.

  PROBES (follow-ups — 3-5 min)
    Dig into specifics only if the opener lands.

  EVIDENCE SIGNALS (what counts as an answer)
    What the interviewer is listening for.

  → CONSEQUENCE: see decision_rules.md Qn
```

Time budget: ~4 min/question × 6 = ~24 min, leaving buffer in the 25-min
behavioral segment. Don't rush; if one question takes 8 minutes and
saturates, skip the weakest probe on the next.

---

## [H-Q1] Primary user — researcher vs. research manager?

> PRODUCT.md: "The Primary User [H]: A researcher doing original work…"
> This is the biggest lever. If wrong, TRIAGE and READ flip as the center.

**OPENER**
"Walk me through the last research direction you pursued seriously. From
the moment you first had the idea to deciding it was worth committing time
to — what did you actually do?"

**PROBES**
- "Who else was involved in the decision to pursue it? Just you, or did
  you need to convince a PI / team / committee?"
- "When you were evaluating whether it was worth it, what were you
  optimizing for — your own curiosity, a publication target, a grant, a
  team's roadmap?"
- "How many directions are you typically choosing between at once?"

**EVIDENCE SIGNALS**
- *Researcher (individual)*: speaks in terms of "I decided," optimizes for
  curiosity/novelty/rigor, evaluates 1–3 directions at a time.
- *Research manager*: speaks in terms of "we / my team / my students,"
  optimizes for portfolio fit/roadmap/headcount, evaluates 5+ directions,
  delegates the deep reading.
- *Mixed*: note both — the product may serve a researcher whose final
  step is a manager pitch.

→ **CONSEQUENCE: decision_rules.md Q1** (changes whether READ or TRIAGE
is the center; affects ScoreReport prominence, IA grouping).

---

## [H-Q2] Desktop vs. mobile as primary context

> PRODUCT.md: "Mobile must reach every route… but the reading workspace is
> designed for desktop."

**OPENER**
"Think about the last time you read a research paper or proposal closely
enough to form a strong opinion. Where were you, and what device were
you on?"

**PROBES**
- "Do you ever read papers on your phone? In what situation?"
- "When you're scanning — flipping through many papers to decide which to
  read — what device is that on?"
- "Is there a 'review while commuting / between meetings' part of your
  workflow? What does it look like?"

**EVIDENCE SIGNALS**
- *Desktop-primary*: deep reading on laptop/desktop; phone only for
  headlines/alerts. (Confirms PRODUCT.md hypothesis.)
- *Tablet/mobile for reading*: meaningful share of deep reading on
  tablet/phone → reading surface must be responsive, not desktop-only.
- *Mobile only for triage/monitoring*: phone is for scanning, not reading
  → current "mobile = triage + monitoring" framing holds.

→ **CONSEQUENCE: decision_rules.md Q2** (changes reading-surface
responsiveness requirements + mobile nav scope).

---

## [H-Q3] Trust in AI-generated scores

> PRODUCT.md §2: "Scores are never flat numbers… A '0.5 unverifiable' is
> shown *as* uncertain."

**OPENER**
"When you're evaluating research — yours or someone else's — and you see
a score or a ranking attached to it (a review score, a novelty rating, a
benchmark leaderboard position), how do you treat it?"

**PROBES**
- "Can you remember a time a score changed your mind? What happened?"
- "Have you ever *distrusted* a score enough to investigate why? Walk me
  through that."
- "If a tool gave you a 'novelty: 0.82' on an idea, what would you do
  with that number — if anything?"

**EVIDENCE SIGNALS**
- *Scores as input*: treats scores as a starting point, then verifies.
  Score breakdowns + provenance are valued. (Confirms ScoreReport design.)
- *Scores as noise*: ignores scores until they've read the substance.
  → scores should shrink; prose dominates even more.
- *Scores as authority*: defers to scores. (Rare in researchers; if
  common, the product has an honesty *responsibility* — even more reason
  to render uncertainty visibly.)
- Key signal: do they ask "how was this calculated?" unprompted? That's
  the provenance-attention signal.

→ **CONSEQUENCE: decision_rules.md Q3** (changes ScoreReport prominence
and whether axis breakdown is default-on or on-demand).

---

## [H-Q4] Run length acceptability — deep vs. many-fast?

> PRODUCT.md §"Core Loop": "They tolerate a 25-minute run because rigor
> takes time." — is that tolerance real?

**OPENER**
"When you start a literature search or analysis task, how long do you
expect it to take? Walk me through your patience for it."

**PROBES**
- "If a tool told you 'this will take 25 minutes and then give you
  results,' what would you do during those 25 minutes?"
- "Do you prefer one thorough pass, or several quick passes where you
  steer between?"
- "Have you ever abandoned a tool because it was too slow? What was the
  threshold?"

**EVIDENCE SIGNALS**
- *Deep-run tolerance*: 25 min is fine if quality is high; they context-
  switch and come back. (Confirms hypothesis; monitoring stays secondary.)
- *Many-fast preference*: wants 2–3 min iterations they can steer; 25 min
  is intolerable. → monitoring/prominence of progress changes; "fast_scan"
  may be the real default, not "deep_research."
- *Threshold reveal*: capture the specific number ("anything over 5 min
  I background").

→ **CONSEQUENCE: decision_rules.md Q4** (changes default strategy,
monitoring prominence, whether "resume watching" is a primary action).

---

## [H-Q5] Governance frequency — daily act or rare audit?

> PRODUCT.md §"Scope": governance is in primary nav "[H — to validate]".

**OPENER**
"In your current research workflow, is there a step where you formally
approve, reject, or sign off on a direction before it proceeds? Tell me
about it."

**PROBES**
- "How often does that happen — daily, weekly, per-project?"
- "Who else needs to sign off? Is it collaborative?"
- "What happens to a direction that doesn't get approved — is it killed,
  or sent back for revision?"

**EVIDENCE SIGNALS**
- *Daily/gate-like*: approval is a frequent, blocking step. Governance
  belongs in primary nav (GOVERN group, as PRODUCT.md speculates).
- *Rare/audit-like*: sign-off happens at milestones (paper submission,
  grant review), not per-idea. → governance drops to secondary nav; the
  primary flow has no governance step.
- *Collaborative*: multiple approvers → governance UI needs assignment/
  delegation, not just approve/deny.

→ **CONSEQUENCE: decision_rules.md Q5** (changes whether GOVERN is a
primary nav group; changes approval UI complexity).

---

## [H-Q6] Compare side-by-side vs. evaluate one-at-a-time?

> PRODUCT.md §"Core Loop" assumes one-at-a-time. This may be a *missing*
> primary pattern.

**OPENER**
"When you have several research directions on the table, do you evaluate
them one at a time, or do you compare them against each other? Walk me
through the last time."

**PROBES**
- "Do you ever put two proposals side by side — literally or mentally?
  What are you comparing?"
- "What makes you pick one over another when they're close?"
- "Have you ever used a tool that let you compare options directly? Did
  it work?"

**EVIDENCE SIGNALS**
- *One-at-a-time*: serial evaluation; the current IA is right. ScoreReport
  stays single-artifact.
- *Side-by-side*: comparison is a real, frequent pattern → triage gets a
  compare mode; reading surface gets a "compare with" action. This is a
  *new primary surface*, absent from PRODUCT.md.
- *Mental compare*: they compare in their head, not in the tool → low-
  fidelity compare support (a "pin" + a compare page) may suffice.

→ **CONSEQUENCE: decision_rules.md Q6** (the highest-impact answer: may
add a whole new primary surface to the contract).

---

## Closing (open)

"Before we wrap — what's the one thing about how you do research that I
didn't ask about, but you think I should know?"

This catches the unknown-unknowns. Capture verbatim; these often surface
in the PRODUCT.md v1 amendment as new `[H]` questions for a future round.

## Moderator notes

- **Silence is OK.** Researchers think before speaking; don't rush to
  fill a 5-second pause.
- **"Tell me more about that"** is the single best probe.
- **Don't defend the product.** If they criticize Elephant Rock's
  approach, that's the point. "That's helpful — tell me more."
- **Watch for the hypothetical trap.** "Would you use X?" → rephrase to
  "When did you last do something like X?"
- **Capture intensity.** A casual "sure, I guess" and a vivid "oh, that
  would change everything" are different evidence. The matrix has an
  *intensity* column for this reason.
