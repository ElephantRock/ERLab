# BATCH-185 BLUEPRINT
## Doom Loop Detection for Pipeline Stages

**Batch ID:** BATCH-185
**Cycle Mode:** STANDARD (AIV v5.3)
**Source:** `huggingface/ml-intern` → `agent/core/doom_loop.py`

---

### Problem Statement
Run #124 hung 11+ hours on idea generation. Gap analysis can produce identical gaps across iterations. Idea generation can produce near-identical ideas. No detection mechanism exists. Per-stage timeout (30 min) is a blunt instrument — it doesn't catch the problem until timeout expires.

### Solution
Port ML Intern's doom loop detection pattern to Elephant Rock's pipeline context. After each stage completes, hash the output and check for:
1. **Identical consecutive outputs** — same stage produces identical results 3+ times
2. **Repeating sequences** — pattern [stage_A_output_X, stage_B_output_Y, stage_A_output_X] detected 2+ times

When detected, log a warning and force the stage to return what it has instead of continuing to loop.

---

### TASK-01: Create `backend/pipeline/monitoring/doom_loop.py`

Port these concepts from ML Intern:

```python
@dataclass(frozen=True)
class StageOutputSignature:
    stage_name: str
    output_hash: str  # MD5 of serialized output

def hash_stage_output(output: Any) -> str:
    """Canonicalize + hash stage output for comparison."""
    
def detect_identical_consecutive(
    signatures: list[StageOutputSignature], threshold: int = 3
) -> str | None:
    """Return stage name if threshold+ identical consecutive outputs found."""
    
def detect_repeating_sequence(
    signatures: list[StageOutputSignature],
) -> list[StageOutputSignature] | None:
    """Detect repeating patterns of length 2-5 with 2+ repetitions."""
    
def check_pipeline_doom(stage_history: list[dict]) -> str | None:
    """High-level check: takes list of {stage_name, output_hash}, returns corrective message or None."""
```

Key differences from ML Intern:
- ML Intern hashes tool call args + results. We hash stage outputs (gap texts, idea titles+descriptions, proposal content).
- ML Intern operates on `litellm.Message` objects. We operate on `StageReport` dicts.
- Use `json.dumps(output, sort_keys=True, separators=(",",":"))` for canonical serialization before hashing.
- Hash only structured data (gap titles, idea titles+scores), not full text (too much variation).

### TASK-02: Wire into Orchestrator

In `backend/pipeline/orchestrator.py`:
- In the main stage loop (around line 1185), after each stage completes and produces a result:
  1. Extract output summary from the stage result (gap titles, idea titles, proposal first 500 chars)
  2. Hash it
  3. Append to `_doom_history` list
  4. Call `check_pipeline_doom(_doom_history)`
  5. If doom detected: log WARNING, set a flag that forces remaining optional stages to skip
- Add `self._doom_history: list[StageOutputSignature] = []` to `__init__`
- Reset `_doom_history` at start of each `run()` call

### TASK-03: Output Hash Extraction

Create helper `_extract_stage_fingerprint(stage_name: str, result: PipelineResult) -> str` that extracts the minimal fingerprint for each stage type:

| Stage | Fingerprint |
|:--|:--|
| gap_analysis | Concatenated gap titles |
| idea_generation | Concatenated idea titles + novelty scores |
| proposal_synthesis | First 500 chars of each proposal |
| evaluation | Concatenated scores |
| Other stages | Empty string (no doom check) |

Only gap_analysis, idea_generation, and proposal_synthesis need fingerprints — these are the stages most likely to loop.

### TASK-04: Tests

File: `backend/tests/test_pipeline/test_batch185_doom_loop.py`

```
test_01_identical_gaps_detected     — 3 identical gap title lists → doom detected
test_02_identical_ideas_detected    — 3 identical idea lists → doom detected  
test_03_repeating_sequence_detected — [gap_A, idea_B, gap_A] ×2 → doom detected
test_04_legitimate_variation_ok     — different outputs each time → no doom
test_05_threshold_not_met           — only 2 identical → no doom (need 3)
test_06_empty_history               — no stages → no doom
test_07_single_stage                — 1 stage → no doom
test_08_fingerprint_extraction      — gap titles extracted correctly
```

---

### Acceptance Criteria
- [ ] `doom_loop.py` with 4 public functions + dataclass
- [ ] Orchestrator checks doom after each stage
- [ ] Only gap/idea/proposal stages have fingerprints
- [ ] 8 tests passing
- [ ] Zero regressions in existing tests
