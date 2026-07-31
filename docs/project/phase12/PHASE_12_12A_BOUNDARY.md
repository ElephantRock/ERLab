# Phase 12 / 12A — Synthesis Boundary Analysis

## How the paper synthesizer combines inputs

The synthesis pipeline combines:
1. **proposal_text** — creative research narrative (from idea_generation + proposal_synthesis)
2. **source_papers** — formatted literature with [SOURCE-N] citations
3. **experiment_context** — experiment spec + observed results with [RESULT-N] markers

`PaperSynthesizer._build_user_prompt()` (paper_synthesizer.py:118-145) structures the prompt:
```
## Research Domain
## Supporting Literature (CLOSED-BOOK)
## Research Proposal to Expand    ← THE PROBLEM
<proposal_text>
Now write a complete academic paper expanding this proposal.
```

The `experiment_context` is appended to `synthesis_sources` at synthesis_service.py:127-128,
entering the prompt as supplementary context AFTER the proposal.

## The exact boundary where proposal framing overrides the executed method

The LLM receives:
1. The proposal as the PRIMARY expansion target ("expand THIS proposal")
2. The experiment context as SUPPLEMENTARY information

Because the proposal is positioned as the expansion target and the experiment
is supplementary, the LLM centers the proposal's creative narrative and treats
experiment results as secondary. This is why quantum proposals produce quantum
papers even when the experiment is classical logistic regression.

## The fix

Make the title, result sentences, and key empirical claims DETERMINISTIC —
generated from persisted evidence BEFORE the LLM call, then INJECTED as fixed
sections the LLM cannot override. Reuse Phase 11 components at synthesis time.
