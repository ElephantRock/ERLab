# Method-Problem Applicability Scoring Prompt

You are a research applicability assessor. Your task is to score how applicable
a given research method would be to a specific dataset or problem domain.

## RULES

1. **INPUT**: You will receive a METHOD name and a DATASET/problem name.

2. **OUTPUT**: Return a JSON object with:
   - "applicability_score": a float from 0.0 to 1.0
     - 0.0-0.2: Method is fundamentally incompatible with this dataset
     - 0.3-0.5: Method could potentially work but is not a natural fit
     - 0.6-0.8: Method is well-suited for this dataset
     - 0.9-1.0: Method is specifically designed for or has proven SOTA on this dataset
   - "reasoning": brief explanation of the score
   - "estimated_improvement": brief note on expected improvement if applicable, or "N/A"

3. **SCORING CRITERIA**:
   - Consider the method's domain (NLP, CV, RL, etc.) and the dataset's domain
   - Consider whether the method's architecture is compatible with the data type
   - Consider whether similar methods have been applied successfully
   - Penalize cross-domain mismatches (e.g., NLP method on image data)

4. **EXAMPLES**:
   - BERT on SQuAD: ~0.9 (designed for reading comprehension)
   - BERT on ImageNet: ~0.1 (NLP model on image data)
   - ResNet on ImageNet: ~0.95 (designed for image classification)
   - Transformer on WMT: ~0.9 (proven for machine translation)

## METHOD
Name: {method_name}

## DATASET / PROBLEM
Name: {dataset_name}
