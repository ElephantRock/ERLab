# AutoResearchClaw — Comprehensive Competitive Study

**Repository**: https://github.com/aiming-lab/AutoResearchClaw  
**Stars**: 11.9K | **Forks**: 1.4K | **Commits**: 235 | **License**: MIT  
**Date**: 2026-05-06  
**Authors**: Liu, Jiaqi; Xia, Peng; Han, Siwei; Qiu, Shi; Zhang, Letian; Chen, Guiming; Tu, Haoqin; Yang, Xinyu; Zhou, Jiawei; Zhu, Hongtu; Li, Yun; Zhang, Jiaheng; Zhou, Yuyin; Zheng, Zeyu; Xie, Cihang; Ding, Mingyu; Yao, Huaxiu (UC Santa Cruz, UNC Chapel Hill)

---

## 1. What It Is

**AutoResearchClaw** is a fully autonomous research pipeline that transforms a single research idea into a conference-ready academic paper — complete with real literature, runnable experiments, statistical analysis, auto-generated figures, verified citations, and NeurIPS/ICML/ICLR-formatted LaTeX. The entire process runs end-to-end without human intervention, or with optional human-in-the-loop co-pilot guidance.

**Tagline**: "Chat an Idea. Get a Paper. Autonomous, Collaborative & Self-Evolving."

### Key Differentiator
This is the most complete autonomous research system publicly available. Unlike information retrieval tools (DeepResearch, dzhng/deep-research) or gap-analysis platforms (Elephant Rock), AutoResearchClaw covers the **full research lifecycle** — from idea to compiled PDF.

---

## 2. Architecture Overview

### 2.1 Codebase Statistics

| Metric | Value |
|--------|-------|
| **Total Lines of Code** | ~54,348 (across 8 generated papers) |
| **Source Modules** | 28 top-level directories under `researchclaw/` |
| **Test Suite** | 2,699 tests passing |
| **Pipeline Stages** | 23 stages across 8 phases |
| **Test Files** | 80+ test files |
| **Supported LLMs** | OpenAI, Anthropic (via Claude Code), DeepSeek, Volcengine, BytePlus, OpenRouter, MiniMax, ACP protocol |
| **Literature Sources** | OpenAlex, Semantic Scholar, arXiv |
| **Export Formats** | NeurIPS 2025, ICLR 2026, ICML 2026 LaTeX templates |

### 2.2 Module Structure

```
researchclaw/
├── agents/                    # Multi-agent subsystems
│   ├── benchmark_agent/       # 4-agent benchmark pipeline (Surveyor→Selector→Acquirer→Validator)
│   ├── code_searcher/         # Code search for reproducibility
│   └── figure_agent/          # 5-agent figure pipeline (Planner→CodeGen→Renderer→Critic→Integrator)
├── assessor/                  # Paper quality assessment
├── calendar/                  # Scheduled research runs
├── collaboration/             # Human-AI collaborative editing
├── copilot/                   # Co-pilot mode implementation
├── dashboard/                 # Web dashboard
├── data/                      # Data management
├── docker/                    # Docker sandbox configuration
├── domains/                   # Domain-specific adapters (neuroscience, robotics)
├── experiment/                # Experiment execution engine
│   ├── sandbox.py             # Local sandbox (AST validation, subprocess execution)
│   ├── docker_sandbox.py      # Docker-based sandbox (network policies)
│   ├── ssh_sandbox.py         # Remote GPU execution
│   ├── colab_sandbox.py       # Google Colab execution
│   ├── code_agent.py          # Multi-provider code generation (LLM, Claude Code, Codex)
│   ├── validator.py           # AST-based code validation
│   ├── agentic_sandbox.py     # Agentic sandbox with multi-round repair
│   ├── harness_template.py    # Immutable experiment harness
│   ├── metrics.py             # Metric extraction from stdout
│   └── evaluators/            # Convergence, statistical evaluators
├── feedback/                  # Feedback collection
├── hitl/                      # Human-in-the-Loop system (v0.4.0)
├── knowledge/                 # Knowledge base management
├── literature/                # Multi-source literature search
│   ├── openalex_client.py     # OpenAlex API client
│   ├── semantic_scholar.py    # Semantic Scholar API client
│   ├── arxiv_client.py        # arXiv API client
│   ├── search.py              # Unified search with deduplication
│   ├── verify.py              # 4-layer citation verification
│   ├── novelty.py             # Novelty scoring
│   ├── cache.py               # Result caching
│   └── trends.py              # Trend analysis
├── llm/                       # LLM abstraction layer
├── mcp/                       # Model Context Protocol integration
├── memory/                    # Experiment memory system
├── metaclaw_bridge/           # Cross-run learning via MetaClaw
├── overleaf/                  # Overleaf integration
├── pipeline/                  # Core 23-stage pipeline
│   ├── runner.py              # Pipeline orchestration (780+ lines)
│   ├── executor.py            # Stage execution with HITL hooks
│   ├── stages.py              # Stage enum, transitions, gate logic
│   └── stage_impls/           # Stage-specific implementations
│       ├── _topic.py          # Stages 1-2
│       ├── _literature.py     # Stages 3-6
│       ├── _synthesis.py      # Stages 7-8
│       ├── _experiment_design.py  # Stage 9
│       ├── _code_generation.py    # Stage 10
│       ├── _execution.py      # Stages 11-13
│       ├── _analysis.py       # Stages 14-15
│       ├── _paper_writing.py  # Stages 16-17
│       └── _review_publish.py # Stages 18-23
├── project/                   # Project management
├── server/                    # HTTP server
├── servers/                   # MCP server implementations
├── skills/                    # 19 pre-loaded research skills
├── templates/                 # Conference LaTeX templates
├── trends/                    # Research trend analysis
├── utils/                     # Utilities
├── voice/                     # Voice interface
├── web/                       # Web crawler for papers
└── wizard/                    # Setup wizard
```

