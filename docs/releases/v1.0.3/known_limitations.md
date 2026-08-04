# v1.0.3 Known Limitations

These limitations bound the v1.0.3 release claim. They are non-blocking for the
reconciliation track but must not be silently exceeded.

1. **OpenAI-only live validation.** The OpenAI-compatible cloud path is the only
   live-validated provider path for this release.
2. **Contract conformance without universal live proof.** Anthropic, Gemini,
   Ollama, and LiteLLM conform to the shared usage-attribution contract
   (verified by the provider-usage test suite), but they do not have universal
   live end-to-end proof for this release.
3. **Tool-call accounting is out of claim.** `complete_with_tools` attribution
   (including the Gemini/Ollama tool-call `run_id` propagation gap noted during
   Commit 2) is outside the v1.0.3 release claim and remains an open
   improvement.
4. **Experiment execution is opt-in.** Experiment execution is spec-driven
   (`experiment_spec_id`) and is not demonstrated by a literature-only run.
5. **No human peer-review claim.** Papers produced by ERLab are reviewed by
   independent computational review (GPT-5.3 LLM), not human peer review.
6. **No autonomous scientific-validity claim.** ERLab does not establish
   publication-ready scientific validity autonomously.
7. **No arbitrary-domain generality claim.** The empirical experiment path is
   demonstrated on registered datasets (UCI Iris, Wine Quality, Concrete
   Strength), not arbitrary domains.
8. **Datasets and external dependencies are not bundled.** Datasets (under
   `data/`, gitignored) and external provider credentials must be obtained
   separately — see [REPRODUCIBILITY.md](../../../REPRODUCIBILITY.md).
9. **Test-order / global-singleton contamination.** Test-order/global-singleton
   contamination was observed in broad mixed-order test selections: affected
   tests passed in isolation, and the issue reproduced on the prior baseline
   (Commit 4 / `caf18f5`), confirming it is pre-existing and not introduced by
   the v1.0.3 changes. It is classified as an improvement, not a release blocker.

## Evidence-provenance gap

**F-5 / F-6 labels cannot be asserted.** No repository source (README,
REPRODUCIBILITY.md, SECURITY.md, ARCHITECTURE.md, CHANGELOG.md, `docs/`, or
session memory) currently defines findings labelled F-5 or F-6. Because the
referent of those labels cannot be established from repository evidence, this
dossier does not assert any F-5 or F-6 finding as resolved, open, or
non-blocking. This is recorded as an evidence-provenance gap, not as a resolved
finding; if the labels are tracked outside the repository, their source must be
supplied before any claim about them can be made.
