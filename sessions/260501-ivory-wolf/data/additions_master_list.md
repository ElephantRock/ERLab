# Elephant Rock — Master Additions List

**Generated**: 2026-05-06  
**Sources**: 16 competitive studies + simonw/research methodology + honest deep assessment + 75 AIV batches  
**Scope**: Everything identified as missing, weak, or worth adding — from every competitive study, every gap analysis, and every pipeline run.

---

## TIER 1 — Critical (Blocks real users from getting value)

These are the things that prevent a real researcher from actually using Elephant Rock productively.

### T1-01. Fast Path Mode (2-minute pipeline)
**Source**: dzhng/deep-research, u14app/deep-research, LDR  
**What**: Skip knowledge graph, embeddings, tree search, clustering for rapid results. User selects "Quick Scan" vs "Deep Research". Quick scan: literature → gaps → ideas → short proposals in 2-5 minutes. Deep: current pipeline (25+ min).  
**Why**: Every successful tool has a fast mode. 25 minutes is too long for exploration. Users will bounce before seeing results.  
**How**: New `PipelineStrategy` enum, `FastPathOrchestrator` that only runs ingestion → gap analysis → ideation → light synthesis. No ChromaDB, no tree search.

### T1-02. Iterative Reflection Loop
**Source**: langchain-ai/local-deep-researcher, open-deep-research, Jina DeepResearch, LDR  
**What**: After each pipeline stage, the LLM reflects on the output and decides whether to retry, refine, or proceed. "Does this gap list cover the domain?" "Is this idea truly novel?"  
**Why**: Currently the pipeline runs straight through. Every competitive tool iterates. The single-pass approach produces mediocre results.  
**How**: Add `ReflectionStage` after gap analysis and ideation. LLM evaluates its own output with a rubric. If score < threshold, regenerate with feedback.

### T1-03. Multi-Dimensional Proposal Evaluation
**Source**: Jina DeepResearch (5-dimension eval)  
**What**: Score proposals on 5 dimensions: Novelty, Feasibility, Completeness, Rigor, Clarity. Each dimension gets a 0-1 score with written justification. Currently we only have a single novelty score.  
**Why**: A single score tells the user nothing about WHY a proposal is good or bad. 5 dimensions give actionable feedback.  
**How**: New `ProposalEvaluator` class with dimension-specific prompts. Store as JSON alongside proposals. Display as radar chart in frontend.

### T1-04. Research Journal per Pipeline Run
**Source**: simonw/research methodology  
**What**: Every pipeline run produces a `notes.md` tracking what happened at each stage: what queries were tried, what failed, what succeeded, what was surprising. Plus a clean `README.md` summary.  
**Why**: Currently pipeline runs produce raw JSON artifacts. No narrative. No sense of journey. Researchers need the story, not just the data.  
**How**: `JournalWriter` class that accumulates stage notes during pipeline execution. Generates markdown report at end.

### T1-05. Live Pipeline Progress with Real Messages
**Source**: open-deep-research (animated activity panel), u14app/deep-research  
**What**: Replace generic "Stage 3/7 complete" with actual LLM thoughts: "Searching for papers on sparse attention...", "Found 23 papers, clustering by topic...", "Gap identified: no work on attention in genomic sequences".  
**Why**: Current SSE events are too coarse. Users see nothing for 10+ minutes then everything appears. The "thinking" panel is the #1 UX feature of ChatGPT Deep Research.  
**How**: Hook into each stage's internal steps. Emit granular SSE events with natural language descriptions.

---

## TIER 2 — High Impact (Makes the platform competitive)

These are what the top-rated competitors have that we don't.

### T2-01. Pluggable Strategy Architecture
**Source**: LDR (strategy factory pattern)  
**What**: Define pipeline strategies as named configs: "quick_scan", "deep_research", "academic_proposal", "literature_review". Each strategy specifies which stages to run, parameters, timeouts. Users select strategy at pipeline start.  
**Why**: One pipeline config doesn't fit all use cases. A literature review doesn't need proposal synthesis. A quick scan doesn't need tree search.  
**How**: `StrategyFactory` with YAML/JSON strategy definitions. Current pipeline becomes "deep_research" strategy.