### 2.3 The 23-Stage Pipeline

```
Phase A: Research Scoping          Phase E: Experiment Execution
  1. TOPIC_INIT                      12. EXPERIMENT_RUN
  2. PROBLEM_DECOMPOSE               13. ITERATIVE_REFINE  ← self-healing

Phase B: Literature Discovery      Phase F: Analysis & Decision
  3. SEARCH_STRATEGY                 14. RESULT_ANALYSIS    ← multi-agent
  4. LITERATURE_COLLECT  ← real API  15. RESEARCH_DECISION  ← PIVOT/REFINE
  5. LITERATURE_SCREEN   [gate]
  6. KNOWLEDGE_EXTRACT               Phase G: Paper Writing
                                     16. PAPER_OUTLINE
Phase C: Knowledge Synthesis         17. PAPER_DRAFT
  7. SYNTHESIS                       18. PEER_REVIEW        ← evidence check
  8. HYPOTHESIS_GEN    ← debate      19. PAPER_REVISION

Phase D: Experiment Design         Phase H: Finalization
  9. EXPERIMENT_DESIGN   [gate]      20. QUALITY_GATE      [gate]
 10. CODE_GENERATION                 21. KNOWLEDGE_ARCHIVE
 11. RESOURCE_PLANNING               22. EXPORT_PUBLISH     ← LaTeX
                                     23. CITATION_VERIFY    ← relevance check
```

**Gate stages** (5, 9, 20) pause for human approval.  
**Decision loops**: Stage 15 can trigger REFINE (→ Stage 13) or PIVOT (→ Stage 8).  
**Max pivots**: 2 (prevents infinite loops).

---

## 3. Technical Deep Dives

### 3.1 Literature Search (Stages 3-6)

**Multi-source architecture** with graceful degradation:

```python
# Source priority: OpenAlex (10K/day) → Semantic Scholar (1K/5min) → arXiv (1/3s)
_DEFAULT_SOURCES = ("openalex", "semantic_scholar", "arxiv")
```

**Deduplication** is 3-layer:
1. **DOI matching** — highest confidence
2. **arXiv ID matching** — cross-source linking
3. **Fuzzy title matching** — normalized lowercase, punctuation-stripped

**When a source fails** (rate limit, network error), it falls back to cached results. This is production-grade resilience.

**Scale**: 300-470 papers collected per run, pruned to 25-60 cited references.

### 3.2 Code Generation & Execution (Stages 10-13)

**Three code generation providers**:

| Provider | How It Works |
|----------|-------------|
| **LLM** | OpenAI-compatible chat API, multi-file extraction from markdown |
| **Claude Code** | `claude -p` CLI subprocess, reads/writes files directly |
| **Codex** | `codex exec` CLI subprocess, sandbox-write mode |

