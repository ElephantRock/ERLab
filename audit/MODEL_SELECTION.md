# Live Paper E2E Model Selection

The prior audit used `qwen2.5:0.5b` only as a low-resource connectivity fallback. That model is not accepted for research-paper generation validation.

The corrected live-paper E2E uses:

- Provider: Ollama
- Model: `qwen2.5:7b`
- Context cap: 8192 tokens
- Parallelism: 1
- Loaded models: 1

Rationale: `qwen2.5:7b` is the largest Qwen2.5 model that can reasonably fit on the standard private-repository GitHub-hosted Linux runner while leaving headroom for the ERLab backend. The audit must still fail unless the product produces, evaluates, persists, restarts, exports, and retrieves a complete paper.
