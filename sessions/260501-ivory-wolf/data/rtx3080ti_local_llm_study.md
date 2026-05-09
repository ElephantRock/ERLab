# RTX 3080 Ti Local LLM Strategy — Study for Elephant Rock Platform

**Date**: 2026-05-09  
**Current Hardware**: AMD Radeon 780M (2GB VRAM) on dev machine  
**Target Hardware**: NVIDIA RTX 3080 Ti (12GB VRAM) at `100.64.0.1` (LM Studio)  
**Status**: LM Studio machine currently OFFLINE

---

## Current Setup vs Reference Proposal

```
┌─────────────────────┬─────────────────────────┬────────────────────────────┐
│ Aspect              │ Current Setup            │ Reference Proposal         │
├─────────────────────┼─────────────────────────┼────────────────────────────┤
│ LLM Engine          │ LM Studio (Anthropic SDK)│ llama.cpp server           │
│ Primary Model       │ qwen/qwen3-4b-2507 (4B) │ Qwen2.5-14B-Q4_K_M (14B)  │
│ Fast Model          │ (same as primary)        │ Qwen2.5-7B-Q6_K (7B)      │
│ Code Model          │ (none)                   │ DeepSeek-Coder-V2-Lite     │
│ Cloud Fallback      │ z.ai glm-5.1             │ GPT-4o API                 │
│ Embeddings          │ Ollama nomic-embed-text  │ (not covered)              │
│ Protocol            │ Anthropic SDK ↔ LM Studio│ OpenAI-compatible API      │
│ GPU                 │ RTX 3080 Ti (12GB)       │ RTX 3080 Ti (12GB)         │
│ Routing             │ Task-based (thinking/gen) │ Task-tier (3 tiers)        │
│ Server Ports        │ :1234 (single)           │ :8080, :8081, :8082        │
└─────────────────────┴─────────────────────────┴────────────────────────────┘
```

---

## What the Reference Proposes

### 3-Tier Model Architecture

| Tier | Model | VRAM | Purpose | Elephant Rock Module Mapping |
|:-----|:------|:-----|:--------|:-----------------------------|
| **Primary** | Qwen2.5-14B Q4_K_M | ~9.5GB | Complex reasoning | GapAnalyzer, StudyDesigner, ProposalSynthesizer, ConnectionAgent |
| **Fast** | Qwen2.5-7B Q6_K | ~7GB | Extraction, verification | ClaimExtractor, WikiVerifier, ContradictionDetector |
| **Code** | DeepSeek-Coder-V2-Lite IQ4_XS | ~7GB (MoE, 2.4B active) | Pseudocode, LaTeX | StudyDesigner.pseudocode, Export (LaTeX) |

### Key Architecture: llama.cpp Multi-Server

The reference proposes running **3 llama.cpp servers simultaneously** on different ports:
- `:8080` → Qwen2.5-14B (complex reasoning)
- `:8081` → Qwen2.5-7B (fast tasks)
- `:8082` → DeepSeek-Coder (code)

### Routing Logic: Task-Type Based

```python
# Maps task names to model tiers
tier_routing = {
    'gap_analysis': 'PRIMARY',        # 14B model
    'study_design': 'PRIMARY',        # 14B model
    'synthesis': 'PRIMARY',           # 14B model
    'claim_extraction': 'FAST',       # 7B model
    'verification': 'FAST',           # 7B model
    'classification': 'FAST',         # 7B model
    'code_generation': 'CODE',        # DeepSeek
    'pseudocode': 'CODE',             # DeepSeek
}
```

---

## Feasibility Assessment for Our Setup

### ✅ What Works

1. **VRAM Budget**: 12GB is sufficient for the proposed models:
   - Qwen2.5-14B Q4_K_M ≈ 9.5GB + 2.5GB context = 12GB ✅
   - Qwen2.5-7B Q6_K ≈ 7GB (can run alongside if only one at a time)
   - DeepSeek-Coder-V2-Lite ≈ 8GB active (MoE, only 2.4B active params)