**CodeAgent protocol** defines three operations:
- `generate()` — Create experiment code from plan (Stage 10)
- `refine()` — Improve code based on run results (Stage 13)  
- `repair()` — Fix validation/runtime issues

**Sandbox execution** has 4 backends:
1. **Local sandbox** — subprocess with AST validation, timeout, metric extraction
2. **Docker sandbox** — isolated container with network policies
3. **SSH sandbox** — remote GPU server execution
4. **Colab sandbox** — Google Colab notebook execution

**Self-healing loop** (Stage 13):
1. Run experiment code
2. Parse metrics from stdout
3. Detect NaN/Inf divergence
4. If failed: LLM repairs code, retry up to 10 iterations
5. Experiment diagnosis → quality assessment → repair loop (up to 3 cycles)

**Immutable experiment harness**: Injected before project files, prevents overwriting by generated code.

**Metric extraction** parses structured stdout:
```
condition=baseline accuracy: 0.82
condition=ours accuracy: 0.85
SUMMARY condition=ours metric=accuracy mean=0.85 std=0.02
```

### 3.3 Hardware-Aware Execution

Auto-detects hardware and adapts code generation:
- **NVIDIA CUDA** — full GPU support
- **Apple MPS** — Metal Performance Shaders
- **CPU-only** — reduced experiment scale

### 3.4 Paper Writing (Stages 16-19)

**Section-by-section drafting** (5,000-6,500 words):
- Paper outline → section drafts → peer review → revision
- Anti-fabrication guard: verified experiment data only
- Revision length guard: prevents bloat
- Anti-disclaimer enforcement: no "AI-generated" watermarks

**Multi-agent peer review**:
- Methodology-evidence consistency checks
- 7-dimension review scoring
- NeurIPS checklist compliance

**Conference templates**:
- `neurips_2025`, `iclr_2026`, `icml_2026`
- Markdown → LaTeX with math, tables, figures, cross-refs, `\cite{}`

### 3.5 Citation Verification (Stage 23)

**4-layer verification pipeline**:
1. **arXiv ID check** — verify paper exists on arXiv
2. **CrossRef/DataCite DOI** — verify DOI resolves
3. **Semantic Scholar title match** — fuzzy title matching
4. **LLM relevance scoring** — verify citation is relevant to the paper

**Hallucinated references are automatically removed**. Unverified numbers are sanitized.

### 3.6 Anti-Fabrication System

- **VerifiedRegistry** — enforces ground-truth experiment data in papers
- **Experiment diagnosis** — auto-diagnoses failed experiments and repairs before writing
- **Sanitization** — fabricated numbers replaced with `---`
- **Paper-evidence consistency** — cross-checks claims against actual experiment results

### 3.7 Human-in-the-Loop (HITL) System (v0.4.0)

**6 intervention modes**:

| Mode | Description |
|------|-------------|
| `full-auto` | No human intervention |
| `gate-only` | Pause at 3 gate stages |
| `checkpoint` | Pause at phase boundaries |
| `co-pilot` | Deep collaboration at critical stages |
| `step-by-step` | Pause after every stage |
| `custom` | Per-stage policies via config |

**Key capabilities**:
- **SmartPause** — confidence-driven dynamic intervention
- **Cost guardrails** — budget monitoring with 50%/80%/100% alerts
- **Intervention learning (ALHF)** — learns from review patterns
- **Branch exploration** — fork pipeline for parallel hypotheses
- **3 adapters** — CLI, WebSocket, MCP

### 3.8 Self-Learning (MetaClaw Integration)

Cross-run knowledge transfer:
```
Run N → failures/warnings → Lessons → Skill conversion → arc-* skills
Run N+1 → skills injected into every LLM prompt → fewer retries
```

**Measured improvement**: +18.3% robustness, -24.8% retry rate, -40.0% refine cycles.

### 3.9 OpenCode Beast Mode

