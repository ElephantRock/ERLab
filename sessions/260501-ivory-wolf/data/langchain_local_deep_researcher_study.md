# langchain-ai/local-deep-researcher — Comprehensive Competitive Study

**Repository**: https://github.com/langchain-ai/local-deep-researcher  
**Stars**: 9.1K | **Forks**: 949 | **Commits**: 146 | **License**: MIT  
**Author**: Lance Martin (LangChain)  
**Version**: 0.0.1 | **Date**: 2026-05-06  
**Tech Stack**: Python, LangGraph, LangChain, Ollama, LM Studio  

---

## 1. What It Is

**Local Deep Researcher** is a fully local web research assistant that runs **entirely on your machine** — no cloud API keys required (except for optional search). Give it a topic and it iteratively searches the web, summarizes findings, reflects on knowledge gaps, and generates new search queries to fill those gaps. After a configurable number of cycles, it produces a Markdown summary with all sources cited.

**Tagline**: "Fully local web research and report writing assistant"

**Key differentiator**: Runs 100% locally with Ollama or LM Studio. No data leaves your machine (unless you opt into cloud search APIs).

---

## 2. Architecture Overview

### 2.1 Codebase Statistics

| Metric | Value |
|--------|-------|
| **Source files** | 7 Python files |
| **Total LOC (source)** | ~500 lines |
| **Test files** | 0 |
| **Dependencies** | 11 (langgraph, langchain-community, tavily-python, langchain-ollama, duckduckgo-search, langchain-openai, openai, httpx, markdownify, python-dotenv) |
| **LLM Providers** | 2 (Ollama, LM Studio) |
| **Search APIs** | 4 (DuckDuckGo, Tavily, Perplexity, SearXNG) |
| **Runtime** | ~2-5 minutes (depends on model + loop count) |

### 2.2 Complete Source Tree

```
src/ollama_deep_researcher/
├── __init__.py           # Package init
├── configuration.py      # 10 configurable fields (Pydantic model)
├── graph.py              # LangGraph state machine (5 nodes, 1 router)
├── lmstudio.py           # LM Studio LLM adapter
├── prompts.py            # 6 prompt templates
├── state.py              # 3 state dataclasses (7 fields total)
└── utils.py              # 4 search providers + helpers
```

**That's the entire project.** 7 files, ~500 lines of source code.

### 2.3 Dependencies

```toml
langgraph>=1.1.0           # State machine orchestration
langchain-community>=0.4.0 # Community integrations (SearXNG)
tavily-python>=0.7.23      # Tavily search API
langchain-ollama>=1.0.0    # Ollama LLM integration
duckduckgo-search>=7.3.0   # DuckDuckGo search (free, no API key)
langchain-openai>=1.1.14   # OpenAI-compatible (for LM Studio)
openai>=2.31.0             # OpenAI client
httpx>=0.28.1              # HTTP client for page fetching
markdownify>=0.11.0        # HTML → Markdown conversion
python-dotenv==1.2.2       # Environment variable loading
```

---

## 3. The LangGraph State Machine

### 3.1 Graph Structure

```
START → generate_query → web_research → summarize_sources → reflect_on_summary
                                                                      │
                                                          ┌───────────┘
                                                          │
                                                    route_research
                                                     ┌────┴────┐
                                                     │         │
                                              loop_count    loop_count
                                                ≤ max         > max
                                                     │         │
                                              web_research  finalize_summary → END
                                             (next iteration)
```

### 3.2 State Schema

```python
@dataclass
class SummaryState:
    research_topic: str          # User's input topic
    search_query: str            # Current search query
    web_research_results: list   # Accumulated search results (append-only)
    sources_gathered: list       # Accumulated sources (append-only)
    research_loop_count: int     # Current iteration number
    running_summary: str         # Evolving summary

@dataclass
class SummaryStateInput:
    research_topic: str          # Only input needed

@dataclass
class SummaryStateOutput:
    running_summary: str         # Final output
```

### 3.3 Node Functions (5 nodes)