### T2-02. More Search Engines (2 → 25)
**Source**: LDR (25+ search engines)  
**What**: Add: Semantic Scholar (with API key), PubMed, Google Scholar, DBLP, CrossRef, CORE, Microsoft Academic, Wikipedia, Google Patents, Europe PMC. Currently only OpenAlex + arXiv.  
**Why**: 2 search engines = limited coverage. Real researchers use 5-10 sources. LDR has 25.  
**How**: Implement `AcademicSearchSource` for each. Each has `search()`, `get_paper()`, `rate_limit_info()`. Add `MultiSourceSearcher` that fans out queries and merges results.

### T2-03. Knowledge Library (Persistent Research Memory)
**Source**: LDR (knowledge library loop)  
**What**: Every paper, gap, and idea from every pipeline run is indexed in a persistent knowledge base. Future runs query this library first before hitting external sources. Research compounds over time.  
**Why**: Currently each pipeline run starts from scratch. Run #2 doesn't know about Run #1. This is insane for a research tool.  
**How**: Persistent ChromaDB/collection per domain. On pipeline start, query existing knowledge first. New papers are added to the library.

### T2-04. Cross-Engine Relevance Filter
**Source**: LDR  
**What**: After gathering papers from multiple engines, use an LLM to rerank by relevance, deduplicate by DOI/title similarity, and filter out irrelevant results.  
**Why**: Multiple search engines = lots of noise. Need intelligent post-search filtering.  
**How**: `RelevanceFilter` class that takes papers + original query, calls LLM to score relevance 0-1, deduplicates, returns top-K.

### T2-05. SOUL.md — Platform Research Philosophy
**Source**: dexter (SOUL.md personality system)  
**What**: A `SOUL.md` file that defines Elephant Rock's research philosophy: what makes a good gap, what makes a novel idea, what makes a rigorous proposal. The LLM reads this before generating anything.  
**Why**: Currently the LLM has no personality or philosophy. It generates generic academic content. A defined philosophy produces more distinctive, higher-quality output.  
**How**: `SOUL.md` in project root with sections on research values, quality criteria, domain expertise, and anti-patterns.

### T2-06. SKILL.md — Extensible Research Skills
**Source**: dexter (SKILL.md workflows), simonw/research (OpenAI Skills)  
**What**: Define multi-step research skills as markdown files: "Systematic Review Skill", "Proposal Writing Skill", "Literature Mapping Skill", "Gap Validation Skill". Each skill defines steps, prompts, and quality criteria.  
**Why**: Currently the pipeline is rigid. Skills would let users customize the research process without code changes.  
**How**: `skills/` directory with `.md` files. `SkillLoader` parses frontmatter + steps. Pipeline orchestrator selects skills based on user intent.

### T2-07. Thinking/Task Model Split
**Source**: u14app/deep-research  
**What**: Use a small, fast model (e.g., Gemini Flash) for "thinking" tasks (classification, extraction, ranking) and a large model (Claude, GPT-4) for "generation" tasks (writing proposals, synthesizing ideas).  
**Why**: Currently every LLM call uses the same model. Small tasks don't need a big model. This would cut costs 50-70% and speed up the pipeline.  
**How**: Extend `ProviderFactory` with `thinking_model` and `generation_model` config. Stages declare which type they need.

### T2-08. Error Analysis as Knowledge
**Source**: Jina DeepResearch  
**What**: When a gap is rejected, an idea scores low, or a proposal fails quality checks, store the rejection reason as structured learning. Future runs query this "failure database" to avoid repeating mistakes.  
**Why**: Currently failures are invisible. The pipeline doesn't learn from its mistakes across runs.  
**How**: `failure_log` table in DB. Each failure has: stage, input_hash, reason, suggestion. Queried at pipeline start.

---

## TIER 3 — Significant (Differentiators & Quality)

These would make Elephant Rock stand out from the competition.

### T3-01. Recursive Breadth × Depth Literature Search
**Source**: dzhng/deep-research  
**What**: Start with a broad query, identify the most relevant papers, then recursively search for papers that cite them or are cited by them. Breadth = how many branches to follow. Depth = how many citation hops.  
**Why**: Current literature search is flat — one query, one result set. Recursive citation following finds the foundational papers that simple keyword search misses.  
**How**: `RecursiveLiteratureSearcher` with `breadth` and `depth` params. Uses OpenAlex citations API.

### T3-02. Round-Robin Gap Queue
**Source**: Jina DeepResearch  
**What**: Instead of generating all gaps at once, maintain a queue of sub-problems and cycle through them systematically. Each cycle deepens understanding of one gap before moving to the next.  
**Why**: Current approach generates gaps in one shot, then moves on. No deep exploration of individual gaps.  
**How**: `GapQueue` class with round-robin scheduling. Each gap gets N exploration rounds.

