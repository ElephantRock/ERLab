# nickscamara/open-deep-research — Comprehensive Competitive Study

**Repository**: https://github.com/nickscamara/open-deep-research  
**Stars**: 6.2K | **Forks**: 736 | **Commits**: 46 | **License**: Apache-2.0  
**Author**: Nick Scamara (Firecrawl/Mendable)  
**Date**: 2026-05-06  
**Tech Stack**: Next.js 15, TypeScript, Vercel AI SDK, Firecrawl, shadcn/ui, Drizzle ORM  
**Description**: "An Open-Source clone of OpenAI's Deep Research experiment"  

---

## 1. What It Is

**Open Deep Research** is a consumer-facing web research tool that clones OpenAI's Deep Research feature. Instead of using a fine-tuned o3 model, it uses **Firecrawl's search + extract APIs** with a reasoning model (o1/o3-mini/DeepSeek-R1) to iteratively research a topic across the web and produce a comprehensive analysis.

**Key claim**: Open-source clone of OpenAI Deep Research — takes a question, searches the web iteratively with reasoning, and produces a detailed analysis report.

**Target user**: Non-technical consumers who want ChatGPT-style "Deep Research" they can self-host.

---

## 2. Architecture Overview

### 2.1 Source Structure

```
open-deep-research/
├── app/
│   ├── (auth)/                    # Authentication pages
│   │   ├── auth.ts                # NextAuth configuration
│   │   └── login/                 # Login page
│   ├── (chat)/                    # Main chat interface
│   │   ├── actions.ts             # Server actions (title gen, message CRUD)
│   │   ├── layout.tsx             # Chat layout
│   │   ├── page.tsx               # Main page
│   │   ├── chat/[id]/page.tsx     # Individual chat view
│   │   └── api/
│   │       ├── chat/route.ts      # ★ CORE: All research logic lives here
│   │       ├── document/          # Document CRUD
│   │       ├── files/upload/      # File upload
│   │       ├── history/           # Chat history
│   │       ├── suggestions/       # Document suggestions
│   │       └── vote/              # Message voting
│   ├── globals.css
│   └── layout.tsx
├── components/                    # 45+ React components
│   ├── deep-research.tsx          # ★ Research progress panel
│   ├── data-stream-handler.tsx    # ★ SSE streaming data handler
│   ├── chat.tsx                   # Main chat interface
│   ├── message.tsx                # Message rendering
│   ├── search-results.tsx         # Search results display
│   ├── extract-results.tsx        # Extracted data display
│   ├── scrape-results.tsx         # Scraped page display
│   ├── model-selector.tsx         # Model selection dropdown
│   ├── app-sidebar.tsx            # Chat history sidebar
│   ├── block.tsx                  # Document editing panel
│   ├── editor.tsx                 # Rich text editor (ProseMirror)
│   ├── code-editor.tsx            # Code editor (CodeMirror)
│   ├── spreadsheet-editor.tsx     # Spreadsheet editor
│   └── ui/                        # shadcn/ui primitives
├── hooks/
│   ├── use-block.ts               # Document block state
│   └── use-user-message-id.ts     # Message ID tracking
├── lib/
│   ├── ai/
│   │   ├── index.ts               # ★ Model provider abstraction
│   │   ├── models.ts              # Model definitions
│   │   ├── prompts.ts             # System prompts
│   │   └── custom-middleware.ts   # AI SDK middleware
│   ├── db/
│   │   ├── schema.ts              # Drizzle ORM schema
│   │   ├── queries.ts             # Database queries
│   │   └── migrate.ts             # Migration runner
│   ├── deep-research-context.tsx  # ★ React context for research state
│   ├── rate-limit.ts              # Upstash rate limiting
│   └── utils.ts                   # Utility functions
├── public/
├── Dockerfile
├── docker-compose.yml
├── drizzle.config.ts
├── next.config.ts
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

### 2.2 Key Dependencies

| Package | Purpose |
|---------|---------|
| `next` 15.0.3-canary | App Router with RSC |
| `ai` 4.1.16 | Vercel AI SDK (streamText, generateText, generateObject) |
| `@mendable/firecrawl-js` | Firecrawl web search + extract + scrape |
| `@ai-sdk/openai` | OpenAI model provider |
| `@openrouter/ai-sdk-provider` | OpenRouter model provider |
| `@ai-sdk/togetherai` | TogetherAI (DeepSeek-R1) |
| `drizzle-orm` + `@vercel/postgres` | Database (Postgres/Neon) |
| `@upstash/ratelimit` + `@upstash/redis` | Rate limiting |
| `next-auth` 5.0.0-beta | Authentication |
| `shadcn/ui` (Radix) | UI components |
| `framer-motion` | Animations |
| `zod` | Schema validation |

---

## 3. The Deep Research Engine — Core Algorithm

### 3.1 The Only File That Matters: `app/(chat)/api/chat/route.ts`

**The entire deep research algorithm is in a single ~400-line route handler.** This is the most important file in the repository. Everything else is UI scaffolding.

### 3.2 Algorithm: Iterative Search → Extract → Analyze Loop

```
Input: User question + maxDepth (7 by default)
         ↓
