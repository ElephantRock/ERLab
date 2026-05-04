# Comprehensive Study Report: Karpathy's Autoresearch & Claude Autoresearch (Udit Goenka)

**Date:** 2026-05-04  
**Analyst:** Elephant Rock Lead (Ivory Wolf Session)  
**Source:** `C:\Next AI\ref\autoresearch-master`  
**Report Version:** 1.0

---

## 1. Executive Summary

The autoresearch project exists in two forms:

1. **Karpathy's Original** — A minimal 630-line Python framework for autonomous overnight LLM training optimization. One metric (val_bpb), one modifiable file (`train.py`), 5-minute time budget, git as memory.

2. **Claude Autoresearch (Udit Goenka)** — A domain-agnostic generalization that extends Karpathy's core loop into a 10-command agent plugin system supporting code, content, security, debugging, shipping, documentation, and subjective refinement across any measurable domain.

Both share the same DNA: **Modify → Verify → Keep/Discard → Repeat**, with mechanical metrics, atomic changes, and git-backed automatic rollback.

---

## 2. Architecture Overview

### 2.1 Karpathy's Original Architecture

```
autoresearch/
├── prepare.py       (389 lines) — Data download, BPE tokenizer training, evaluation harness
├── train.py         (630 lines) — Single-GPU GPT pretraining with Flash Attention 3
├── program.md       (~200 lines) — Agent instructions for experiment workflow
├── results.tsv      — Experiment tracking log
└── .git/            — Memory and audit trail
```

**Key components:**
- **prepare.py (READ-ONLY):** Downloads ClimbMix-400B shards, trains rustbpe tokenizer (8192 vocab), builds `token_bytes.pt` for BPB evaluation, provides `make_dataloader()` with best-fit packing (100% utilization, no padding)
- **train.py (MODIFIABLE):** GPT model with Flash Attention 3, RMS norm, rotary embeddings, GQA, value embeddings, learning rate schedule, mixed-precision training
- **program.md:** Branch naming (`experiment-YYYYMMDD-description`), file reading protocol, modification rules, results.tsv format, git commit workflow
- **Evaluation:** Bits-per-byte (BPB) metric via `evaluate_bpb()` — vocab-size-independent, sums per-token cross-entropy in nats, converts to bits/byte

### 2.2 Claude Autoresearch Architecture

```
autoresearch/
├── AGENTS.md                    — Universal agent interface (any AI agent)
├── README.md                    — Full documentation
├── COMPARISON.md                — Original vs Claude comparison
├── CONTRIBUTING.md              — Contribution guidelines
├── program.md                   — Karpathy's original agent instructions
├── prepare.py                   — Karpathy's original data prep
├── train.py                     — Karpathy's original training script
├── guide/                       — 15 comprehensive guides
│   ├── getting-started.md
│   ├── autoresearch.md
│   ├── autoresearch-debug.md
│   ├── autoresearch-fix.md
│   ├── autoresearch-learn.md
│   ├── autoresearch-plan.md
│   ├── autoresearch-predict.md
│   ├── autoresearch-reason.md
│   ├── autoresearch-scenario.md
│   ├── autoresearch-security.md
│   ├── autoresearch-ship.md
│   ├── advanced-patterns.md
│   ├── chains-and-combinations.md
│   ├── examples-by-domain.md
│   └── scenario/               — Scenario dimension templates
├── claude-plugin/               — Claude Code distribution
│   ├── skills/autoresearch/
│   │   ├── SKILL.md             — 1200+ line main skill definition
│   │   └── references/          — 11 detailed workflow references
│   └── commands/autoresearch/   — 10 subcommand registrations
├── scripts/
│   └── release.md               — Release process
└── .claude-plugin/
    └── marketplace.json         — Plugin marketplace registration
```

---

## 3. The 10 Commands

### 3.1 Core Loop: `/autoresearch`

The foundational autonomous iteration loop. User provides Goal, Scope, Metric, and Verify command. Agent loops: read context → ideate change → modify → commit → verify → guard → decide (keep/discard/crash) → log → repeat.

**Key features:**
- Unbounded (runs forever until interrupted) or bounded (`Iterations: N`)
- Plateau detection (stops after 15 iterations without metric improvement)
- Guard commands (safety net preventing regressions while optimizing primary metric)
- Metric-valued guards with regression thresholds (e.g., "bundle can grow max 5%")
- Noise handling (multi-run median, min-delta threshold, confirmation runs)
- Git-as-memory: agent reads `git log` and `git diff` every iteration
- Atomic changes enforced (one-sentence test, >5 file warning)
- Results logged to TSV with iteration/commit/metric/delta/guard/status/description

