# deep-research (dzhng) — Competitive Study Report

**Source:** https://github.com/dzhng/deep-research  
**Stars:** 18.9K | **Forks:** 1.9K | **License:** MIT  
**Language:** TypeScript | **LOC:** ~500  
**Date:** 2026-05-06

---

## 1. What It Is

A minimalist (<500 LOC) TypeScript research agent. You give it a question, it recursively searches the web, extracts learnings, dives deeper, and writes either a concise answer or a multi-page research report.

**It is closer to our space than Alibaba's DeepResearch — but it still doesn't do what we do.**

---

## 2. Architecture

The entire system is one recursive function. Here's the complete flow:

```
User Query
  → Generate follow-up questions (LLM)
  → User answers questions
  → Generate SERP queries (LLM, structured output)
  → For each query:
      → Firecrawl search (web search + scrape to markdown)
      → Extract learnings + follow-up questions (LLM, structured output)
      → If depth > 0:
          → Recurse with new breadth/2, depth-1
      → Else:
          → Accumulate learnings + URLs
  → Deduplicate learnings + URLs
  → Write final report or answer (LLM, structured output)
```

### Core Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| **Breadth** | 4 | Number of SERP queries per level |
| **Depth** | 2 | Recursion levels |
| **Concurrency** | 2 | Parallel Firecrawl requests |

### Data Flow

```
Level 0: breadth=4 → 4 queries → 4×5 results → learnings + follow-ups
Level 1: breadth=2 → 2 queries per direction → 2×5 results → learnings
Level 2: breadth=1 → 1 query → 5 results → final learnings
```

Total: 4 + 8 + 8 = **20 SERP queries**, **~100 pages scraped**, **~60 learnings extracted**.

### Technology Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | OpenAI o3-mini / DeepSeek R1 via Fireworks | Structured output via Vercel AI SDK |
| Search + Scrape | Firecrawl | One API for search → markdown conversion |
| Structured Output | Vercel AI SDK + Zod | `generateObject()` with Zod schemas |
| Concurrency | p-limit | Simple semaphore for rate limiting |
| Language | TypeScript | Developer experience, easy to understand |

### Key Source Files

| File | LOC | What It Does |
|------|-----|-------------|
| `deep-research.ts` | ~170 | The recursive `deepResearch()` function |
| `prompt.ts` | ~15 | System prompt (12 lines!) |
| `feedback.ts` | ~25 | Generate follow-up questions |
| `run.ts` | ~90 | CLI entry point |
| `ai/providers.ts` | ~30 | LLM provider abstraction |

---

## 3. The Recursive Algorithm (the real innovation)

This is the smartest part of the entire system, and it's ~50 lines:

```typescript
deepResearch({ query, breadth, depth, learnings, visitedUrls }) {
  // 1. Generate SERP queries based on query + prior learnings
  serpQueries = await generateSerpQueries({ query, learnings, numQueries: breadth })
  
  // 2. Process all queries in parallel (with concurrency limit)
  results = await Promise.all(serpQueries.map(async serpQuery => {
    // 2a. Search and scrape
    result = await firecrawl.search(serpQuery.query, { limit: 5 })
    
    // 2b. Extract learnings + follow-up questions from content
    newLearnings = await processSerpResult({ query, result })
    
    // 2c. Recurse if depth > 0
    if (depth - 1 > 0) {
      return deepResearch({
        query: serpQuery.researchGoal + followUpQuestions,
        breadth: ceil(breadth / 2),  // Halve breadth each level
        depth: depth - 1,
        learnings: [...learnings, ...newLearnings.learnings],
        visitedUrls: [...visitedUrls, ...newUrls],
      })
    }
  }))
  
  // 3. Deduplicate and return
  return { learnings: unique(results.flatMap(r => r.learnings)),
           visitedUrls: unique(results.flatMap(r => r.visitedUrls)) }
}
```

**Why this is elegant:**
- Each recursion level uses prior learnings to generate better queries
- Breadth halves each level (4 → 2 → 1), preventing exponential blowup
- Learnings accumulate across all levels — the final report sees everything
- The `researchGoal` from each SERP query carries context into the next level

---

## 4. Output Quality Assessment

### What the sample report looks like

The `report.md` in the repo is a 2,500-word report on "NVIDIA RTX 5000 Series Gaming Performance" with:
- 8 sections (Introduction, Architecture, Benchmarks, AI/Upscaling, Power/Thermal, Competitive Analysis, Market Impact, Conclusion)
- Specific numbers (575W TDP, 30-35% uplift, $1,999.99 pricing)
- Comparison tables
- 20 cited URLs at the bottom

### Honest quality verdict

**It's good for a summary. It's not good for research.**

| Quality Dimension | Rating | Why |
|-------------------|--------|-----|
| Factual accuracy | B+ | Numbers match sources, no hallucinations visible |
| Depth | C | Surface-level synthesis of search results — no original analysis |
| Structure | B | Clean sections, logical flow, but formulaic |
| Citation quality | C | URLs listed at the bottom, not inline citations |
| Original insight | D | Zero original thinking — pure aggregation |
| Academic rigor | D- | No methodology, no peer review, no uncertainty quantification |
| Novelty | F | Finds what already exists, nothing new |

---

## 5. Elephant Rock vs. dzhng/deep-research

### Where We're Similar

Both are **pipeline orchestration** — we both call external LLMs and external search APIs. Neither trains a custom model. Both use recursive/expansive search patterns.

### Where We're Different

