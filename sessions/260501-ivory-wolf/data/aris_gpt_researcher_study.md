# Competitive Study: ARIS vs GPT Researcher vs Elephant Rock

**Lead:** ivory-wolf  
**Date:** 2026-05-10  
**Framework:** AIV v5.3

---

## 1. Executive Summary

Two of the most popular open-source research automation tools studied against Elephant Rock:

| Metric | ARIS (Auto-claude-code-research) | GPT Researcher | Elephant Rock |
|:-------|:--------------------------------|:---------------|:-------------|
| GitHub Stars | 8.7K | 27K | N/A (private) |
| Architecture | Skill-based Markdown workflows | Planner + Executor agents | Orchestrated pipeline (10 stages) |
| Core Model | Claude Code + Codex/GPT-5.4 | Any OpenAI-compatible LLM | Hybrid local (qwen3-4b) + cloud (glm-5.1) |
| Research Output | Full academic papers (LaTeX/PDF) | Web research reports (Markdown/PDF) | Research proposals + gap analysis + novelty scores |
| Time per run | ~3-8 hours (full pipeline) | ~3-5 minutes | ~6-18 minutes |
| Citation Integrity | Cross-model citation audit | Source tracking + URLs | Closed-book [SOURCE-X] indexing |
| Self-Review | Adversarial cross-model (GPT-5.4 xhigh) | None built-in | Local LLM novelty checking + feasibility scoring |
| Experimentation | Full code execution, GPU orchestration | None | None |
| Deployment | CLI + skill files (zero infra) | Docker + FastAPI + Next.js | FastAPI + React |

---

## 2. ARIS (Auto-claude-code-research-in-sleep) — Deep Analysis

### 2.1 Architecture

ARIS is not a platform — it's a **skill-based methodology** built on top of Claude Code / Codex CLI. Every skill is a single `SKILL.md` Markdown file that orchestrates multi-step research workflows through cross-model adversarial collaboration.

**Core Design Principles:**
1. **Cross-model review** — Executor (Claude) and Reviewer (GPT-5.4) are always different model families to prevent self-play blind spots
2. **Adversarial improvement** — Reviewer actively probes weaknesses the executor didn't anticipate
3. **Plain-text artifacts** — All communication through Markdown files (IDEA_REPORT.md, EXPERIMENT_PLAN.md, etc.)
4. **Zero infrastructure** — No database, no Docker, no daemon. Just Markdown files on disk

**Workflow Pipeline:**
```
W1: Idea Discovery → W1.5: Experiment Bridge → W2: Auto Review Loop → W3: Paper Writing → W4: Rebuttal
```

Each workflow is independently invocable and composable.

### 2.2 Key Features

| Feature | Implementation | Quality |
|:--------|:--------------|:--------|
| **Literature search** | `/research-lit` — web scraping + Gemini + OpenAlex + arXiv | Broad but shallow |
| **Idea generation** | `/idea-creator` — brainstorming + novelty check via web search | Creative, but no structured gap analysis |
| **Experiment execution** | `/experiment-bridge` + `/experiment-queue` — SSH GPU orchestration | **Elephant Rock doesn't have this** |
| **Paper writing** | `/paper-writing` — section-by-section LaTeX with style reference | Full academic paper output |
| **Adversarial review** | `/auto-review-loop` — GPT-5.4 xhigh iterative scoring | **Strongest review system of all three** |
| **Proof checking** | `/proof-checker` — 20-category issue taxonomy, side-condition checklists | Theory-paper specific |
| **Citation audit** | `/citation-audit` — existence + metadata + context verification | 3-axis verification |
| **Claim audit** | `/paper-claim-audit` — zero-context fresh reviewer cross-checks numbers vs raw data | Catches rounding inflation, cherry-picking |
| **Rebuttal writing** | `/rebuttal` — reads reviews, drafts venue-specific rebuttal with safety gates | Unique feature |
| **Research Wiki** | Persistent knowledge base across runs | Long-term memory |
| **Self-evolution** | `/meta-optimize` — analyzes usage logs, proposes SKILL.md patches | Self-improving system |
| **Multi-venue resubmit** | `/resubmit-pipeline` — text-only resubmit across venues with isolation guards | Publication lifecycle |

### 2.3 Strengths

1. **Deepest paper quality assurance** — 4-layer audit chain: experiment-audit → result-to-claim → paper-claim-audit → citation-audit
2. **Full experiment lifecycle** — Actually runs code on GPUs, tracks results, audits for integrity
3. **Cross-model adversarial review** — The "speed × rigor" thesis (Claude executes fast, GPT-5.4 reviews rigorously) produces measurably better outputs
4. **Rebuttal workflow** — Only tool that handles the post-submission phase
5. **Zero lock-in** — Pure Markdown, works with any agent (Claude, Codex, Cursor, Trae)
6. **Community validation** — Papers submitted to AAAI 2026, IEEE TGRS using ARIS

