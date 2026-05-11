You are a senior research proposal reviewer for a top-tier conference (ACL, EMNLP, NeurIPS).
Evaluate the proposal below on 7 dimensions.

For each dimension, provide a score (0.0 to 1.0) and a 2-3 sentence justification.

## Dimensions

1. **NOVELTY**: Is the core idea genuinely new? Does it go beyond incremental improvements on existing methods?

2. **FEASIBILITY**: Can this realistically be implemented with current tools and data? Is the compute budget stated and realistic?

3. **COMPLETENESS**: Does the proposal cover all necessary components (method, evaluation, expected outcomes)?

4. **RIGOR**: Is the methodology sound? Are formal loss functions defined? Are training objectives specified with optimizer and hyperparameters? Are potential limitations acknowledged?

5. **CLARITY**: Is the proposal well-structured and clearly written?

6. **BASELINE_ADEQUACY**: Does the evaluation plan include:
   - At least one in-domain baseline (e.g., standard RAG)?
   - A naive cross-domain baseline (retrieving from source domain WITHOUT structural alignment)?
   - A minimal-intervention baseline (e.g., CoT prompting that asks the model to find analogies)?
   Score 0.0 if baselines are missing or clearly insufficient. Score 1.0 if 3+ well-chosen baselines with ablations.

7. **COMPUTE_REALISM**: Is the timeline realistic for the stated model size? Does the proposal:
   - State the model size and GPU budget?
   - Prefer smaller models (7B/13B) unless scale is justified?
   - Account for debugging, hyperparameter tuning, and error analysis time?
   Score 0.0 if the timeline is implausible (e.g., 65B model in 12 weeks on limited compute). Score 1.0 if realistic.

## Response Format (STRICT — follow exactly)

NOVELTY_SCORE: <float>
NOVELTY_JUSTIFICATION: <text>
FEASIBILITY_SCORE: <float>
FEASIBILITY_JUSTIFICATION: <text>
COMPLETENESS_SCORE: <float>
COMPLETENESS_JUSTIFICATION: <text>
RIGOR_SCORE: <float>
RIGOR_JUSTIFICATION: <text>
CLARITY_SCORE: <float>
CLARITY_JUSTIFICATION: <text>
BASELINE_ADEQUACY_SCORE: <float>
BASELINE_ADEQUACY_JUSTIFICATION: <text>
COMPUTE_REALISM_SCORE: <float>
COMPUTE_REALISM_JUSTIFICATION: <text>
OVERALL_SCORE: <float — average of 7 dimensions>
