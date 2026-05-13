# BATCH-186 BLUEPRINT
## Research Sub-Agent for Literature Search

**Batch ID:** BATCH-186
**Cycle Mode:** STANDARD (AIV v5.3)
**Source:** `huggingface/ml-intern` → `agent/tools/research_tool.py`
**Depends on:** BATCH-185 (doom loop detection)

---

### Problem
Literature search runs all queries in one context. When context fills up, quality degrades. No independent budget per query. No way to use cheaper model for search vs expensive model for synthesis.

### Solution
Port ML Intern's research sub-agent pattern. Each search query gets its own isolated context with:
- Independent message history (doesn't pollute main pipeline)
- Context budget: warn at 80%, hard-stop at 95%
- Iteration limit: 20 iterations per sub-agent
- Doom loop detection (reuses BATCH-185)
- Cheaper model for search (local qwen3-4b), expensive for synthesis (cloud)

---

### TASK-01: Create `backend/pipeline/literature/research_agent.py`

```python
class ResearchSubAgent:
    """Isolated research context for a single search query."""

    def __init__(self, query: str, domain: str,
                 thinking_model: str, generation_model: str,
                 max_iterations: int = 20,
                 context_budget: int = 100_000):
        self.messages = [system_prompt, user_task]
        self.iteration = 0
        self.max_iterations = max_iterations
        self.context_budget = context_budget

    async def run(self, search_fn, embedding_fn) -> list[dict]:
        """Execute research loop. Returns list of paper dicts."""

    def _check_context_budget(self, token_count: int) -> str | None:
        """Return warning message if over budget, None if fine."""

    def _check_doom(self) -> str | None:
        """Reuse doom_loop.check_pipeline_doom on search history."""
```

The sub-agent doesn't use tools like ML Intern's does (we don't have HF docs/GitHub tools). Instead, it takes `search_fn` and `embedding_fn` callables that it can invoke to search and embed papers. This keeps it decoupled from the specific search service implementation.

### TASK-02: Wire into MultiSourceSearcher

In `backend/pipeline/literature/multi_source.py`:
- Each query from the query list spawns a ResearchSubAgent
- Agents run in parallel via `asyncio.gather()`
- Results are merged back into the main paper list
- If sub-agent hits context budget, return what it has so far

### TASK-03: Config options

Add to `backend/config.py`:
- `research_subagent_enabled: bool = False` (opt-in for now)
- `research_subagent_max_iterations: int = 20`
- `research_subagent_context_budget: int = 100_000`

### TASK-04: Tests

File: `backend/tests/test_pipeline/test_batch186_research_agent.py`

```
test_01_subagent_returns_papers       — mock search_fn returns papers
test_02_iteration_limit_respected     — stops after max_iterations
test_03_context_budget_warn           — warns at 80% budget
test_04_context_budget_hard_stop      — stops at 95% budget
test_05_doom_loop_detected            — reuses BATCH-185 detection
test_06_empty_query_returns_empty     — edge case
test_07_parallel_agents               — 3 agents run concurrently
test_08_cheaper_model_used            — thinking_model differs from generation_model
```

---

### Acceptance Criteria
- [ ] ResearchSubAgent class with independent context
- [ ] Integrates with MultiSourceSearcher (opt-in via config)
- [ ] Context budget enforcement (warn + hard stop)
- [ ] Doom loop detection within sub-agent
- [ ] 8 tests passing
- [ ] Zero regressions
