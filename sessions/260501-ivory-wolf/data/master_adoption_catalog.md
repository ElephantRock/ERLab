# Master Adoption Catalog — Everything Studied, Everything Worth Adopting

**Date:** 2026-05-11  
**Scope:** All 20+ studies conducted over 10 days, consolidated into a single actionable catalog  
**Format:** Each item: Source → Feature → What → How → Effort → Priority  

---

## How to Read This

- **P0** = Must have. Blocks real users or is a proven quality multiplier.
- **P1** = Should have. Makes the platform competitive.
- **P2** = Nice to have. Differentiator.
- **P3** = Future. Aspirational.

Already-built items are marked ✅ and listed at the bottom for reference.

---

## 1. CROSS-MODEL ADVERSARIAL REVIEW

**Source:** ARIS (8.7K ⭐)  
**What:** Route completed proposals through a different model family for adversarial scoring. ARIS uses Claude→execute, GPT-5.4→review. The reviewer must be a different family to prevent self-play blind spots. Iterative: reviewer scores, executor revises, repeat until score threshold met.  
**How:** New pipeline stage after proposal_deepening. Cloud LLM (glm-5.1) receives full proposal + source papers. Scores on Soundness, Novelty, Feasibility, Clarity (1-10 each). If overall < 7, feeds revision notes back to synthesizer. Max 3 rounds.  
**Effort:** 8h  
**Priority:** **P0** — ARIS's #1 innovation. Single biggest quality multiplier.

---

## 2. FULL PAPER SYNTHESIS (LaTeX)

**Source:** ARIS, AutoResearchClaw, AI-Scientist  
**What:** Convert proposals into publication-ready LaTeX papers with BibTeX, figures, tables, proper academic formatting. Section-by-section generation with citation rounds.  
**How:** New `PaperWriter` stage. Takes proposal + source papers. Generates: Abstract → Introduction → Related Work → Method → Experiments → Results → Conclusion. Uses Semantic Scholar for citation verification. Outputs .tex + .bib + compiled PDF.  
**Effort:** 12h  
**Priority:** **P0** — Academic researchers need LaTeX, not Markdown.

---

## 3. 3-AXIS CITATION AUDIT

**Source:** ARIS  
**What:** Verify every citation on 3 axes: (1) Does the paper exist? (2) Does metadata match? (3) Is the citation context appropriate? Cross-family reviewer checks.  
**How:** Post-processing stage after proposal synthesis. For each [SOURCE-X] reference: verify DOI exists via CrossRef, check title/year/authors match, verify claim context is appropriate for the cited paper. Flag mismatches.  
**Effort:** 4h  
**Priority:** **P1** — Goes beyond our [SOURCE-X] indexing to verify correctness.

---

## 4. PAPER CLAIM AUDIT

**Source:** ARIS  
**What:** Zero-context fresh reviewer cross-checks all quantitative claims in proposals against source paper abstracts. Catches rounding inflation, cherry-picked numbers, misattributed results.  
**How:** Extract quantitative claims from proposals (regex for numbers + context). For each claim, ask LLM (different model) to verify against source paper. Flag unsupported claims.  
**Effort:** 4h  
**Priority:** **P1** — Catches a class of errors our current pipeline can't.

---

## 5. EXPERIMENT BRIDGE / CODE EXECUTION

**Source:** ARIS (SSH GPU), AutoResearchClaw (4-backend sandbox), AI-Scientist (Aider), Google Paper (tree search + sandbox)  
**What:** Execute proposed experiments in sandboxed environments. Collect real results. Feed back into proposals. ARIS uses SSH GPU orchestration. AutoResearchClaw has 4 backends (local, Docker, SSH, Colab). AI-Scientist uses Aider to modify code.  
**How:** Start with Docker sandbox (safest). Wire existing `sandboxing/protocol.py` to Docker backend. Add memory/time limits from simonw's QuickJS sandbox research. Experiment template system per domain.  
**Effort:** 20h  
**Priority:** **P1** — Without this, proposals describe hypothetical experiments with no real validation.

---

## 6. DOCKER COMPOSE DEPLOYMENT

**Source:** GPT Researcher (27K ⭐), u14app/deep-research, LDR  
**What:** One-command `docker compose up` that starts backend + frontend + SQLite. Production-ready.  
**How:** Dockerfile for backend (Python), Dockerfile for frontend (Node/Vite build), docker-compose.yml. .env for configuration. Volume mount for SQLite data persistence. Health checks.  
**Effort:** 6h  
**Priority:** **P0** — Without this, nobody else can use the platform.

