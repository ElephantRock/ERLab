# u14app/deep-research — Comprehensive Competitive Study

**Repository**: https://github.com/u14app/deep-research  
**Stars**: 4.6K | **Forks**: 1.1K | **License**: MIT  
**Version**: 0.11.1 | **Date**: 2026-05-06  
**Tech Stack**: Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui, Vercel AI SDK  
**Inspired by**: [dzhng/deep-research](https://github.com/dzhng/deep-research)

---

## 1. What It Is

**u14app/deep-research** is a web-based "deep research" tool that generates comprehensive research reports from a single query in ~2 minutes. It uses a Thinking model (for planning/report writing) and a Task model (for search processing) with web search to produce detailed, citation-linked Markdown reports.

**Tagline**: "Lightning-Fast Deep Research Report"

**Positioning**: A consumer-friendly research report generator — not a scientific paper writer, not a gap-analysis engine, not an experiment runner. Think "ChatGPT Deep Research, but open-source and self-hosted."

---

## 2. Architecture Overview

### 2.1 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | Next.js 15 (App Router, Turbopack) |
| **Frontend** | React 19, Tailwind CSS 3, shadcn/ui |
| **State** | Zustand (5 stores: global, history, knowledge, setting, task) |
| **AI SDK** | Vercel AI SDK (`ai` v4.3) |
| **LLM Providers** | 14 providers (Gemini, OpenAI, Anthropic, DeepSeek, Grok, Mistral, Azure, OpenRouter, Ollama, etc.) |
| **Search Engines** | 6 providers (SearXNG, Tavily, Firecrawl, Exa, Bocha, Brave) + model-native search |
| **Streaming** | Server-Sent Events (SSE) |
| **API** | SSE endpoint + MCP server (StreamableHTTP + SSE transport) |
| **Deployment** | Vercel, Cloudflare Pages, Docker, static export |
| **PWA** | Progressive Web App with service worker |
| **Storage** | Browser-local (IndexedDB via localforage) |
| **Rendering** | react-markdown, KaTeX (math), Mermaid (diagrams), rehype-highlight |

### 2.2 Source Structure

```
src/
├── app/
│   ├── api/
│   │   ├── ai/              # AI provider route
│   │   ├── crawler/         # Web crawler route
│   │   ├── mcp/             # MCP server (StreamableHTTP + SSE)
│   │   ├── search/          # Search provider route
│   │   ├── sse/             # SSE streaming endpoint
│   │   └── utils.ts         # API helper functions
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Main page
│   └── sw.ts                # Service worker (PWA)
├── components/
│   ├── Artifact.tsx         # Report editor (WYSIWYM + Markdown)
│   ├── History.tsx          # Research history browser
│   ├── Setting.tsx          # Settings panel
│   ├── Internal/            # Internal UI components
│   ├── Knowledge/           # Local knowledge base components
│   ├── MagicDown/           # Enhanced Markdown rendering
│   ├── Provider/            # LLM/search provider config
│   ├── Research/
│   │   ├── Topic.tsx        # Research topic input
│   │   ├── SearchResult.tsx # Search results display
│   │   ├── FinalReport/     # Final report rendering
│   │   ├── WorkflowProgress.tsx  # Pipeline progress
│   │   └── Feedback.tsx     # Research feedback/suggestions
│   └── ui/                  # shadcn/ui primitives
├── constants/
│   └── prompts.ts           # 17 customizable prompt templates
├── hooks/                   # React hooks
├── locales/                 # i18n (en, zh, es)
├── store/
│   ├── global.ts            # Global UI state
│   ├── history.ts           # Research history persistence
│   ├── knowledge.ts         # Knowledge base state
│   ├── setting.ts           # Settings persistence
│   └── task.ts              # Research task state
└── utils/
    ├── deep-research/
    │   ├── index.ts         # Core DeepResearch class (~300 lines)
    │   ├── prompts.ts       # Prompt construction helpers
    │   ├── provider.ts      # 14 LLM provider factory
    │   └── search.ts        # 6 search provider factory
    ├── parser/              # Output parsers
    ├── animate-text.ts      # Text animation utilities
    ├── artifact.ts          # Artifact editing
    ├── crawler.ts           # Web crawler
    ├── file.ts              # File upload/processing
    ├── markdown.ts          # Markdown utilities
    ├── model.ts             # Model utilities
    └── text.ts              # Text utilities (ThinkTag processor)
```

### 2.3 Core Engine (~300 lines)

The entire research engine is a single class `DeepResearch` with 5 methods:

```typescript
class DeepResearch {
  // Step 1: Generate research plan using Thinking model
  async writeReportPlan(query: string): Promise<string>
  
  // Step 2: Generate SERP search queries from plan
  async generateSERPQuery(reportPlan: string): Promise<SearchTask[]>
  
  // Step 3: Execute search tasks sequentially
  async runSearchTask(tasks: SearchTask[]): Promise<SearchTask[]>
  
  // Step 4: Write final report using Thinking model
  async writeFinalReport(plan, tasks): Promise<FinalReportResult>
  
  // Orchestrate all steps
  async start(query: string): Promise<FinalReportResult>
}
```

**That's it.** The entire research engine is ~300 lines of TypeScript. Compare this to AutoResearchClaw's 54K+ lines across 28 modules.

---

## 3. How It Works — Step by Step

### 3.1 Research Flow

```
User enters topic
       ↓
[Thinking Model] Generate research plan (streamed)
       ↓
[Thinking Model] Generate SERP queries (JSON array)
       ↓
For each SERP query:
  ├── Option A: Model-native search (Gemini grounding, OpenAI web_search_preview, OpenRouter web plugin)
  └── Option B: External search API (Tavily, Firecrawl, Exa, Bocha, Brave, SearXNG)
       ↓
[Task Model] Process search results into "learnings" (streamed)
       ↓
Repeat search if user requests more depth
       ↓
[Thinking Model] Write final report from all learnings (streamed, 5+ pages)
       ↓
Return: { title, finalReport, learnings, sources, images }
```

### 3.2 Model Architecture

| Model Type | Purpose | Examples |
|-----------|---------|---------|
| **Thinking Model** | Report planning, SERP generation, final report writing | Gemini 2.0 Flash Thinking, GPT-4o, Claude 3.5 Sonnet |
| **Task Model** | Search result processing, learning extraction | Gemini 2.0 Flash, GPT-4o-mini, Claude 3 Haiku |

The Thinking model handles the "deep" work (planning, synthesis). The Task model handles the "fast" work (processing individual search results). This split is elegant — use expensive reasoning only where it matters.

### 3.3 Search Architecture

**6 external search providers + model-native search:**

| Provider | Type | Features |
|----------|------|----------|
| **Tavily** | API | Advanced search, images, raw content |
| **Firecrawl** | API | Web scraping + search, markdown output |
| **Exa** | API | Research paper focused, summaries, image links |
| **Bocha** | API | Web + image search, summaries |
| **Brave** | API | Web + image search (separate endpoints) |
| **SearXNG** | Self-hosted | Metasearch (Google, Bing, DuckDuckGo, Brave, Wikipedia, arXiv, Google Scholar, PubMed) |
| **Model-native** | Built-in | Gemini grounding, OpenAI web_search_preview, OpenRouter web plugin |

**For academic scope**, SearXNG can route to arXiv, Google Scholar, and PubMed specifically.

### 3.4 Streaming Architecture

All research progress is streamed via SSE:

```
event: progress  data: { step: "report-plan", status: "start" }
event: message   data: { type: "text", text: "<report-plan>\n" }
event: message   data: { type: "text", text: "## Key Findings..." }
event: reasoning data: { type: "text", text: "Let me think about..." }
event: progress  data: { step: "serp-query", status: "end", data: [...] }
event: progress  data: { step: "search-task", status: "start", name: "AI trends 2024" }
event: progress  data: { step: "final-report", status: "start" }
event: message   data: { type: "text", text: "<final-report>\n" }
event: progress  data: { step: "final-report", status: "end", data: {...} }
```

The SSE API also supports **GET requests** — you can watch a deep research run via URL like a video.

### 3.5 MCP Server

Exposed as a Model Context Protocol service for integration with other AI tools:

```
StreamableHTTP: /api/mcp     (transport: streamable-http)
SSE:           /api/mcp/sse  (transport: sse)
```

Timeout: 600s (deep research takes time).

---

## 4. Key Features in Detail

### 4.1 Local Knowledge Base

Users can upload text, Office, PDF files as a local knowledge base. During research, the system retrieves from both the knowledge base and web search.

### 4.2 Artifact Editor

Two editing modes:
- **WYSIWYM** (What You See Is What You Mean) — rich text editing
- **Markdown** — raw markdown editing

Plus:
- Adjust reading level
- Change article length
- Full-text translation

### 4.3 Knowledge Graph

One-click Mermaid diagram generation from the research report. Extracts entities and relationships, renders as a graph.

### 4.4 Research History

All previous research results saved locally (IndexedDB). Users can:
- Review past research
- Resume research from any stage
- Conduct deeper research on previous topics

### 4.5 Custom Prompt Templates

17 customizable prompt templates:
1. `systemInstruction` — System persona
2. `outputGuidelinesPrompt` — Output formatting rules
3. `systemQuestionPrompt` — Clarification questions
4. `guidelinesPrompt` — Integration guidelines
5. `reportPlanPrompt` — Report planning
6. `serpQuerySchemaPrompt` — JSON schema for SERP queries
7. `serpQueriesPrompt` — SERP query generation
8. `queryResultPrompt` — Model-native search processing
9. `citationRulesPrompt` — Citation formatting
10. `searchResultPrompt` — External search processing
11. `searchKnowledgeResultPrompt` — Knowledge base search processing
12. `reviewPrompt` — Follow-up research review
13. `finalReportCitationImagePrompt` — Image citation rules
14. `finalReportReferencesPrompt` — Reference citation rules
15. `finalReportPrompt` — Final report generation
16. `rewritingPrompt` — Text rewriting
17. `knowledgeGraphPrompt` — Knowledge graph generation

All overridable via config or API parameter.

### 4.6 Multi-Key Payload

Support multiple API keys per provider (comma-separated). The system polls across keys for better rate limit handling.

### 4.7 Privacy

All data stored locally in the browser (IndexedDB). No server-side storage. Server proxy mode is optional.

---

## 5. Comparison with Elephant Rock

### 5.1 Feature Matrix

| Feature | Elephant Rock | u14app/deep-research |
|---------|:---:|:---:|
| **Literature Search** | OpenAlex + arXiv (real academic APIs) | 6 search engines (general web) |
| **Gap Analysis** | ✅ Full pipeline | ❌ None |
| **Idea Generation** | ✅ With tree search + Borda voting | ❌ None |
| **Novelty Scoring** | ✅ Real 768-dim embeddings | ❌ None |
| **Experiment Execution** | ❌ No sandbox | ❌ None |
| **Paper Writing** | Proposals (35K+ chars) | Research reports (Markdown) |
| **LaTeX Export** | ❌ None | ❌ None |
| **Citation Verification** | Basic | ✅ Inline citation with source links |
| **Knowledge Graph** | ✅ Full KG + RAG | ✅ Mermaid diagram generation |
| **Frontend** | Full React SPA (19 pages) | Next.js SPA (single page + settings) |
| **Streaming** | SSE pipeline progress | SSE full research progress |
| **Multi-LLM** | Anthropic only | 14 providers |
| **Local Knowledge Base** | ❌ None | ✅ File upload + processing |
| **Report Editing** | ❌ None | ✅ WYSIWYM + Markdown |
| **MCP Server** | ❌ None | ✅ StreamableHTTP + SSE |
| **PWA** | ❌ None | ✅ Progressive Web App |
| **Docker** | ❌ None | ✅ One-command Docker |
| **i18n** | 9 languages | 3 languages |
| **Runtime** | 10-26 min (pipeline) | ~2 min (research report) |
| **Code Size** | ~77K LOC (Python+TS) | ~5K LOC (TypeScript only) |

### 5.2 Where u14app/deep-research Excels

1. **Speed**: ~2 minutes vs our 10-26 minutes. Different product — fast reports vs deep proposals.
2. **Multi-LLM**: 14 providers vs our single Anthropic endpoint. Massive flexibility.
3. **Search diversity**: 6 external search engines + model-native search vs our 2 academic APIs.
4. **UI polish**: Clean, modern Next.js + shadcn/ui. Artifact editor, knowledge graphs, history.
5. **MCP integration**: Can be used as a tool by other AI systems.
6. **PWA**: Works like a native app.
7. **Docker**: One-command deployment.
8. **Simplicity**: ~300 lines of core logic. Elegant and maintainable.
9. **Customizable prompts**: 17 templates all overridable.
10. **Local knowledge base**: Upload documents for context-aware research.

### 5.3 Where Elephant Rock Excels

1. **Academic rigor**: Real academic APIs (OpenAlex, arXiv), not general web search.
2. **Gap identification**: Unique gap analysis pipeline with clustering and dedup.
3. **Novel idea generation**: Tree search + Borda voting + novelty scoring with real embeddings.
4. **Research depth**: Proposals with 10 sections, 35K+ chars. Their reports are shallower.
5. **Vector embeddings**: Real 768-dim Ollama embeddings for similarity search.
6. **Knowledge graph**: Full vector store + KG + RAG, not just Mermaid diagrams.
7. **Pipeline architecture**: 32 subsystems with stages, checkpoints, resume.
8. **Domain-specific**: Purpose-built for research discovery. General purpose for them.

---

## 6. Comparison with Other Tools

### 6.1 vs dzhng/deep-research (its inspiration)

| Aspect | dzhng/deep-research | u14app/deep-research |
|--------|-------------------|---------------------|
| **Stars** | 18.9K | 4.6K |
| **Language** | Python (500 LOC) | TypeScript (~5K LOC) |
| **Frontend** | None (CLI) | Full Next.js SPA |
| **LLM Support** | OpenAI only | 14 providers |
| **Search** | Tavily only | 6 engines + model-native |
| **Deployment** | CLI | Vercel, Cloudflare, Docker, static |
| **MCP** | ❌ | ✅ |
| **PWA** | ❌ | ✅ |
| **Knowledge Base** | ❌ | ✅ |
| **History** | ❌ | ✅ |
| **Editing** | ❌ | ✅ (WYSIWYM + Markdown) |

**Verdict**: u14app is a production-grade web product built on dzhng's algorithm. Same core idea, much more polished.

### 6.2 vs AutoResearchClaw

| Aspect | AutoResearchClaw | u14app/deep-research |
|--------|-----------------|---------------------|
| **Output** | Full academic papers (10-19 pages, LaTeX) | Research reports (Markdown) |
| **Experiments** | ✅ Sandbox execution with self-healing | ❌ None |
| **Code Generation** | ✅ Multi-provider | ❌ None |
| **Citation Verification** | ✅ 4-layer (arXiv → DOI → S2 → LLM) | Basic (source links) |
| **Anti-Fabrication** | ✅ VerifiedRegistry + sanitization | ❌ None |
| **HITL** | ✅ 6 modes | Basic (question → answer flow) |
| **Self-Learning** | ✅ MetaClaw cross-run learning | ❌ None |
| **Code Size** | 54K+ LOC (Python) | ~5K LOC (TypeScript) |
| **Runtime** | 50min - 7hrs | ~2 min |
| **Search** | 3 academic APIs | 6 general search engines |
| **MCP** | ❌ | ✅ |

**Verdict**: Completely different products. AutoResearchClaw is a scientific paper factory. u14app is a fast research report generator.

---

## 7. Technical Assessment

### 7.1 Architecture Quality

| Dimension | Rating | Notes |
|-----------|:------:|-------|
| **Simplicity** | ⭐⭐⭐⭐⭐ | ~300 LOC core engine. Brilliant in its simplicity. |
| **Extensibility** | ⭐⭐⭐⭐ | 14 LLM providers, 6 search engines, 17 customizable prompts |
| **UI/UX** | ⭐⭐⭐⭐⭐ | Next.js + shadcn/ui. Clean, modern, responsive |
| **Streaming** | ⭐⭐⭐⭐⭐ | Full SSE streaming with progress events |
| **Deployment** | ⭐⭐⭐⭐⭐ | Vercel, Cloudflare, Docker, static export, PWA |
| **API Design** | ⭐⭐⭐⭐ | SSE + MCP. GET endpoint for live viewing is clever |
| **Testing** | ⭐⭐ | No visible test suite |
| **Documentation** | ⭐⭐⭐⭐ | Good README, API docs, deployment guides |
| **Privacy** | ⭐⭐⭐⭐⭐ | All data local, no server storage |

### 7.2 Strengths

1. **Elegant simplicity**: ~300 LOC core. The "Thinking + Task" model split is clever and cost-efficient.
2. **Consumer-friendly**: PWA, one-command deploy, no backend needed (browser-only mode).
3. **14 LLM providers**: By far the most flexible in terms of model support.
4. **6 search engines**: Plus model-native search. Covers all bases.
5. **Full streaming**: Every step streamed to the UI in real-time.
6. **MCP integration**: Can be used as a tool by other AI systems.
7. **Customizable**: 17 prompt templates all overridable via config.
8. **Fast**: ~2 minutes for a research report.

### 7.3 Limitations

1. **No academic rigor**: General web search, not academic APIs. No DOI/arXiv/S2 integration.
2. **No gap analysis**: Cannot identify research gaps or generate novel ideas.
3. **No experiment execution**: Cannot run code or validate hypotheses.
4. **No citation verification**: Sources are linked but not verified.
5. **No anti-fabrication**: LLM can hallucinate facts that aren't in the sources.
6. **No paper writing**: Reports are Markdown, not LaTeX or conference-ready.
7. **No test suite**: No visible automated testing.
8. **Sequential search**: Tasks run one at a time (no parallelism).
9. **Shallow depth**: Reports are broad but not deep — no domain-specific analysis.
10. **No reproducibility**: No checksums, no manifests, no versioning.

---

## 8. Key Learnings for Elephant Rock

### 8.1 What We Should Adopt

1. **Thinking/Task model split**: Use a strong reasoning model for planning and a fast model for processing. We currently use one model for everything.
2. **Multi-LLM support**: Support multiple providers. Our Anthropic-only approach limits flexibility.
3. **SSE streaming with progress events**: Their streaming UX is excellent. Our SSE is pipeline-focused but could learn from their granular step-by-step approach.
4. **MCP server**: Expose our pipeline as an MCP tool for integration with other AI systems.
5. **Docker one-command deployment**: Essential for adoption.
6. **Customizable prompts**: Our prompts are hardcoded. Their 17-template system with overrides is more flexible.
7. **Research history**: Save and revisit past research runs.
8. **Artifact editing**: Let users edit proposals after generation.
9. **Knowledge graph visualization**: Mermaid diagram from research output.
10. **PWA**: Offline-capable, installable web app.

### 8.2 What We Should NOT Copy

1. **General web search**: Our academic API approach is more rigorous and appropriate for research.
2. **No verification**: Our 4-layer citation verification (even if basic) is better than none.
3. **Report format**: Our structured proposals with 10 sections are more rigorous than free-form Markdown.
4. **No gap analysis**: Our gap identification pipeline is our core differentiator.

### 8.3 Integration Opportunities

1. **Use as a frontend**: u14app's clean Next.js UI could be adapted as an alternative frontend for Elephant Rock.
2. **Use as a search layer**: Their 6-engine search + local knowledge base could enhance our literature search.
3. **MCP integration**: They expose MCP; we could consume it for web search during pipeline runs.
4. **Report polishing**: After our pipeline generates a proposal, u14app could be used to enhance and format it.

---

## 9. Competitive Positioning Map

```
                    Academic Rigor
                         ↑
    Elephant Rock ●      |     ● AutoResearchClaw
                         |
                         |
                         |
   u14app/deep-research ○|
                         |
   dzhng/deep-research ○ |
                         |
    ChatGPT Research ○   |
                         └────────────────────→ Speed / UX Polish
```

**u14app/deep-research** occupies the "fast, polished, consumer-friendly" quadrant. It's not academically rigorous, but it's fast and beautiful.

---

## 10. Assessment & Rating

| Dimension | Score (1-10) | Notes |
|-----------|:---:|-------|
| **Speed** | **10** | ~2 minutes. Fastest research tool we've studied. |
| **Simplicity** | **10** | ~300 LOC core. Elegant minimalism. |
| **UI/UX** | **9** | Next.js + shadcn/ui. Clean, modern, PWA. |
| **Extensibility** | **9** | 14 LLMs, 6 search engines, 17 customizable prompts. |
| **Deployment** | **10** | Vercel, Cloudflare, Docker, static, PWA. |
| **API Design** | **9** | SSE + MCP + GET endpoint for live viewing. |
| **Privacy** | **10** | All data local. No server storage. |
| **Academic Rigor** | **3** | General web search, no verification, no gap analysis. |
| **Innovation** | **5** | Clean execution of dzhng's algorithm. Not novel. |
| **Testing** | **2** | No visible test suite. |
| **Documentation** | **7** | Good README, API docs. Could use more examples. |
| **Community** | **7** | 4.6K stars, 1.1K forks. Active development. |
| **Overall** | **7.6/10** | Excellent consumer tool. Not a research system. |

---

## 11. Critical Observations

### 11.1 The "Good Enough" Problem

u14app/deep-research produces reports that are "good enough" for most users in 2 minutes. For 90% of use cases (blog posts, background research, topic summaries), this is sufficient. Our 26-minute pipeline that produces research proposals is overkill for these users.

### 11.2 The MCP Opportunity

By exposing an MCP server, u14app can be consumed by any AI tool. This makes it a potential building block for more complex systems — including ours. We could use their fast search as a preliminary step before our deeper analysis.

### 11.3 The Multi-LLM Lesson

Their 14-provider support is a significant advantage. Users can bring their own API key, use free Gemini, or run local Ollama. Our single-provider approach limits our audience.

### 11.4 The ~300 LOC Lesson

The entire research engine is ~300 lines. This is a powerful reminder that complexity is not always necessary. For producing research reports, you don't need 77K LOC — you need a good prompt, a search API, and streaming.

---

## 12. Conclusion

**u14app/deep-research** is the best open-source "ChatGPT Deep Research" clone available. It's fast (~2 min), beautiful (Next.js + shadcn/ui), extensible (14 LLMs, 6 search engines), and easy to deploy (Vercel/Cloudflare/Docker). Its ~300 LOC core engine is a masterclass in simplicity.

However, it is fundamentally a **consumer research report generator**, not a research discovery system. It doesn't identify gaps, generate novel ideas, run experiments, verify citations, or produce academic papers. For those capabilities, Elephant Rock and AutoResearchClaw remain the only options.

The key lesson for us: **speed and UX matter**. u14app's 2-minute reports with streaming progress are dramatically more user-friendly than our 26-minute pipeline runs. We should consider a "fast path" mode that skips embeddings, tree search, and detailed analysis for rapid initial results.

**Rating: 7.6/10** — Best-in-class consumer research tool. Not competitive for academic research.