┌─────────────────────────────────────────────────┐
│ For depth = 1 to maxDepth:                      │
│                                                  │
│  1. SEARCH: Firecrawl.search(topic)              │
│     → Get top N results                          │
│                                                  │
│  2. EXTRACT: Firecrawl.extract(top 3 URLs)       │
│     → Parallel extraction from each URL          │
│     → Accumulate findings[]                      │
│                                                  │
│  3. ANALYZE: generateText(reasoningModel)        │
│     → "What has been learned? What gaps remain?"  │
│     → Returns JSON: { analysis, gaps,            │
│        shouldContinue, nextSearchTopic }          │
│                                                  │
│  4. If shouldContinue=false OR gaps=[]: break     │
│  5. topic = gaps.shift()                          │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│ Final Synthesis:                                 │
│   generateText(reasoningModel, maxTokens=16000)  │
│   → Comprehensive analysis from all findings     │
│   → Returns markdown report                      │
└─────────────────────────────────────────────────┘
         ↓
Output: Comprehensive research report (markdown)
```

### 3.3 The Deep Research Tool — Complete Code Analysis

```typescript
deepResearch: {
  description: 'Perform deep research on a topic...',
  parameters: z.object({
    topic: z.string().describe('The topic or question to research'),
  }),
  execute: async ({ topic, maxDepth = 7 }) => {
    // Time limit: 4.5 minutes
    const timeLimit = 4.5 * 60 * 1000;

    // State tracking
    const researchState = {
      findings: [],           // Accumulated { text, source } pairs
      summaries: [],          // Analysis summaries from each iteration
      nextSearchTopic: '',    // Next topic to search (from analysis)
      urlToSearch: '',        // Specific URL to search (from analysis)
      currentDepth: 0,
      failedAttempts: 0,
      maxFailedAttempts: 3,
      completedSteps: 0,
      totalExpectedSteps: maxDepth * 5,
    };

    // Main research loop
    while (researchState.currentDepth < maxDepth) {
      researchState.currentDepth++;

      // 1. SEARCH PHASE
      let searchTopic = researchState.nextSearchTopic || topic;
      const searchResult = await app.search(searchTopic);

      // 2. EXTRACT PHASE (parallel)
      const topUrls = searchResult.data.slice(0, 3).map(r => r.url);
      const newFindings = await extractFromUrls([
        researchState.urlToSearch,
        ...topUrls
      ]);
      researchState.findings.push(...newFindings);

      // 3. ANALYSIS PHASE (reasoning model)
      const analysis = await generateText({
        model: customModel(reasoningModel.apiIdentifier, true),
        prompt: `Analyze findings about: ${topic}
                 What has been learned? What gaps remain?
                 Time remaining: ${timeRemainingMinutes} minutes.
                 Return JSON: { analysis: { summary, gaps[], 
                   shouldContinue, nextSearchTopic, urlToSearch } }`
      });

      // 4. STOP CONDITIONS
      if (!analysis.shouldContinue || analysis.gaps.length === 0) break;
      topic = analysis.gaps.shift() || topic;
    }

    // 5. FINAL SYNTHESIS
    const finalAnalysis = await generateText({
      model: customModel(reasoningModel.apiIdentifier, true),
      maxTokens: 16000,
      prompt: `Create comprehensive analysis of ${topic} from findings...`
    });

    return { success: true, data: { findings, analysis: finalAnalysis.text } };
  }
}
```

### 3.4 Key Design Decisions

1. **maxDepth = 7**: Up to 7 iterations of search → extract → analyze
2. **Time limit = 4.5 minutes**: Hard timeout regardless of depth
3. **Top 3 results only**: Extracts from the top 3 search results per iteration
4. **Parallel extraction**: All 3 URLs extracted simultaneously via `Promise.all`
5. **Reasoning model for analysis**: Uses o1/o3-mini/DeepSeek-R1 for analysis, NOT the chat model
6. **Chat model for routing**: Uses gpt-4o for tool calling and chat management
7. **Two-model split**: Router model (gpt-4o) + Reasoning model (o1/o3-mini/DeepSeek-R1)

### 3.5 The `analyzeAndPlan` Function — The Brain

```typescript
const analyzeAndPlan = async (findings) => {
  const result = await generateText({
    model: customModel(reasoningModel.apiIdentifier, true),
    prompt: `You are a research agent analyzing findings about: ${topic}
             You have ${timeRemainingMinutes} minutes remaining.
             Current findings: ${findings.map(f => `[From ${f.source}]: ${f.text}`).join('\n')}
             
             What has been learned? What gaps remain? What specific aspects should be investigated next?
             If less than 1 minute remains, set shouldContinue to false.
             
             Respond in JSON format:
             {
               "analysis": {
                 "summary": "summary of findings",
                 "gaps": ["gap1", "gap2"],
                 "nextSteps": ["step1", "step2"],
                 "shouldContinue": true/false,
                 "nextSearchTopic": "optional topic",
                 "urlToSearch": "optional url"
               }
             }`
  });
  return JSON.parse(result.text).analysis;
};
```

This is the **iterative reflection** pattern — after each search+extract cycle, the reasoning model reflects on what's been learned and decides what to search for next. This is the same pattern used by langchain-ai/local-deep-researcher.

---

## 4. The Four Tools

### 4.1 Tool Inventory

| Tool | API | Purpose | Active in |
|------|-----|---------|-----------|
| **search** | Firecrawl.search() | Web search | Both modes |
| **extract** | Firecrawl.extract() | Structured data extraction from URLs | Both modes |
| **scrape** | Firecrawl.scrapeUrl() | Full page scraping | Both modes |
| **deepResearch** | Internal loop | Iterative search→extract→analyze | Deep Research mode only |

### 4.2 Tool Activation Logic

```typescript
// Normal mode: search + extract + scrape only
experimental_activeTools: experimental_deepResearch ? allTools : firecrawlTools,