---

## 7. LOCAL DOCUMENT INGESTION

**Source:** GPT Researcher  
**What:** Research your own PDFs, Word docs, CSVs alongside web sources. User points to a folder, documents get parsed and ingested as supplementary sources.  
**How:** Expand upload-zone to accept multiple file formats. Use `markitdown` (already in toolchain) for conversion. Feed parsed content into ingestion stage as supplementary papers.  
**Effort:** 6h  
**Priority:** **P1** — Unique to GPT Researcher. Researchers want to include their own papers.

---

## 8. RECURSIVE DEEP RESEARCH (TREE EXPLORATION)

**Source:** GPT Researcher, dzhng/deep-research (18.9K ⭐), u14app/deep-research  
**What:** Start with broad query, identify relevant papers, recursively search citing/cited papers. Configurable depth and breadth. dzhng's algorithm: breadth=4, depth=2 → ~20 queries, ~100 pages, ~60 learnings.  
**How:** Enhance `deep_research` strategy. Use OpenAlex citations API for citation graph traversal. `RecursiveLiteratureSearcher` with breadth/depth params. Already partially parallelized.  
**Effort:** 8h  
**Priority:** **P1** — Finds foundational papers that flat keyword search misses.

---

## 9. ITERATIVE REFLECTION LOOP

**Source:** langchain/local-deep-researcher, open-deep-research, Jina DeepResearch, LDR  
**What:** After each pipeline stage, LLM reflects on output quality and decides whether to retry, refine, or proceed. "Does this gap list cover the domain?" "Is this idea truly novel?" langchain-LDR uses a 5-node LangGraph: generate_query → web_research → summarize → reflect → route (loop or finish).  
**How:** Add `ReflectionStage` after gap_analysis and ideation. LLM evaluates its own output against a rubric. If score < threshold, regenerate with feedback included in prompt. Max 2 retries.  
**Effort:** 6h  
**Priority:** **P1** — Every competitive tool iterates. Single-pass produces mediocre results.

---

## 10. MULTI-DIMENSIONAL PROPOSAL EVALUATION

**Source:** Jina DeepResearch (5.2K ⭐)  
**What:** Score proposals on 5 dimensions: Novelty, Feasibility, Completeness, Rigor, Clarity. Each gets 0-1 score with written justification. Jina checks answers for definitiveness, freshness, completeness, plurality, and strict quality.  
**How:** New `ProposalEvaluator` with dimension-specific prompts. Store as JSON alongside proposals. Display as radar chart in frontend. Currently we have single novelty score.  
**Effort:** 4h  
**Priority:** **P1** — A single score tells user nothing about WHY a proposal is good.

---

## 11. 5-STATE VERIFICATION (Not Binary)

**Source:** Reference implementation study (BATCH-131)  
**What:** Instead of binary supported/unsupported, use 5 states: SUPPORTED, UNSUPPORTED, PARTIALLY_SUPPORTED, UNCLEAR, ERROR. Preserve per-claim evidence and confidence.  
**How:** Extend WikiVerifier response model. Add `needs_human_review` flag when unsupported ratio > threshold. Cap keyword confidence at 0.7 (prevent overconfidence).  
**Effort:** 3h  
**Priority:** **P1** — Nuanced verification produces better downstream trust.

---

## 12. STAGED CONFIDENCE (PROGRESSIVE TRUST)