### T3-03. Anti-Fabrication System (Verified Registry)
**Source**: AutoResearchClaw  
**What**: Every claim in a proposal must be traceable to a specific paper in the literature. If a claim can't be sourced, it's flagged. Build a `VerifiedRegistry` that maps claims → source papers.  
**Why**: Currently proposals can contain fabricated citations or unsupported claims. An anti-fabrication system ensures everything is grounded.  
**How**: `ClaimExtractor` pulls claims from proposals. `ClaimVerifier` checks each against the paper corpus. Unverified claims are flagged.

### T3-04. LaTeX/PDF Export with Domain Templates
**Source**: AutoResearchClaw, AI-Researcher  
**What**: Export proposals as LaTeX with domain-specific templates (NLP, CV, systems, theory). Compile to PDF. Currently export is only markdown.  
**Why**: Academic researchers need LaTeX. Markdown is not a deliverable format for grants or submissions.  
**How**: `LaTeXExporter` with template inheritance. Domain templates define sections, formatting, citation style. Use `jinja2` + `pdflatex`.

### T3-05. Sandboxed Code Execution
**Source**: AutoResearchClaw (4-backend sandbox), simonw/research (QuickJS sandbox, Codex sandbox)  
**What**: Execute experiment code in a sandboxed environment (Docker, subprocess, or WASM). The experiment generator already exists but execution is stubbed.  
**Why**: Without execution, the "experiment" stage is just more text generation. Real experiments need real code execution with real results.  
**How**: Wire up existing `docker_backend.py` or `subprocess_backend.py`. Add memory/time limits inspired by QuickJS sandbox research.

### T3-06. 3-Tier Context Management
**Source**: dexter  
**What**: Microcompact → memory flush → compaction → truncation. When context exceeds limits, first summarize older content, then compact into key points, then truncate oldest. Never lose the most important context.  
**Why**: Current pipeline has no context management. Long runs risk running out of context or losing important earlier findings.  
**How**: `ContextManager` class with 3 strategies. Integrated into each stage's prompt construction.

### T3-07. Tool Concurrency with Safety Flags
**Source**: dexter  
**What**: Mark tools as read-only or mutation. Run read-only tools in parallel, mutations sequentially. Add `safe_parallel=True` flag to tool definitions.  
**Why**: Current pipeline runs stages sequentially. Literature searches across multiple engines could run in parallel.  
**How**: `ToolExecutor` with concurrency flags. `asyncio.gather()` for read-only tools, sequential for mutations.

### T3-08. MCP Server (Expose Pipeline as Tool)
**Source**: LDR (MCP server), existing `backend/pipeline/tools/mcp/`  
**What**: Expose the Elephant Rock pipeline as an MCP tool so other AI systems (Claude, Cursor, etc.) can start research pipelines programmatically.  
**Why**: The MCP server code exists but is not wired up. This would make Elephant Rock a tool within other AI workflows, not just a standalone app.  
**How**: Complete MCP server implementation. Register tools: `start_pipeline`, `get_run_status`, `get_gaps`, `get_ideas`, `get_proposals`.

### T3-09. Self-Improving Prompts via TextGrad
**Source**: SkyworkAI/DeepResearchAgent  
**What**: After each pipeline run, evaluate prompt quality. Use "textual gradient descent" — generate prompt improvements based on output quality scores. Maintain a prompt version history.  
**Why**: Currently prompts are static. They don't improve over time. TextGrad would make the pipeline self-improving.  
**How**: `PromptEvolutionEngine`. After each run, compute "loss" (quality scores). Generate prompt variants. A/B test on next run.

### T3-10. Planning Agent (Hierarchical Pipeline Control)
**Source**: SkyworkAI/DeepResearchAgent  
**What**: A "planning agent" that decides which pipeline stages to run based on the research question. Simple questions get 3 stages. Complex ones get all 7+. The planner adapts mid-run.  
**Why**: Currently all pipeline runs follow the same stage sequence. A planning agent would make the pipeline adaptive.  
**How**: `PlanningAgent` that takes research question + time budget, outputs a stage plan. Re-plans after each stage.

---

## TIER 4 — Valuable (Polish & Depth)

These add polish and make the platform feel complete.

