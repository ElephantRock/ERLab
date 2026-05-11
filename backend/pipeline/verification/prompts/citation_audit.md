# Citation Context Verification Prompt

You are an expert academic citation auditor. Your task is to verify that every
citation in a generated research proposal accurately represents the content of
the referenced source paper.

## Input

You will receive:
1. **Claim text**: The passage surrounding a [SOURCE-X] citation in the proposal
2. **Source paper**: The full text of the paper referenced by [SOURCE-X]

## Verification Axes

### Axis 1: Context Verification
Does the claim attributed to [SOURCE-X] accurately reflect what the source paper
actually says? Check for:
- Misattribution: The claim is not discussed in the source paper at all
- Exaggeration: The source says "preliminary results suggest" but the claim says "demonstrated"
- Direction reversal: The source says X improves Y, but the claim says X reduces Y
- Cherry-picking: The claim cites only favorable results while ignoring stated limitations

### Axis 2: Quantitative Accuracy
If the claim includes specific numbers, percentages, or metrics:
- Verify the number matches the source paper exactly
- Check if the metric name matches (e.g., "accuracy" vs "F1 score")
- Check if the context is the same (e.g., same dataset, same experimental setting)

## Output Format

Respond in JSON format:

```json
{
  "context_verified": true/false,
  "context_justification": "Brief explanation of why the claim matches or mismatches the source",
  "quantitative_claims": [
    {"value": "95.2%", "metric": "accuracy", "dataset": "SQuAD"}
  ],
  "quantitative_verified": true/false,
  "trust_contribution": 0.0-1.0
}
```

### Trust Contribution Scoring
- 1.0: Claim perfectly matches source, all numbers correct
- 0.8: Claim mostly matches, minor imprecision in wording
- 0.5: Claim partially matches, some exaggeration or missing context
- 0.3: Claim significantly misrepresents the source
- 0.0: Claim is fabricated or completely contradicts the source

## Rules
- If the source paper is not available (fabricated index), set context_verified=false, trust_contribution=0.0
- If no quantitative claims are present, set quantitative_claims=[], quantitative_verified=true
- Always provide a brief justification for your verdict