// Deep Research mode: adds the deepResearch tool
const allTools: AllowedTools[] = [...firecrawlTools, 'deepResearch'];
```

The `deepResearch` tool is only available when the user toggles "Deep Research" mode in the UI.

### 4.3 Firecrawl Integration

All web access goes through **Firecrawl** (by Mendable):

```typescript
const app = new FirecrawlApp({ apiKey: process.env.FIRECRAWL_API_KEY });

// Search
const result = await app.search(query);
// Returns: { success, data: [{ url, title, description, markdown }] }

// Extract (structured)
const result = await app.extract(urls, { prompt });
// Returns: { success, data: extracted_structured_data }

// Scrape
const result = await app.scrapeUrl(url);
// Returns: { success, markdown }
```

Firecrawl is a **paid SaaS** — this is NOT a self-contained solution. Every search, extract, and scrape call goes through Firecrawl's API.

---

## 5. Model Configuration

### 5.1 Two-Model Architecture

| Model Type | Purpose | Default | Alternatives |
|------------|---------|---------|-------------|
| **Router Model** | Tool calling, chat management | gpt-4o | gpt-4o-mini |
| **Reasoning Model** | Analysis, gap identification, synthesis | o1-mini | o1, o3-mini, DeepSeek-R1 |

### 5.2 Provider Routing

```typescript
export const customModel = (apiIdentifier: string, forReasoning: boolean) => {
  const hasOpenRouterKey = process.env.OPENROUTER_API_KEY;

  // Route to OpenRouter if API key present
  if (hasOpenRouterKey) {
    return wrapLanguageModel({
      model: openrouter(modelId),
      middleware: customMiddleware,
    });
  }

  // Otherwise route to OpenAI or TogetherAI
  const model = modelId === 'deepseek-ai/DeepSeek-R1'
    ? togetherai(modelId)
    : openai(modelId);
};
```

### 5.3 JSON Schema Validation Bypass

Some models (DeepSeek-R1) don't support structured JSON outputs:

```typescript
const BYPASS_JSON_VALIDATION = process.env.BYPASS_JSON_VALIDATION === 'true';
// When true, allows non-OpenAI models for reasoning tasks
// Responses may be less structured
```

---

## 6. Real-Time Streaming UI

### 6.1 Data Stream Events

The UI receives real-time updates via SSE (Server-Sent Events):

```typescript
type DataStreamDelta = {
  type: 'activity-delta' | 'source-delta' | 'depth-delta' | 
        'progress-init' | 'finish' | 'text-delta' | 'user-message-id';
  content: Activity | Source | Depth | string;
};
```

### 6.2 Activity Types

| Type | Color | Meaning |
|------|-------|---------|
| `search` | Yellow→Green | Searching the web |
| `extract` | Yellow→Green | Extracting data from URL |
| `analyze` | Yellow→Green | Reasoning model analyzing findings |
| `synthesis` | Yellow→Green | Final synthesis generation |
| `thought` | Yellow→Green | General reasoning |

### 6.3 Deep Research Panel

A fixed-position panel shows real-time progress:

- **Activity tab**: Shows search/extract/analyze steps with timestamps
- **Sources tab**: Shows discovered URLs with titles and domains
- **Animated**: Uses framer-motion for smooth transitions

---

## 7. Infrastructure

### 7.1 Database Schema

Uses **Drizzle ORM** with **Vercel Postgres (Neon)**:

- `chat` table: id, createdAt, title, userId, visibility
- `message` table: id, chatId, role, content, createdAt
- `document` table: id, title, kind, content, userId, createdAt
- `suggestion` table: id, documentId, originalText, suggestedText
- `vote` table: id, messageId, isUpvoted
- `user` table: id, email, password

### 7.2 Authentication

NextAuth.js v5 with:
- Anonymous session creation (no login required)
- Credential-based auth
- Session verification before every API call

### 7.3 Rate Limiting

```typescript
const { success } = await rateLimiter.limit(identifier); // Upstash Redis
if (!success) return new Response('Too many requests', { status: 429 });
```

### 7.4 Deployment

- **Vercel** (primary target): One-click deploy with Postgres + Blob
- **Docker**: Dockerfile + docker-compose.yml provided
- **Function timeout**: 300s (5 min) default, 60s on Hobby tier

---

## 8. LOC Analysis

| Component | Files | LOC Estimate |
|-----------|-------|-------------|
| Core research logic (route.ts) | 1 | ~400 |
| AI model config | 3 | ~100 |
| Prompts | 1 | ~80 |
| Data stream handler | 1 | ~120 |
| Deep research UI | 1 | ~100 |
| Chat components | ~15 | ~1,500 |
| Document/block components | ~10 | ~1,200 |
| Auth | ~3 | ~200 |
| DB schema/queries | ~3 | ~300 |
| UI primitives (shadcn) | ~20 | ~1,500 |
| Configuration | ~8 | ~200 |
| **Total** | **~65** | **~5,700** |

**Effective research code**: ~400 LOC in `route.ts`. The rest is UI/infrastructure scaffolding from the Vercel AI Chatbot template.

---

## 9. Comparison with Other Tools

### 9.1 vs Elephant Rock

| Feature | Elephant Rock | Open Deep Research |
|---------|:---:|:---:|
| **Purpose** | Academic research proposals | Consumer web research reports |
| **Output** | Structured proposals (10 sections) | Markdown analysis report |
| **Literature search** | OpenAlex + arXiv (academic) | Firecrawl (web) |
| **Gap analysis** | ✅ Full clustering pipeline | ❌ (LLM decides "gaps" in analysis) |
| **Novelty scoring** | ✅ 768-dim embeddings | ❌ |
| **Idea generation** | ✅ Tree search | ❌ |
| **Proposal synthesis** | ✅ 10-section proposals | ❌ |
| **Code execution** | ❌ | ❌ |
| **Paper writing** | ❌ | ❌ |
| **Iterative reflection** | ❌ | ✅ (7-iteration loop) |
| **Knowledge graph** | ✅ | ❌ |
| **Embeddings** | ✅ Ollama 768d | ❌ |
| **Frontend** | React (20 pages) | Next.js (chat UI) |
| **Backend** | Python/FastAPI | TypeScript/Next.js |
| **Runtime** | 10-26 min (partial) | ~4.5 min (complete) |
| **Self-hostable** | ✅ | ✅ |
| **API cost** | ~$0.01 (Ollama local) | ~$0.10-0.50 (OpenAI/Firecrawl) |

### 9.2 vs AI-Researcher (HKUDS)

| Feature | AI-Researcher | Open Deep Research |
|---------|:---:|:---:|
| **Stars** | 5.3K | 6.2K |
| **Output** | Full academic paper + code + experiments | Web research report |
| **Code execution** | ✅ Docker + GPU | ❌ |
| **Paper writing** | ✅ 6-section LaTeX | ❌ |
| **Experiment execution** | ✅ Real training runs | ❌ |
| **Academic validation** | ✅ NeurIPS 2025 | ❌ |
| **Multi-agent** | ✅ 7 agents | ❌ (single tool loop) |
| **Search provider** | arXiv + GitHub | Firecrawl (web) |
| **Model providers** | 1 (OpenRouter) | 3 (OpenAI, OpenRouter, TogetherAI) |
| **Deployment** | Docker + GPU | Vercel (serverless) |
| **Core LOC** | ~9,400 | ~400 |
| **Runtime** | Hours | ~5 minutes |

### 9.3 vs dzhng/deep-research

| Feature | dzhng/deep-research | Open Deep Research |
|---------|:---:|:---:|
| **Stars** | 18.9K | 6.2K |
| **Core LOC** | ~500 | ~400 |
| **Search algorithm** | Recursive breadth×depth | Flat iterative loop |
| **Search provider** | Tavily | Firecrawl |
| **Frontend** | Next.js | Next.js |
| **Thinking model** | ✅ (separate) | ✅ (separate) |
| **Extract tool** | ❌ | ✅ (structured extraction) |
| **Scrape tool** | ❌ | ✅ (full page scrape) |
| **Source panel** | Basic | ✅ Animated activity panel |
| **Auth** | ❌ | ✅ (NextAuth) |
| **Persistence** | ❌ | ✅ (Postgres) |

### 9.4 vs u14app/deep-research

| Feature | u14app/deep-research | Open Deep Research |
|---------|:---:|:---:|
| **Stars** | 4.6K | 6.2K |
| **Core LOC** | ~300 | ~400 |
| **LLM providers** | 14 | 3 (OpenAI, OpenRouter, TogetherAI) |
| **Search engines** | 6 | 1 (Firecrawl) |
| **MCP server** | ✅ | ❌ |
| **PWA** | ✅ | ❌ |
| **Customizable prompts** | 17 | 1 (system prompt) |
| **Iterative reflection** | ✅ (SERP review) | ✅ (analyzeAndPlan) |
| **Document editing** | ❌ | ✅ (ProseMirror editor) |
| **Code generation** | ❌ | ✅ (CodeMirror editor) |

---

## 10. Key Architectural Patterns

### 10.1 Iterative Reflection Loop

The core innovation (shared with langchain-deep-researcher and dzhng/deep-research):

```
Search → Extract → Analyze → "What's missing?" → Search again
```

After each iteration, the reasoning model decides:
1. **What has been learned** (summary)
2. **What gaps remain** (gaps array)
3. **Whether to continue** (shouldContinue boolean)
4. **What to search next** (nextSearchTopic string)

This is a simple but effective pattern that produces much better results than a single search pass.

### 10.2 Two-Model Split

```
Router (gpt-4o):  Tool calling, chat management, user interaction
Reasoning (o1):   Analysis, gap identification, synthesis, planning
```

Cheap model handles orchestration, expensive model handles thinking. This is the same pattern used by:
- u14app/deep-research (Thinking model + Task model)
- AI-Researcher (Completion model + Cheap model)

### 10.3 Time-Aware Research

```typescript
const timeElapsed = Date.now() - startTime;
const timeRemaining = timeLimit - timeElapsed;
const timeRemainingMinutes = Math.round((timeRemaining / 1000 / 60) * 10) / 10;

