# SkyworkAI/DeepResearchAgent — Comprehensive Competitive Study

**Repository**: https://github.com/SkyworkAI/DeepResearchAgent  
**Stars**: 3.4K | **Forks**: 439 | **Commits**: 133 | **License**: MIT  
**Version**: v2.0.0 (self-evolving)  
**Author**: SkyworkAI (Skywork AI — Chinese AI company)  
**Language**: Python 99.8%  
**Date**: 2026-05-06  

---

## 1. What It Is

**DeepResearchAgent** (DRA) is a **self-evolving agent framework** — not a research tool per se, but a **protocol and runtime** for building LLM-based agent systems that can improve themselves over time. It introduces two novel protocol layers:

- **RSPL (Resource Substrate Protocol Layer)**: Models prompts, agents, tools, environments, and memory as protocol-registered resources with explicit state, lifecycle, and versioned interfaces.
- **SEPL (Self Evolution Protocol Layer)**: Specifies a closed-loop operator interface to propose, assess, and commit improvements with auditable lineage and rollback.

**Key differentiator from ALL competitors**: It is the **only framework with built-in self-evolution** — agents that can optimize their own prompts via TextGrad (textual gradient descent), GRPO, Reinforce++, or reflection-based optimizers. No other research tool can improve itself.

**Second differentiator**: It is a **general-purpose agent framework** with environments for trading (Alpaca, Binance, Hyperliquid), mobile automation (ADB), browser control (operator browser), GitHub, filesystem, databases, and FAISS vector search — not just web research.

---

## 2. Architecture Overview

### 2.1 The Self-Evolution Loop

```
Act → Observe → Optimize → Remember → Act again (improved)
```

1. **Act**: Agent produces actions using LLM + tools
2. **Observe**: Capture outcomes, traces, intermediate reasoning, environment feedback
3. **Optimize**: Update prompts/solutions/variables using optimizer (TextGrad, GRPO, Reinforce++, reflection)
4. **Remember**: Persist summaries/insights to memory for later steps and sessions

### 2.2 Core Building Blocks

| Block | Location | Purpose |
|-------|----------|---------|
| **Agents** | `src/agent/` | Runtime logic that decides what to do next |
| **Tools** | `src/tool/` | Callable capabilities exposed to agents |
| **Environments** | `src/environment/` | Stateful interfaces (filesystem, browser, trading, mobile, DB, FAISS) |
| **Memory** | `src/memory/` | Session/event memory with summarization and insights |
| **Optimizers** | `src/optimizer/` | Self-improvement algorithms (TextGrad, GRPO, Reinforce++, reflection) |
| **Tracer** | `src/tracer/` | Record trajectories across runs |
| **Versioning** | `src/version/` | Manage iterative artifacts |
| **Config** | `configs/` | MMEngine-style composable configs |
| **Registry** | `src/registry.py` | `@AGENT.register_module()`, `@TOOL.register_module()`, etc. |

### 2.3 Source Structure

