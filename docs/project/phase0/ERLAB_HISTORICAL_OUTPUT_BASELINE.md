# ERLab Historical Output Baseline

> **Phase 0 — Work Package 0C.**
> **Purpose:** recover an actual historical product output for later comparison with the current system (Phase 3).
> **Baseline HEAD:** `d5990bc4e603767dc1282a7044122ed5e9be8ea5`.

## Recovered artifact *[VERIFIED]*

| Field | Value |
|---|---|
| Title | "Graph-of-Thought Meets Neuro-Symbolic Reasoning: A Systematic Gap Analysis and Research Roadmap for Structured, Verifiable AI" |
| Author (front-matter) | Elephant Rock Research Platform — AI/Structured Reasoning Division |
| Date (front-matter) | 2026-05-07 |
| Original path | `sessions/260501-ivory-wolf/data/GoT_NSR_Research_Paper.md` (+ `.tex`) |
| Source commit | last present at `e2c0171^` = `c275c6d9dab73335e09534e8b66faf7126435102` (platform HEAD, 2026-06-07) |
| Deletion commit | `e2c0171d22809e69bfeda1cb7d18be195b44e96c` ("Phase 0: Clean migration baseline", 2026-06-16) |
| Recovery command (md) | `git show e2c0171^:sessions/260501-ivory-wolf/data/GoT_NSR_Research_Paper.md` |
| Recovery command (tex) | `git show e2c0171^:sessions/260501-ivory-wolf/data/GoT_NSR_Research_Paper.tex` |
| Original blob hash (md) | `c59b75a951bccdbe6cb884c05b94913ac0cc407d` |
| Original blob hash (tex) | `e59f1b393884bbd208fa5dcc275237d6d231841f` |
| Recovered sha256 (md) | `de3efcb48d725aeb4a6dfbe857e148342b3ad017891655cef05971a51ea32d0f` |
| Recovered sha256 (tex) | `656ac3abe2081ab5648810a2e7a61212d6ddecc3870a44c6b8b3982637c2571e` |
| Byte-identity check | **VERIFIED** — `git hash-object` of both recovered files matches the original blob hashes exactly |
| Recovered storage | `docs/project/phase0/historical_baseline/GoT_NSR_Research_Paper.{md,tex}` |
| Generation status | **pipeline-generated** (per front-matter author "Elephant Rock Research Platform"; Appendix A documents the exact pipeline configuration used) |

## Recovery provenance

The paper was present in the tree at every commit from its creation through the Phase 0 wipe parent (`c275c6d`, 2026-06-07). It was deleted as one of the 1,573 files removed in the Phase 0 clean-baseline commit (`e2c0171`, 2026-06-16). Recovery was performed with `git show <parent>:<path>` and verified byte-identical to the original blob via `git hash-object`.

## Historical output assessment *[VERIFIED]*

| Attribute | Value |
|---|---|
| Word count | 4,347 words (`.md`) |
| Section completeness | **Complete.** 8 numbered sections: (1) Introduction, (2) Background & Related Work (3 subsections), (3) Methodology, (4) Systematic Gap Analysis (4 subsections, 17 gaps), (5) Proposed Research Directions (6 proposals), (6) Unified Research Roadmap (3 phases), (7) Discussion (4 subsections incl. Limitations), (8) Conclusion, plus References and Appendix A: Pipeline Configuration |
| Citation count | **10 numbered references** in a proper bibliography (Besta GoT, Wei CoT, Yao ToT, Garcez NSR, Lamb NSCR, Ren, Mitsui CLAUSE, Lyu Proof of Thought, He, Prakash). **Note:** uses numbered-reference style (`[1]`…`[10]`), NOT the current `[SOURCE-N]` citation-marker scheme |
| Bibliography presence | **Yes** — dedicated `# References` section with 10 fully-formatted entries (authors, year, title, venue) |
| Approximate length | 33 KB (md) / 37 KB (tex) |
| Structure type | Full academic paper: YAML front-matter (title/authors/date/abstract/keywords), abstract (~200 words), 8 sections, references, appendix |
| Associated run artifacts | Front-matter + Appendix A document: strategy=`deep_research`, LLM=`z.ai glm-5.1`, embedding=`Ollama nomic-embed-text (768-dim)`, sources=`arXiv/OpenAlex/Semantic Scholar/PubMed/CrossRef`, ~160–200 papers analyzed across 3 studies, 17 gaps, 6 proposals. **No machine-readable run directory survives** (the associated `data/runs/` entries were also deleted in Phase 0 wipe) |
| Evaluation artifacts | **None recoverable** — `quality_report.json` for this run was deleted in Phase 0; the paper itself is the only surviving artifact |
| Obvious corruption/truncation | **None.** Structure is complete, no mid-section breaks, references resolve, abstract is well-formed |
| Citation markers vs current system | Uses `[N]` numbered references; current pipeline emits `[SOURCE-N]` markers — **a citation-format divergence to account for in any comparison** |
| Role: workflow fixture | **Yes** — suitable for comparing workflow completion, paper length/structure, section coverage, export formats, and user effort. It is an authentic, complete, pipeline-generated full paper on a known topic (GoT × NSR), with documented provenance. |
| Role: quality gold standard | **No — explicitly not.** This paper must NOT be treated as ground truth for citation or scientific quality. Three caveats: (1) **no associated evaluation artifact survived** (`quality_report.json` was deleted in Phase 0); (2) **no machine-readable run provenance survived** (the associated `data/runs/` entry was also deleted); (3) **its 10 references have not been independently validated.** Citation and scientific-quality validation belongs in the later product-comparison phase, not in Phase 0. |

## Distinction from the two hand-written papers *[VERIFIED]*

Per the current-state report and confirmed in this recovery: the other two deleted historical papers were **hand-written**, not pipeline output:

| Paper | Author | Evidence |
|---|---|---|
| `GoT_NSR_Research_Paper.md` (THIS recovery) | **Pipeline** ("Elephant Rock Research Platform") | front-matter author + Appendix A pipeline config + structured gap-analysis methodology |
| `ai_empirical_validity_paper.md` (deleted) | **Hand-written** (the Lead) | file note: "pipeline's synthesis stage was broken… produced only ~1,500-char stubs" |
| `self_improvement_research_paper.md` (deleted) | **Hand-written** (the Lead) | survey/position paper format inconsistent with pipeline output |

**The two hand-written papers are NOT presented as pipeline-generation proof.** Only `GoT_NSR_Research_Paper` qualifies as an authentic pipeline-generated historical output. They are recorded here as historical research outputs but are excluded from the regression-baseline role.

## Exit condition *[VERIFIED — classification corrected on acceptance]*

> At least one authentic pipeline-generated historical paper is recovered, provenance-bound, and classified for future comparison.

**Met, with a scoped role.** `GoT_NSR_Research_Paper.md` (+ `.tex`) recovered byte-identical from `e2c0171^`, provenance fully documented, assessed as a complete 4,347-word paper with 10 references. **Classified as a historical workflow fixture** (compare completion / length / structure / section coverage / export formats / user effort), **not as a quality gold standard** — no evaluation artifact survived, no machine-readable run provenance survived, and its 10 references have not been independently validated. Citation and scientific-quality validation belongs in the later product-comparison phase.

---

*End of Work Package 0C. Recovery + documentation only; no repository source or product artifact modified.*
