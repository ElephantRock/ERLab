# jina-ai/node-DeepResearch — Comprehensive Competitive Study

**Repository**: https://github.com/jina-ai/node-DeepResearch  
**Stars**: 5.2K | **Forks**: 451 | **Commits**: 571 | **License**: Apache-2.0  
**Version**: v1.4.0 (Feb 12, 2025)  
**Author**: Jina AI (Han Xiao, founder)  
**Language**: TypeScript 98.9%  
**Runtime**: Node.js  
**Date**: 2026-05-06  

---

## 1. What It Is

**Jina DeepResearch** is an **agentic web search tool** that iteratively searches, reads webpages, and reasons until it finds a definitive answer (or runs out of token budget). Unlike OpenAI/Gemini/Perplexity's "Deep Research" which optimizes for long-form articles, this tool focuses on **finding the right answer** — concise, accurate, well-sourced.

**Key differentiator from all competitors**: It has a **multi-dimensional answer evaluation system** that checks answers for definitiveness, freshness, completeness, plurality, and strict quality before accepting them. No other open-source research tool has this.

**Official deployment**: https://search.jina.ai  
**OpenAI-compatible API**: `https://deepsearch.jina.ai/v1/chat/completions`

---

## 2. Architecture Overview

### 2.1 Source Structure

```
node-DeepResearch/
├── src/
│   ├── agent.ts              ★ CORE ENGINE (~750 LOC) — the entire research loop
│   ├── config.ts             # Model provider configuration (Gemini/OpenAI/Vertex)
│   ├── types.ts              # TypeScript type definitions
│   ├── app.ts                # CLI entry point
│   ├── cli.ts                # CLI argument parsing
│   ├── server.ts             # OpenAI-compatible server
│   ├── logging.ts            # Logging utilities
│   ├── tools/                # 20 tool modules
│   │   ├── evaluator.ts      ★ Multi-dimensional answer evaluation
│   │   ├── jina-search.ts    # Jina search API
│   │   ├── brave-search.ts   # Brave search API
│   │   ├── serper-search.ts  # Google Serper API
│   │   ├── read.ts           # Jina Reader (webpage reading)
│   │   ├── query-rewriter.ts # Search query optimization
│   │   ├── jina-dedup.ts     # Query deduplication
│   │   ├── jina-rerank.ts    # URL relevance reranking
│   │   ├── jina-latechunk.ts # Late chunking for context
│   │   ├── jina-classify-spam.ts # Spam URL classification
│   │   ├── serp-cluster.ts   # SERP result clustering
│   │   ├── research-planner.ts # Sub-problem decomposition
│   │   ├── code-sandbox.ts   # JavaScript code execution
│   │   ├── error-analyzer.ts # Error diagnosis & blame
│   │   ├── finalizer.ts      # Final answer formatting
│   │   ├── reducer.ts        # Multi-answer reduction
│   │   ├── build-ref.ts      # Reference/citation building
│   │   ├── embeddings.ts     # Jina embeddings API
│   │   ├── cosine.ts         # Cosine similarity
│   │   └── segment.ts        # Text segmentation
│   ├── utils/
│   │   ├── schemas.ts        # Zod schemas for structured output
│   │   ├── safe-generator.ts # LLM call wrapper with retry
│   │   ├── token-tracker.ts  # Token budget management
│   │   ├── action-tracker.ts # Action logging
│   │   ├── url-tools.ts      # URL ranking, dedup, normalization
│   │   ├── text-tools.ts     # Markdown cleanup, HTML→MD
│   │   ├── date-tools.ts     # Date formatting
│   │   └── image-tools.ts    # Image dedup with embeddings
│   ├── __tests__/            # Jest tests
│   ├── evals/                # Evaluation harness
│   └── cli/                  # CLI output formatters
├── config.json               # Model + tool configuration
├── Dockerfile
├── docker-compose.yml
├── package.json
└── tsconfig.json
```

### 2.2 Dependencies