```
DeepResearchAgent/
├── configs/                         ★ MMEngine-style config composition
│   ├── base.py                     # Base config (model, memory, workdir)
│   ├── tool_calling_agent.py       # Tool-calling agent config
│   ├── planning_agent.py           # Hierarchical planning config
│   ├── trading_strategy_agent.py   # Trading agent config
│   ├── interday_trading.py         # Interday trading config
│   ├── intraday_trading.py         # Intraday trading config
│   ├── online_trading_agent.py     # Live trading config
│   ├── offline_trading_agent.py    # Backtesting config
│   ├── mobile_agent.py             # Mobile automation config
│   ├── operator_browser_agent.py   # Browser control config
│   ├── esg_agent.py               # ESG analysis config
│   ├── multi_agent_debate.py       # Multi-agent debate config
│   ├── ai_capability_debate.py     # AI capability debate
│   └── agents/ tools/ environments/ memory/ process/ # Sub-configs
├── src/
│   ├── registry.py                 ★ Registry pattern (AGENT, TOOL, ENV, MEMORY, OPTIMIZER)
│   ├── agent/
│   │   ├── tool_calling_agent.py  ★ Core: Think→Action→Observe loop
│   │   ├── planning_agent.py      ★ Hierarchical multi-agent planner
│   │   ├── debate_manager.py      # Multi-agent debate orchestration
│   │   ├── trading_strategy_agent.py
│   │   ├── interday_trading_agent.py
│   │   ├── intraday_trading_agent.py
│   │   ├── online_trading_agent.py
│   │   ├── offline_trading_agent.py
│   │   ├── mobile_agent.py
│   │   ├── operator_browser_agent.py
│   │   ├── esg_agent.py
│   │   ├── context.py             # Agent context management
│   │   ├── types.py               # Agent, AgentResponse, AgentExtra
│   │   └── server.py              # Agent Communication Protocol (ACP)
│   ├── tool/
│   │   ├── default_tools/
│   │   │   ├── web_searcher.py    # Web search (Google, Bing, Baidu, DuckDuckGo)
│   │   │   ├── web_fetcher.py     # Web page fetching
│   │   │   ├── bash.py            # Bash execution
│   │   │   ├── python_interpreter.py # Python code execution
│   │   │   ├── file_reader.py     # File reading
│   │   │   ├── file_editor.py     # File editing
│   │   │   ├── done.py            # Task completion signal
│   │   │   ├── mdify.py           # Markdown processing
│   │   │   ├── leetcode.py        # LeetCode submission
│   │   │   ├── search/            # Search sub-tools
│   │   │   ├── executor/          # Code execution sub-tools
│   │   │   └── markdown/          # Markdown sub-tools
│   │   ├── workflow_tools/         # AgentBus workflow tools
│   │   ├── mcp_tools/             # MCP integration
│   │   ├── esg_tools/             # ESG analysis tools
│   │   ├── other_tools/           # Additional tools
│   │   ├── context.py             # Tool context management
│   │   ├── server.py              # Tool Communication Protocol (TCP)
│   │   └── types.py               # Tool types
│   ├── environment/
│   │   ├── filesystem/            # File system environment
│   │   ├── browser/               # Browser environment
│   │   ├── operator_browser/      # Operator browser (visual)
│   │   ├── mobile/                # Mobile (ADB) environment
│   │   ├── database/              # Database environment
│   │   ├── faiss/                 # FAISS vector search environment
│   │   ├── github/                # GitHub environment
│   │   ├── alpacaentry/           # Alpaca trading environment
│   │   ├── binanceentry/          # Binance trading environment
│   │   ├── hyperliquidentry/      # Hyperliquid trading environment
│   │   ├── quickbacktest/         # Quick backtesting environment
│   │   └── server.py              # Environment Communication Protocol (ECP)
│   ├── optimizer/
│   │   ├── textgrad/              ★ TextGrad framework (vendored)
│   │   ├── textgrad_optimizer.py  ★ Prompt optimization via textual gradients
│   │   ├── reflection_optimizer.py # Reflection-based optimization
│   │   ├── grpo_optimizer.py      # Group Relative Policy Optimization
│   │   └── reinforce_plus_plus_optimizer.py # Reinforce++ RL optimizer
│   ├── memory/                     # Memory systems (session, event, insights)
│   ├── model/                      # Model manager (OpenAI, Anthropic, Google)
│   ├── prompt/                     # Prompt templates + prompt manager
│   ├── tracer/                     # Trajectory recording
│   ├── version/                    # Artifact versioning
│   ├── skill/                      # Skill system
│   ├── session/                    # Session management
│   ├── benchmark/                  # GAIA benchmark
│   ├── config/                     # Config manager (MMEngine-based)
│   ├── logger/                     # Logging
│   ├── utils/                      # Utilities
│   └── visualization/              # Visualization tools
├── libs/                           # Vendored libraries (TextGrad, etc.)
├── datasets/                       # Benchmark datasets
├── examples/                       # Example scripts
├── tests/                          # Tests
└── workdir/                        # Runtime artifacts
```

### 2.4 Dependencies

| Package | Purpose |
|---------|---------|
| `langchain` + `langgraph` | LLM orchestration + agent graphs |
| `mmengine` | MMEngine config system (from OpenMMLab) |
| `openai` + `anthropic` + `google-generativeai` | LLM providers |
| `crawl4ai` + `firecrawl` | Web crawling |
| `ddgs` + `baidusearch` + `googlesearch-python` | Search engines |
| `torch` + `transformers` | PyTorch + Hugging Face (for RL optimizers) |
| `scikit-learn` + `numpy` + `pandas` | Data science |
| `faiss-cpu` | Vector search |
| `alpaca-py` + `binance-connector` + `hyperliquid-python-sdk` | Trading |
| `adbutils` | Mobile automation |
| `scrapy` + `beautifulsoup4` | Web scraping |
| `streamlit` + `flask` + `plotly` | Visualization |
| `PyGithub` + `GitPython` | GitHub integration |
| `gymnasium` | RL environments |
| `nano-vectordb` | Lightweight vector DB |