| Node | Function | LLM Call | Output |
|------|----------|----------|--------|
| **generate_query** | Generate search query from topic | ✅ (JSON mode or tool calling) | `search_query` |
| **web_research** | Execute web search | ❌ | `sources_gathered`, `web_research_results` |
| **summarize_sources** | Summarize/extend running summary | ✅ (free text) | `running_summary` |
| **reflect_on_summary** | Identify gaps, generate follow-up query | ✅ (JSON mode or tool calling) | `search_query` |
| **finalize_summary** | Deduplicate sources + format | ❌ | `running_summary` (final) |

### 3.4 Edge Logic

```python
# After reflect_on_summary, route based on loop count
def route_research(state, config):
    if state.research_loop_count <= configurable.max_web_research_loops:
        return "web_research"     # Continue loop
    else:
        return "finalize_summary" # Done, produce output
```

Default `max_web_research_loops`: **3** (so 3 search-summarize-reflect cycles).

---

## 4. The Research Loop in Detail

### 4.1 Cycle 1: Initial Research

```
User topic: "Transformer architecture improvements 2024"
    ↓
[LLM] Generate query: "machine learning transformer architecture explained"
    ↓
[Search] DuckDuckGo/Tavily/Perplexity/SearXNG → 3 results
    ↓
[LLM] Summarize results → running_summary
    ↓
[LLM] Reflect on summary → "Knowledge gap: performance benchmarks"
    ↓
[LLM] Generate follow-up query: "transformer performance benchmarks 2024"
```

### 4.2 Cycle 2+: Iterative Deepening

```
[Search] Follow-up query → 3 more results
    ↓
[LLM] EXTEND existing summary with new context
    ↓
[LLM] Reflect on updated summary → identify new gap
    ↓
[LLM] Generate new follow-up query
```

### 4.3 Final Cycle

```
[LLM] Final reflection → loop_count > max → finalize
    ↓
Deduplicate sources by URL
    ↓
Append formatted source list to summary
    ↓
Output: Markdown summary + source citations
```

---

## 5. Key Technical Details

### 5.1 Dual Output Modes: JSON Mode vs Tool Calling

```python
# JSON mode (default) — Ollama format="json"
llm = ChatOllama(model="llama3.2", temperature=0, format="json")

# Tool calling — for models that support it
llm = ChatOllama(model="llama3.2", temperature=0)
llm = llm.bind_tools([Query])
```

**Why both?** Some models (DeepSeek R1 7B/1.5B) can't produce reliable JSON. Tool calling is the fallback.

### 5.2 Thinking Token Stripping

```python
def strip_thinking_tokens(text: str) -> str:
    """Remove <think?> and </think?> tags from reasoning models."""
    while "/contentassist" in text and "type" in text:
        start = text.find("complexContent")
        end = text.find("type=text") + len("type=text")
        text = text[:start] + text[end:]
    return text
```

Handles DeepSeek R1 and similar reasoning models that emit thinking tokens.

### 5.3 Source Deduplication and Formatting

Sources are deduplicated by URL across all iterations:

```python
unique_sources = {}
for source in sources_list:
    if source["url"] not in unique_sources:
        unique_sources[source["url"]] = source
```

### 5.4 Full Page Fetching

Optional feature: after search, fetch full HTML content from result URLs and convert to Markdown:

```python
def fetch_raw_content(url: str) -> Optional[str]:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url)
        return markdownify(response.text)
```

Truncated to `max_tokens_per_source * 4` characters (default: 4000 chars).

### 5.5 LangGraph Studio Integration

The graph is designed to run inside **LangGraph Studio** — LangChain's visual debugging tool. Users can:
- Watch the state machine execute in real-time
- See each node's input/output
- Visualize the graph structure
- Configure parameters via UI

### 5.6 LangSmith Tracing

Search functions are decorated with `@traceable` for LangSmith observability:

```python
@traceable
def duckduckgo_search(query, max_results=3, fetch_full_page=False): ...
@traceable
def tavily_search(query, fetch_full_page=True, max_results=3): ...
@traceable
def perplexity_search(query, perplexity_search_loop_count=0): ...
@traceable
def searxng_search(query, max_results=3, fetch_full_page=False): ...
```

---