| Package | Purpose |
|---------|---------|
| `ai` (Vercel AI SDK) | LLM orchestration, structured output, streaming |
| `@ai-sdk/google` | Gemini model provider |
| `@ai-sdk/openai` | OpenAI model provider |
| `zod` + `zod-to-json-schema` | Schema validation + structured output |
| `duck-duck-scrape` | DuckDuckGo search (fallback provider) |
| `axios` | HTTP client |
| `dotenv` | Environment variables |

---

## 3. The Core Engine — `agent.ts`

### 3.1 The 5-Action Agent Loop

The entire algorithm is a single `while` loop with 5 possible actions:

```typescript
while (tokenBudget not exceeded) {
  // 1. Build prompt with available actions
  const { system, urlList } = getPrompt(context, questions, keywords,
    allowReflect, allowAnswer, allowRead, allowSearch, allowCoding,
    knowledge, urls);

  // 2. LLM chooses an action (structured output via Zod schema)
  const result = await generator.generateObject({ schema, system, messages });

  // 3. Execute the chosen action
  switch (result.action) {
    case 'search':   // Search the web
    case 'visit':    // Read webpage content
    case 'reflect':  // Generate sub-questions (gap analysis)
    case 'answer':   // Provide an answer
    case 'coding':   // Execute JavaScript code
  }

  // 4. If answer → evaluate it
  // 5. If bad answer → store error analysis, try again
}
```

### 3.2 The 5 Actions

| Action | Purpose | Key Behavior |
|--------|---------|-------------|
| **search** | Search the web | Queries → results → SERP clustering → knowledge items |
| **visit** | Read webpages | Top-K URLs → Jina Reader → content chunks → knowledge |
| **reflect** | Gap analysis | Generate sub-questions → dedup → add to gaps queue |
| **answer** | Provide answer | Answer → evaluate → accept or reject with feedback |
| **coding** | Code execution | JavaScript sandbox for counting/sorting/transforming |

### 3.3 The Gap Queue System

```typescript
const gaps: string[] = [question];  // Start with original question

while (budget not exceeded) {
  // Rotate through gaps round-robin
  const currentQuestion = gaps[totalStep % gaps.length];
  
  // If LLM chooses 'reflect':
  gaps.push(...newSubQuestions);
  
  // If LLM answers a sub-question correctly:
  gaps.splice(gaps.indexOf(currentQuestion), 1);
  
  // When gaps is empty and original question answered → done
}
```

This is a **round-robin gap queue** — the agent cycles through all unanswered questions, working on each in turn. This is fundamentally different from the simple "N iterations" approach of Open Deep Research.

### 3.4 Action Disabling Pattern

After each action, the agent **disables that same action for the next step**:

```typescript
// After search
allowSearch = false;  // Can't search again immediately
allowAnswer = false;  // Prevents premature answer from snippets

// After visit
allowRead = false;   // Can't visit again immediately

// After reflect
allowReflect = false; // Can't reflect again immediately
```

This forces the agent to **alternate between actions** — search → visit → reflect → answer — rather than getting stuck in loops.

### 3.5 Beast Mode

When the token budget is 85%+ consumed, the agent enters "Beast Mode":

```
🔥 ENGAGE MAXIMUM FORCE! ABSOLUTE PRIORITY OVERRIDE! 🔥
PRIME DIRECTIVE:
- DEMOLISH ALL HESITATION! ANY RESPONSE SURPASSES SILENCE!
- PARTIAL STRIKES AUTHORIZED
- TACTICAL REUSE FROM PREVIOUS CONVERSATION SANCTIONED
- WHEN IN DOUBT: UNLEASH CALCULATED STRIKES BASED ON AVAILABLE INTEL!
FAILURE IS NOT AN OPTION. EXECUTE WITH EXTREME PREJUDICE! ⚡️
```

Beast mode forces an answer using all accumulated knowledge, even if incomplete. "Any answer is better than no answer."

---

## 4. The Answer Evaluation System — The Key Innovation