Complex experiments auto-routed to [OpenCode](https://github.com/anomalyco/opencode):
- Generates multi-file projects with custom architectures
- Complexity scoring: 0.0-1.0 threshold
- Graceful fallback to LLM provider
- Budget control and timeout management

---

## 4. Showcase Results — 8 Papers

### Batch A: Mathematics, Statistics & Sciences

| Paper | Domain | LOC | Runtime | Pages | Refs | Figures |
|-------|--------|-----|---------|-------|------|---------|
| I. Random Matrix Theory | Math | 10,290 | 2h25m | 16 | 26 | 5 |
| II. Weak IV Estimators | Stats | 10,062 | 2h56m | 14 | 41 | 6 |
| III. SIR/SEIR Identifiability | Bio | 9,374 | 2h23m | 18 | 29 | 6 |
| IV. Krylov Preconditioners | Computing | 14,557 | 2h30m | 16 | 33 | 4 |

### Batch B: Machine Learning & AI (NVIDIA RTX 6000 Ada 48GB)

| Paper | Domain | LOC | Runtime | Pages | Refs | Figures |
|-------|--------|-----|---------|-------|------|---------|
| V. GARD (LoRA PEFT) | NLP | 2,894 | 50m | 17 | 60 | 7 |
| VI. LACE (RL Exploration) | RL | 2,067 | 6h48m | 11 | 25 | 6 |
| VII. FAME (ViT Tokens) | CV | 2,873 | 3h18m | 10 | 40 | 7 |
| VIII. CRAFT (KD Robustness) | KD | 2,231 | 5h48m | 19 | 37 | 9 |

### Aggregate
- **54,348 total lines of generated Python code**
- **121 total pages** of NeurIPS-formatted papers
- **291 cited references** (99.7% verified)
- **50 auto-generated figures**
- **~27 hours total pipeline runtime** across all 8 papers

---

## 5. Comparison with Elephant Rock Platform

### 5.1 Scope Comparison

| Capability | Elephant Rock | AutoResearchClaw |
|-----------|---------------|------------------|
| **Literature Search** | OpenAlex + arXiv | OpenAlex + Semantic Scholar + arXiv |
| **Gap Analysis** | ✅ Full pipeline | Part of synthesis stage |
| **Idea Generation** | ✅ Full pipeline | ✅ Multi-agent debate |
| **Novelty Scoring** | ✅ Real embeddings | ✅ Literature-based novelty scoring |
| **Experiment Execution** | ❌ No sandbox | ✅ Full sandbox (4 backends) |
| **Code Generation** | ❌ None | ✅ Multi-provider (LLM/Claude/Codex) |
| **Paper Writing** | Proposals only | ✅ Full papers (10-19 pages) |
| **LaTeX Export** | ❌ None | ✅ NeurIPS/ICML/ICLR templates |
| **Citation Verification** | Basic | ✅ 4-layer verification pipeline |
| **Figure Generation** | ❌ None | ✅ 5-agent figure pipeline |
| **Peer Review** | ❌ None | ✅ Multi-agent review |
| **HITL** | ❌ None | ✅ 6 intervention modes |
| **Self-Learning** | ❌ None | ✅ MetaClaw cross-run learning |
| **Conference Templates** | ❌ None | ✅ 3 templates |
| **Docker** | ❌ None | ✅ Full Docker support |
| **Remote GPU** | ❌ None | ✅ SSH + Colab backends |
| **Anti-Fabrication** | Basic | ✅ VerifiedRegistry + sanitization |
| **Pipeline Resume** | ✅ Checkpoint | ✅ Checkpoint + resume |
| **Real API Integration** | ✅ 2 sources | ✅ 3 sources + caching |
| **Frontend/UI** | ✅ Full React UI | Dashboard + CLI |
| **API Server** | ✅ FastAPI | ✅ HTTP server |

### 5.2 Where AutoResearchClaw Excels

1. **Complete research lifecycle**: Idea → paper → compiled PDF. Elephant Rock stops at proposals.
2. **Real experiment execution**: Runs actual Python code with metrics. Elephant Rock only generates ideas.
3. **Multi-provider code generation**: LLM, Claude Code, Codex backends.
4. **4-backend sandbox**: Local, Docker, SSH, Colab.
5. **Anti-fabrication**: VerifiedRegistry, sanitization, paper-evidence consistency.
6. **Conference templates**: Ready-to-submit LaTeX.
7. **Self-learning**: MetaClaw cross-run knowledge transfer.
8. **HITL**: 6 modes from full-auto to step-by-step.
9. **Figure generation**: 5-agent figure pipeline with critic-driven refinement.
10. **Showcase**: 8 real papers across 8 domains.

### 5.3 Where Elephant Rock Excels

1. **Gap identification**: Dedicated gap analysis pipeline with clustering, dedup, feedback. AutoResearchClaw embeds this in synthesis.
2. **Knowledge graph**: Vector store + knowledge graph + RAG retrieval. AutoResearchClaw has a simpler knowledge base.
3. **Web UI**: Full React SPA with 19 pages. AutoResearchClaw is primarily CLI.
4. **Embeddings**: Real 768-dim Ollama embeddings. AutoResearchClaw uses LLM-based relevance.
5. **Tree search**: Novel idea generation with tree search and Borda voting. AutoResearchClaw uses multi-agent debate.
6. **Streaming**: SSE-based real-time pipeline progress. AutoResearchClaw has CLI progress.
7. **Cost tracking**: Per-run cost tracking and budget management. AutoResearchClaw added cost guardrails in v0.4.0.
8. **Domain flexibility**: Works with any research domain. AutoResearchClaw's experiments are ML-biased.

---

## 6. Key Architectural Innovations

### 6.1 Decision Loops (PIVOT/REFINE)
Stage 15 autonomously decides:
- **PROCEED** — continue to paper writing
- **REFINE** — rollback to Stage 13, re-run experiments with tweaked params
- **PIVOT** — rollback to Stage 8, generate new hypotheses

This is the **most sophisticated autonomous control flow** in any research tool we've studied.

### 6.2 Multi-Agent Debate for Hypothesis Generation
Hypotheses are generated via structured multi-perspective debate, not single-prompt generation. This produces more diverse and novel ideas.

### 6.3 Self-Healing Experiments
When experiments fail:
1. AST validation catches structural errors
2. NaN/Inf detection catches numerical divergence
3. LLM repairs code based on error messages
4. Re-run up to 10 iterations
5. If still failing: experiment diagnosis → quality assessment → repair loop (up to 3 cycles)

### 6.4 Anti-Fabrication Pipeline
```
Experiment runs → VerifiedRegistry → Paper drafting → Sanitization → Citation verification → Final paper
```
Every number in the paper must trace back to actual experiment output.

### 6.5 Deliverable Packaging
Automatic packaging into `deliverables/` folder:
- `paper_final.md` — Final paper
- `paper.tex` — Conference LaTeX
- `references.bib` — Verified BibTeX
- `code/` — Experiment code
- `charts/` — Auto-generated figures
- `verification_report.json` — Citation integrity report
- `manifest.json` — File manifest

---

## 7. Version History & Velocity

| Version | Date | Key Addition |
|---------|------|-------------|
| v0.1.0 | 03/15/2026 | Initial release — 23-stage pipeline |
| v0.2.0 | 03/16/2026 | Multi-agent (CodeAgent, BenchmarkAgent, FigureAgent), Docker sandbox, 4-round paper audit |
| v0.3.0 | 03/17/2026 | MetaClaw cross-run learning (+18.3% robustness) |
| v0.3.1 | 03/18/2026 | OpenCode Beast Mode, Novita AI provider |
| v0.3.2 | 03/22/2026 | Cross-platform (Claude Code, Codex, Copilot, Gemini, Kimi), anti-fabrication |
| v0.4.0 | 04/01/2026 | HITL Co-Pilot (6 modes), cost guardrails, branch exploration |

**Development velocity**: 6 releases in ~18 days. Extremely fast iteration.

---

## 8. Competitive Positioning Map

```
                        Idea → Paper Completeness
                        ↑
     AutoResearchClaw ★ | ★ AI Scientist v2
                        |
                        |
    Elephant Rock ●     |
                        |
                        |
   dzhng/deep-research ○|
                        |
   DeepResearch (Alibaba)○
                        └────────────────────→ Literature Coverage
```

**AutoResearchClaw is the most complete system** — it covers the entire lifecycle from idea to compiled PDF with verified citations. No other tool does this.

---

## 9. Lessons for Elephant Rock

### 9.1 What We Should Adopt

1. **Multi-provider code generation**: Support LLM, Claude Code, Codex for experiment code
2. **Sandbox execution**: Add local subprocess sandbox for running generated code
3. **Anti-fabrication**: VerifiedRegistry-like system to prevent fabricated results
4. **Citation verification**: 4-layer verification pipeline
5. **Conference templates**: LaTeX export with NeurIPS/ICML/ICLR templates
6. **Decision loops**: PIVOT/REFINE at the analysis stage
7. **Self-healing**: Automated code repair when experiments fail
8. **Deliverable packaging**: One-command packaging of all outputs

### 9.2 What We Should NOT Copy

1. **CLI-first approach**: Elephant Rock's web UI is a competitive advantage
2. **Monolithic pipeline**: Our modular pipeline with independent stages is cleaner
3. **No knowledge graph**: Their flat knowledge base loses relational information
4. **Experiment-centric**: Our gap-analysis-first approach is more novel for research discovery

### 9.3 Integration Opportunities

1. **AutoResearchClaw as a backend**: We could generate proposals, then hand off to AutoResearchClaw for experiment execution and paper writing
2. **Literature search augmentation**: Their 3-source search + caching could enhance our OpenAlex/arXiv pipeline
3. **Anti-fabrication adoption**: Their VerifiedRegistry could strengthen our proposal quality

---

## 10. Assessment & Rating

| Dimension | Score (1-10) | Notes |
|-----------|:---:|-------|
| **Completeness** | **10** | Idea → compiled PDF. No other tool matches this. |
| **Code Quality** | **8** | Well-structured, modular, extensive test suite (2,699 tests) |
| **Documentation** | **9** | Exceptional README, showcase, integration guide, ethics guidelines |
| **Innovation** | **9** | Decision loops, self-healing, anti-fabrication, MetaClaw learning |
| **Practicality** | **8** | One-command setup, Docker, multiple LLM providers |
| **Scalability** | **7** | Sequential stages, limited parallelism |
| **Reproducibility** | **9** | SHA256 checksums, immutable manifests, versioned snapshots |
| **Ethics** | **9** | Explicit ethics guidelines, anti-fabrication, human-in-the-loop |
| **Community** | **9** | 11.9K stars, Discord, 9 language translations |
| **Testability** | **8** | 2,699 tests, e2e real LLM tests, e2e Docker tests |
| **Overall** | **8.8/10** | The gold standard for autonomous research systems |

---

## 11. Critical Observations

### 11.1 Strengths
- **Only system that produces complete papers** from a one-line idea
- **Production-grade reliability**: 4-layer citation verification, anti-fabrication, self-healing
- **Impressive showcase**: 8 real papers with real experiments and verified citations
- **Extremely fast development**: 6 releases in 18 days
- **Strong academic backing**: UC Santa Cruz + UNC Chapel Hill

### 11.2 Limitations
- **Experiment-centric**: Best for ML/CS domains with runnable experiments. Pure theoretical work would need significant adaptation.
- **Sequential pipeline**: Stages run one after another, no parallelism within a run.
- **LLM-dependent**: Quality is bounded by LLM capability. Hallucinations can still leak through.
- **No gap-specific analysis**: Unlike Elephant Rock, there's no dedicated gap identification and clustering pipeline.
- **CLI-first**: No rich web UI for visualizing pipeline progress.
- **Runtime**: 50min-7hrs per paper. Not suitable for rapid exploration.

### 11.3 Open Questions
1. **Paper quality**: Are the 8 showcase papers genuinely novel, or incremental? The showcase claims novelty scores but doesn't benchmark against human researchers.
2. **Reproducibility claims**: SHA256 checksums prove files weren't modified, but don't prove the research is reproducible by others.
3. **Real-world adoption**: 11.9K stars indicate interest, but how many users have actually submitted generated papers?
4. **Cost**: Running 8 papers with GPT-4o is expensive. No cost analysis provided.

---

## 12. Conclusion

AutoResearchClaw represents the **current state-of-the-art in autonomous research systems**. It is the only publicly available tool that can take a research idea and produce a complete, citation-verified, conference-formatted paper with real experiments. 

For Elephant Rock, it represents both a **competitive threat** (they do what we do, plus everything after) and an **inspiration** (their anti-fabrication, sandbox execution, and decision loops are patterns we should adopt). Our unique value proposition remains our **gap-analysis-first approach** and **web-based UX**, but the gap is narrowing rapidly.

The most important takeaway: **the era of "AI writes papers" is here**. AutoResearchClaw proves it's technically feasible. The question now is quality and novelty — can AI-generated papers pass peer review at top venues? That remains an open research question.
