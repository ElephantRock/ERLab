# DeepResearch (Alibaba-NLP) — Competitive Study Report

**Source:** https://github.com/Alibaba-NLP/DeepResearch  
**Stars:** 18.8K | **Forks:** 1.4K | **License:** Apache-2.0  
**Date:** 2026-05-06

---

## 1. What It Is

Tongyi DeepResearch is a **30.5B-parameter MoE model (3.3B activated per token)** by Alibaba's Tongyi Lab. It is an **information-seeking web agent** — not a research proposal generator. You give it a question, it searches the web, visits pages, reads academic papers, and produces a factual answer.

**It is a different species from Elephant Rock.** They solve different problems.

---

## 2. Architecture

### 2.1 Model

- **Tongyi-DeepResearch-30B-A3B** — Mixture of Experts, 30.5B total / 3.3B active
- 128K context length
- Open-source weights on HuggingFace and ModelScope
- Custom-trained from scratch for agentic tasks (not a general-purpose LLM with agent wrappers)

### 2.2 Training Pipeline (the real innovation)

Three-stage pipeline — this is what makes it state-of-the-art:

**Stage 1: Agentic Continual Pre-Training (CPT)**
- Collects data from documents, crawled web pages, knowledge graphs, historical search trajectories
- Reorganizes into "entity-anchored open-world knowledge memory"
- Generates multi-style (question, answer) pairs from randomly sampled entities
- Constructs "first-order" and "higher-order" action synthesis data
- Teaches the model tool-use behavior at the pre-training level

**Stage 2: Supervised Fine-Tuning (SFT)**
- Fully synthetic data — no human annotation
- QA pairs generated via knowledge graph walks, isomorphic table fusion, and difficulty escalation
- ReAct trajectories (Thought→Action→Observation) for structured reasoning
- IterResearch trajectories for sustained planning in long-horizon tasks
- Automated PhD-level question synthesis via iterative complexity upgrades

**Stage 3: On-Policy Reinforcement Learning**
- Custom GRPO (Group Relative Policy Optimization)
- Strictly on-policy — learning signal always relevant to current capabilities
- Token-level policy gradient loss
- Leave-one-out advantage estimation for variance reduction
- Selective negative sample filtering (prevents "format collapse")
- **Key insight: "data and training environment stability are more critical than the RL algorithm"**
- Synthetic Wikipedia-based training environment (no live API calls during training)

### 2.3 Inference Paradigms

**ReAct Mode (Light)**
- Standard Thought→Action→Observation loop
- No prompt engineering — tests intrinsic model capability
- Up to 100 LLM calls per query
- 150-minute timeout
- 110K token context budget

**Heavy Mode (IterResearch)**
- Deconstructs task into "research rounds"
- Each round: reconstructs streamlined workspace from previous round's key findings
- Maintains evolving "central report"
- Multiple Research Agents run in parallel
- Synthesis Agent integrates their reports
- Solves "cognitive suffocation" from ever-expanding context

### 2.4 Tools

| Tool | What It Does |
|------|-------------|
| **Search** | Google search via Serper API. Batch queries. Chinese/English aware. |
| **Visit** | Fetches web pages, extracts content relevant to a "goal". Uses Jina for reading. |
| **Google Scholar** | Academic paper search via Serper Scholar API. |
| **Python Interpreter** | Executes Python code in sandboxed environment. For computation. |
| **File Parser** | Parses PDF, DOCX, PPTX, TXT, CSV, XLSX, ZIP, MP4, MP3. Uses Dashscope. |

---

## 3. Benchmarks (State-of-the-Art)