---

## 3. The Agent Architecture

### 3.1 ToolCallingAgent — The Core Agent

The core agent implements a Think → Act → Observe loop:

```python
while step < max_steps:
    # 1. THINK: LLM produces structured output
    think_output = await model_manager(
        model=self.model_name,
        messages=messages,
        response_format=ThinkOutput  # {thinking, evaluation, memory, next_goal, actions}
    )
    
    # 2. ACT: Execute each action sequentially
    for action in think_output.actions:
        if action.type == "skill":
            response = await scp(name=action.name, input=action_args)
        else:  # tool
            response = await tcp(name=action.name, input=action_args)
    
    # 3. OBSERVE: Record to tracer + memory
    await tracer.add_record(observation, tool, task_id)
    await memory_manager.add_event(...)
    
    # 4. Check if done
    if response["done"]:
        break
```

The ThinkOutput structured output includes:
- `thinking`: Chain-of-thought reasoning
- `evaluation_previous_goal`: Evaluation of the previous step
- `memory`: What to remember for future steps
- `next_goal`: What to do next
- `actions`: List of `{type, name, args}` to execute

### 3.2 PlanningAgent — Hierarchical Multi-Agent

The PlanningAgent decomposes tasks and dispatches to sub-agents via an AgentBus:

```python
class PlanDecision(BaseModel):
    thinking: str               # Chain-of-thought
    analysis: str               # Evaluation of previous round
    plan_update: str            # Updated plan
    dispatches: List[SubTaskDispatch]  # Sub-agents to call concurrently
    is_done: bool               # Task complete?
    final_result: Optional[str] # Final answer
```

**The AgentBus drives the multi-round loop:**

```
Round 1: PlanningAgent → "Search for X and analyze Y"
  → Dispatches tool_calling_agent(task="Search for X") concurrently with esg_agent(task="Analyze Y")
  → Collects results

Round 2: PlanningAgent → "Based on results, now investigate Z"
  → Dispatches tool_calling_agent(task="Investigate Z")
  → Collects results

Round N: PlanningAgent → "Task complete, here's the final result"
  → is_done=True, final_result=...
```

**The plan.md system** tracks every round with Mermaid diagrams, execution logs, and analysis — similar to Cursor's plan files.

### 3.3 Agent Communication Protocols

| Protocol | Server | Purpose |
|----------|--------|---------|
| **ACP** (Agent Communication Protocol) | `agent/server.py` | Agent-to-agent dispatch |
| **TCP** (Tool Communication Protocol) | `tool/server.py` | Agent-to-tool calls |
| **ECP** (Environment Communication Protocol) | `environment/server.py` | Agent-to-environment interaction |
| **SCP** (Skill Communication Protocol) | `skill/server.py` | Agent-to-skill calls |
| **MCP** (Model Context Protocol) | `tool/mcp_tools/` | MCP integration |

### 3.4 All Agent Types

| Agent | Purpose |
|-------|---------|
| **ToolCallingAgent** | Core: Think→Act→Observe with tool calling |
| **PlanningAgent** | Hierarchical planner that dispatches sub-agents |
| **DebateManager** | Multi-agent debate orchestration |
| **TradingStrategyAgent** | Trading strategy development |
| **InterdayTradingAgent** | Interday (daily) trading |
| **IntradayTradingAgent** | Intraday (minute-level) trading |
| **OnlineTradingAgent** | Live trading execution |
| **OfflineTradingAgent** | Backtesting |
| **MobileAgent** | Mobile phone automation via ADB |
| **OperatorBrowserAgent** | Visual browser control |
| **ESGAgent** | ESG (Environmental, Social, Governance) analysis |
| **SimpleChatAgent** | Simple chat interface |

---

## 4. The Self-Evolution System

### 4.1 Four Optimizer Types

| Optimizer | File | Method |
|-----------|------|--------|
| **TextGrad** | `textgrad_optimizer.py` | Textual gradient descent on prompts |
| **Reflection** | `reflection_optimizer.py` | LLM-based reflection and improvement |
| **GRPO** | `grpo_optimizer.py` | Group Relative Policy Optimization (RL) |
| **Reinforce++** | `reinforce_plus_plus_optimizer.py` | Reinforce++ RL algorithm |