2. **Quality Improvement**: Qwen2.5-14B is significantly better than our current qwen3-4b:
   - Better reasoning for gap analysis (currently times out on z.ai)
   - Better study design generation
   - Better contradiction detection

3. **Cost Savings**: Running locally = $0 per call vs z.ai paid API
   - Especially valuable for the pipeline burst problem (100+ calls per run)

4. **Speed**: 20-40 tok/sec on 3080 Ti is usable for pipeline stages

### ⚠️ Problems with the Reference

1. **CANNOT run all 3 models simultaneously on 12GB**:
   - Qwen2.5-14B (9.5GB) + Qwen2.5-7B (7GB) = 16.5GB > 12GB ❌
   - The reference claims you can run 3 servers, but that requires 24GB+ VRAM
   - **Reality**: Only 1 model at a time, or use model swapping

2. **llama.cpp vs LM Studio**: We already have LM Studio working with the Anthropic SDK. Switching to llama.cpp would:
   - Require rewriting the provider layer
   - Lose LM Studio's nice UI for model management
   - Gain OpenAI-compatible API (easier testing)

3. **Qwen2.5 vs Qwen3**: The reference suggests Qwen2.5, but Qwen3 is newer and better. Our current `qwen/qwen3-4b-2507` is already Qwen3-based.

4. **Model download sizes**: 
   - Qwen2.5-14B Q4_K_M ≈ 8.5GB download
   - Qwen2.5-7B Q6_K ≈ 6GB download
   - DeepSeek-Coder-V2-Lite ≈ 7GB download
   - Total: ~21.5GB (we have 50GB free)

5. **Windows compatibility**: The reference uses bash scripts. We'd need Windows equivalents.

---

## Recommended Adaptation for Elephant Rock

### Strategy: Tiered Single-Model with LM Studio Model Swapping

Since we **can't run 3 models simultaneously** on 12GB, use LM Studio's model management:

```
┌─────────────────────────────────────────────────────┐
│              LM Studio (:1234)                       │
│                                                      │
│  DAYTIME:  Qwen3-4B (fast extraction/verification)  │
│  PIPELINE: Auto-swap to Qwen2.5-14B for gap analysis│
│  NIGHT:    DeepSeek-Coder for batch processing      │
│                                                      │
│  Fallback: Cloud z.ai glm-5.1 (when GPU busy)       │
└─────────────────────────────────────────────────────┘
```

### Implementation Plan

**Phase 1: Upgrade Primary Model** (Qwen3-4B → Qwen3-14B or Qwen2.5-14B)
- Download Qwen2.5-14B-Instruct-Q4_K_M.gguf (~8.5GB)
- Load in LM Studio at `100.64.0.1:1234`
- Update `.env`: `EROCK_LMSTUDIO_MODEL=Qwen2.5-14B-Instruct-Q4_K_M`
- **Benefit**: 14B model is dramatically better for gap analysis, study design, synthesis

**Phase 2: Keep Cloud as Fast Tier**
- Claim extraction, verification, classification → cloud z.ai (fast, no VRAM needed)
- Gap analysis, study design, synthesis, connections → local 14B (complex reasoning)
- **This avoids the "can't run 2 models" problem**

**Phase 3: Add Code Model for Export** (optional)
- Load DeepSeek-Coder-V2-Lite when running exports
- Use for LaTeX generation in export pipeline
- Swap back to Qwen2.5-14B after export completes

### Updated .env Configuration

```bash
# Primary: Local 14B on LM Studio (complex reasoning)
EROCK_LMSTUDIO_ENABLED=true
EROCK_LMSTUDIO_BASE_URL=http://100.64.0.1:1234
EROCK_LMSTUDIO_MODEL=Qwen2.5-14B-Instruct-Q4_K_M

# Cloud: z.ai for fast/extraction tasks  
EROCK_ANTHROPIC_API_KEY=<existing>
EROCK_ANTHROPIC_MODEL=glm-5.1
EROCK_ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
EROCK_DEFAULT_PROVIDER=anthropic

# Routing: Local for thinking, Cloud for generation
EROCK_THINKING_MODEL=lmstudio
EROCK_GENERATION_MODEL=anthropic
```