### T4-01. Domain-Specific Prompts
**Source**: Competitive gap analysis  
**What**: Different prompts for different domains: CS/NLP, biology, medicine, social science, engineering. Each domain has different evaluation criteria, proposal structures, and terminology.  
**Why**: Current prompts are generic academic. A biomedical researcher needs different quality criteria than a systems researcher.

### T4-02. Collaborative Annotations
**Source**: Competitive gap analysis  
**What**: Let multiple users annotate gaps, ideas, and proposals with comments, tags, and ratings. Show annotation threads on each entity.  
**Why**: Research is collaborative. Currently Elephant Rock is single-user. Annotations enable team research.

### T4-03. Citation Graph Visualization
**Source**: Research Rabbit, Semantic Scholar  
**What**: Interactive visualization showing which papers cite which, where gaps exist in the citation network, and how ideas connect to the literature.  
**Why**: The knowledge graph exists but is abstract. A citation graph is what researchers actually want to see.

### T4-04. Budget/Time Controls
**Source**: Honest assessment finding  
**What**: User sets max time (5min, 15min, 30min, 60min) and max cost ($0.50, $1, $5, $10). Pipeline respects these limits and degrades gracefully (skip stages, reduce paper count, use smaller model).  
**Why**: Currently a pipeline run costs an unknown amount and takes 10-26 minutes. Users need control.

### T4-05. Pipeline Comparison View
**Source**: UX gap  
**What**: Side-by-side comparison of two pipeline runs: same topic, different parameters. Show how gaps, ideas, and proposals differ.  
**Why**: Users want to see how parameter changes affect output. Currently you can only view one run at a time.

### T4-06. Email/Notification on Completion
**Source**: UX gap  
**What**: When a long pipeline run completes, send an email or push notification with a summary: "Your pipeline run found 5 gaps and 2 ideas. Top idea scored 0.92."  
**Why**: 25-minute pipeline runs require users to keep the tab open. They should be able to close it.

### T4-07. Proposal Versioning & Diffing
**Source**: simonw/research (git-based tracking)  
**What**: Track proposal revisions. Show diff between versions. Let users edit proposals and regenerate sections.  
**Why**: Currently proposals are generated once. No iteration, no refinement after generation.

### T4-08. Batch Pipeline Scheduling
**Source**: dexter (cron scheduling)  
**What**: Schedule recurring pipeline runs: "Run a pipeline on this topic every Monday" or "Re-run when new papers appear."  
**Why**: Research is ongoing. A one-shot pipeline misses papers published after the run.

### T4-09. API Key Management UI
**Source**: UX gap  
**What**: Settings page with fields for: OpenAI API key, Anthropic API key, Semantic Scholar API key, etc. Currently keys are in `.env` only.  
**Why**: Non-technical users can't edit `.env` files. The settings page needs API key management.

### T4-10. Dark Mode
**Source**: UX standard  
**What**: Toggle between light and dark themes. Persist preference.  
**Why**: Every modern app has dark mode. Researchers work at night.

### T4-11. Keyboard Navigation & Shortcuts
**Source**: UX gap  
**What**: `j/k` to navigate ideas, `Enter` to open, `Escape` to close, `/` to focus search, `?` for help.  
**Why**: Power users navigate with keyboards. Current UI is mouse-only.

### T4-12. Export to Notion/Obsidian/Markdown
**Source**: UX gap  
**What**: One-click export of pipeline results to Notion, Obsidian vault, or standalone markdown files.  
**Why**: Researchers use these tools. Proposals should land where they work.

---

## TIER 5 — Nice-to-Have (Long-term vision)

These are aspirational features based on cutting-edge research.

### T5-01. Judge-ML Dual Agent Loop
**Source**: AI-Researcher (NeurIPS 2025 Spotlight)  
**What**: One agent generates a proposal, another agent (the Judge) critiques it. They iterate until the Judge approves. This produces significantly better output than single-pass generation.  
**Why**: AI-Researcher's #1 innovation. Judge quality produces better papers than any other technique.

### T5-02. GPU Code Execution (Docker + CUDA)
**Source**: AI-Researcher  
**What**: Execute experiment code with GPU access inside Docker containers. Run real neural network training, evaluate on real datasets.  
**Why**: AI-Researcher produces papers with real experimental results. Elephant Rock produces text about hypothetical experiments.