### 4.2 TextGrad Optimizer — The Most Interesting

TextGrad treats prompts as **optimizable variables** with "gradients":

```python
# 1. Extract optimizable variables from agent prompts
tg_vars = optimizer.extract_optimizable_variables(agent)
# Variables with require_grad=True in prompt templates

# 2. Run optimization loop
for step in range(optimization_steps):
    # Sync TextGrad variables back to agent prompts
    optimizer.sync_to_agent(tg_vars, agent)
    
    # Clear prompt caches so new values take effect
    optimizer.clear_prompt_caches(tg_vars)
    
    # Execute agent with current prompts
    result = await agent.ainvoke(task=task, files=files)
    
    # Compute loss via LLM evaluation
    loss = await compute_loss(result, task, optimizer_model)
    
    # Add loss as "gradient" to TextGrad variables
    for var in tg_vars:
        var.set_gradient(loss_feedback)
    
    # Update variables via TextGrad optimizer
    tg_optimizer.step(tg_vars)

# 3. Agent now uses improved prompts
```

**Black-box optimization**: The agent's internal LLM calls (LangChain) have no direct computation graph connection to TextGrad. The optimizer uses input-output feedback rather than gradient propagation through reasoning.

### 4.3 Prompt Variable System

Prompts are templates with variables that can be marked as optimizable:

```python
{
    "name": "agent_context_rules",
    "type": "system_prompt_module",
    "description": "Agent context rules",
    "require_grad": True,  # ✅ Marked for optimization
    "template": None,
    "variables": AGENT_CONTEXT_RULES
}
```

The optimizer extracts all `require_grad=True` variables from `system_prompt` and `agent_message_prompt`, converts them to TextGrad Variables, and optimizes them.

### 4.4 RL Optimizers (GRPO, Reinforce++)

These use PyTorch for actual gradient-based optimization:

- **GRPO**: Group Relative Policy Optimization — evaluates multiple candidate responses, computes relative advantages, updates policy
- **Reinforce++**: Policy gradient method with variance reduction

These require `torch` + `transformers` + `gymnasium` dependencies.

---

## 5. Environment System

### 5.1 All Environments

| Environment | Purpose |
|-------------|---------|
| **Filesystem** | Read/write/create files |
| **Browser** | Web browsing with Playwright |
| **Operator Browser** | Visual browser (screenshot-based) |
| **Mobile** | Android phone automation via ADB |
| **Database** | SQL database interaction |
| **FAISS** | Vector similarity search |
| **GitHub** | Repository operations |
| **Alpaca** | Stock/crypto trading (Alpaca API) |
| **Binance** | Crypto trading (Binance API) |
| **Hyperliquid** | Perpetual futures trading |
| **QuickBacktest** | Fast strategy backtesting |
| **Qlib** | Quantitative research (Microsoft Qlib) |

### 5.2 Environment State Injection

Environments inject **state** into agent context on every step:

```python
async def _get_environment_context(self, ctx, record, **kwargs):
    environment_context = "<environment_context>"
    for env_name in config.env_names:
        env_info = await ecp.get_info(env_name)
        rules = env_info.rules
        state = await ecp.get_state(env_name, ctx=ctx)
        environment_context += f"<{env_name}>{rules}{state}</{env_name}>"
    return {"environment_context": environment_context}
```

This is how trading agents see their portfolio, browser agents see the current page, and mobile agents see the phone screen.

---

## 6. Tool System

### 6.1 Default Tools

| Tool | Purpose |
|------|---------|
| **web_searcher** | Search Google, Bing, Baidu, DuckDuckGo |
| **web_fetcher** | Fetch web page content |
| **bash** | Execute bash commands |
| **python_interpreter** | Execute Python code |
| **file_reader** | Read files |
| **file_editor** | Edit files |
| **done** | Signal task completion |
| **mdify** | Markdown processing |
| **leetcode** | Submit LeetCode solutions |

### 6.2 Specialized Tool Categories

| Category | Purpose |
|----------|---------|
| **workflow_tools** | AgentBus workflow operations |
| **mcp_tools** | Model Context Protocol integration |
| **esg_tools** | ESG analysis tools |
| **other_tools** | Additional tools |

---

## 7. Comparison with Other Tools

### 7.1 vs Elephant Rock