### 4.1 Multi-Dimensional Evaluation

This is the **most sophisticated answer quality system** among all competitors. Before accepting an answer, the system evaluates it on multiple dimensions:

| Dimension | What It Checks | When Applied |
|------------|---------------|-------------|
| **Definitive** | Does the answer provide a clear, confident response? | Almost always |
| **Freshness** | Is the answer content still current? | Time-sensitive questions |
| **Plurality** | Does the answer provide the right number of items? | "List 5 examples" questions |
| **Completeness** | Does the answer address all explicitly mentioned aspects? | Multi-aspect questions |
| **Strict** | A ruthless reviewer that finds every weakness | Always (final gate) |

### 4.2 Evaluation Flow

```typescript
// Step 1: Evaluate the QUESTION to determine what checks are needed
const evaluationMetrics = await evaluateQuestion(question, context, schemaGen);
// Returns: ['definitive', 'freshness', 'strict'] etc.

// Step 2: When agent produces an answer, evaluate it
const evaluation = await evaluateAnswer(question, answer, evaluationMetrics, ...);

// Step 3: If evaluation fails
if (!evaluation.pass) {
  // Store error analysis as knowledge
  allKnowledge.push({
    question: "Why is this answer bad?",
    answer: evaluation.think + errorAnalysis.recap + errorAnalysis.blame,
    type: 'qa'
  });
  
  // Disable answer action (force agent to search/read more)
  allowAnswer = false;
  
  // Add improvement plan to next answer attempt
  finalAnswerPIP.push(evaluation.improvement_plan);
}
```

### 4.3 The Evaluator's Sophistication

The evaluator uses **few-shot examples in 6 languages** (English, Chinese, Japanese, German, French, Korean). The prompt for definitiveness alone is 100+ examples long. The completeness evaluator has an explicit table:

```
| Question Type | Expected Items | Rules |
|---------------|----------------|-------|
| "Few"         | 2-4            | ...   |
| "Several"     | 3-7            | ...   |
| "Many"        | 7+             | ...   |
| "Comprehensive"| 10+           | ...   |
```

### 4.4 Strict Evaluator (The Final Gate)

The strict evaluator is explicitly designed to **reject answers**:

```
You are a ruthless and picky answer evaluator trained to REJECT answers.
You can't stand any shallow answers. Find ANY weakness.
Argue AGAINST the answer with the strongest possible case.
Then argue FOR the answer.
Only then synthesize a final improvement plan: "For get a pass, you must..."
```

If the strict evaluator rejects, it provides an **improvement plan** that gets injected into the next answer attempt as `<reviewer-1>` feedback.

---

## 5. URL Ranking & Selection

### 5.1 Multi-Signal URL Scoring

URLs are scored using multiple signals:

```typescript
type BoostedSearchSnippet = SearchSnippet & {
  freqBoost: number;        // Frequency of appearance across searches
  hostnameBoost: number;    // Hostname-specific boost
  pathBoost: number;        // URL path relevance
  jinaRerankBoost: number;  // Jina Rerank API score
  finalScore: number;       // Combined weighted score
};
```

### 5.2 URL Processing Pipeline

```
Search results
  → normalizeUrl (dedup, clean)
  → addToAllURLs (track frequency)
  → filterURLs (remove visited, bad hostnames)
  → rankURLs (Jina Rerank + frequency + hostname + path boosts)
  → keepKPerHostname (diversity: max 2 per hostname)
  → sortSelectURLs (top 20 for prompt)
```

### 5.3 Diversity Enforcement

```typescript
// Improve diversity by keeping top 2 URLs per hostname
weightedURLs = keepKPerHostname(weightedURLs, 2);
```

This prevents the agent from reading 10 pages from the same domain.

---

## 6. Search Providers

| Provider | Type | Notes |
|----------|------|-------|
| **Jina Search** | Default | Jina's search API, 30 results per query |
| **DuckDuckGo** | Free fallback | Scraped, no API key needed |
| **Brave** | Optional | Brave Web Search API |
| **Serper** | Optional | Google SERP via Serper.dev |
| **arXiv** | Academic | arXiv paper search via Jina |