### T5-03. Reference Codebase Grounding
**Source**: AI-Researcher  
**What**: Give the pipeline a reference codebase (e.g., HuggingFace Transformers). The pipeline generates ideas grounded in actual code structures and APIs, not just paper abstracts.  
**Why**: AI-Researcher generates ideas that can actually be implemented because they're grounded in real code.

### T5-04. Domain-Specific LaTeX Templates
**Source**: AI-Researcher  
**What**: LaTeX templates for: ML conference papers (NeurIPS, ICML, ICLR), journal articles (Nature, PNAS), grant proposals (NSF, NIH), and PhD thesis chapters.  
**Why**: Different venues have different formatting requirements. One-size-fits-all LaTeX doesn't work.

### T5-05. OR-Tools Integration for Optimization
**Source**: google/or-tools study  
**What**: Use OR-Tools to optimize: literature search ordering (minimize API calls while maximizing coverage), experiment scheduling (GPU time allocation), budget allocation across pipeline stages.  
**Why**: The pipeline makes no optimization decisions. It could be smarter about resource allocation.

### T5-06. Community Gap/Idea Marketplace
**Source**: Competitive landscape analysis  
**What**: Users share their gaps and ideas publicly. Others can vote, extend, or build on them. Create a "research problem marketplace."  
**Why**: Currently all research is siloed per user. A marketplace creates network effects.

### T5-07. Multilingual Pipeline
**Source**: Competitive landscape analysis  
**What**: Accept research questions in any language. Search literature in multiple languages. Generate proposals in the user's preferred language.  
**Why**: Research is global. English-only is a significant limitation.

### T5-08. Real-Time Collaboration (WebSocket)
**Source**: Competitive landscape analysis  
**What**: Multiple users view the same pipeline run in real-time. Cursor sharing, live annotations, shared proposal editing.  
**Why**: Research teams work together. Real-time collaboration is table stakes for modern tools.

### T5-09. Automated Literature Monitoring
**Source**: LDR (news subscriptions)  
**What**: User defines a research topic. The platform monitors arXiv, Semantic Scholar, etc. daily and notifies when new relevant papers appear. Automatically updates gaps and ideas.  
**Why**: Research doesn't stop after one pipeline run. Ongoing monitoring keeps the research current.

### T5-10. Quality-Scored Journal Rankings
**Source**: LDR (journal quality scoring, 212K+ sources)  
**What**: Score journals by impact factor, acceptance rate, review quality, and domain relevance. Use scores to weight paper quality in gap analysis.  
**Why**: Not all papers are equal. A paper in Nature should carry more weight than a preprint.

---

## Summary Table

| Tier | Count | Items | Est. LOC Each | Priority |
|------|:-----:|:-----:|:-------------:|:--------:|
| **T1 — Critical** | 5 | Fast path, reflection, multi-dim eval, journal, live progress | 200-500 | DO NOW |
| **T2 — High Impact** | 8 | Strategies, search engines, knowledge library, relevance filter, SOUL.md, skills, model split, error analysis | 200-800 | DO NEXT |
| **T3 — Significant** | 10 | Recursive search, gap queue, anti-fabrication, LaTeX, sandbox, context mgmt, concurrency, MCP, TextGrad, planner | 300-1000 | PLAN |
| **T4 — Valuable** | 12 | Domain prompts, annotations, citation graph, budget controls, comparison, notifications, versioning, scheduling, API keys, dark mode, shortcuts, export | 100-500 | BACKLOG |
| **T5 — Nice-to-Have** | 10 | Judge loop, GPU execution, codebase grounding, LaTeX templates, OR-Tools, marketplace, multilingual, real-time collab, monitoring, journal rankings | 500-2000 | VISION |
| **TOTAL** | **45** | | | |

---

## Recommended Execution Order

If I had to pick **10 to build next**, in order:

1. **T1-01**: Fast Path Mode — Ship a 2-minute pipeline TODAY
2. **T1-05**: Live Progress Messages — Keep users engaged during runs
3. **T2-01**: Pluggable Strategies — Architecture for all pipeline modes
4. **T1-02**: Iterative Reflection — Close the quality gap
5. **T2-02**: More Search Engines — Semantic Scholar + PubMed + Google Scholar
6. **T1-03**: Multi-Dimensional Eval — 5-score proposals
7. **T2-03**: Knowledge Library — Research compounds across runs
8. **T2-05**: SOUL.md — Define our research philosophy
9. **T3-01**: Recursive Literature Search — Find foundational papers
10. **T1-04**: Research Journal per Run — Narrative documentation
