# Phase 13 — Closeout Evidence

## 1. Initial-composition provenance

All three papers generated with exactly 1 provider call each. Raw provider
outputs and assembled papers saved as audit artifacts.

```text
              provider_calls   removed_claims   eval   revisions   patches
Iris          1                0               ready  0           0
Wine          1                0               ready  0           0
Concrete      1                0               ready  0           0
```

Raw provider-output hashes:
```
Iris:      203c24cc... (0 [RESULT-N] in raw, 0 unauthorized claims)
Wine:      203c24cc... (0 [RESULT-N] in raw, 0 unauthorized claims)
Concrete:  9921e64c... (0 [RESULT-N] in raw, 0 unauthorized claims)
```

Note: In this run the provider did not generate unauthorized achievement
claims (0 removed). In the prior run (commit f3a81b7) the provider did
generate achievement claims that were stripped — the sanitizer was active
and correctly scoped. The architecture handles both cases.

Deterministic component hashes (stable across re-generation):
```
Iris:      title=a5fc100a... results=b10bdd47...
Wine:      title=b00d1f7c... results=fd5552ce...
Concrete:  title=31b55724... results=109439d7...
```

## 2. Sanitizer bounds

The sanitizer (`validate_provider_output` + stripping in `assemble_typed_paper`)
removes ONLY sentences matching:
- `achieved (an)? <word> (of)? <number>`
- `outperformed ... <number>`

It does NOT remove:
- Literature citations ([SOURCE-N])
- Limitations or negative interpretations
- Slot placeholders ({{EMPIRICAL_*}})
- Non-empirical prose

It fails closed: `validate_provider_output` rejects any [RESULT-N] marker
in provider output, which cannot be stripped (it's a structural violation).

## 3. Evidence integrity

```text
ExperimentResult count: 26 (unchanged from Phase 12)
Phase 11 revision hashes: all 6 rows identical
Manifest hashes: Iris=2d847cf9... Wine=2fb54697... Concrete=a8b971e2...
Metric values: all unchanged
```

## 4. Restart persistence

Phase 11 revision history (6 rows for proposals 64, 65) — all 6 hashes IDENTICAL post-restart.

Phase 13 assembled papers (ephemeral, not persisted to DB) — file hashes
IDENTICAL when re-read from disk.

Deterministic components reconstructed from spec — hashes IDENTICAL across
re-generation (deterministic by construction).

## 5. External-review record

```text
reviewer:        GPT-5.3 (ChatGPT, model=auto)
conversation_id: 6a6c1ba7-bc9c-83eb-8e6c-1efaf3155f05
review date:     2026-07-31

Evidence supplied:
  - Architecture description (typed claim composition)
  - Iris: title, methods, results, conclusion
  - Wine: title, methods, results, conclusion
  - Concrete: title, methods, results, conclusion

Questions asked:
  1. Does the revised narrative describe the executed experiment?
  2. Any unexecuted method credited?
  3. Do empirical claims remain supported?
  4. Any blocker?

Raw response (verbatim):
  "Paper 1 — Iris: no concern. The narrative identifies the executed
   dataset and multinomial logistic-regression method. No unexecuted
   method receives credit, and the comparison is deterministically
   supported by the frozen baseline and model results.

   Paper 2 — Wine: no concern. The narrative attributes the outcome to
   the executed logistic-regression experiment. The conclusion is
   supported by deterministic evidence composition, with no indicated
   method substitution or unsupported empirical claim.

   Paper 3 — Concrete: no concern. The narrative correctly credits linear
   regression and applies the lower-is-better direction for RMSE. The
   conclusion follows from the frozen model and mean-baseline results.

   The revised narratives describe the executed experiments, no unexecuted
   method is credited, and the central empirical claims remain supported.
   No blocker is evident in any paper from the supplied evidence."
```

## Verification

```text
Backend:    5,032 passed, 0 failed (1 known timing flake)
Frontend:   988 passed, 0 failed
HEAD:       4c0d11e
Working tree: clean
```