The default is **Jina Search** — this is a paid API (free tier with 1M tokens).

---

## 7. Model Configuration

### 7.1 Two-Tier Model Architecture

| Tool | Default Model | Purpose |
|------|--------------|---------|
| `agent` | gemini-2.5-flash | Main reasoning (choose action) |
| `agentBeastMode` | gemini-2.5-flash | Forced answer generation |
| `evaluator` | gemini-2.5-flash (temp=0.6) | Answer evaluation |
| `finalizer` | gemini-2.5-flash-lite | Answer formatting |
| `queryRewriter` | gemini-2.5-flash (temp=0.1) | Query optimization |
| `errorAnalyzer` | gemini-2.5-flash | Error diagnosis |
| `coder` | gemini-2.5-flash (temp=0.7) | Code generation |
| `serpCluster` | gemini-2.5-flash | Search result clustering |
| `researchPlanner` | gemini-2.5-flash | Sub-problem decomposition |
| `reducer` | gemini-2.5-flash (16K tokens) | Multi-answer reduction |

### 7.2 Provider Options

```typescript
// Gemini (default)
export GEMINI_API_KEY=...

// OpenAI
export OPENAI_API_KEY=...
export LLM_PROVIDER=openai

// Local LLM (Ollama/LMStudio)
export LLM_PROVIDER=openai
export OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export DEFAULT_MODEL_NAME=qwen2.5-7b
```

---

## 8. Team Mode (Parallel Research)

When `teamSize > 1`, the agent **decomposes the problem into sub-problems** and researches them in parallel:

```typescript
if (teamSize > 1) {
  const subproblems = await researchPlan(question, teamSize, soundBites, ...);
  
  if (subproblems.length > 1) {
    // Parallel call getResponse for each subproblem
    const responses = await Promise.all(
      subproblems.map(subproblem => getResponse(subproblem, ...teamSize=1))
    );
    
    // Aggregate answers
    thisStep = {
      answer: responses.map(r => r.answer).join('\n\n'),
      references: responses.map(r => r.references).flat(),
      isAggregated: true
    };
  }
}
```

This is the **only open-source research tool with built-in parallel decomposition**.

---

## 9. OpenAI-Compatible Server

The tool can run as an API server:

```bash
npm run serve --secret=your_token

# OpenAI-compatible endpoint
POST http://localhost:3000/v1/chat/completions
```

Features:
- Streaming support (`stream: true`)
- Special tokens: `<thinkXML>...</thinkXML>` for reasoning steps
- GitHub-flavored markdown footnotes for citations
- `reasoning_effort`: low/medium/high
- Custom parameters: `budget_tokens`, `max_attempts`, `boost_hostnames`, `bad_hostnames`, `with_images`, `team_size`

---

## 10. Comparison with Other Tools

### 10.1 vs Elephant Rock

| Feature | Elephant Rock | Jina DeepResearch |
|---------|:---:|:---:|
| **Purpose** | Academic research proposals | Web answer finding |
| **Output** | Structured proposals (10 sections) | Concise answer with citations |
| **Literature search** | OpenAlex + arXiv (academic) | Jina/Brave/Serper (web) |
| **Gap analysis** | ✅ Clustering + embeddings | ✅ Sub-question decomposition |
| **Novelty scoring** | ✅ 768-dim embeddings | ❌ |
| **Answer evaluation** | ❌ | ✅ 5-dimension eval system |
| **Idea generation** | ✅ Tree search | ❌ |
| **Proposal synthesis** | ✅ 10-section proposals | ❌ |
| **Code execution** | ❌ | ✅ JavaScript sandbox |
| **Paper writing** | ❌ | ❌ |
| **Parallel research** | ❌ | ✅ Team mode |
| **URL ranking** | Basic | ✅ 4-signal scoring |
| **Beast mode** | ❌ | ✅ Forced answer at budget limit |
| **Error analysis** | ❌ | ✅ Blame + improvement plan |
| **Frontend** | React (20 pages) | External (deepsearch-ui) |
| **Backend** | Python/FastAPI | TypeScript/Node.js |
| **Runtime** | 10-26 min | 10s-5min |
| **Self-hostable** | ✅ | ✅ |
| **Academic validation** | ❌ | ❌ |