## 6. Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_web_research_loops` | 3 | Number of search-summarize-reflect cycles |
| `local_llm` | `llama3.2` | Model name |
| `llm_provider` | `ollama` | `ollama` or `lmstudio` |
| `search_api` | `duckduckgo` | `duckduckgo`, `tavily`, `perplexity`, `searxng` |
| `fetch_full_page` | `true` | Fetch full page content from URLs |
| `ollama_base_url` | `http://localhost:11434/` | Ollama API endpoint |
| `lmstudio_base_url` | `http://localhost:1234/v1` | LM Studio API endpoint |
| `strip_thinking_tokens` | `true` | Remove `<think?>` tags |
| `use_tool_calling` | `false` | Use tool calling instead of JSON mode |

**Priority**: Environment variables > LangGraph UI config > Default values.

---

## 7. Search Providers in Detail

| Provider | API Key Required | Features |
|----------|-----------------|----------|
| **DuckDuckGo** | ❌ None (default) | Free, no auth, text search, full page fetch |
| **Tavily** | ✅ `TAVILY_API_KEY` | Advanced search, raw content, highly rated |
| **Perplexity** | ✅ `PERPLEXITY_API_KEY` | Uses `sonar-pro` model, returns citations |
| **SearXNG** | ❌ Self-hosted | Metasearch engine, configurable backends |

### DuckDuckGo (Default)
```python
with DDGS() as ddgs:
    search_results = list(ddgs.text(query, max_results=max_results))
```
Free, no API key, reasonable quality. Default choice for fully local operation.

### Perplexity
```python
payload = {
    "model": "sonar-pro",
    "messages": [
        {"role": "system", "content": "Search the web and provide factual information with sources."},
        {"role": "user", "content": query},
    ],
}
```
Uses Perplexity's `sonar-pro` model as both search and summarizer. Returns citations automatically.

---

## 8. Comparison with Elephant Rock

### 8.1 Feature Matrix

| Feature | Elephant Rock | local-deep-researcher |
|---------|:---:|:---:|
| **Literature Search** | OpenAlex + arXiv (academic APIs) | DuckDuckGo/Tavily/Perplexity/SearXNG (general web) |
| **Gap Analysis** | ✅ Full pipeline with clustering + dedup | ✅ Iterative reflection (simpler but effective) |
| **Idea Generation** | ✅ Tree search + Borda voting | ❌ None (only summarizes) |
| **Novelty Scoring** | ✅ 768-dim embeddings | ❌ None |
| **Knowledge Graph** | ✅ Full KG + vector store + RAG | ❌ None |
| **Experiments** | ❌ | ❌ |
| **Paper Writing** | Proposals (35K chars) | Summaries (Markdown) |
| **Citation Verification** | Basic | Basic (source URLs) |
| **Self-Reflection** | ❌ No iterative refinement | ✅ Core feature (reflect → new query) |
| **Frontend** | Full React SPA (19 pages) | LangGraph Studio (visual graph debugger) |
| **100% Local** | ❌ (needs z.ai API) | ✅ (Ollama + DuckDuckGo) |
| **Runtime** | 10-26 min | 2-5 min |
| **Code Size** | ~77K LOC | ~500 LOC |
| **Docker** | ❌ | ✅ |
| **Streaming** | SSE | LangGraph state streaming |

### 8.2 Where local-deep-researcher Excels

1. **100% local**: Runs entirely on your machine. No cloud API required for LLM (Ollama) or search (DuckDuckGo).
2. **Iterative self-reflection**: The core loop of "summarize → reflect on gaps → new query" is elegant and effective.
3. **Extreme simplicity**: ~500 LOC total. You can understand the entire system in 15 minutes.
4. **LangGraph visual debugging**: Watch the state machine execute in real-time with full state inspection.
5. **LangSmith tracing**: Built-in observability for every search call.
6. **Thinking token handling**: Properly handles reasoning models (DeepSeek R1) that emit `<think?>` tags.
7. **Full page fetching**: Optional HTML→Markdown conversion for deeper source content.
8. **Configurable depth**: `max_web_research_loops` controls how deep the research goes.
9. **Docker support**: One-command deployment.

### 8.3 Where Elephant Rock Excels