| Dimension | dzhng/deep-research | Elephant Rock |
|-----------|---------------------|---------------|
| **Code size** | 500 LOC | 77,516 LOC |
| **Output** | Research report (aggregation) | Research proposal (original) |
| **Goal** | "What is known about X?" | "What should be researched about X?" |
| **Search** | Google (via Firecrawl) | OpenAlex + arXiv (academic) |
| **Recursion** | Breadth × Depth tree | Linear pipeline (7 stages) |
| **Novelty scoring** | None | Vector similarity against all known papers |
| **Gap identification** | None | LLM analyzes papers for missing angles |
| **Idea generation** | None | Tree search + ideation agents |
| **Feasibility** | None | Scored on data/compute/methodology |
| **Proposal writing** | Report from aggregated learnings | Full proposal with math notation |
| **Knowledge graph** | None | Persistent entities + relationships |
| **Frontend** | None (CLI only) | 19-page React app |
| **Embeddings** | None | Real 768-dim Ollama vectors |
| **Follow-up questions** | ✓ Asks user to clarify | ✗ Runs autonomously |
| **Parallel search** | ✓ p-limit concurrency | Sequential source calls |
| **Docker** | ✓ Dockerfile included | ✗ No Docker |
| **Setup time** | 2 minutes | 30+ minutes |

### What They Do Better

1. **Simplicity.** 500 LOC vs our 77K. Their entire system is one recursive function. Ours has 32 subsystems. Simplicity wins for adoption and contribution.

2. **Web search breadth.** Firecrawl searches the entire live web. We search only academic databases. Their information surface is 100× larger.

3. **Follow-up clarification.** They ask the user 3 questions before starting. We take a domain string and run. Their approach produces more targeted output.

4. **Parallel execution.** They process multiple SERP queries concurrently with p-limit. We call sources sequentially.

5. **Docker.** They have a Dockerfile and docker-compose. We have nothing.

6. **Time to value.** `npm install && npm start` → research report in 2 minutes. Our platform needs Python, Node, Ollama, ChromaDB, SQLite, Alembic migrations, and a 26-minute pipeline run.

### What We Do Better

1. **Novelty detection.** They have zero concept of whether their report says anything new. We vector-embed every idea and compare against all known papers.

2. **Gap identification.** They find what's known. We find what's *missing*. This is the fundamental difference.

3. **Original idea generation.** They aggregate. We create. Their output is a summary; ours is a proposal for new research.

4. **Feasibility evaluation.** They don't assess whether the research is doable. We score on data availability, compute requirements, and methodological complexity.

5. **Structured proposals.** Their report is free-form markdown. Our proposals have 10 specific sections including mathematical notation, evaluation plans, and risk mitigation.

6. **Persistent knowledge.** They are stateless — run, output, done. We build a knowledge graph that accumulates across runs.

7. **Academic rigor.** We search OpenAlex (peer-reviewed papers). They search Google (any web page). Our sources are more trustworthy.

---

## 6. What We Should Steal

### 6.1 Adopt Immediately

**Recursive breadth×depth search pattern.** Our literature search is flat — search once, done. Their approach of "search → extract learnings → generate better queries → search again" is clearly superior. We should make our literature search recursive:

```
Current:  search("transformer attention") → 40 papers → done
Better:   search("transformer attention") → 40 papers → extract gaps →
          search("attention mechanism + gap1") → 20 more →
          search("attention + gap2") → 15 more → ...
```

**Follow-up clarification.** Before running a 26-minute pipeline, ask the user 3 questions to narrow the domain. This costs nothing and dramatically improves targeting.

**Parallel source queries.** Our OpenAlex and arXiv calls are sequential. Run them concurrently.

### 6.2 Adopt Medium-Term

**Firecrawl for web search.** Add a general web search source alongside academic databases. When the user asks about a cutting-edge topic with few academic papers, web search fills the gap.

**Two output modes.** They offer "report" (long) or "answer" (short). We only produce proposals. Adding a "literature review" mode that just summarizes what's known would be useful.

**Progress reporting.** They track `totalQueries` and `completedQueries`. Our SSE streaming exists but the frontend hasn't been tested against real data.

### 6.3 Acknowledge as Design Difference

**Statelessness.** They're designed to be stateless — run once, produce output, forget. We're designed to accumulate knowledge. These are valid different architectural choices. Theirs is simpler; ours is more powerful.

**500 LOC.** We can't get there. Our platform has 32 subsystems, 20 API routes, 19 frontend pages, 6 DB migrations. That's not bloat — that's a platform vs. a script. But we should resist adding complexity without clear value.

---

## 7. The Brutal Honest Assessment

**dzhng/deep-research is what most people actually want when they say "AI research tool."**

Ask a question → get a well-sourced report → done. In 2 minutes. With Docker. For free.

**Most people don't want what Elephant Rock does.** They don't want to identify research gaps. They don't want novelty scores. They don't want proposals with math notation. They want a summary of what's known, fast.

**But the people who DO want what we do — active researchers, PhD students, R&D teams — have no other tool that does it.** dzhng/deep-research doesn't help them find what's missing. Alibaba's DeepResearch doesn't help them either. Nothing does.

Our market is small but it has zero competition.

---

## 8. Key Takeaways

> **1. Steal the recursive breadth×depth search.** It's 50 lines of code that would make our literature search dramatically better.

> **2. Steal the follow-up questions.** 25 lines of code that would dramatically improve targeting.

> **3. Steal Docker.** One Dockerfile that lets anyone run the platform in 60 seconds.

> **4. Don't try to compete on what they do.** They aggregate faster and simpler. We should own the niche they can't touch: gap identification → novel ideas → scored proposals.

> **5. Our 77K LOC platform needs a "fast path."** A 500-line mode that does: domain → quick gaps → quick ideas → quick proposal. No knowledge graph, no embeddings, no tree search. Just LLM calls. For when users want results in 2 minutes, not 26.