### 10.2 vs Open Deep Research (nickscamara)

| Feature | Open Deep Research | Jina DeepResearch |
|---------|:---:|:---:|
| **Stars** | 6.2K | 5.2K |
| **Core LOC** | ~400 | ~750 |
| **Search providers** | 1 (Firecrawl) | 4 (Jina, DuckDuckGo, Brave, Serper) |
| **Answer evaluation** | ❌ | ✅ 5 dimensions |
| **Gap analysis** | ❌ (LLM decides "gaps") | ✅ Round-robin gap queue |
| **URL ranking** | None | ✅ 4-signal scoring |
| **Team mode** | ❌ | ✅ Parallel decomposition |
| **Code execution** | ❌ | ✅ JavaScript sandbox |
| **Beast mode** | ❌ | ✅ |
| **Error analysis** | ❌ | ✅ Blame + improvement |
| **Docker** | ✅ | ✅ |
| **OpenAI-compatible API** | ❌ | ✅ |
| **Local LLM support** | ❌ | ✅ (Ollama/LMStudio) |
| **Product tie-in** | Firecrawl (paid) | Jina Search + Reader (freemium) |

### 10.3 vs dzhng/deep-research

| Feature | dzhng/deep-research | Jina DeepResearch |
|---------|:---:|:---:|
| **Stars** | 18.9K | 5.2K |
| **Algorithm** | Recursive breadth×depth | Flat iterative loop with gap queue |
| **Answer evaluation** | ❌ | ✅ 5 dimensions |
| **Search breadth** | High (recursive) | Medium (linear) |
| **URL ranking** | Basic | ✅ Multi-signal |
| **Local LLM** | ✅ | ✅ |
| **Citations** | Basic | ✅ Structured footnotes |
| **Team mode** | ❌ | ✅ |

---

## 11. Key Architectural Innovations

### 11.1 The Evaluation Loop

The most important innovation. No other tool has this:

```
Agent produces answer
  → Evaluate: Is it definitive?
    → No → Store error, force more research
    → Yes → Evaluate: Is it fresh?
      → No → Store error, search for recent data
      → Yes → Evaluate: Is it complete?
        → No → Store error, research missing aspects
        → Yes → Evaluate: Is it strict-quality?
          → No → Apply improvement plan, retry
          → Yes → ACCEPT
```

Each failed evaluation produces **structured feedback** that gets injected into the next answer attempt:

```xml
<answer-requirements>
- You provide deep, unexpected insights...
- Follow reviewer's feedback and improve your answer quality.
<reviewer-1>
For get a pass, you must include specific numerical data...
</reviewer-1>
</answer-requirements>
```

### 11.2 The Gap Queue with Round-Robin

Unlike tools that iterate on a single topic, Jina DeepResearch maintains a **queue of unanswered questions** and cycles through them:

```
gaps = ["original question"]

Step 1: Work on "original question" → reflect → add 3 sub-questions
gaps = ["original question", "sub-q1", "sub-q2", "sub-q3"]

Step 2: Work on "sub-q1" → search → visit → answer → accepted
gaps = ["original question", "sub-q2", "sub-q3"]

Step 3: Work on "sub-q2" → search → visit → answer → accepted
gaps = ["original question", "sub-q3"]

Step 4: Work on "sub-q3" → search → visit → answer → accepted
gaps = ["original question"]

Step 5: Work on "original question" → answer → evaluate → pass → DONE
```

### 11.3 Error Analysis as Knowledge