1. **Academic APIs**: OpenAlex + arXiv for real academic papers. Their DuckDuckGo is general web.
2. **Novel idea generation**: We generate novel research ideas. They only summarize existing knowledge.
3. **Gap identification**: Our clustering + dedup pipeline identifies structural gaps. Their "reflection" is shallower.
4. **Embeddings**: Real 768-dim Ollama embeddings for similarity search.
5. **Knowledge graph**: Full KG + vector store + RAG.
6. **Proposal writing**: 35K-char structured proposals vs their Markdown summaries.
7. **Multi-stage pipeline**: 32 subsystems with checkpoints, resume, decision loops.
8. **Web UI**: Full React SPA vs their LangGraph Studio debugger.

---

## 9. The Iterative Reflection Pattern — Key Innovation

The most important architectural insight from this project is the **IterDRAG-inspired reflection loop**:

```
Query → Search → Summarize → Reflect → Gap? → New Query → Search → ...
```

This pattern was inspired by [IterDRAG](https://arxiv.org/html/2410.04343v1):
- Decompose a query into sub-queries
- Retrieve documents for each sub-query
- Answer the sub-query
- Build on the answer by retrieving docs for the next sub-query

**How it differs from our pipeline**:
- **Our approach**: Search once → extract gaps → generate ideas → score novelty → write proposal
- **Their approach**: Search → summarize → reflect → search again → extend summary → repeat

**The key difference**: Their reflection is **iterative search refinement** — the LLM identifies what's missing and searches again. Our gap analysis is **structural gap identification** — we cluster findings and identify what topics are missing from the literature.

**Both approaches have merit**. Their iterative search produces more comprehensive coverage. Our structural analysis produces more novel insights. A hybrid approach could be powerful.

---

## 10. LangGraph as an Orchestration Framework

This project is a showcase for **LangGraph** — LangChain's state machine library. Key observations:

### 10.1 Strengths
- **Visual debugging**: LangGraph Studio shows graph execution in real-time
- **State management**: Automatic state persistence and inspection
- **Configuration**: Pydantic models with environment variable overrides
- **Tracing**: LangSmith integration for observability
- **Deployment**: Multiple options (local, Docker, LangGraph Cloud)

### 10.2 Trade-offs
- **LangChain dependency**: Heavy dependency chain (langchain, langchain-community, langchain-ollama, etc.)
- **No custom UI**: Stuck with LangGraph Studio or API access
- **Overhead**: LangGraph adds complexity for what is essentially a 5-step loop

### 10.3 Lessons for Elephant Rock
- **Consider LangGraph** for pipeline orchestration — it handles state, checkpoints, and visual debugging out of the box
- **LangSmith tracing** is excellent for debugging pipeline runs
- **But**: Our custom FastAPI + React approach gives more control over the UI

---

## 11. Comparison with Other Tools in This Space

| Tool | Stars | LOC | Local? | Reflection Loop? | Output |
|------|-------|-----|--------|-----------------|--------|
| **local-deep-researcher** | 9.1K | ~500 | ✅ | ✅ | Markdown summary |
| **u14app/deep-research** | 4.6K | ~5K | ❌ | ✅ | Markdown report |
| **dzhng/deep-research** | 18.9K | ~500 | ❌ | ✅ | Markdown report |
| **AutoResearchClaw** | 11.9K | 54K+ | ❌ | ✅ (PIVOT/REFINE) | Full papers |
| **Elephant Rock** | — | 77K | Partial | ❌ | Proposals |

**Key insight**: The reflection loop pattern is universal. Every research tool uses some variant of "search → summarize → reflect → search again." The difference is what happens with the final output.

---

## 12. Key Learnings for Elephant Rock

### 12.1 What We Should Adopt

1. **Iterative reflection loop**: Add a "reflect → re-search" step after gap analysis. If the LLM identifies gaps that need more information, search again before generating ideas.
2. **Full page fetching**: Optionally fetch full HTML content from search results and convert to Markdown. Our current approach only uses snippets.
3. **LangSmith-style tracing**: Add structured tracing to every pipeline step for debugging.
4. **Configurable depth**: Let users control how deep the research goes (like `max_web_research_loops`).
5. **Thinking token handling**: Properly handle `<think?>` tokens from reasoning models like DeepSeek R1.
6. **100% local mode**: Support fully local operation with Ollama for users who don't want cloud APIs.

### 12.2 What We Should NOT Copy

1. **LangGraph dependency**: Our custom pipeline gives more control
2. **No idea generation**: They only summarize; we generate novel ideas
3. **General web search**: Our academic APIs are more appropriate for research
4. **No embeddings/vectors**: They don't use any similarity search

### 12.3 Integration Opportunities

1. **Use as a search refinement step**: After our initial literature search, use their reflection loop to find additional papers
2. **Use their DuckDuckGo search**: Free, no-API-key search as a fallback when OpenAlex/arXiv fail
3. **Use LangGraph for pipeline visualization**: Port our pipeline to LangGraph for better debugging

---

## 13. Assessment & Rating

| Dimension | Score (1-10) | Notes |
|-----------|:---:|-------|
| **Simplicity** | **10** | ~500 LOC. The most elegant research tool we've studied. |
| **100% Local** | **10** | Runs entirely on your machine. Privacy-first. |
| **Educational Value** | **10** | Best learning tool for understanding iterative research agents. |
| **Reflection Loop** | **9** | Clean implementation of IterDRAG-inspired iterative refinement. |
| **Framework Integration** | **9** | Excellent LangGraph + LangSmith showcase. |
| **Observability** | **9** | LangSmith tracing + LangGraph Studio visual debugging. |
| **Search Flexibility** | **7** | 4 providers but no academic APIs. |
| **Output Quality** | **5** | Markdown summaries. No structured proposals, no papers. |
| **Innovation** | **6** | Clean execution of a known pattern. Not novel. |
| **Testing** | **1** | Zero test files. |
| **Documentation** | **8** | Good README, video tutorials. |
| **Community** | **9** | 9.1K stars, LangChain branding, active maintenance. |
| **Overall** | **7.8/10** | The gold standard for simple, local, iterative research agents. |

---

## 14. Critical Observations

### 14.1 The Power of Simplicity

At ~500 LOC, this project achieves what tools 100x its size try to do. The core insight: **a 5-node state machine with a reflection loop produces surprisingly good research summaries**. You don't need 77K LOC to do research automation.

### 14.2 The LangChain Ecosystem Play

This project is clearly a **LangGraph showcase** — it demonstrates state machines, visual debugging, configuration, and tracing. The 9.1K stars reflect LangChain's brand power more than the tool's capabilities.

### 14.3 The Missing Innovation

The tool summarizes existing knowledge well but **generates nothing new**. It doesn't identify novel research directions, generate hypotheses, or propose experiments. It's a **knowledge aggregator**, not a **research discovery engine**.

### 14.4 The "Good Enough" Problem (Again)

Like u14app/deep-research, this tool produces "good enough" summaries in 2-5 minutes. For most users, that's sufficient. Our 26-minute pipeline that produces novel research proposals is overkill for these use cases.

### 14.5 The Reflection Pattern is Universally Applicable

Every successful research tool uses some form of iterative reflection:
- **local-deep-researcher**: Reflect on summary → new query (explicit)
- **u14app/deep-research**: Review SERP queries → follow-up research
- **AutoResearchClaw**: PIVOT/REFINE decision loops (Stage 15)
- **Elephant Rock**: ❌ No iterative refinement (we should add this)

---

## 15. Conclusion

**langchain-ai/local-deep-researcher** is the most elegant research automation tool we've studied. At ~500 LOC, it demonstrates that iterative search-summarize-reflect loops produce surprisingly good results. It's the best starting point for anyone wanting to understand how AI research agents work.

However, it's fundamentally a **knowledge aggregator** — it summarizes what's already known. It doesn't generate novel ideas, identify structural gaps in the literature, or produce academic papers. For research discovery, Elephant Rock and AutoResearchClaw remain the only options.

The most important takeaway for us: **add an iterative reflection loop to our pipeline**. After our initial literature search and gap analysis, let the LLM reflect on what's missing and search again. This single feature could dramatically improve our coverage depth.

**Rating: 7.8/10** — Best-in-class simple local research agent. A masterclass in minimalism. Not a research discovery system.