### 3.2 Planning Wizard: `/autoresearch:plan`

Interactive setup that converts a plain-language goal into a validated autoresearch configuration. Scans codebase for tooling, suggests scope/metric/verify, dry-runs the verify command to confirm it works.

### 3.3 Debug Loop: `/autoresearch:debug`

Autonomous bug-hunting using the scientific method. Each iteration tests one hypothesis. Logs confirmed bugs with file:line evidence and severity ratings. Can auto-chain to `fix` via `--fix` flag.

### 3.4 Fix Loop: `/autoresearch:fix`

Auto-detects broken tests/types/lint/build, fixes one error per iteration, stops at zero. Can read debug findings via `--from-debug`. Supports category targeting (`--category test|type|lint|build`).

### 3.5 Security Audit: `/autoresearch:security`

STRIDE threat model + OWASP Top 10 + red-team adversarial personas. Every finding requires code evidence. Tracks coverage across 6 STRIDE categories and 10 OWASP categories. Supports `--diff` (delta mode), `--fix` (auto-remediation), `--fail-on` (CI/CD gating).

### 3.6 Ship Workflow: `/autoresearch:ship`

Universal shipping with 8 phases: Identify → Inventory → Checklist → Prepare → Dry-run → Ship → Verify → Log. Supports 9 shipment types (code-pr, code-release, deployment, content, marketing-email, marketing-campaign, sales, research, design). Composite metric: `(checklist_passing/total)*80 + (dry_run_passed?15:0) + (no_blockers?5:0)`.

### 3.7 Scenario Explorer: `/autoresearch:scenario`

Generates use cases and edge cases from a seed scenario across 12 exploration dimensions (happy path, error, edge case, abuse, scale, concurrent, temporal, data variation, permission, integration, recovery, state transition). Domain templates for software, product, business, security, marketing.

### 3.8 Multi-Persona Prediction: `/autoresearch:predict`

Simulates 3-8 expert personas that independently analyze code, debate findings (1-3 rounds), and reach consensus. Personas: Architect, Security Analyst, Performance Engineer, Reliability Engineer, Devil's Advocate. Anti-herd mechanism. File-based knowledge representation (.md files ARE the knowledge graph). Supports `--chain` to pipe to downstream commands.

### 3.9 Documentation Engine: `/autoresearch:learn`

4 modes: init (from scratch), update (refresh existing), check (read-only health), summarize (quick inventory). Dynamic doc discovery (`docs/*.md`), validation-fix loop (max 3 retries), scale-aware scouting.

### 3.10 Adversarial Refinement: `/autoresearch:reason`

For subjective domains where no objective metric exists. Isolated multi-agent loop: Generate-A → Critic → Generate-B → Synthesize-AB → Blind Judge Panel → Convergence check. Every agent is cold-start (no shared session prevents sycophancy). Judges get randomized labels (X/Y/Z not A/B/AB). Convergence = N consecutive rounds where incumbent wins majority vote. Oscillation detection stops runaway loops.

---

## 4. Core Protocol: The Autonomous Loop

### 4.1 Loop Phases

```
Phase 0: Precondition Checks (git repo, dirty tree, lock files, detached HEAD, hooks)
Phase 1: Review (read files, results log, git log -20, git diff HEAD~1)
Phase 2: Ideate (fix crashes > exploit successes > explore new > combine near-misses > simplify > radical)
Phase 3: Modify (ONE atomic change, one-sentence test, max files check)
Phase 4: Commit (before verification! enables clean rollback)
Phase 5: Verify (mechanical metric extraction, timeout 2x normal, noise handling)
Phase 5.5: Guard (pass/fail or metric-valued with threshold, max 2 rework attempts)
Phase 6: Decide (keep/discard/crash/no-op/hook-blocked/metric-error)
Phase 7: Log (TSV: iteration/commit/metric/delta/guard/status/description)
Phase 8: Repeat (or stop if bounded and done)
```

### 4.2 Decision Logic

```
IF metric_improved AND (no guard OR guard_passed):
    KEEP — commit stays, git history preserves success
ELIF metric_improved AND guard_failed:
    REVERT → rework (max 2 attempts) → if still fails → DISCARD
ELIF metric_same_or_worse:
    DISCARD — safe_revert() (git revert preferred, git reset fallback)
ELIF crashed:
    Fix (max 3 tries) or DISCARD
```

### 4.3 Git-as-Memory System