Failed answers don't just get rejected — they become **knowledge items**:

```typescript
allKnowledge.push({
  question: "Why is this answer bad?",
  answer: evaluation.think + errorAnalysis.recap + errorAnalysis.blame + errorAnalysis.improvement,
  type: 'qa'
});
```

The agent learns from its mistakes within a single research session.

### 11.4 Action Alternation Enforcement

By disabling the current action type for the next step, the agent is forced to **cycle through all available information sources** before attempting another answer:

```
Step 1: answer (disabled next step)
Step 2: search (disabled next step)
Step 3: visit (disabled next step)
Step 4: reflect (disabled next step)
Step 5: answer → evaluate → reject
Step 6: search (disabled next step)
...
```

---

## 12. Strengths

1. **Best answer quality system**: 5-dimension evaluation with structured feedback loops. No competitor has this.
2. **Gap queue with round-robin**: Systematic coverage of all sub-questions, not just "search more."
3. **Error analysis as learning**: Failed answers become knowledge for future attempts.
4. **Multi-provider search**: 4 search backends (Jina, DuckDuckGo, Brave, Serper) + arXiv.
5. **Team mode**: Only tool with built-in parallel research decomposition.
6. **URL ranking**: 4-signal scoring (frequency, hostname, path, rerank) with diversity enforcement.
7. **Beast mode**: Always produces an answer, even if budget is exhausted.
8. **Local LLM support**: Works with Ollama/LMStudio for fully private research.
9. **OpenAI-compatible API**: Can be used as a drop-in replacement for any OpenAI client.
10. **Docker support**: Self-hostable in 60 seconds.
11. **Code execution**: JavaScript sandbox for data processing tasks.
12. **Multi-language evaluation**: Few-shot examples in 6 languages (EN, ZH, JA, DE, FR, KO).

---

## 13. Limitations

1. **Jina dependency**: Core functionality (search, read, rerank, embeddings, dedup) all require Jina API keys.
2. **Consumer-grade output**: Produces concise answers, not academic papers or proposals.
3. **No academic search**: No OpenAlex, Semantic Scholar, or arXiv integration (despite arXiv search option).
4. **No novelty scoring**: Unlike Elephant Rock, can't evaluate idea novelty.
5. **No knowledge graph**: No structured knowledge representation.
6. **No tree search**: Unlike Elephant Rock, doesn't explore idea space systematically.
7. **Token budget, not time budget**: Stops at token count, not time limit.
8. **No streaming progress UI**: Unlike Open Deep Research, no real-time activity panel.
9. **Gemini-centric**: Default model is Gemini; other providers are secondary.
10. **No experiment execution**: Unlike AI-Researcher, can't run ML experiments.
11. **No paper writing**: Unlike AI-Researcher, can't produce academic papers.
12. **TypeScript/Node.js**: Less common for research tools (Python dominates).

---

## 14. What Elephant Rock Can Learn

### 14.1 Must Adopt (High Priority)

1. **Multi-dimensional answer evaluation**: The 5-dimension eval system (definitive, fresh, complete, plural, strict) should be applied to research proposals. Before accepting a proposal, evaluate it on: novelty (does it add anything new?), feasibility (can it be implemented?), completeness (does it address all aspects?), rigor (are methods sound?).

2. **Error analysis as knowledge**: When a proposal is rejected, store the rejection reason as structured knowledge that improves future proposal attempts.

3. **Round-robin gap queue**: Instead of processing gaps linearly, cycle through them so all sub-problems get attention.

### 14.2 Should Consider (Medium Priority)

4. **Action alternation enforcement**: Force the pipeline to alternate between stages rather than getting stuck in one.

5. **Beast mode**: When budget is exhausted, produce the best possible output from accumulated knowledge rather than failing silently.

6. **Team mode (parallel decomposition)**: When researching a complex topic, decompose it into sub-problems and research them in parallel.

### 14.3 Could Consider (Low Priority)