| Benchmark | Score | What It Tests |
|-----------|-------|---------------|
| **HLE** (Humanity's Last Exam) | 32.9 | Academic reasoning at expert level |
| **BrowseComp** | 43.4 | Complex information seeking (English) |
| **BrowseComp-ZH** | 46.7 | Complex information seeking (Chinese) |
| **xbench-DeepSearch** | 75 | User-centric deep search tasks |
| **FRAMES** | — | Multi-hop factual reasoning |
| **SimpleQA** | — | Single-hop factual accuracy |
| **WebWalkerQA** | — | Web traversal comprehension |

Outperforms all proprietary and open-source deep research agents including OpenAI's DeepResearch.

---

## 4. Elephant Rock vs. DeepResearch — Honest Comparison

### They Are Not Competitors

| Dimension | Elephant Rock | DeepResearch |
|-----------|--------------|--------------|
| **What it does** | Generates novel research ideas + proposals | Answers factual questions via web search |
| **Input** | A research domain (e.g. "transformer attention") | A specific question (e.g. "What is the capital of France?") |
| **Output** | Original research proposal with gaps, novelty scores, feasibility | Factual answer with sources |
| **Core innovation** | Gap identification, novelty checking, proposal synthesis | Agentic web search with RL-trained reasoning |
| **Model** | Uses external LLM (Anthropic/OpenAI) | Custom 30B MoE model trained from scratch |
| **Literature sources** | Academic databases (OpenAlex, arXiv) | Live web search (Google, Google Scholar) |
| **Novelty detection** | Vector similarity against embedded papers | N/A — doesn't generate novel ideas |
| **Training** | None — pipeline orchestration | Full CPT → SFT → RL pipeline |
| **Deployment** | Self-hosted Python backend | vLLM + OpenAI-compatible API |
| **Open source** | Code only (no model weights) | Code + model weights (Apache-2.0) |
| **Stars on GitHub** | N/A (private) | 18.8K |

### What DeepResearch Does Better

1. **Web search quality.** They use Google (Serper) + Google Scholar. We use OpenAlex + arXiv. Their search is broader, faster, and covers the live web — not just academic papers.

2. **Reasoning depth.** Their model was RL-trained specifically for multi-step information seeking. Our pipeline orchestrates general-purpose LLMs. Their model *is* the agent; our pipeline *uses* an agent.

3. **Training methodology.** Their three-stage pipeline (CPT → SFT → RL) is state-of-the-art. We have no training pipeline at all — we're a software platform that calls external models.

4. **IterResearch paradigm.** Their "Heavy Mode" solves context window pollution by reconstructing workspaces each round. Our pipeline accumulates everything in memory.

5. **Benchmarks.** They have quantitative proof of performance on 7 benchmarks. We have zero benchmarks.

6. **Team & resources.** Alibaba Tongyi Lab. Hundreds of researchers. We are... us.

### What Elephant Rock Does That DeepResearch Doesn't

1. **Gap identification.** DeepResearch doesn't find what's missing in a field. It answers questions. We analyze the literature landscape and identify research gaps — unanswered questions that *should* exist.

2. **Novel idea generation.** DeepResearch retrieves existing information. We generate *new* research ideas. Nobody has published what we propose — by design.

3. **Proposal synthesis.** DeepResearch produces factual answers. We produce full research proposals with Title, Abstract, Introduction, Related Work, Proposed Method (with math), Evaluation Plan, Timeline, References, Risk Mitigation.

4. **Novelty scoring.** We embed ideas and compare against all known papers using vector similarity. DeepResearch has no concept of novelty — it retrieves facts.

5. **Feasibility evaluation.** We score ideas on data availability, compute requirements, and methodological complexity. DeepResearch doesn't evaluate feasibility of anything.

6. **Knowledge graph.** We build a persistent knowledge graph with entities and relationships (CITES, EXTENDS, USES_METHOD). DeepResearch has no persistent knowledge structure.

7. **Full-stack platform.** We have a 19-page React frontend, REST API, SSE streaming, user auth, dashboard, knowledge graph visualization, cost tracking. DeepResearch is a Python script.

---

## 5. What We Should Learn From DeepResearch

### 5.1 Adopt Immediately

**IterResearch for proposal synthesis.** Our proposal synthesizer jams everything into one massive LLM call. DeepResearch's approach — reconstruct a focused workspace each round, maintain a central report, iterate — would dramatically improve proposal quality. This is directly applicable to our `ProposalSynthesizer.synthesize()` method.

**Batch search queries.** DeepResearch's Search tool accepts arrays of queries in one call. Our literature search calls sources sequentially. Batching would cut literature search time.

**Tool sandboxing for reliability.** DeepResearch built a sandboxed tool environment with caching, retry, and fallback providers. Our pipeline has no tool sandbox — when OpenAlex goes down, the pipeline fails.

### 5.2 Adopt Medium-Term

**ReAct-style reasoning traces.** Our pipeline stages are opaque — run gap analysis, get gaps. DeepResearch shows its reasoning in every step. Making our pipeline stages produce visible thought traces would improve debuggability and trust.

**Quality via RL feedback loops.** We score proposals once. DeepResearch iteratively refines through on-policy rollouts. Even without custom model training, we could implement a "self-critique → revise" loop using our existing LLM provider.

### 5.3 Acknowledge as Out of Scope

**Custom model training (CPT → SFT → RL).** We don't have the compute, data, or team to train a 30B MoE model. This is Alibaba's competitive advantage. We should focus on being the best *software platform* that uses whatever models are available.

---

## 6. The Honest Competitive Position

**DeepResearch is a model. Elephant Rock is a platform.**

DeepResearch answers questions better than anything open-source. That's impressive. But it doesn't generate research proposals. It doesn't identify gaps. It doesn't score novelty. It doesn't synthesize 4,500-word proposals with mathematical notation.

Our competitive moat is the **pipeline architecture** — the seven stages that transform "a domain" into "a novel research proposal." No one else does this specific thing. DeepResearch does information retrieval. AI Scientist generates ideas from a single paper. We do the full cycle: search → ingest → gap → ideate → novelty → feasibility → propose.

The risk: if Alibaba (or OpenAI, or Google) decides to add gap identification and proposal generation to their agent, they'll do it with a custom-trained model and crush us on quality. Our defense is speed and focus — we should ship the best research proposal platform before they notice the opportunity exists.

---

## 7. Key Takeaway

> **Study DeepResearch for its engineering discipline — the training pipeline, the IterResearch paradigm, the tool sandboxing, the benchmark rigor. But don't imitate its product. It's a search agent. We are a research discovery engine. These are different products for different users.**