| Feature | Elephant Rock | DRA |
|---------|:---:|:---:|
| **Purpose** | Academic research proposals | General agent framework |
| **Self-evolution** | ❌ | ✅ TextGrad + GRPO + Reinforce++ |
| **Hierarchical agents** | ❌ | ✅ PlanningAgent → sub-agents |
| **Environments** | 0 | 12+ (trading, browser, mobile, DB, FAISS) |
| **Gap analysis** | ✅ | ❌ |
| **Novelty scoring** | ✅ | ❌ |
| **Proposal synthesis** | ✅ | ❌ |
| **Prompt optimization** | ❌ | ✅ TextGrad with gradient tracking |
| **Memory system** | ❌ | ✅ Session + event + insights |
| **Tracer** | ❌ | ✅ Trajectory recording |
| **Academic search** | OpenAlex + arXiv | Google + Bing + Baidu |
| **Trading** | ❌ | ✅ Alpaca + Binance + Hyperliquid |
| **Mobile control** | ❌ | ✅ ADB |
| **Browser control** | ❌ | ✅ Playwright + visual |
| **Config system** | .env | MMEngine composable configs |
| **Research output** | Structured proposals | General task output |

### 7.2 vs LDR (LearningCircuit)

| Feature | LDR | DRA |
|---------|:---:|:---:|
| **Self-evolution** | ❌ | ✅ |
| **Strategies** | 20+ | Unlimited (configurable agents) |
| **Search engines** | 25+ | 4 (Google, Bing, Baidu, DDG) |
| **Encrypted storage** | ✅ SQLCipher | ❌ |
| **Knowledge library** | ✅ | ❌ |
| **Environments** | 0 | 12+ |
| **Trading** | ❌ | ✅ Full trading system |
| **Mobile** | ❌ | ✅ |
| **Browser control** | ❌ | ✅ |
| **MCP** | ✅ | ✅ |
| **Product maturity** | Full web app | Framework + examples |

### 7.3 vs Jina DeepResearch

| Feature | Jina DR | DRA |
|---------|:---:|:---:|
| **Answer evaluation** | ✅ 5-dimension | ❌ |
| **Self-evolution** | ❌ | ✅ |
| **Gap queue** | ✅ Round-robin | ❌ |
| **Hierarchical agents** | ❌ | ✅ |
| **Environments** | 0 | 12+ |
| **Optimizers** | 0 | 4 (TextGrad, GRPO, Reinforce++, reflection) |

---

## 8. Key Architectural Innovations

### 8.1 Self-Evolution Protocol

The SEPL (Self Evolution Protocol Layer) is genuinely novel. No other tool has:
- **Prompt optimization via TextGrad**: Treat prompts as optimizable variables, compute "gradients" from execution feedback, update prompts
- **RL-based optimization**: GRPO and Reinforce++ for policy improvement
- **Auditable lineage**: Every optimization step is recorded with before/after states
- **Rollback capability**: Can revert to previous prompt versions

### 8.2 Hierarchical Multi-Agent via AgentBus

The PlanningAgent + AgentBus pattern:
- PlanningAgent makes ONE LLM call per round
- AgentBus dispatches sub-agents concurrently (BROADCAST) or sequentially (UNICAST)
- Results feed back to PlanningAgent for the next round
- Plan.md tracks every round with Mermaid diagrams

### 8.3 MMEngine-Style Config Composition

From OpenMMLab's config system:
```python
# configs/tool_calling_agent.py
_base_ = ["base.py"]
tag = "tool_calling"
workdir = f"workdir/{tag}"
model_name = "openrouter/gpt-4o"
```

This enables config inheritance, composition, and CLI overrides:
```bash
python run.py --config configs/tool_calling_agent.py --cfg-options model_name=openrouter/gemini-3-flash
```

### 8.4 Resource Registry Pattern

Everything is a registered module:
```python
@AGENT.register_module(force=True)
class ToolCallingAgent(Agent): ...

@TOOL.register_module(force=True)
class WebSearcher(BaseTool): ...

@ENV.register_module(force=True)
class BrowserEnvironment(BaseEnvironment): ...
```

Auto-discovery handles registration. Config files reference modules by name.

### 8.5 Environment-as-Context Injection

Environments inject their state into the agent's prompt on every step. This means:
- Trading agents see their portfolio + market data every step
- Browser agents see the current page every step
- Mobile agents see the phone screen every step

This is more elegant than tool-based environment interaction.

---