Every iteration:
1. `git log --oneline -20` → see experiment sequence (kept vs reverted)
2. `git diff HEAD~1` → inspect last kept change to understand WHY it worked
3. Pattern detection: which files drive improvements
4. Failed approaches logged via revert commits (avoid repeating)

This is the key innovation: the git log IS the agent's memory. Without it, agents repeat failures. With it, each iteration builds on all prior knowledge.

### 4.4 Noise Handling Strategies

| Strategy | Description | When to Use |
|----------|-------------|-------------|
| Multi-run median | Run verify N times, use median | Benchmark times, Lighthouse |
| Min-delta threshold | Ignore improvements below noise floor | ML accuracy, API latency |
| Confirmation run | Re-verify before final keep decision | Noisy metrics |
| Environment pinning | Control external factors (seeds, caches) | ML training, JIT-dependent |

### 4.5 Plateau Detection

Tracks `iterations_since_best`. When >= `plateau_patience` (default 15), pauses and asks user: stop, continue, or change strategy. Configurable via `Plateau-Patience: N` or disabled with `off`.

---

## 5. Technical Details: Karpathy's Training Infrastructure

### 5.1 Data Pipeline (prepare.py)

- **Source:** ClimbMix-400B-shuffled (6,542 parquet shards from HuggingFace)
- **Tokenizer:** rustbpe BPE with 8,192 vocab, GPT-4-style split pattern
- **Special tokens:** `<|reserved_0|>` (BOS) through `<|reserved_3|>`
- **Validation:** Pinned shard 6542, EVAL_TOKENS = 40 × 524,288 ≈ 20.97M tokens
- **Data loader:** Best-fit packing (100% utilization, no padding), BOS-aligned, infinite iterator with epoch tracking
- **Metric:** Bits-per-byte (BPB) — `total_nats / (log(2) × total_bytes)` — vocab-size-independent

### 5.2 Training Script (train.py)

- **Model:** GPT with Flash Attention 3, RMS norm, rotary embeddings, GQA, value embeddings
- **Context:** MAX_SEQ_LEN = 2048
- **Budget:** TIME_BUDGET = 300 seconds (5 minutes)
- **Agent constraint:** Only `train.py` can be modified; `prepare.py` is read-only
- **Experiment workflow:** Branch per experiment → modify train.py → run training → record val_bpb → commit or revert

### 5.3 Constants (Immutable)

| Constant | Value | Purpose |
|----------|-------|---------|
| MAX_SEQ_LEN | 2048 | Context length |
| TIME_BUDGET | 300 | Training time per experiment (seconds) |
| EVAL_TOKENS | 20,971,520 | Validation evaluation tokens |
| VOCAB_SIZE | 8192 | BPE vocabulary size |
| MAX_SHARD | 6542 | Total data shards |

---

## 6. Command Chaining System

Commands can be piped together with `--chain` for multi-stage pipelines:

| Chain | Purpose |
|-------|---------|
| `debug → fix` | Find bugs then auto-repair |
| `predict → debug` | Expert analysis then targeted investigation |
| `scenario → debug → fix` | Edge cases → bug hunt → repair |
| `security → fix → security` | Audit → repair → verify |
| `predict → scenario,debug,security,fix,ship` | Full quality pipeline |
| `reason → predict → fix` | Subjective debate → empirical validation → implementation |
| `learn → security` | Document then audit |
| `plan → loop → ship` | Full improvement lifecycle |

**Context preservation:** Each stage writes structured output (TSV logs, markdown reports, JSON handoffs) that downstream stages read automatically. No copy-paste between steps.

---

## 7. The 7 Core Principles

1. **Constraint = Enabler:** Autonomy succeeds through intentional constraint (bounded scope, single metric, fixed iteration cost)
2. **Strategy ≠ Tactics:** Humans set direction; agents execute iterations
3. **Mechanical Metrics Only:** If you can't verify with a command, you can't iterate autonomously
4. **Fast Verification:** Verification speed determines experiment throughput
5. **Iteration Cost Shapes Behavior:** Cheap = bold exploration; expensive = conservative
6. **Git as Memory:** Every experiment committed, failed ones reverted, history IS the learning mechanism
7. **Honest Limitations:** State what the system cannot do; don't oversell

---

## 8. Comparison: Elephant Rock vs. Autoresearch

### 8.1 Conceptual Mapping

