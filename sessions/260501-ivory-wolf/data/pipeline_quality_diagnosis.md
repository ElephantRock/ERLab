# Pipeline Quality Diagnosis

**Context:** Research paper on GoT × NSR was reviewed. Three critical weaknesses exposed:

---

## Problem 1: Hallucinated References

**What happened:** The proposal synthesizer's prompt says "Cite papers from the supporting literature using author-year format: (Author, Year)." The LLM complies — but it also fabricates citations when the supporting literature doesn't cover a topic it wants to discuss.

**Root cause:** The synthesis prompt gives the LLM paper titles/abstracts as context, but:
- There's NO instruction to ONLY cite papers from the provided literature
- There's NO post-generation verification that cited papers exist
- The `_parse_references()` method just captures raw text — it never checks

**Fix needed:**
1. Add explicit instruction to synthesis prompt: "Only cite papers listed in the Supporting Literature section. Do not invent citations."
2. Add `ReferenceVerifier` as a post-synthesis stage that flags/corrects unverifiable citations
3. Wire the verifier into the proposal pipeline so it runs automatically

---

## Problem 2: Shallow Proposals

**What happened:** Proposals read as "high-level framing rather than deeply specified research plans." The reviewer noted TopoReason's "Kolmogorov complexity" mention is specific, but Guardian Angels' "confidence ledger" is evocative but underspecified.

**Root cause:** The synthesis prompt asks for "500+ words" for the method section and "mathematical formulations" — but the LLM generates plausible-looking math without concrete architecture. The prompt says "algorithmic steps" but the LLM interprets this loosely.

**Fix needed:**
1. Add a `ProposalDeepener` pass after synthesis: a second LLM call that takes the high-level proposal and forces it to produce:
   - Concrete architecture (modules, interfaces, data flow)
   - A worked toy example with synthetic data
   - Expected failure modes with root causes
   - Measurable success criteria (metric, target, baseline)
2. This is a SEPARATE stage, not a prompt change — the deepener uses the proposal as input and produces enriched output

---

## Problem 3: No Pipeline Quality Metrics

**What happened:** The paper claims "~160-200 papers analyzed" and "17 gaps identified" but provides no precision/recall. The reviewer correctly notes: "we don't see recall/precision metrics on gap detection or a validation study."

**Root cause:** The pipeline has NO self-evaluation mechanism. It runs stages sequentially and assumes the output is good. There's no measurement of:
- How many detected gaps are real vs. hallucinated?
- How many known important gaps were missed?
- How novel are the generated ideas actually?

**Fix needed:**
1. `PipelineEvaluator` computes precision/recall against a gold-standard gap list
2. For any domain, maintain a "known important gaps" list that serves as ground truth
3. After each pipeline run, generate a `PipelineEvaluationReport` with metrics
4. Wire this into the orchestrator as an optional post-run evaluation stage

---

## Problem 4 (bonus): Cross-Run Deduplication

**What happened:** Runs #67, #68, #69 produced 17 gaps total, but some overlap significantly (e.g., G3 "cost-efficiency benchmarks" and U6 "sustainable architectures"). The paper presents them as 17 distinct gaps.

**Fix needed:** Add cross-run gap deduplication using semantic similarity before presenting gaps in any output.

---

## Priority

| Fix | Impact | Effort | Priority |
|:----|:-------|:-------|:---------|
| ReferenceVerifier in synthesis prompt | HIGH — prevents hallucinated citations | LOW — prompt change + wiring | P0 |
| ReferenceVerifier post-stage | HIGH — catches what prompt misses | MEDIUM — new stage | P1 |
| ProposalDeepener as stage | HIGH — makes proposals concrete | MEDIUM — new stage + prompt | P1 |
| PipelineEvaluator | MEDIUM — enables quality measurement | LOW — already built | P2 |
| Cross-run gap dedup | MEDIUM — prevents duplicate gaps | LOW — similarity check | P2 |