7. **Multi-signal URL ranking**: The 4-signal scoring (frequency, hostname, path, rerank) for paper relevance.

8. **Query rewriting**: Use LLM to rewrite search queries based on initial search results.

---

## 15. Assessment & Rating

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Answer Quality** | 9.5/10 | Best in class — 5-dimension eval with feedback loops |
| **Code Quality** | 8/10 | Clean TypeScript, well-structured |
| **Innovation** | 9/10 | Gap queue, eval loop, error learning, team mode |
| **Practicality** | 9/10 | Works immediately, OpenAI-compatible API |
| **Documentation** | 8/10 | Good README, blog posts, multi-language guides |
| **Academic Rigor** | 2/10 | Not designed for academic research |
| **Cost Efficiency** | 6/10 | Requires Jina API (freemium) + Gemini/OpenAI |
| **Extensibility** | 8/10 | Modular tools, configurable models |
| **Community** | 8/10 | 5.2K stars, 571 commits, active development |

**Overall: 7.9/10** — The most **intelligent** web research tool. The evaluation system and gap queue are genuine innovations that produce measurably better answers than competitors. But it's consumer-focused, not academic.

---

## 16. Competitive Position Summary

```
Answer Quality Ranking:
  Jina DeepResearch     ★★★★★  (5-dimension eval, error learning, beast mode)
  dzhng/deep-research   ★★★☆☆  (recursive breadth×depth)
  Open Deep Research    ★★★☆☆  (iterative reflection)
  langchain-deep-researcher ★★★☆☆ (reflection node)
  u14app/deep-research  ★★☆☆☆  (SERP review)

Academic Research Ranking:
  AI-Researcher         ★★★★★  (full papers + experiments)
  AutoResearchClaw      ★★★★☆  (23-stage pipeline)
  Elephant Rock         ★★★★☆  (gap→novelty→proposals)

Ease of Self-Hosting:
  dzhng/deep-research   ★★★★★  (500 LOC, simple)
  Jina DeepResearch     ★★★★☆  (npm install, Docker)
  langchain-deep-researcher ★★★★☆ (500 LOC)
  Elephant Rock         ★★★☆☆  (Docker, needs Ollama)
  AI-Researcher         ★★☆☆☆  (Docker + GPU + hours)
```

---

## 17. Key Takeaways

1. **The evaluation system is the real innovation** — 5 dimensions of answer quality checking with structured feedback loops. No other tool does this. Elephant Rock should adopt this pattern for proposal quality.

2. **The gap queue is smarter than simple iteration** — round-robin through all sub-questions ensures complete coverage. This is a better approach than linear "search again" loops.

3. **Error analysis as knowledge** is brilliant — failed attempts become learning opportunities. When a proposal is rejected, the rejection reason should become structured knowledge for future attempts.

4. **Team mode (parallel decomposition)** is unique — decompose a complex question into sub-problems and solve them in parallel. This is the only tool with built-in parallelism.

5. **Beast mode is a good safety net** — "any answer is better than no answer" with forced synthesis at budget exhaustion. Elephant Rock should have a similar fallback.

6. **Jina dependency is the weakness** — search, read, rerank, embeddings, dedup all go through Jina APIs. Without Jina, this tool doesn't work. Elephant Rock's OpenAlex + arXiv are more independent.

7. **5.2K stars for 571 commits** — active development (10× more commits than Open Deep Research, 10× fewer than AI-Researcher).

8. **The multi-language evaluation examples are impressive** — the evaluator has few-shot examples in English, Chinese, Japanese, German, French, and Korean. This makes it work well globally.

9. **The code sandbox is a unique feature** — JavaScript execution for counting, filtering, sorting, and data processing. This could be useful in Elephant Rock for evaluating feasibility of proposed methods.

10. **Position in the landscape**: Jina DeepResearch is the **best answer-finding tool** but not a research tool. It finds the right answer to a question; Elephant Rock generates novel research proposals. They're complementary — Jina for "what is the answer?", Elephant Rock for "what should we research next?"