// In the analysis prompt:
`You have ${timeRemainingMinutes} minutes remaining.
 If less than 1 minute remains, set shouldContinue to false.`
```

The research loop is **time-aware** — it tells the reasoning model how much time is left and asks it to decide whether to continue or synthesize. This prevents timeout failures.

### 10.4 Real-Time Activity Streaming

The UI shows real-time progress via SSE:

```typescript
// Server sends
dataStream.writeData({ type: 'activity-delta', content: activity });
dataStream.writeData({ type: 'source-delta', content: source });
dataStream.writeData({ type: 'depth-delta', content: { current, max } });

// Client receives
const { addActivity, addSource } = useDeepResearch();
```

This creates a "live research" experience where users can watch the agent searching, extracting, and analyzing in real time.

---

## 11. Strengths

1. **Beautiful UX**: Polished chat interface with animated activity panel, source list, and document editing
2. **Iterative reflection**: The search→analyze→plan loop produces much better results than single-pass search
3. **Two-model split**: Cost-effective routing (gpt-4o for tools, o1 for analysis)
4. **Time-aware**: Automatically wraps up before timeout
5. **One-click deploy**: Vercel deployment with Postgres + Blob
6. **Multiple model providers**: OpenAI, OpenRouter, TogetherAI
7. **Structured extraction**: Firecrawl's extract API provides structured data, not just raw HTML
8. **Real-time streaming**: Users watch research happen live
9. **Full persistence**: Chat history, documents, and votes saved to Postgres
10. **Authentication**: Built-in with anonymous sessions for quick start
11. **Document editing**: Side-by-side chat + document editor
12. **Docker support**: Self-hostable without Vercel
13. **Rate limiting**: Upstash Redis prevents abuse

---

## 12. Limitations

1. **Firecrawl dependency**: NOT self-contained — requires Firecrawl API key ($$$). Every search/extract/scrape is a paid API call.
2. **Consumer-grade**: Produces web research reports, not academic papers. No citation verification, no novelty scoring, no gap analysis.
3. **No academic search**: Uses web search only. No arXiv, no Semantic Scholar, no OpenAlex.
4. **No code execution**: Unlike AI-Researcher, can't run experiments.
5. **No paper writing**: Unlike AI-Researcher, can't produce academic papers.
6. **Flat iteration**: Unlike dzhng/deep-research's recursive breadth×depth, this uses a simple linear loop.
7. **Single search provider**: Only Firecrawl. No fallback to Google, Bing, etc.
8. **JSON parsing fragility**: Analysis parsing uses `JSON.parse()` on raw LLM output — fragile.
9. **No parallel research**: Researches one topic at a time, no parallel branch exploration.
10. **Generic prompts**: Single system prompt for all tasks. No domain-specific customization.
11. **Vercel lock-in**: Primary deployment target is Vercel (Postgres, Blob, serverless functions).
12. **No MCP**: No Model Context Protocol integration.
13. **No local models**: Requires cloud LLM access (OpenAI, TogetherAI, or OpenRouter).
14. **Template-derived**: Core architecture is a modified Vercel AI Chatbot template — not purpose-built.

---

## 13. What Elephant Rock Can Learn

### 13.1 Must Adopt

1. **Iterative reflection loop**: The search→analyze→plan→search-again pattern is the #1 missing feature in Elephant Rock. After gap analysis, let the LLM reflect on gaps and re-search for missing information.

2. **Time-aware research**: Tell the LLM how much time/budget remains and let it decide whether to continue. This prevents runaway costs and timeout failures.

3. **Real-time activity streaming**: Show users what the pipeline is doing at each step. Elephant Rock has SSE but doesn't expose detailed activity logs like this.

### 13.2 Should Consider

4. **Two-model split for cost optimization**: Use Ollama/cheap model for orchestration, expensive model for reasoning. Elephant Rock already does this partially.

5. **Structured extraction**: When searching literature, extract structured data (authors, methods, results) rather than just storing abstract text.

### 13.3 Skip

6. **Firecrawl dependency**: Elephant Rock already has OpenAlex + arXiv — better than Firecrawl for academic use cases.

7. **Vercel deployment**: Elephant Rock uses Docker, which is more appropriate for a research platform.

---

## 14. Assessment & Rating

| Dimension | Score | Notes |
|-----------|-------|-------|
| **UX Polish** | 9.5/10 | Beautiful chat UI with animated research panel |
| **Core Algorithm** | 6/10 | Simple iterative loop, not novel |
| **Code Quality** | 7/10 | Clean TypeScript, but 95% is template code |
| **Innovation** | 4/10 | Clone of OpenAI Deep Research, no novel techniques |
| **Practicality** | 9/10 | One-click deploy, works immediately |
| **Documentation** | 7/10 | Good README, but no API docs |
| **Academic Rigor** | 1/10 | Not designed for academic research |
| **Cost Efficiency** | 5/10 | Requires paid Firecrawl + paid LLM |
| **Extensibility** | 6/10 | Easy to modify prompts, hard to change architecture |
| **Community** | 8/10 | 6.2K stars, 736 forks, active |

**Overall: 6.3/10** — A polished consumer product, not a research tool. The UI is beautiful and the iterative reflection pattern is worth studying, but it's fundamentally a ChatGPT Deep Research clone built on the Vercel AI Chatbot template with Firecrawl integration. The actual research logic is ~400 LOC.

---

## 15. Competitive Position Summary

```
Consumer Web Research:
  u14app/deep-research (4.6K) ── Most customizable (14 LLM, 6 search)
  Open Deep Research (6.2K) ──── Best UX (animated activity panel)
  dzhng/deep-research (18.9K) ── Best algorithm (recursive breadth×depth)
  langchain-deep-researcher (9.1K) ── Best for local/private research

