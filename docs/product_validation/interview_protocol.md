# Researcher Validation Protocol

> **Purpose:** de-risk `PRODUCT.md` before committing to Phase 1 (IA) and
> Phase 2 (reading surface). PRODUCT.md is explicitly a v0 hypothesis; this
> protocol is how it becomes v1.
>
> **Scope:** 3–5 participants, ~60 minutes each. Small-n qualitative,
> hypothesis-driven (not exploratory). The goal is *decision-grade evidence*
> on the 6 load-bearing `[H]` questions, not statistical generalization.

## Why interviews, not a survey

The `[H]` questions are about *behavioral preferences and mental models*
(how do you triage? do you trust scores? do you compare proposals?). These
are ill-suited to multiple-choice because respondents don't know their own
answers until they describe their workflow. Open-ended behavioral prompts,
followed up with "show me," surface what people actually do — which
reliably differs from what they say they do. 3–5 deep interviews is the
right tool; 50 survey responses would be cheaper and less informative.

## Recruitment

### Who
**Active researchers producing original work**, ideally in domains Elephant
Rock already targets (AI/NLP, computational biology, ML theory). Recruitees
must have, in the last 12 months:
- Written or reviewed at least one research proposal or paper.
- Used at least one literature-discovery or idea-generation tool (Elicit,
  Consensus, Semantic Scholar, Connected Papers, ResearchRabbit, etc.).

Avoid: pure engineers who don't do research; people whose research is
purely theoretical and never touches empirical proposals (different
workflow); people who have *built* a competing tool (biased framing).

### N = 3–5, not more
The point is **saturation**, not sample size. In qualitative research,
3–5 participants are typically sufficient to either confirm or refute a
small set of hypotheses; by interview 4–5 you should be hearing the same
patterns repeat. If by interview 5 the answers are still surprising, the
hypotheses are under-specified and you need to refine them, not add more
participants. Stop when saturation is reached.

### Incentive
Pay them. Researcher time is scarce; unpaid recruitment selects for the
wrong sample. A $50–100 honorarium (or equivalent) per session is standard
for 60 minutes.

## Session structure (60 minutes)

| Time | Segment | Purpose |
|---|---|---|
| 0:00–0:05 | Consent + recording confirmation | Ethics; allows verbatim transcription. |
| 0:05–0:15 | **Workflow timeline** — "walk me through your last proposal/paper from idea to submission" | Ground the conversation in *their* reality before introducing ours. Surfaces context the script can't anticipate. |
| 0:15–0:40 | **Behavioral prompts** (see `interview_script.md`) — the 6 `[H]` questions, each opened with a behavior recall, not a preference question | Decision-grade evidence per question. |
| 0:40–0:55 | **Artifact reaction** — show the current Elephant Rock UI (dashboard + idea-detail) for ~10 min; capture first-impression friction points | Calibrates the "what's wrong" claims against a concrete stimulus, not abstraction. |
| 0:55–1:00 | Open follow-up — "what didn't I ask that I should have?" | Catches the unknown unknowns. |

### The two anti-patterns to avoid in moderation

1. **Leading questions.** "Do you think scores are useful?" primes a yes.
   The script (`interview_script.md`) is built around *behavioral recall*
   ("tell me about the last time you decided a direction wasn't worth
   pursuing — what did you look at?") precisely to avoid this. If you find
   yourself asking "would you use X?", rephrase to "when did you last use
   something like X, and what happened?"
2. **Demoing the product first.** If you show the UI before the behavioral
   prompts, participants will rationalize their workflow to fit what they
   saw. The artifact-reaction segment is deliberately last.

## Capture

- **Record (audio) every session**, with consent. Notes alone miss the
  verbatim phrasing that signals conviction vs. hedging.
- **One `evidence_matrix.md` row per participant**, filled during/before
  transcription. The matrix is the structured artifact; the recording is
  the raw evidence.
- **Flag every verbatim quote** you might cite in the eventual PRODUCT.md
  amendment. Quotes carry more weight than paraphrase.

## Synthesis

### Per-question, not per-participant
After all sessions, synthesize **by `[H]` question**, not by participant.
For each of the 6 questions:
1. List each participant's answer + supporting quote.
2. Note agreement / disagreement.
3. Assign a verdict: **confirmed / revised / refuted / inconclusive**.
4. If revised, write the *new* PRODUCT.md wording.
5. If inconclusive, write a follow-up question for the next round (rare;
   most should resolve in 3–5).

### Triangulation, not vote-counting
A 3–2 split is *not* "majority wins." Look for the **strongest evidence**,
not the most frequent. One participant describing a vivid, specific
workflow that contradicts the hypothesis may outweigh three vague
agreements — especially if that participant is closest to the target user
profile. Document the reasoning, not the tally.

### Output
The synthesis produces the **PRODUCT.md v1 amendment proposal** — for each
`[H]` question, either:
- **Reaffirm** (with evidence), removing the `[H]` marker, or
- **Revise** (with the new wording + evidence), or
- **Keep `[H]`** (inconclusive — defer; do not let it block Phase 1/2
  unless it's load-bearing for those phases, which `decision_rules.md`
  specifies).

## Definition of done for this protocol

```text
- 3–5 interviews conducted and recorded (with consent).
- evidence_matrix.md completed for every participant.
- Per-question synthesis written (confirmed / revised / refuted / inconclusive).
- PRODUCT.md v1 amendment proposal drafted.
- INTERFACE_CONTRACT.md amendment drafted IF any revision changes a
  load-bearing assumption (see decision_rules.md for which do).
```

## What this protocol deliberately does NOT do

- **Usability testing.** We are not testing the current UI's usability;
  we are testing whether the *product definition* matches reality. The
  artifact-reaction segment is calibration, not task-based usability
  (that comes after Phase 2, on the redesigned surface).
- **Feature prioritization.** "What features do you want?" produces noise.
  The script avoids it. We want to know *what they do*, then derive
  features from that.
- **Pricing/packaging.** Out of scope.
- **Statistical claims.** N=3–5 informs this product; it does not
  generalize to "researchers everywhere." Be honest about this in the
  synthesis — overclaiming from small-n is the classic qualitative trap.
