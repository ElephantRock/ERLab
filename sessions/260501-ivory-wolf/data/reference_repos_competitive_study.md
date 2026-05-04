# Competitive Landscape: Deep Study of Reference Repositories

**Date:** 2026-05-04  
**Analyst:** Elephant Rock Lead (Ivory Wolf Session)  
**Source:** `C:\Next AI\ref\` (~600 repositories)  
**Report Version:** 1.0

---

## 1. Executive Summary

This report studies the most relevant reference repositories from a library of ~600 projects, comparing them against Elephant Rock's autonomous research pipeline. Three tiers of competitive relevance emerged:

**Tier 1 — Direct Competitors (research automation):**
- AI-Scientist (Sakana AI) — v1 and v2
- RD-Agent (Microsoft) — R&D automation with MLE-bench leadership
- Autoresearch (Karpathy/Goenka) — already studied

**Tier 2 — Methodological Overlaps (self-improvement/optimization):**
- EvoPrompt, TextGrad, Self-Refine, Reflexion — iterative improvement
- ScoreFlow, MLGym — automated ML engineering

**Tier 3 — Component-Level Relevance (agents/evaluation/knowledge):**
- MetaGPT, OpenHands, AutoAgent — multi-agent frameworks
- Critic-V, CriticEval — evaluation frameworks
- ToolLLM, ToolRL — tool use and learning
- RAG-Anything, StructRAG — retrieval-augmented generation
- OpenNARS, Soar — cognitive architectures (already in Elephant Rock)

---

## 2. Tier 1: Direct Competitors

### 2.1 AI-Scientist v1 (Sakana AI)

**Architecture:** 6-module pipeline
```
generate_ideas.py → check_idea_novelty() → perform_experiments.py → perform_writeup.py → perform_review.py → [perform_improvement()]
```

**Pipeline flow:**
1. **Idea Generation** (546 lines): LLM generates ideas with `Name`, `Title`, `Experiment`, `Interestingness` (1-10), `Feasibility` (1-10), `Novelty` (1-10). Iterative refinement with N reflections. Seed ideas from JSON.
2. **Novelty Check** (within generate_ideas.py): LLM uses Semantic Scholar API iteratively — up to 10 rounds of searching, each round the LLM decides if it's found a prior that invalidates the idea. Binary novel/not-novel decision.
3. **Experiment Execution** (166 lines): Uses **Aider** (AI coding assistant) to modify `experiment.py` and `plot.py` based on the idea description. Runs the experiment, collects metrics.
4. **Paper Writeup** (579 lines): LLM writes LaTeX paper section by section (Abstract, Introduction, Background, Method, Experimental Setup, Results, Conclusion). Uses Semantic Scholar for citations.
5. **Review** (395 lines): GPT-4o generates ICLR-style review with Soundness, Presentation, Contribution, Overall (1-10), Decision (Accept/Reject). 5-reflection ensemble review.
6. **Improvement** (optional): Reviews feed back to Aider to improve the paper.

**Key features:**
- Template-based: Each domain (NanoGPT, 2D Diffusion, Grokking) has its own `experiment.py`, `prompt.json`, `seed_ideas.json`, `latex/template.tex`
- Aider for code modification: The AI uses Aider (a coding assistant) to modify experiment files
- Multi-GPU parallel execution: Workers process ideas in parallel across GPUs
- Literature search via Semantic Scholar API or OpenAlex
- Cost: ~$15/paper with Claude 3.5 Sonnet
- Success rate: Depends on model and template complexity

**Comparison with Elephant Rock:**

| Dimension | AI-Scientist v1 | Elephant Rock |
|-----------|----------------|---------------|
| Scope | ML-only (code-based experiments) | Any research domain (literature-based) |
| Idea generation | Single LLM, template-seeded | Multi-agent (Ideator/Critic/Refiner + Borda Tournament) |
| Novelty check | Semantic Scholar API, LLM decides | Vector store + knowledge graph + truth values |
| Experiment execution | Aider modifies code, runs on GPU | Sandboxed experiment execution (BATCH-49) |
| Paper generation | LaTeX section-by-section | Markdown research paper via LLM synthesis |
| Review | GPT-4o ensemble (5 reviewers) | Quality gate scores (novelty/feasibility/impact) |
| Knowledge persistence | JSON files per run | PostgreSQL + ChromaDB + knowledge graph |
| Multi-agent | No (single LLM) | Yes (Ideator, Critic, Refiner, consciousness states) |
| Self-improvement | No | Yes (quality ratchet, evolution engine) |
| Cross-run learning | No (each idea is independent) | Yes (cross-run gap dedup, truth revision) |
| Templates | Required (3 built-in) | Domain-agnostic (user provides queries) |
| Codebase size | ~2,457 lines | 77,516+ lines |

**Elephant Rock advantages:**
- Multi-agent architecture produces better ideas (Borda Tournament)
- Knowledge persistence enables cross-run learning
- No template requirement — works on any domain
- Self-improvement engine
- Full web UI with 19 pages

**AI-Scientist advantages:**
- Actually runs experiments (code execution + GPU training)
- Produces LaTeX papers with real experimental results
- Semantic Scholar novelty checking with iterative search
- Review system with ICLR-style scoring
- Lower cost per paper ($15 vs ~$40-50 for Elephant Rock)

### 2.2 AI-Scientist v2 (Sakana AI)

**Architecture:** Agentic Tree Search
```
perform_ideation.py → launch_scientist_bfts.py (Best-First Tree Search)
```

**Key innovation: Progressive agentic tree search (BFTS)**
- No human-authored templates required
- Generalizes across ML domains
- Experiment manager agent guides tree search
- Multiple parallel exploration paths (`num_workers`)
- Max debug depth for failing nodes
- Multiple initial root nodes (`num_drafts`)

**Pipeline:**
1. **Ideation** (`perform_ideation_temp_free.py`): Takes a topic description markdown file, generates ideas with Semantic Scholar novelty checking
2. **BFTS** (`launch_scientist_bfts.py`): Best-first tree search over experiment implementations. Each node is a code modification. Branches explore different approaches.
3. **Writeup**: Section-by-section LaTeX generation with citation rounds
4. **Review**: GPT-4o ensemble review

**Configuration** (`bfts_config.yaml`):
- `num_workers`: Parallel exploration paths (3)
- `steps`: Maximum nodes to explore (21)
- `num_seeds`: Initial root nodes (3)
- `max_debug_depth`: Debug attempts before abandoning path
- `debug_prob`: Probability of attempting debug
- `num_drafts`: Independent trees to grow

**Key difference from v1:** v2 is exploratory and generalized. v1 follows well-defined templates for high success rates. v2 has lower success rates but broader applicability.

**Comparison with Elephant Rock:**

| Dimension | AI-Scientist v2 | Elephant Rock |
|-----------|----------------|---------------|
| Search strategy | Best-first tree search over code | Sequential pipeline with multi-agent debate |
| Domain generality | ML-only but template-free | Any domain with literature |
| Experiment running | Yes (GPU-based, tree search) | Limited (sandboxed) |
| Template requirement | No (template-free) | No |
| Tree search | Core innovation (BFTS) | No (linear pipeline) |
| Cost | $15-20/run | $40-50/run |

**Key takeaway for Elephant Rock:** The tree search pattern is powerful — instead of a single path through the pipeline, exploring multiple branches and selecting the best could improve idea quality. Elephant Rock's current linear pipeline could benefit from branching at the idea generation stage.

### 2.3 RD-Agent (Microsoft)

**Architecture:** Research + Development dual-agent loop
```
R-Agent (proposes ideas) → D-Agent (implements them) → Evaluate → Feed back to R-Agent
```

**Core modules (rdagent/core/):**
- `evolving_agent.py` — Agent that evolves over iterations
- `evolving_framework.py` — Framework for evolutionary optimization
- `knowledge_base.py` — Persistent knowledge across iterations
- `evaluation.py` — Evaluation metrics and scoring
- `proposal.py` — Idea/factor/model proposals
- `developer.py` — Code implementation agent
- `interactor.py` — Agent interaction protocols

**Scenarios:**
1. **Quant Trading (RD-Agent-Q):** Data-centric multi-agent framework for factor-model co-optimization. 2× higher ARR than benchmark factor libraries, 70% fewer factors.
2. **Data Science / Kaggle:** Top performer on MLE-bench (30.22% vs AIDE's 16.9%)
3. **Research Copilot:** Reads papers/reports and implements models/factors
4. **Data Mining:** Iteratively proposes data & models, learns from data

**Key innovation: Knowledge-driven R&D loop**
- R-Agent proposes based on accumulated knowledge
- D-Agent implements and returns results
- Results feed back into knowledge base
- Knowledge base persists across iterations (similar to Elephant Rock's knowledge graph)

**Comparison with Elephant Rock:**

| Dimension | RD-Agent | Elephant Rock |
|-----------|---------|---------------|
| R/D split | Explicit (R-Agent + D-Agent) | Integrated (Ideator/Critic/Refiner) |
| Domain | ML + Quant Trading | Scientific research (any domain) |
| Code execution | Yes (Docker-sandboxed) | Yes (sandboxed experiments) |
| Knowledge base | Persistent, evolving | PostgreSQL + ChromaDB + knowledge graph |
| Evaluation | Real metrics (ARR, Kaggle score) | LLM-based quality scores |
| Web UI | Yes (real-time interaction + trace viewing) | Yes (19 pages) |
| Open source | Yes (PyPI package, Docker) | Yes (local development) |
| MLE-bench | #1 position | Not benchmarked |
| Paper generation | No | Yes (research papers from pipeline output) |
| Multi-agent | 2 (R + D) | 3+ (Ideator/Critic/Refiner/Consciousness) |

**Key takeaway for Elephant Rock:** The R/D split is elegant — one agent proposes, another implements, and results feed back. Elephant Rock's multi-agent system is richer for idea generation but lacks the tight implementation loop. The knowledge-driven evolution pattern matches Elephant Rock's self-improvement engine conceptually but is more mature in implementation.

---

## 3. Tier 2: Methodological Overlaps

### 3.1 EvoPrompt

**Concept:** Evolutionary prompt optimization using LLMs. Generates prompt variants, evaluates them, selects the best, mutates/crosses over, repeats.

**Relevance to Elephant Rock:** The evolutionary approach maps directly to Elephant Rock's `evolution.py` self-improvement engine. Both use iterative generation → evaluation → selection. Elephant Rock already implements this pattern.

### 3.2 TextGrad

**Concept:** Automatic "differentiation" via text — treats LLM responses as computational graphs, computes "gradients" (critique) and backpropagates to improve inputs.

**Architecture:**
- `variable.py` — Text variables with gradient tracking
- `loss.py` — Textual loss functions (critique)
- `engine.py` — Backpropagation engine
- `model.py` — LLM interface

**Relevance to Elephant Rock:** TextGrad's "textual gradient" concept maps to Elephant Rock's Critic agent. The key insight is making critique structured and actionable — not just "this could be better" but specific suggestions that can be "backpropagated" to improve the original. Elephant Rock's Refiner agent does this but could benefit from TextGrad's formal gradient-tracking pattern.

### 3.3 Self-Refine

**Concept:** Iterative self-refinement without external feedback. LLM generates → provides self-feedback → refines → repeats until convergence.

**Architecture:** Per-task modules (acronym, commongen, gsm, pie, readability, responsegen, sentiment_reversal) with `task_init.py` → `feedback.py` → `task_iterate.py`.

**Relevance to Elephant Rock:** Self-Refine's init → feedback → iterate pattern is identical to Elephant Rock's idea refinement stage. The convergence detection (stop when improvement plateaus) is something Elephant Rock could adopt — currently the pipeline has a fixed number of refinement rounds.

### 3.4 Reflexion

**Concept:** Language agents with verbal reinforcement learning. Agent acts → gets verbal feedback (not scalar reward) → stores reflection in memory → uses reflection to improve future actions.

**Architecture:**
- HotpotQA (multi-hop QA)
- ALFWorld (embodied instruction following)
- WebShop (web navigation)
- Programming tasks

**Relevance to Elephant Rock:** Reflexion's key innovation is **verbal reinforcement learning** — instead of scalar rewards, the agent receives natural language critiques that it stores and retrieves for future decisions. Elephant Rock's self-improvement engine and knowledge graph serve a similar purpose, but Reflexion's explicit memory-of-failures pattern could strengthen the gap analysis stage.

### 3.5 ScoreFlow

**Concept:** Multi-agent optimization framework using Score-based Flow. Multiple agents collaborate, with a scoring mechanism guiding the flow of information.

**Relevance to Elephant Rock:** ScoreFlow's score-guided multi-agent flow is conceptually similar to Elephant Rock's quality gate system. The scoring mechanism determines which agents' outputs are used in subsequent stages — similar to Elephant Rock's Borda Tournament for idea selection.

### 3.6 MLGym

**Concept:** A framework and benchmark for evaluating LLM agents on AI research tasks. Provides standardized environments for ML research automation.

**Relevance to Elephant Rock:** MLGym provides a benchmarking framework. Elephant Rock currently has no external benchmark for measuring research quality. Adopting or building on MLGym's evaluation methodology would provide objective quality metrics.

---

## 4. Key Architectural Patterns Across Repos

### 4.1 The Generate → Evaluate → Refine Loop

Present in ALL competitive systems:
- **AI-Scientist:** generate ideas → novelty check → experiment → writeup → review
- **RD-Agent:** R proposes → D implements → evaluate → feed back
- **Autoresearch:** modify → verify → keep/discard → repeat
- **Self-Refine:** generate → self-feedback → refine → repeat
- **TextGrad:** forward → compute gradient → backpropagate
- **Elephant Rock:** search literature → analyze gaps → generate ideas → evaluate → refine

**Pattern:** Every system has a generation step, an evaluation step, and a refinement/selection step. The differences are in:
1. **Who generates:** Single LLM vs. multi-agent debate
2. **Who evaluates:** LLM self-evaluation vs. external tools vs. ensemble
3. **How refinement works:** Iterative improvement vs. evolutionary selection vs. tree search

### 4.2 Knowledge Persistence

| System | Knowledge Storage | Cross-run? |
|--------|-------------------|-----------|
| AI-Scientist v1 | JSON files per idea | No |
| AI-Scientist v2 | Experiment logs | No |
| RD-Agent | Knowledge base (persistent) | Yes |
| Autoresearch | Git history | Yes (git log) |
| Elephant Rock | PostgreSQL + ChromaDB + knowledge graph | Yes |

**Pattern:** Knowledge persistence across iterations is what separates toys from production systems. Elephant Rock and RD-Agent are the only systems with structured cross-run knowledge.

### 4.3 Tree Search vs. Linear Pipeline

| System | Search Strategy |
|--------|----------------|
| AI-Scientist v1 | Linear (idea → experiment → paper) |
| AI-Scientist v2 | Best-first tree search |
| RD-Agent | Evolutionary loop |
| Autoresearch | Linear with rollback |
| Elephant Rock | Linear pipeline |

**Pattern:** Tree search (v2) explores multiple branches, while linear pipelines (v1, Elephant Rock) follow a single path. Tree search has higher cost but better results. Elephant Rock's multi-agent Borda Tournament partially compensates — it evaluates multiple ideas in parallel but doesn't branch the pipeline itself.

### 4.4 Experiment Execution

| System | Can Run Experiments? | How? |
|--------|---------------------|------|
| AI-Scientist v1/v2 | Yes | Aider modifies code, runs on GPU |
| RD-Agent | Yes | Docker-sandboxed code execution |
| Autoresearch | Yes | Shell commands + git rollback |
| Elephant Rock | Limited | Sandboxed experiment execution (BATCH-49) |
| Self-Refine | No | LLM-only |

**Pattern:** The most capable systems can actually run code. Elephant Rock's sandboxed execution (added in BATCH-49) is a step in the right direction but needs to reach parity with AI-Scientist's Aider-based code modification.

---

## 5. Gap Analysis: Elephant Rock vs. Competitive Landscape

### 5.1 What Elephant Rock Does Better

1. **Multi-agent idea generation:** Borda Tournament with Ideator/Critic/Refiner > single-LLM generation in AI-Scientist
2. **Knowledge persistence:** PostgreSQL + ChromaDB + knowledge graph with truth values > JSON files or git history
3. **Cross-run learning:** Gap dedup + truth revision + knowledge graph > no cross-run learning in competitors
4. **Domain generality:** No templates required > template-bound (AI-Scientist v1) or ML-only (all competitors)
5. **Self-improvement:** Quality ratchet + evolution engine > no self-improvement in any competitor
6. **Consciousness architecture:** 5-state machine + impasse detection + curiosity drive > no comparable system
7. **Frontend:** 19-page web UI with real-time WebSocket > CLI-only in most competitors

### 5.2 What Competitors Do Better

1. **Experiment execution:** AI-Scientist runs real experiments on GPU with code modification via Aider. Elephant Rock's sandboxed execution is limited.
2. **Novelty checking:** AI-Scientist's iterative Semantic Scholar search with LLM-judged novelty is more rigorous than Elephant Rock's vector store similarity.
3. **Paper generation:** AI-Scientist produces LaTeX papers with real experimental results. Elephant Rock's papers are literature-synthesis only.
4. **Review system:** AI-Scientist's ensemble review (5 GPT-4o reviewers, ICLR-style scoring) is more rigorous than Elephant Rock's quality gates.
5. **Tree search:** AI-Scientist v2's best-first tree search explores more of the idea space than Elephant Rock's linear pipeline.
6. **Cost efficiency:** $15/paper (AI-Scientist) vs. ~$40-50/paper (Elephant Rock)
7. **Benchmarking:** RD-Agent is #1 on MLE-bench. Elephant Rock has no external benchmark.
8. **R/D split:** RD-Agent's explicit Research/Development agent split with implementation feedback is more effective than Elephant Rock's generation-only approach.

### 5.3 Critical Gaps (Priority Order)

| # | Gap | Priority | Effort | Impact |
|---|-----|----------|--------|--------|
| 1 | No real experiment execution (Aider-like code modification) | CRITICAL | High | Would transform Elephant Rock from literature-synthesis to full research automation |
| 2 | No Semantic Scholar novelty checking (iterative search) | HIGH | Medium | Current vector store similarity is insufficient for novelty validation |
| 3 | No LaTeX paper generation with experimental results | HIGH | Medium | Current markdown papers lack rigor without experimental data |
| 4 | No ensemble review system | MEDIUM | Low | Quality gates are LLM-based but single-agent; ensemble would improve reliability |
| 5 | No tree search at pipeline level | MEDIUM | High | Linear pipeline misses exploration opportunities |
| 6 | No external benchmarking | MEDIUM | Medium | MLE-bench or similar would provide objective quality metrics |
| 7 | No R/D agent split | LOW | High | Multi-agent architecture partially addresses this |
| 8 | Cost per paper too high | LOW | Medium | Multi-agent architecture inherently costs more |

---

## 6. Actionable Recommendations

### 6.1 Immediate (Next Sprint)

**REC-01: Semantic Scholar Novelty Checking**
- Add iterative Semantic Scholar API search during novelty evaluation
- LLM judges novelty by searching for prior work, up to 10 rounds
- Similar to AI-Scientist's `check_idea_novelty()` but integrated into the pipeline
- Estimated effort: 2-3 days

**REC-02: Ensemble Review System**
- Instead of single quality gate evaluation, use 3-5 LLM evaluations with ICLR-style scoring
- Aggregate scores: Soundness, Novelty, Significance, Presentation, Overall
- Accept/reject threshold with confidence scoring
- Estimated effort: 1-2 days

### 6.2 Medium-Term (Next Roadmap)

**REC-03: Aider Integration for Experiment Execution**
- Integrate Aider (or similar AI coding assistant) into the sandboxed execution environment
- Allow pipeline to generate and run code experiments based on ideas
- Collect real metrics (accuracy, loss, F1, etc.) as evidence
- This would make Elephant Rock a FULL research automation platform, not just literature synthesis
- Estimated effort: 2-3 weeks

**REC-04: LaTeX Paper Generation**
- Add LaTeX template system for research paper output
- Include experimental results (if REC-03 implemented), tables, figures
- Semantic Scholar citations integrated into LaTeX
- PDF output alongside current markdown
- Estimated effort: 1-2 weeks

**REC-05: Pipeline Tree Search**
- Add branching at the idea generation stage
- Multiple parallel idea paths explored, best selected via quality scores
- Similar to AI-Scientist v2's BFTS but adapted for literature-based research
- Estimated effort: 2-3 weeks

### 6.3 Long-Term (Strategic)

**REC-06: External Benchmarking**
- Evaluate Elephant Rock on MLE-bench or build a research-quality benchmark
- Compare against AI-Scientist v1/v2 and RD-Agent on same tasks
- Publish results for credibility

**REC-07: Knowledge-Driven R/D Loop**
- Adopt RD-Agent's R/D split: Research agent proposes, Development agent implements
- Results feed back to knowledge base, informing future proposals
- Evolution across runs, not just within runs

---

## 7. Summary Matrix

| Feature | AI-Scientist v1 | AI-Scientist v2 | RD-Agent | Autoresearch | Elephant Rock |
|---------|----------------|----------------|----------|-------------|---------------|
| Domain | ML only | ML only | ML + Quant | Any measurable | Any research |
| Multi-agent | No | No | R+D dual | No | Yes (3+) |
| Experiment exec | Yes (Aider) | Yes (BFTS) | Yes (Docker) | Yes (Shell) | Limited |
| Novelty check | Semantic Scholar | Semantic Scholar | Knowledge base | Git history | Vector store |
| Paper generation | LaTeX | LaTeX | No | No | Markdown |
| Review system | Ensemble (5) | Ensemble (5) | Real metrics | Metric-based | Quality gates |
| Knowledge persist | No | No | Yes | Git | Yes (DB+Vector+Graph) |
| Cross-run learning | No | No | Yes | Yes (git) | Yes (dedup+truth) |
| Self-improvement | No | No | Evolutionary | Metric-driven | Quality ratchet |
| Tree search | No | Yes (BFTS) | No | No | No |
| Web UI | No | No | Yes | No | Yes (19 pages) |
| Cost/paper | ~$15 | ~$20 | N/A | Varies | ~$40-50 |
| Codebase (LOC) | ~2,500 | ~3,000 | ~10,000+ | ~12,000 (docs) | 77,516 |
| External benchmark | No | No | MLE-bench #1 | No | No |

---

## 8. Key Insight

**Elephant Rock's unique advantage is its knowledge architecture.** No other system has:
- A persistent knowledge graph with OpenNARS truth values
- Cross-run gap deduplication with truth revision
- A 5-state consciousness machine with impasse detection
- Multi-agent Borda Tournament idea selection
- Self-improvement with quality ratchet

**Elephant Rock's critical gap is experiment execution.** All three Tier 1 competitors can run real experiments and collect real metrics. Elephant Rock generates ideas from literature but cannot validate them empirically. Closing this gap would make Elephant Rock the most comprehensive autonomous research platform.

The path forward is clear: **preserve the knowledge architecture advantage while adding experiment execution capability.** Elephant Rock's 77,516-line codebase and 1,833 tests provide a robust foundation that competitors lack. The missing piece is the implementation feedback loop — the ability to not just propose ideas, but to test them and learn from the results.

---

*End of report.*