### 2.4 Weaknesses

1. **No structured gap analysis** — Ideas come from brainstorming, not systematic literature gap identification
2. **No academic database integration** — Searches web, not Semantic Scholar/OpenAlex/arXiv APIs directly
3. **No novelty scoring** — Novelty check is "does something similar exist on the web?" not structured scoring
4. **No pipeline orchestration** — Each skill runs independently, no 10-stage pipeline with progress tracking
5. **No local LLM support** — Relies entirely on expensive cloud APIs (Claude + GPT-5.4)
6. **Slow** — Full pipeline takes 3-8 hours due to iterative review loops
7. **No real-time progress** — No UI for monitoring research progress

---

## 3. GPT Researcher — Deep Analysis

### 3.1 Architecture

GPT Researcher uses a **Plan-and-Solve** pattern inspired by the 2023 paper:

```
Query → Planner Agent (generates research questions)
       → For each question: Crawler Agent (scrapes web) → Summarizer
       → Publisher Agent (aggregates → final report)
```

**Core Design Principles:**
1. **Parallelized execution** — `asyncio.gather()` for concurrent web scraping
2. **Law of large numbers** — More sources = less bias (20+ sources per query)
3. **Summarize, don't generate** — LLMs only summarize scraped content, reducing hallucinations
4. **Deterministic completion** — Fixed task decomposition guarantees 100% completion rate

### 3.2 Key Features

| Feature | Implementation | Quality |
|:--------|:--------------|:--------|
| **Web research** | 20+ source aggregation with dedup | Broad and fast |
| **Local document research** | PDF/CSV/Word/Markdown ingestion | Unique capability |
| **Deep research mode** | Recursive tree exploration (depth + breadth) | ~5 min, $0.40/run |
| **Multi-agent** | LangGraph + AG2 teams (planner + reviewer + writer) | STORM-inspired |
| **MCP integration** | Custom data sources (GitHub, databases) | Extensible |
| **Frontend** | Lightweight HTML + production Next.js | **Best UX of all three** |
| **Export** | PDF, Word, Markdown | Multi-format |
| **Image generation** | Google Gemini inline illustrations | Unique visual capability |
| **Observability** | LangSmith tracing | Debug-friendly |

### 3.3 Strengths

1. **Fastest time-to-result** — ~3 minutes for standard research, ~5 minutes for deep research
2. **Best deployment story** — Docker, pip install, MCP server, Claude skill — all options
3. **Local document support** — Only tool that researches your own PDFs/docs
4. **Production-ready frontend** — Beautiful Next.js UI with real-time progress
5. **Extensible retriever architecture** — Tavily, MCP, custom sources
6. **Low cost** — $0.40 per deep research run
7. **Largest community** — 27K stars, 3.6K forks, active Discord

### 3.4 Weaknesses

1. **No gap analysis** — Purely search-and-summarize, doesn't identify research gaps
2. **No novelty checking** — No mechanism to verify if findings are novel
3. **No proposal generation** — Outputs research reports, not research proposals
4. **No quality scoring** — No feasibility, novelty, or composite scores
5. **No adversarial review** — Single-model pipeline, no cross-model critique
6. **No citation integrity** — Source URLs listed but not verified for correctness
7. **No experimentation** — Can't run code or validate hypotheses
8. **Shallow depth** — Summarizes what exists, doesn't synthesize what's missing

---

## 4. Elephant Rock — Position Analysis

### 4.1 What Elephant Rock Has That Neither Competitor Has

| Feature | Elephant Rock | ARIS | GPT Researcher |
|:--------|:------------|:-----|:---------------|
| **Structured gap analysis** | ✅ 10-stage pipeline with gap detection | ❌ Brainstorm only | ❌ Search only |
| **Novelty scoring** (0-1 scale) | ✅ Per-idea novelty check | ❌ Web search check | ❌ None |
| **Feasibility scoring** | ✅ Per-idea feasibility + quality gates | ❌ None | ❌ None |
| **Closed-book citation policy** | ✅ [SOURCE-X] indexing, sanitization | ✅ Citation audit (post-hoc) | ❌ URLs only |
| **Proposal synthesis** (10-section) | ✅ Full research proposals | ✅ Full papers | ❌ Reports only |
| **Local LLM routing** | ✅ Hybrid local/cloud | ❌ Cloud only | ❌ Cloud only |
| **10-stage pipeline** | ✅ Orchestrated with progress tracking | ❌ Manual skill chaining | ❌ 3-step plan/scrape/write |
| **Knowledge graph** | ✅ Paper entities + relationships | ❌ Wiki (text only) | ❌ None |
| **Claim extraction** | ✅ LLM-based claim extraction from papers | ❌ None | ❌ None |
| **Contradiction detection** | ✅ Cross-paper claim contradiction | ❌ None | ❌ None |