| Autoresearch Concept | Elephant Rock Equivalent |
|---------------------|------------------------|
| Core loop (modify→verify→keep/discard) | Pipeline stages (literature→gaps→ideas→evaluation→refinement) |
| Single metric (val_bpb) | Quality gate scores (novelty, feasibility, impact) |
| Git as memory | Database persistence (pipeline_runs, ideas, gaps) |
| Automatic rollback | Quality ratchet (only accept improvements) |
| Atomic changes | One stage at a time in pipeline |
| Results TSV | Pipeline run results (ideas.md, gaps.md) |
| Guard commands | Quality gate thresholds |
| Plateau detection | Stage completion criteria |
| Interactive setup (`/autoresearch:plan`) | Pipeline configuration (`pipeline-new.tsx`) |
| Bounded iterations (`Iterations: N`) | Max iterations config per stage |
| Command chaining | Pipeline orchestration (9 stages sequential) |
| Security audit | (Not present — could adopt) |
| Scenario exploration | Gap analysis (conceptually similar) |
| Multi-persona predict | Multi-agent Ideator/Critic/Refiner with Borda Tournament |
| Adversarial reason | (Not present — could adopt for gap evaluation) |
| Ship workflow | Export dialog (partial) |

### 8.2 Key Differences

| Dimension | Autoresearch | Elephant Rock |
|-----------|-------------|---------------|
| Domain | Any measurable domain | Scientific research automation |
| Agent model | Single agent (Claude/Codex) | Multi-agent (Ideator, Critic, Refiner) |
| Metric type | Objective (single number) | Multi-dimensional (novelty, feasibility, impact, confidence) |
| Memory | Git commits | PostgreSQL + ChromaDB vector store |
| Verification | Shell command (exit code) | LLM-based quality evaluation |
| Rollback | `git revert` | Quality ratchet (don't accept worse ideas) |
| Scope | File-level (glob patterns) | Domain-level (research queries) |
| Iteration speed | Seconds to minutes | Minutes to hours (LLM calls) |
| Output | Metric improvement | Research ideas, gaps, papers |
| Agent personality | None | Curiosity-driven, impasse-detecting |

### 8.3 What Elephant Rock Can Learn from Autoresearch

1. **Mechanical verification where possible:** Autoresearch's insistence on mechanically verifiable metrics is powerful. Elephant Rock's quality gates are LLM-based (subjective). Adding even one mechanical metric (e.g., "number of unique references not in previous run") would strengthen the loop.

2. **Git-as-memory for research iterations:** Elephant Rock stores results in a database, but doesn't use git history as a learning mechanism across runs. Tracking which configuration changes led to better results would enable meta-learning.

3. **Atomic changes:** Autoresearch enforces one change per iteration. Elephant Rock's pipeline already does this per-stage, but within stages (e.g., idea generation), multiple LLM calls happen without individual verification.

4. **Guard commands:** Elephant Rock has quality gates but no "guard" concept — a separate check that existing good results aren't degraded by new runs. Cross-run dedup (BATCH-42) partially addresses this.

5. **Plateau detection:** When research quality stops improving across runs, the platform doesn't detect or signal this. Could add plateau detection for the quality scores.

6. **Command chaining:** The pipeline is fixed 9-stage sequential. Autoresearch's chaining concept could enable flexible pipelines (e.g., "gaps → ideas → evaluate → if score < threshold → more gaps").

7. **Security audit:** Elephant Rock has no security scanning. Autoresearch's `security` command pattern could be adapted for research integrity checks (citation verification, plagiarism detection, statistical validity).

8. **Scenario exploration for test coverage:** The `scenario` command's 12-dimension exploration could strengthen Elephant Rock's gap analysis by systematically exploring research space dimensions.

### 8.4 What Autoresearch Can Learn from Elephant Rock

1. **Multi-agent architecture:** Autoresearch uses a single agent. Elephant Rock's Ideator/Critic/Refiner with Borda Tournament produces better results through adversarial collaboration.

2. **Persistent knowledge graph:** Autoresearch relies on git (text). Elephant Rock's knowledge graph with truth values and vector store enables semantic search and cross-run learning.

3. **Domain-specific pipeline stages:** Autoresearch's generic loop works for anything measurable, but Elephant Rock's 9-stage pipeline (literature search → gap analysis → idea generation → evaluation → refinement → proposals → knowledge graph → reporting) is optimized for research quality.

4. **Consciousness state machine:** Elephant Rock's 5-state consciousness model (IDLE→EXPLORING→ANALYZING→SYNTHESIZING→REFLECTING) provides richer state tracking than autoresearch's binary keep/discard.

5. **Self-improvement:** Elephant Rock has a self-improvement engine with quality ratchet. Autoresearch improves metrics but doesn't improve its own methodology.

---

## 9. Assessment: Suitability for Elephant Rock Integration

### 9.1 Direct Adoption: NOT Recommended

Autoresearch is fundamentally a **single-agent optimization loop** designed for Claude Code or Codex. It's not a library — it's a skill/plugin system with no programmatic API. Integrating it directly into Elephant Rock's Python backend would require:

1. Rewriting the entire protocol in Python (it's designed for agent prompts, not code)
2. Replacing the git-based memory with Elephant Rock's existing database
3. Replacing the shell-command verification with LLM-based evaluation
4. Adapting the single-agent model to Elephant Rock's multi-agent architecture

The effort would essentially be reimplementing the concepts, not adopting the code.

### 9.2 Concept Adoption: RECOMMENDED

Several autoresearch concepts are worth incorporating into Elephant Rock:

| Concept | Implementation Path | Priority |
|---------|-------------------|----------|
| Mechanical metrics for research quality | Add citation count, reference uniqueness, gap coverage % as supplementary metrics alongside LLM scores | HIGH |
| Git-as-memory for configuration learning | Track which pipeline configs lead to better results across runs | MEDIUM |
| Guard concept for cross-run quality | "Don't accept a new run if it doesn't improve on the best previous run's top idea score" | MEDIUM |
| Plateau detection for research domains | Signal when additional runs in a domain stop yielding novel insights | LOW |
| Command chaining for flexible pipelines | Allow users to compose custom pipeline flows (e.g., "gaps → ideas → paper" without full 9-stage run) | MEDIUM |
| Security/Integrity audit mode | Citation verification, statistical validity checks, plagiarism detection | LOW |

### 9.3 The Reason Command: Highest-Value Adaptation

The `/autoresearch:reason` adversarial refinement protocol (Generate-A → Critic → Generate-B → Synthesize-AB → Blind Judge Panel → Convergence) maps directly to Elephant Rock's multi-agent idea evaluation. Currently, Elephant Rock uses a Borda Tournament. Adding a blind judge convergence mechanism could improve idea quality:

1. Generate idea A (Ideator)
2. Critic attacks A (Critic)
3. Generate idea B informed by A + critique (Refiner)
4. Synthesize AB (best of both)
5. Blind judges score A, B, AB without knowing origin
6. Keep winner, repeat until convergence

This is structurally identical to what Elephant Rock already does but adds the cold-start isolation and blind judging that prevents anchoring bias.

---

## 10. File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `prepare.py` | 389 | Data download, tokenizer training, evaluation harness |
| `train.py` | 630 | GPT training script (modifiable) |
| `program.md` | ~200 | Agent instructions for experiment workflow |
| `README.md` | ~150 | Project overview |
| `COMPARISON.md` | ~200 | Original vs Claude comparison |
| `AGENTS.md` | ~500 | Universal agent interface |
| `SKILL.md` | ~1200 | Main Claude Code skill definition |
| `autonomous-loop-protocol.md` | ~800 | Detailed loop protocol |
| `core-principles.md` | ~250 | 7 universal principles |
| `results-logging.md` | ~300 | TSV logging protocol |
| `advanced-patterns.md` | ~700 | Guards, MCP, CI/CD, noise handling |
| `chains-and-combinations.md` | ~600 | Multi-command pipelines |
| 11 reference files | ~3000 | Per-command workflow details |
| 15 guide files | ~5000 | User-facing documentation |
| **Total** | **~12,000+** | |

---

## 11. Key Takeaways

1. **Autoresearch's genius is constraint:** By limiting scope to one metric, one file, and 5-minute iterations, it enables autonomous overnight optimization. Elephant Rock's research pipeline is inherently more complex, but the principle of "constrain to enable autonomy" applies.

2. **Git-as-memory is the killer feature:** The agent reads its own git history every iteration to learn from successes and avoid repeating failures. This is a pattern Elephant Rock could adapt using its database.

3. **Mechanical metrics are non-negotiable:** "If you can't verify with a command, you can't iterate autonomously." Elephant Rock's LLM-based evaluation is necessary for research quality, but adding mechanical supplementary metrics would strengthen the loop.

4. **The 10-command ecosystem is the real innovation:** The core loop is simple. The value comes from the 10 specialized commands (debug, fix, security, ship, scenario, predict, learn, reason, plan) and their chaining system.

5. **The Reason command is the most relevant to Elephant Rock:** Blind judge convergence with cold-start agents maps directly to multi-agent idea evaluation and could improve research output quality.

6. **Not worth adopting as code:** Autoresearch is a Claude Code/Codex plugin, not a library. The concepts are valuable, but the implementation is agent-prompt-based and would need complete reimplemention.

---

*End of report.*