Academic Research:
  AI-Researcher (5.3K) ───────── Only tool that produces full papers
  AutoResearchClaw (11.9K) ───── Most complete pipeline (23 stages)
  
Research Discovery:
  Elephant Rock ───────────────── Only tool with gap→novelty→proposal pipeline
```

**Open Deep Research is the best-consumer-facing option** but the **worst option for academic research**. Its value is the UX, not the algorithm.

---

## 16. Key Takeaways

1. **It's a template, not a framework**: 95% of the code is the Vercel AI Chatbot template. The actual research logic is ~400 LOC in one file.

2. **Firecrawl is the moat**: The tool's quality depends entirely on Firecrawl's search and extract quality. Without Firecrawl, this is just a chatbot.

3. **The iterative reflection pattern is the key innovation** — search → extract → analyze → plan → search again. This pattern should be adopted by Elephant Rock.

4. **The real-time activity panel is best-in-class** — watching the agent search, extract, and analyze in real time with animated status indicators is a much better UX than a spinning loader.

5. **Consumer vs. Academic**: This tool is for "What are the best restaurants in Tokyo?" not "What are the open problems in attention mechanism design?" Different target entirely.

6. **The time-aware research pattern** is clever — telling the LLM "you have X minutes remaining" and letting it decide when to wrap up prevents wasted API calls.

7. **6.2K stars but 46 commits** — Most of the popularity comes from the "Open Source Deep Research" branding and the Firecrawl connection, not from technical innovation.

---

## 17. Comparison Table: All 10 Competitors

| Tool | Stars | Purpose | Output | Core LOC | Academic |
|------|-------|---------|--------|----------|----------|
| **AI-Researcher** | 5.3K | Full paper generation | Paper + code + experiments | 9,400 | ✅ NeurIPS |
| **AutoResearchClaw** | 11.9K | Full paper generation | Paper + experiments | 54,000 | ❌ |
| **dzhng/deep-research** | 18.9K | Web research | Report | 500 | ❌ |
| **Open Deep Research** | 6.2K | Web research | Report | 400 | ❌ |
| **langchain-deep-researcher** | 9.1K | Web research | Report | 500 | ❌ |
| **u14app/deep-research** | 4.6K | Web research | Report | 300 | ❌ |
| **Alibaba DeepResearch** | 18.8K | Information seeking | Answer | 5,000+ | ❌ |
| **AI Scientist** | — | Paper generation | Paper | 3,000+ | ✅ |
| **Elicit** | — | Literature review | Summary | SaaS | ✅ |
| **Elephant Rock** | — | Research discovery | Proposals | 77,500 | ❌ |

**Open Deep Research ranks**: #3 in stars among open-source tools, #1 in UX polish, #9 in academic utility.