### Updated Model Routing

```python
# backend/pipeline/model_selection.py (updated routing)

# Gap analysis → LOCAL (avoids z.ai timeout issue!)
"gap_analysis": "lmstudio",        # Was: cloud (timed out after 100 calls)

# Study design → LOCAL (complex reasoning)
"study_design": "lmstudio",

# Connection inference → LOCAL
"connection_inference": "lmstudio",

# Method-problem scoring → LOCAL
"method_problem_scoring": "lmstudio",

# Claim extraction → CLOUD (fast, structured output)
"claim_extraction": "anthropic",

# Wiki verification → CLOUD (fast, short responses)
"wiki_verification": "anthropic",

# Proposal synthesis → CLOUD (long generation)
"proposal_synthesis": "anthropic",
```

---

## Performance Estimates (3080 Ti)

| Pipeline Stage | Current (z.ai) | Proposed (Local 14B) | Improvement |
|:---------------|:---------------|:---------------------|:------------|
| Gap analysis | **5 min (TIMEOUT)** | ~30 sec | ✅ Fixes the critical bug |
| Study design | ~20 sec | ~45 sec | Slower but works |
| Connection inference | ~10 sec | ~15 sec | Similar |
| Method-problem scoring | ~8 sec | ~12 sec | Similar |
| Full pipeline run | **FAILS at gap analysis** | ~15 min estimated | ✅ Actually completes |

### The Critical Benefit

The **#1 reason to adopt this**: Our pipeline currently **FAILS** at gap analysis because z.ai blocks connections after 100+ rapid API calls during ingestion. Running gap analysis locally completely eliminates this problem — no rate limits, no connection errors, no timeouts.

---

## Immediate Action Items

| # | Action | Priority | Effort |
|:--|:-------|:---------|:-------|
| 1 | Download Qwen2.5-14B-Instruct-Q4_K_M.gguf to LM Studio machine | **URGENT** | 10 min |
| 2 | Update `.env` to use 14B model for thinking tasks | **URGENT** | 2 min |
| 3 | Route gap_analysis → local LM Studio | **URGENT** | 5 min |
| 4 | Test pipeline with local gap analysis | HIGH | 15 min |
| 5 | Route study_design + connection_inference → local | MEDIUM | 5 min |
| 6 | Add DeepSeek-Coder for export (optional) | LOW | 30 min |

### Download Command (on LM Studio machine)

The simplest approach: **Use LM Studio's UI** to search and download `Qwen2.5-14B-Instruct GGUF Q4_K_M`. LM Studio handles the download, quantization selection, and GPU offloading automatically.

Alternatively via command line:
```bash
# On the LM Studio machine (100.64.0.1)
wget https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf
```

---

## What We Should NOT Adopt from the Reference

1. ❌ **llama.cpp multi-server** — LM Studio already provides the same functionality with a better UI
2. ❌ **3 simultaneous models** — 12GB VRAM can't fit them. Use single-model + cloud instead
3. ❌ **LocalLLMProvider class** — Our AnthropicProvider wrapper already works with LM Studio
4. ❌ **Qwen2.5-7B as "fast tier"** — Cloud z.ai is faster and already works for extraction
5. ❌ **Bash scripts** — We're on Windows. Use LM Studio's GUI or PowerShell

## What We SHOULD Adopt

1. ✅ **Qwen2.5-14B Q4_K_M** as primary local model (replaces 4B)
2. ✅ **Task-type routing** to local vs cloud
3. ✅ **Gap analysis → LOCAL** (fixes the critical pipeline failure)
4. ✅ **Model swap strategy** (14B for reasoning, cloud for extraction)
5. ✅ **Performance monitoring** (tok/sec tracking per stage)