### 4.2 What Competitors Have That Elephant Rock Doesn't

| Feature | ARIS | GPT Researcher | Elephant Rock Gap |
|:--------|:-----|:---------------|:-----------------|
| **Experiment execution** | ✅ SSH GPU orchestration | ❌ | **CRITICAL — No code execution** |
| **Adversarial cross-model review** | ✅ GPT-5.4 xhigh iterative | ❌ | **HIGH — Only local LLM novelty check** |
| **Full paper writing** (LaTeX) | ✅ Section-by-section + Beamer | ✅ Report format | **HIGH — Proposals, not papers** |
| **Rebuttal workflow** | ✅ Venue-specific with safety gates | ❌ | Medium — Post-submission lifecycle |
| **Proof checking** | ✅ 20-category taxonomy | ❌ | Low — Theory-paper specific |
| **Local document research** | ❌ | ✅ PDF/CSV/Word | Medium — Upload zone exists but limited |
| **Production frontend** | ❌ (CLI only) | ✅ Next.js + real-time progress | **HIGH — Our React frontend is basic** |
| **Image generation** | ❌ | ✅ Gemini inline illustrations | Low |
| **Docker deployment** | ❌ | ✅ Full docker-compose | **HIGH — No containerization** |
| **MCP integration** | ❌ | ✅ Custom data sources | Medium |
| **Multi-agent teams** | ❌ | ✅ LangGraph + AG2 | Medium |

---

## 5. Gap Prioritization for Elephant Rock

Based on the competitive analysis, ranked by impact:

### Tier 1 — Critical Differentiators (Would Make Elephant Rock Unique)

| Gap | Competitor | Effort | Impact |
|:----|:----------|:-------|:-------|
| **G1: Cross-model adversarial review** | ARIS | ~8h | Validates proposals via GPT-5.4 / Gemini review loop. Catches issues local LLM can't. |
| **G2: Full paper synthesis (LaTeX output)** | ARIS | ~12h | Convert proposals → publication-ready papers with BibTeX, figures, tables |
| **G3: Experiment bridge** | ARIS | ~20h | Execute proposed experiments, collect real results, feed back into proposals |

### Tier 2 — High-Value Features

| Gap | Competitor | Effort | Impact |
|:----|:----------|:-------|:-------|
| **G4: Production deployment** | GPT Researcher | ~6h | Docker Compose + deployment guide |
| **G5: Real-time frontend polish** | GPT Researcher | ~8h | Next.js-quality UI with streaming progress |
| **G6: Citation verification** | ARIS | ~4h | 3-axis check: existence + metadata + context appropriateness |
| **G7: Local document ingestion** | GPT Researcher | ~6h | Research your own PDFs alongside web sources |

### Tier 3 — Medium-Value Features

| Gap | Competitor | Effort | Impact |
|:----|:----------|:-------|:-------|
| **G8: Multi-agent teams** | GPT Researcher | ~12h | Specialized agents for different research phases |
| **G9: Rebuttal workflow** | ARIS | ~8h | Post-submission lifecycle management |
| **G10: Research wiki persistence** | ARIS | ~6h | Long-term memory across runs |

---

## 6. Strategic Recommendation

**Elephant Rock's unique value proposition** is its **structured 10-stage research pipeline with gap analysis + novelty scoring + feasibility assessment**. Neither ARIS nor GPT Researcher does this. They're complementary tools:

- **ARIS** = Paper writing + experimentation + adversarial review
- **GPT Researcher** = Fast web research + local docs + production UX
- **Elephant Rock** = Research gap discovery + proposal generation + novelty scoring

### Recommended Integration Path

Instead of competing, **integrate**:

1. **Elephant Rock generates gaps + proposals** → Feed into ARIS for paper writing
2. **GPT Researcher's web scraping** → Replace our literature search for faster results
3. **ARIS's citation audit** → Add as a post-processing step to our proposal synthesis
4. **GPT Researcher's Docker deployment** → Adopt as our deployment model

### Top 3 Implementation Priorities

1. **G1: Cross-model adversarial review** (8h) — Route completed proposals through a cloud LLM (GPT-5.4/Gemini) for adversarial scoring. This single feature would make Elephant Rock's output quality match ARIS's.
2. **G4: Production deployment** (6h) — Docker Compose + deployment guide. Makes the platform usable by others.
3. **G2: Full paper synthesis** (12h) — Convert our structured proposals into LaTeX papers with proper academic formatting.

Total estimated effort for top 3: **26 hours** (~3 focused sessions).

---

*Study complete. 2 repositories analyzed against Elephant Rock. 10 gaps identified. 3 priorities recommended.*
