# BATCH-187 BLUEPRINT
## Pre-Flight Cost & Time Estimation

**Batch ID:** BATCH-187
**Source:** `huggingface/ml-intern` → `agent/core/cost_estimation.py`

### TASK-01: Create `backend/pipeline/preflight/cost_estimator.py`
- `estimate_run_cost(strategy, stages, model_config) -> CostEstimate`
- Model pricing table: local models = $0.00, cloud glm-5.1 = known price
- Time estimate from historical runs in SQLite

### TASK-02: API endpoint `GET /api/v1/pipeline/estimate`
### TASK-03: Frontend estimate card in pipeline-new.tsx
### TASK-04: 8 tests