**Source:** QA study (technique #4)  
**What:** Claims accumulate trust through verification stages: Keyword overlap (0.0-0.3) → Single LLM (0.3-0.6) → Source-anchored quote (0.6-0.8) → Cross-model consensus (0.8-0.9) → Cross-paper consistency (0.9-1.0). Different downstream actions require different trust levels.  
**How:** Extend TrustTier enum. Add downstream trust gates: gap analysis requires ≥ 0.6, study design requires ≥ 0.8, paper draft requires ≥ 0.95.  
**Effort:** 4h  
**Priority:** **P1** — Prevents low-trust claims from poisoning downstream outputs.

---

## 13. CROSS-MODEL CONSENSUS

**Source:** QA study (technique #1), ARIS  
**What:** Run same verification through two different models (e.g., qwen3-4b + qwen2.5-14b). If both agree → high confidence. If they disagree → flag as uncertain.  
**How:** We have `AdversarialDebate` module (exists but unwired). Wire it into verification pipeline for high-stakes claims. Double LLM cost but catches single-model blind spots.  
**Effort:** 3h  
**Priority:** **P2** — Useful for high-stakes, but doubles cost. Wire existing code.

---

## 14. RESEARCH JOURNAL PER RUN

**Source:** simonw/research (88 projects)  
**What:** Every pipeline run produces a `notes.md` tracking what happened at each stage: queries tried, failures, surprises. Plus a clean `README.md` summary. Simon's pattern: question → investigate → note → report → archive.  
**How:** `JournalWriter` class accumulates stage notes during pipeline execution. Generates markdown report at end. Each run becomes a self-contained research investigation.  
**Effort:** 4h  
**Priority:** **P1** — Currently pipeline runs produce raw JSON. No narrative. No journey.

---

## 15. KNOWLEDGE LIBRARY (PERSISTENT RESEARCH MEMORY)

**Source:** LDR (5.5K ⭐)  
**What:** Every paper, gap, idea from every run is indexed persistently. Future runs query library first before hitting external sources. Research compounds over time. LDR has 212K+ indexed sources.  
**How:** Persistent ChromaDB collection per domain. On pipeline start, query existing knowledge first. New papers added to library. Cross-run deduplication.  
**Effort:** 8h  
**Priority:** **P1** — Currently each run starts from scratch. Run #2 doesn't know Run #1 existed.

---

## 16. MORE SEARCH ENGINES (2 → 10+)

**Source:** LDR (25 engines), AutoResearchClaw (OpenAlex + S2 + arXiv)  
**What:** Add Semantic Scholar, PubMed, Google Scholar, DBLP, CrossRef, CORE, Wikipedia. Currently only OpenAlex + arXiv.  
**How:** Implement `AcademicSearchSource` for each. Each has `search()`, `get_paper()`, `rate_limit_info()`. Add to `MultiSourceSearcher` parallel fan-out.  
**Effort:** 8h  
**Priority:** **P1** — 2 engines = limited coverage. Real researchers use 5-10 sources.

---

## 17. CROSS-ENGINE RELEVANCE FILTER

**Source:** LDR  
**What:** After gathering papers from multiple engines, use LLM to rerank by relevance, deduplicate by DOI/title similarity, filter out noise.  
**How:** `RelevanceFilter` class takes papers + original query, calls LLM to score relevance 0-1, deduplicates by DOI/fuzzy title match, returns top-K.  
**Effort:** 4h  
**Priority:** **P1** — Multiple engines = lots of noise. Need post-search filtering.

---

## 18. SOUL.MD — RESEARCH PHILOSOPHY

**Source:** dexter (SOUL.md personality system)  
**What:** A `SOUL.md` file defining Elephant Rock's research philosophy: what makes a good gap, what makes a novel idea, what makes a rigorous proposal. LLM reads this before generating anything. Dexter defines Buffett+Munger investing philosophy; we'd define research rigor philosophy.  
**How:** Already have `SOUL.md` in project root. Need to enhance with research quality criteria, anti-patterns, and domain expertise. Wire into `soul_loader.py` → every LLM call reads it.  
**Effort:** 2h  
**Priority:** **P2** — Low effort, high impact on output distinctiveness.

---

## 19. SKILL.MD — EXTENSIBLE RESEARCH SKILLS

**Source:** dexter, simonw/research (OpenAI Skills), ARIS  
**What:** Define multi-step research skills as markdown files: "Systematic Review Skill", "Proposal Writing Skill", "Gap Validation Skill". Each skill defines steps, prompts, quality criteria.  
**How:** `skills/` directory with `.md` files. `SkillLoader` parses frontmatter + steps. Pipeline orchestrator selects skills based on user intent. Already have `SKILL.md` in project root.  
**Effort:** 8h  
**Priority:** **P2** — Makes pipeline customizable without code changes.

---

## 20. PLANNING AGENT (ADAPTIVE PIPELINE)

**Source:** SkyworkAI/DeepResearchAgent (3.4K ⭐), GPT Researcher  
**What:** A planning agent decides which stages to run based on the research question. Simple questions get 3 stages. Complex ones get all 10. Re-plans mid-run based on intermediate results.  
**How:** `PlanningAgent` takes research question + time budget, outputs a stage plan. After gap_analysis, re-evaluates: if 0 gaps found, try different search queries. If 10+ gaps, focus on top 3.  
**Effort:** 8h  
**Priority:** **P2** — Makes pipeline adaptive rather than rigid.

---

## 21. SELF-IMPROVING PROMPTS (TEXTGRAD)

**Source:** SkyworkAI/DeepResearchAgent  
**What:** After each pipeline run, evaluate prompt quality. Use "textual gradient descent" — generate prompt improvements based on output quality scores. Maintain prompt version history.  
**How:** `PromptEvolutionEngine`. After each run, compute "loss" (quality scores). Generate prompt variants. A/B test on next run. Roll back if worse.  
**Effort:** 10h  
**Priority:** **P2** — Self-improving pipeline. Unique differentiator.

---

## 22. IDEA RECOMBINATION (FORMALIZED)

**Source:** Google Paper (LLM + Tree Search) — 44% of recombinations beat both parents  
**What:** Systematically take two existing ideas/methods and combine their strengths. Google showed 24/55 recombinations outperformed both parents. This is already partially in our Borda Tournament but not formalized.  
**How:** New pipeline sub-stage after ideation. For each pair of top ideas, generate a "recombined" idea that takes the best elements of both. Score the recombination.  
**Effort:** 4h  
**Priority:** **P2** — Proven by Google to produce breakthroughs.

---

## 23. ROUND-ROBIN GAP QUEUE

**Source:** Jina DeepResearch  
**What:** Instead of generating all gaps at once, maintain a queue of sub-problems and cycle through them systematically. Each cycle deepens understanding of one gap before moving to the next.  
**How:** `GapQueue` class with round-robin scheduling. Each gap gets N exploration rounds. Prevents superficial coverage of many gaps.  
**Effort:** 4h  
**Priority:** **P2** — Deeper exploration of individual gaps.

---

## 24. ERROR ANALYSIS AS KNOWLEDGE

**Source:** Jina DeepResearch  
**What:** When a gap is rejected, idea scores low, or proposal fails quality checks, store the rejection reason as structured learning. Future runs query this "failure database" to avoid repeating mistakes.  
**How:** `failure_log` table in DB. Each failure: stage, input_hash, reason, suggestion. Queried at pipeline start.  
**Effort:** 3h  
**Priority:** **P2** — Pipeline learns from its mistakes across runs.

---

## 25. 3-TIER CONTEXT MANAGEMENT

**Source:** dexter  
**What:** Microcompact → memory flush → compaction → truncation. When context exceeds limits, first summarize older content, compact into key points, then truncate oldest. Never lose the most important context.  
**How:** `ContextManager` class with 3 strategies. Integrated into each stage's prompt construction. Dexter uses token-counter.ts + compact.ts + microcompact.ts.  
**Effort:** 6h  
**Priority:** **P2** — Long runs risk running out of context or losing earlier findings.

---

## 26. MCP SERVER (EXPOSE PIPELINE AS TOOL)

**Source:** GPT Researcher, u14app/deep-research, AutoResearchClaw, LDR  
**What:** Expose Elephant Rock pipeline as an MCP tool so other AI systems can start research pipelines programmatically. Code exists in `backend/pipeline/tools/mcp/` but not wired up.  
**How:** Complete MCP server implementation. Register tools: `start_pipeline`, `get_run_status`, `get_gaps`, `get_ideas`, `get_proposals`. stdio transport.  
**Effort:** 6h  
**Priority:** **P2** — Makes Elephant Rock a tool within other AI workflows.

---

## 27. DOMAIN-SPECIFIC PROMPTS

**Source:** AI-Scientist (templates per domain), Competitive gap analysis  
**What:** Different prompts for different domains: CS/NLP, biology, medicine, social science. Each domain has different evaluation criteria, proposal structures, terminology. Already partially exist in `backend/pipeline/prompts/domains/`.  
**How:** Expand from 3 to 6+ domain prompt files. Auto-detect domain from research query.  
**Effort:** 4h  
**Priority:** **P2** — Generic academic prompts produce generic output.

---

## 28. BUDGET/TIME CONTROLS

**Source:** Honest assessment finding, dexter (cron scheduling)  
**What:** User sets max time (5/15/30/60 min) and max cost ($0.50/$1/$5/$10). Pipeline respects limits, degrades gracefully (skip stages, reduce paper count, use smaller model).  
**How:** `BudgetGuard` (already exists in `budget_guard.py`) extended with user-configurable limits. Frontend exposes controls.  
**Effort:** 4h  
**Priority:** **P2** — Users need control over cost and time.

---

## 29. CITATION GRAPH VISUALIZATION

**Source:** Research Rabbit, Semantic Scholar, dzhng/deep-research  
**What:** Interactive visualization showing which papers cite which, where gaps exist in citation network, how ideas connect to literature.  
**How:** Use D3.js or vis.js for interactive graph. Data from OpenAlex citation API + our knowledge graph. Frontend component.  
**Effort:** 8h  
**Priority:** **P2** — Knowledge graph exists but is abstract. Citation graph is what researchers want to see.

---

## 30. REBUTTAL WORKFLOW

**Source:** ARIS  
**What:** After paper submission and peer review, generate venue-specific rebuttals with safety gates. ARIS has dedicated `/rebuttal` skill that reads reviews, drafts PASTE_READY.txt.  
**How:** New pipeline mode: input = paper + reviews → output = structured rebuttal. Only relevant if we add paper submission workflow.  
**Effort:** 8h  
**Priority:** **P3** — Post-submission lifecycle. Only useful with paper writing.

---

## 31. TEMPORAL TRUST DECAY

**Source:** QA study (technique #6)  
**What:** Older claims lose trust over time. A 2020 paper's claims are less reliable than a 2025 paper's. Decay function based on publication date.  
**How:** Add `publication_year` to claims. Trust modifier: `trust * (0.95 ^ (current_year - pub_year))`. Only for fast-moving fields (configurable per domain).  
**Effort:** 2h  
**Priority:** **P2** — Prevents outdated claims from carrying full weight.

---

## 32. ADVERSARIAL VERIFICATION (TWO-PASS)

**Source:** QA study (technique #5)  
**What:** Two-pass verification: first "is this supported?", then "is there evidence AGAINST this claim?". Catches confirmation bias (LLMs agree too readily).  
**How:** Add second LLM call with inverted prompt: "Find evidence that contradicts or undermines this claim." Combine both passes for final verdict.  
**Effort:** 3h  
**Priority:** **P2** — Catches confirmation bias in verification.

---

## 33. PROVENANCE TRACKING

**Source:** QA study (technique #7)  
**What:** Full chain-of-custody for every claim: which paper → which extraction → which verification → which trust tier → which downstream usage.  
**How:** Add `provenance` JSON field to claims. Track: source_paper_id → extraction_method → verification_passes → trust_tier → used_in_gaps → used_in_ideas → used_in_proposals.  
**Effort:** 4h  
**Priority:** **P2** — Audit trail for research integrity.

---

## 34. AUTOMATED LITERATURE MONITORING

**Source:** LDR (news subscriptions)  
**What:** User defines research topic. Platform monitors arXiv, Semantic Scholar daily. Notifies when new relevant papers appear. Auto-updates gaps and ideas.  
**How:** Scheduled background task. Daily search for new papers matching tracked topics. Diff against existing knowledge. Generate update notifications.  
**Effort:** 8h  
**Priority:** **P3** — Research doesn't stop after one run.

---

## 35. JUDGE-ML DUAL AGENT LOOP

**Source:** AI-Scientist (NeurIPS 2025 Spotlight)  
**What:** One agent generates a proposal, another agent (the Judge) critiques it. They iterate until Judge approves. AI-Scientist shows this produces significantly better output than single-pass.  
**How:** Implement as pipeline stage pair: Generator → Judge → (loop if rejected). Judge uses different model. Max 3 rounds.  
**Effort:** 6h  
**Priority:** **P2** — Overlaps with #1 (adversarial review). Could be the implementation mechanism.

---

## 36. IDEA NOVELTY VIA SEMANTIC SCHOLAR ITERATIVE SEARCH

**Source:** AI-Scientist v1/v2  
**What:** For each idea, iteratively search Semantic Scholar up to 10 rounds. Each round, LLM decides if it found a prior that invalidates the idea. Binary novel/not-novel with reasoning trail.  
**How:** Enhance existing novelty checking. Add Semantic Scholar API calls. Iterative search with LLM-as-judge for each round.  
**Effort:** 4h  
**Priority:** **P1** — Our current novelty check is vector-store only. Semantic Scholar adds web verification.

---

## 37. VENUE-SPECIFIC LaTeX TEMPLATES

**Source:** AI-Scientist, AutoResearchClaw  
**What:** LaTeX templates for NeurIPS, ICML, ICLR, Nature, PNAS, NSF grants, PhD thesis. Different venues have different formatting. AutoResearchClaw has 3 built-in.  
**How:** Template directory with .tex files per venue. User selects venue at pipeline start or export time. `jinja2` fills in content.  
**Effort:** 6h  
**Priority:** **P2** — Depends on #2 (LaTeX paper output).

---

## 38. R&D DUAL AGENT (PROPOSE → IMPLEMENT → EVALUATE)

**Source:** RD-Agent (Microsoft, MLE-bench leader)  
**What:** R-Agent proposes ideas, D-Agent implements them, evaluator scores, feeds back to R-Agent. Closed-loop research. RD-Agent achieves 30.22% on MLE-bench.  
**How:** Extend experiment bridge (#5). After proposal generation, generate implementation plan. Execute. Score results. Feed scores back into proposal refinement.  
**Effort:** 16h  
**Priority:** **P3** — Requires #5 (experiment bridge) first.

---

## 39. OVERLEAF INTEGRATION

**Source:** ARIS, AutoResearchClaw  
**What:** Two-way sync with Overleaf via Git bridge. Write paper locally, push to Overleaf for collaboration. Token stays in OS keychain, never in chat.  
**How:** Overleaf Git bridge integration. `overleaf-sync` command: setup (store credentials), push, pull.  
**Effort:** 4h  
**Priority:** **P3** — Academic collaboration tool. Nice with #2.

---

## 40. MULTI-AGENT DEBATE FOR IDEATION

**Source:** SkyworkAI/DeepResearchAgent, GPT Researcher (LangGraph + AG2)  
**What:** Multiple specialized agents debate ideas: Optimist (generates ideas), Skeptic (challenges assumptions), Contrarian (proposes alternatives). Weighted consensus scoring.  
**How:** We have `AdversarialDebate` module (3 agents). Wire it into ideation stage. Already partially in Borda Tournament.  
**Effort:** 3h  
**Priority:** **P2** — Code exists, just needs wiring.

---

## 41. KARPATHY'S MODIFY→VERIFY→KEEP/DISCARD LOOP

**Source:** autoresearch (Karpathy's original, 630 lines)  
**What:** Atomic change → run verification → if metric improves, keep commit. If not, `git revert`. Results logged to TSV. Plateau detection (stop after 15 iterations without improvement).  
**How:** Apply to pipeline prompt optimization. After each run, if quality scores improve, keep prompt changes. If not, revert. Track in results.tsv.  
**Effort:** 4h  
**Priority:** **P2** — Self-improvement loop. Related to #21 (TextGrad).

---

## 42. GIT-AS-MEMORY

**Source:** autoresearch, simonw/research  
**What:** Every pipeline run produces a git commit with all artifacts. Agent reads `git log` and `git diff` to understand history. Atomic changes enforced.  
**How:** Auto-commit after each pipeline run with structured message. Include all artifacts (gaps, ideas, proposals, journal). Future runs query git history.  
**Effort:** 3h  
**Priority:** **P2** — Persistent, auditable research history.

---

## 43. PLATEAU DETECTION

**Source:** autoresearch  
**What:** Stop iterating when metric hasn't improved for N iterations (default 15). Prevents wasted compute on diminishing returns.  
**How:** Track quality scores across pipeline runs. If 3 consecutive runs show <5% improvement, suggest stopping to user.  
**Effort:** 2h  
**Priority:** **P2** — Prevents wasted compute.

---

## 44. GUARD COMMANDS (REGRESSION PREVENTION)

**Source:** autoresearch  
**What:** While optimizing primary metric, guard commands ensure no regression on secondary metrics. "Improve novelty but ensure feasibility doesn't drop below 0.6."  
**How:** Extend `BudgetGuard` to support secondary guard metrics. If guard trips, reject the change even if primary metric improved.  
**Effort:** 3h  
**Priority:** **P2** — Prevents quality regressions during optimization.

---

## 45. AI-GENERATED HONESTY LABELING

**Source:** simonw/research  
**What:** Every AI-generated report carries an `AI-GENERATED-NOTE` badge. Honest labeling standard.  
**How:** Add to all exported proposals: "This research proposal was generated by an AI pipeline. Claims should be independently verified."  
**Effort:** 0.5h  
**Priority:** **P1** — Ethical requirement. 30 minutes of work.

---

## 46. FIGURE GENERATION

**Source:** AutoResearchClaw (5-agent figure pipeline), GPT Researcher (Gemini image gen)  
**What:** Auto-generate figures for proposals: architecture diagrams, result charts, comparison tables. AutoResearchClaw has 5-agent pipeline (Planner→CodeGen→Renderer→Critic→Integrator).  
**How:** Start simple: generate matplotlib/plotly charts from proposal data. Later: architecture diagrams via Mermaid/Graphviz.  
**Effort:** 6h  
**Priority:** **P2** — Figures make proposals more compelling.

---

## 47. COLLABORATION / HUMAN-IN-THE-LOOP

**Source:** AutoResearchClaw (co-pilot mode + HITL system), ARIS (human checkpoint param)  
**What:** Allow human intervention at pipeline stages. Review gaps before ideation. Edit ideas before synthesis. Co-pilot mode where human guides the process.  
**How:** Pipeline pause points. User can edit gaps/ideas/proposals at each stage. Resume pipeline from edited state.  
**Effort:** 8h  
**Priority:** **P2** — Research is rarely fully autonomous.

---

## 48. MULTI-ENGINE RERANKING

**Source:** Jina DeepResearch (Jina Rerank API), dzhng/deep-research  
**What:** After gathering results from multiple sources, rerank by relevance using embeddings or LLM. Jina uses their Rerank API. dzhng uses LLM to score each result.  
**How:** `Reranker` stage after literature search. Score each paper by relevance to original query. Deduplicate. Return ranked list.  
**Effort:** 4h  
**Priority:** **P1** — Overlaps with #17 (relevance filter). Same feature, different framing.

---

## 49. QUERY REWRITING

**Source:** Jina DeepResearch (query-rewriter.ts), LDR  
**What:** LLM rewrites user's research question into optimal search queries. Different phrasings catch different papers.  
**How:** Before literature search, pass query through LLM to generate 3-5 optimized search queries. Already partially done in our `SearchService`.  
**Effort:** 2h  
**Priority:** **P2** — Small improvement, easy to add.

---

## 50. NEWS / TREND-AWARENESS

**Source:** DeepResearch (Alibaba), LDR (news subscriptions)  
**What:** Weight recent papers higher. Detect trending topics. Surface "hot" research areas.  
**How:** Add recency weighting to literature search results. Track citation velocity. Flag papers with rapidly increasing citations.  
**Effort:** 4h  
**Priority:** **P3** — Nice-to-have for research currency.

---

## 51. BEST-FIRST TREE SEARCH (BFTS)

**Source:** AI-Scientist v2  
**What:** Instead of linear pipeline, use tree search over solution space. Each node is a research direction. Branch and select the most promising.  
**How:** Apply at ideation stage: generate multiple idea branches, evaluate each, explore most promising. Already partially in our "tree search" mode.  
**Effort:** 8h  
**Priority:** **P3** — Complex but powerful. AI-Scientist v2's core innovation.

---

## 52. PWA / OFFLINE SUPPORT

**Source:** u14app/deep-research  
**What:** Progressive Web App with service worker. Works offline. IndexedDB for local storage.  
**How:** Add service worker to Vite build. Cache static assets. IndexedDB for run history.  
**Effort:** 4h  
**Priority:** **P3** — Nice for mobile/offline use.

---

## 53. INTERNATIONALIZATION (i18n)

**Source:** u14app/deep-research (en, zh, es), GPT Researcher (en, zh, ja, ko)  
**What:** Accept research questions in any language. Generate proposals in preferred language.  
**How:** We already have 9 language files in `frontend/src/i18n/`. Need to wire into pipeline prompts.  
**Effort:** 4h  
**Priority:** **P3** — Frontend i18n exists. Pipeline i18n doesn't.

---

## 54. COMPUTATIONAL OPTIMIZATION (OR-TOOLS)

**Source:** google/or-tools study  
**What:** Use OR-Tools to optimize: literature search ordering (minimize API calls while maximizing coverage), experiment scheduling, budget allocation across stages.  
**How:** CP-SAT solver for scheduling. Define constraints: max API calls, max time, min coverage. Solver finds optimal search order.  
**Effort:** 10h  
**Priority:** **P3** — Optimization layer. Only useful at scale.

---

## 55. ALIBABA'S 3-STAGE TRAINING PIPELINE (MODEL)

**Source:** DeepResearch (Alibaba, 30.5B MoE)  
**What:** Agentic Continual Pre-Training → Supervised Fine-Tuning → On-Policy RL. The key insight: "data and training environment stability are more critical than the RL algorithm."  
**How:** Not directly adoptable (would require training a model). But the principle applies: pipeline stability > algorithm sophistication.  
**Effort:** N/A  
**Priority:** **P3** — Inspirational. We can't train a 30B model. But the iterative refinement principle applies to prompts.

---

## ALREADY BUILT ✅

These were studied and then implemented in Phases 1-9:

| # | Feature | Batch | Source |
|:--|:--------|:------|:-------|
| ✅ | Fast Path Mode (fast_scan strategy) | B76 | dzhng, LDR |
| ✅ | Pluggable Strategy Architecture | B76 | LDR |
| ✅ | Thinking/Task Model Split | B78 | u14app |
| ✅ | Live Pipeline Progress (SSE + polling) | B79 | open-deep-research |
| ✅ | Iterative Reflection (Reflector stage) | B80 | langchain-LDR |
| ✅ | Multi-Agent Evaluation (AdversarialDebate) | B81 | SkyworkAI |
| ✅ | Knowledge Library (persistent ChromaDB) | B82 | LDR |
| ✅ | SOUL.md (research philosophy) | B83 | dexter |
| ✅ | Journal Writer (per-run notes) | B84 | simonw/research |
| ✅ | Cross-Engine Relevance Filter | B86 | LDR |
| ✅ | Anti-Fabrication ([SOURCE-X] closed-book) | B89 | AutoResearchClaw |
| ✅ | LaTeX/BibTeX Export | B90 | AutoResearchClaw |
| ✅ | Context Manager (compaction) | B91 | dexter |
| ✅ | Concurrency Control | B92 | dexter |
| ✅ | MCP Server (partial) | B93 | LDR |
| ✅ | Planning Agent | B94 | SkyworkAI |
| ✅ | Cost Tracker | B98 | UX gap |
| ✅ | Pipeline Comparison | B99 | UX gap |
| ✅ | Claim Extraction | B121 | QA study |
| ✅ | Claim Store | B122 | QA study |
| ✅ | Wiki Generation | B123 | ARIS |
| ✅ | Curation Engine | B124 | Competitive |
| ✅ | Contradiction Detection | B125 | Reference impl |
| ✅ | Method Problem Detection | B126 | Reference impl |
| ✅ | Study Design | B127 | Reference impl |
| ✅ | Ingestion Scheduler | B128 | LDR |
| ✅ | Connection Agent | B129 | Reference impl |
| ✅ | Wiki Deepening (LLM reasoning) | B131 | Reference impl |
| ✅ | Contradiction Deepening | B132 | Reference impl |
| ✅ | Method Problem Deepening | B133 | Reference impl |
| ✅ | Study Design Deepening | B134 | Reference impl |
| ✅ | Connection Deepening | B135 | Reference impl |
| ✅ | Source-Anchored Quote Verification | QA-01 | QA study |
| ✅ | Staged Confidence (TrustTier) | QA-02 | QA study |
| ✅ | Corroboration Checker | QA-03 | QA study |
| ✅ | Hybrid Model Routing (local/cloud) | B75 | u14app |
| ✅ | Literature Search Parallelization | Perf | dzhng |
| ✅ | Onboarding Overlay | P1-02 | UX audit |
| ✅ | Sidebar Restructuring | B145 | UX audit |
| ✅ | Error Handling (toast/console.warn) | B142 | UX audit |
| ✅ | Config Externalization | B138-139 | Hardcoded audit |
| ✅ | EROCK_ENV Production Mode | B140 | Security audit |

---

## SUMMARY: REMAINING ADOPTION TARGETS

| Priority | Count | Features | Total Effort |
|:---------|:------|:---------|:-------------|
| **P0** | 3 | Adversarial review, LaTeX paper, Docker deploy | 26h |
| **P1** | 11 | Citation audit, claim audit, local docs, recursive search, reflection loop, multi-dim eval, 5-state verification, staged confidence, journal, knowledge library, more engines | 55h |
| **P2** | 18 | Cross-model consensus, SOUL.md, skills, planning agent, TextGrad, recombination, gap queue, error analysis, context mgmt, MCP, domain prompts, budget controls, citation graph, temporal decay, adversarial verification, provenance, novelty via S2, guard commands | 73h |
| **P3** | 9 | Rebuttal, literature monitoring, R&D dual agent, Overleaf, news awareness, BFTS, PWA, i18n pipeline, OR-Tools | 68h |
| **TOTAL** | **41** | | **222h** |

### If I had to pick 10 to build next:

1. **#1** Cross-model adversarial review (8h) — P0, single biggest quality multiplier
2. **#6** Docker deployment (6h) — P0, unblocks sharing
3. **#2** Full paper synthesis LaTeX (12h) — P0, publication-ready output
4. **#45** AI-generated honesty labeling (0.5h) — P1, ethical requirement
5. **#9** Iterative reflection loop (6h) — P1, every competitor iterates
6. **#15** Knowledge library persistence (8h) — P1, research compounds
7. **#16** More search engines (8h) — P1, coverage gap
8. **#36** Semantic Scholar novelty search (4h) — P1, web-verified novelty
9. **#10** Multi-dimensional proposal evaluation (4h) — P1, actionable feedback
10. **#7** Local document ingestion (6h) — P1, unique capability

**Total: 62.5 hours (~8 focused sessions)**

---

*Catalog complete. 55 items from 20+ studies. 14 already built. 41 remaining. 3 priorities.*