## 9. Strengths

1. **Only framework with self-evolution**: TextGrad + GRPO + Reinforce++ + reflection — agents improve their own prompts
2. **Hierarchical multi-agent**: PlanningAgent → sub-agent dispatch → result collection → next round
3. **Environment system**: 12+ environments including trading, browser, mobile — far beyond web research
4. **MMEngine config system**: Clean composable configs with inheritance and CLI overrides
5. **Resource registry**: Everything is a registered module (agents, tools, environments, memory, optimizers)
6. **Memory system**: Session + event + insights across runs
7. **Tracer**: Trajectory recording for analysis and debugging
8. **Plan.md tracking**: Mermaid diagrams + execution logs for every planning session
9. **Trading integration**: Alpaca + Binance + Hyperliquid + backtesting — the only research tool with financial trading
10. **Mobile automation**: ADB-based phone control — unique among all competitors
11. **Browser control**: Playwright + visual (operator) browser — more capable than any search-only tool
12. **RL optimizers**: GRPO and Reinforce++ using PyTorch for policy optimization
13. **Structured output throughout**: Every LLM call uses Pydantic models for parsing

---

## 10. Limitations

1. **Not a research product**: It's a framework, not a deployable application. No web UI, no Docker one-click, no API server.
2. **No answer evaluation**: Unlike Jina DeepResearch, no multi-dimensional quality checking.
3. **No academic search**: No OpenAlex, arXiv, PubMed, Semantic Scholar integration. Only web search.
4. **No gap analysis**: Unlike Elephant Rock, can't identify research gaps.
5. **No novelty scoring**: Can't evaluate idea novelty.
6. **No knowledge library**: No document download → index → RAG loop like LDR.
7. **Heavy dependencies**: torch + transformers + gymnasium for RL optimizers = multi-GB install.
8. **Sparse documentation**: README is brief, optimizer docs are in Chinese, no API docs.
9. **Only 133 commits**: Early-stage project with limited community.
10. **No benchmarking framework**: No SimpleQA or similar standardized testing.
11. **Chinese-language optimizer docs**: TextGrad optimizer README is entirely in Chinese.
12. **No encrypted storage**: No SQLCipher or equivalent.
13. **No MCP server**: MCP tools exist but no MCP server for external integration.

---

## 11. What Elephant Rock Can Learn

### 11.1 Must Study (High Priority)

1. **Self-evolution / prompt optimization**: The TextGrad optimizer is the most interesting innovation. Applying it to Elephant Rock's synthesis prompts could significantly improve proposal quality over multiple runs.

2. **Hierarchical multi-agent**: The PlanningAgent pattern for decomposing complex research tasks into sub-agent dispatches. Elephant Rock's pipeline could benefit from a planning agent that decides which stages to run.

### 11.2 Should Consider (Medium Priority)

3. **Environment-as-context**: Injecting environment state (pipeline progress, available data) into the agent's prompt on every step, rather than passing it as tool output.

4. **MMEngine config composition**: Clean config inheritance with CLI overrides. Better than .env files.

5. **Resource registry pattern**: Everything (stages, providers, evaluators) as registered modules with auto-discovery.

6. **Memory system across runs**: Persist insights from previous pipeline runs to improve future runs.

### 11.3 Could Consider (Low Priority)

7. **Trading domain**: Not relevant for Elephant Rock's academic research focus.

8. **Mobile automation**: Not relevant.

9. **RL optimizers**: GRPO/Reinforce++ are overkill for prompt optimization. TextGrad is sufficient.

---

## 12. Assessment & Rating

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Innovation** | 9.5/10 | Self-evolution protocol is genuinely novel |
| **Architecture** | 9/10 | Clean registry + config + protocol design |
| **Environment Breadth** | 9/10 | 12+ environments — most versatile |
| **Self-Evolution** | 10/10 | Only tool with built-in prompt optimization |
| **Code Quality** | 7/10 | Clean but sparse tests, Chinese docs |
| **Documentation** | 4/10 | Brief README, optimizer docs in Chinese |
| **Product Readiness** | 3/10 | Framework only — no UI, no Docker, no API |
| **Research Capability** | 5/10 | General purpose, not research-focused |
| **Community** | 6/10 | 3.4K stars, only 133 commits |
| **Academic Rigor** | 2/10 | No academic search, no gap analysis |
| **Ease of Use** | 4/10 | Requires MMEngine knowledge, manual setup |

**Overall: 6.8/10** — The **most architecturally innovative** agent framework, but the **least product-ready**. Self-evolution is a genuine breakthrough that no competitor has. But as a research tool, it lacks search engines, academic databases, answer evaluation, and product features.

---

## 13. Competitive Position Summary

```
Innovation Ranking:
  SkyworkAI DRA           ★★★★★  (Self-evolution, TextGrad, RL optimizers)
  Jina DeepResearch       ★★★★☆  (5-dimension eval, gap queue, beast mode)
  Elephant Rock           ★★★☆☆  (Gap→novelty→tree search)
  LDR (LearningCircuit)   ★★★☆☆  (Strategy factory, knowledge library)

Product Readiness Ranking:
  LDR (LearningCircuit)   ★★★★★  (Full web app, Docker, MCP)
  Jina DeepResearch       ★★★★☆  (Docker, OpenAI API)
  Elephant Rock           ★★★☆☆  (React frontend, needs Ollama)
  SkyworkAI DRA           ★☆☆☆☆  (Framework only, no UI)

Environment Versatility:
  SkyworkAI DRA           ★★★★★  (Trading, browser, mobile, DB, FAISS)
  LDR (LearningCircuit)   ★★☆☆☆  (25 search engines)
  Elephant Rock           ★☆☆☆☆  (Academic databases only)

Academic Research Ranking:
  AI-Researcher           ★★★★★  (Full papers + experiments)
  Elephant Rock           ★★★★☆  (Gap→novelty→proposals)
  LDR (LearningCircuit)   ★★★☆☆  (Reports with citations)
  SkyworkAI DRA           ★★☆☆☆  (General purpose, no academic features)
```

---

## 14. Key Takeaways

1. **Self-evolution is the #1 innovation** — TextGrad-based prompt optimization is genuinely novel. No other tool can improve its own prompts through execution feedback. Elephant Rock should study this deeply.

2. **It's a framework, not a product** — Unlike LDR or Jina DeepResearch, you can't just run it. It requires understanding the MMEngine config system, writing config files, and running Python scripts.

3. **The PlanningAgent pattern is elegant** — One LLM call per round to decide what to do next. The AgentBus handles all dispatching. This separates planning from execution cleanly.

4. **Trading is the unexpected domain** — This is the only "research" tool with Alpaca, Binance, Hyperliquid, and backtesting environments. It's more of a general-purpose agent framework that happens to include research.

5. **The environment system is powerful** — Injecting environment state into the agent prompt on every step is more elegant than tool-based state queries. Elephant Rock could inject pipeline state (current stage, accumulated papers, gaps found) into synthesis prompts.

6. **MMEngine config composition is clean** — `_base_ = ["base.py"]` with CLI overrides is better than .env files. Elephant Rock should consider this pattern.

7. **Sparse documentation and early stage** — 133 commits, Chinese-language optimizer docs, no API documentation. This is a research prototype, not production software.

8. **The memory system is worth studying** — Session + event + insights memory that persists across runs. This enables agents to learn from previous sessions, similar to AutoResearchClaw's MetaClaw cross-run learning.

9. **RL optimizers (GRPO, Reinforce++) require heavy dependencies** — torch + transformers + gymnasium = multi-GB install. For most use cases, TextGrad is sufficient and much lighter.

10. **Position in the landscape**: DRA is the **most architecturally innovative** framework but the **least ready for actual use**. It's a blueprint for how self-evolving agent systems should be designed. The TextGrad optimizer and PlanningAgent pattern could be adopted by any other tool. But as a research tool, it's not competitive — no academic search, no gap analysis, no proposal generation.

11. **The Agent Communication Protocols (ACP/TCP/ECP/SCP) are well-designed** — Clean separation between agent dispatch, tool calls, environment interaction, and skill invocation. This layered protocol design is more rigorous than any competitor's architecture.

12. **Plan.md with Mermaid is brilliant** — Automatic generation of Mermaid execution flow diagrams in plan files. This gives visibility into multi-agent execution that no other tool provides.

13. **The Chinese AI ecosystem angle** — Baidu search, AKShare (Chinese financial data), Tushare (Chinese stock data). This tool is designed for the Chinese market in ways Western tools are not.

14. **The `require_grad` pattern for prompts** — Borrowing from PyTorch's autograd to mark which prompt variables are optimizable is an elegant API design choice that makes the system intuitive for ML practitioners.
