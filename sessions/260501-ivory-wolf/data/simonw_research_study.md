# simonw/research — Comprehensive Competitive Study

**Repository**: https://github.com/simonw/research  
**Local Path**: `C:\Next AI\ref\research-main`  
**Author**: Simon Willison (co-creator of Django, creator of Datasette, LLM, sqlite-utils)  
**License**: MIT (individual sub-projects vary)  
**Date studied**: 2026-05-06  

---

## 1. What It Is

**simonw/research** is NOT a research tool. It is a **research journal** — a monorepo of **88 independent research investigations** conducted by Simon Willison using AI agents (primarily Claude). Each subdirectory is a self-contained research project with a README report, notes, and code artifacts.

This is the **largest publicly documented collection of AI-assisted research investigations** in existence. It demonstrates a methodology: how to use LLMs as research assistants for deep technical exploration.

**Key insight for Elephant Rock**: This repo is NOT a competitor. It is a **methodology blueprint** — a demonstration of how AI-assisted research should be conducted, documented, and accumulated over time.

---

## 2. Repository Structure

### 2.1 Scale

| Metric | Count |
|--------|-------|
| **Research projects** | 88 subdirectories |
| **Total files** | ~589 code files |
| **Python files** | 214 |
| **JavaScript/TypeScript files** | 47 |
| **Go files** | 13 |
| **Rust files** | 7 |
| **Markdown files** | 328 (reports + notes + skills) |
| **Dependencies** | 3 (`cogapp`, `llm`, `llm-github-models`) |

### 2.2 Research Methodology (from AGENTS.md)

Every investigation follows this pattern:

1. **Create a new folder** with an appropriate name
2. **Create `notes.md`** — append notes as you work, tracking what you tried and learned
3. **Build `README.md`** — a research report at the end
4. **Final commit includes only**:
   - `notes.md` and `README.md`
   - Code you wrote
   - `git diff` against modified repos (not full copies)
   - Binary files < 2MB
5. **DO NOT include full copies** of fetched code

### 2.3 README Generation

The README uses **cogapp** for automatic project descriptions:
- A GitHub Action runs `cog -r -P README.md` on every push
- Discovers all subdirectories, sorts by first commit date
- Generates AI summaries using `llm -m github/gpt-4.1`
- Caches summaries in `_summary.md` files

---

## 3. Research Categories

### 3.1 Category Distribution

The 88 projects span 10+ distinct technical domains:

| Category | Projects | Examples |
|----------|:---:|----------|
| **SQLite** | 15 | query linter, ripgrep function, permissions POC, WAL containers, hamming extension, time limit extension, tags benchmark, chronicle vs history, WASM library, syntaqlite extension |
| **WebAssembly / Pyodide** | 12 | cmarkgfm in Pyodide, monty WASM, pyo3-pyodide, node-pyodide, llm-pyodide plugin, WASM REPL CLI, vite browser compiler, pluau WASM |
| **Sandboxing** | 7 | codex sandbox analysis, JavaScript sandboxing research, QuickJS async sandbox, mquickjs sandbox, JavaScript sandboxing, code sandbox investigation |
| **Datasette** | 8 | plugin skill, SQL permissions review, plugin alpha versions, JS init, NPM package, self-hosting, datasette-lite |
| **Python Libraries** | 8 | h3/h3o benchmark, memchr wrapper, tre binding, epsilon wrapper, wazero Python, python-markdown comparison |
| **Browser/CDP** | 4 | WebMCP Chrome demo, rod library research, go-rod CLI, servo crate exploration |
| **Security** | 5 | CSRF protection demo, string redaction, duckdb security, extract system prompts |
| **Cloud/Infra** | 5 | Litestream restarts, cloudflare workers Python SQLite, SeaweedFS testing, environment report |
| **AI/LLM** | 4 | OpenAI API skills, Starlette 1.0 skill, blog tags scikit-learn, deepseek-ocr-nvidia |
| **Misc** | 20 | SVG-to-PNG, ast-grep rewriter, offline notes sync, streaming file upload, GitHub CLI proxy, uv run analysis, env86 analysis, etc. |

### 3.2 Key Research Projects

#### Sandboxing (Most Relevant to Elephant Rock)

| Project | What Was Investigated |
|---------|----------------------|
| **codex-sandbox-investigation** | OpenAI Codex CLI sandbox: macOS Seatbelt + Linux Landlock/seccomp. Three modes: DangerFullAccess, ReadOnly, WorkspaceWrite. Git protection always read-only. |
| **javascript-sandboxing-research** | Compared isolated-vm, vm2, QuickJS, Worker Threads, Deno. Found vm2 deprecated with 20+ CVEs. isolated-vm best for Node.js. |
| **quickjs-async-sandbox** | Built asyncio-friendly QuickJS sandbox in Python. Memory limits, wall-clock timeout, async Python→JS bridge via httpx. 3 critical gotchas documented. |
| **mquickjs-sandbox** | MicroQuickJS sandbox investigation. |
| **javascript-sandboxing** | Worker-threads-based sandboxing approach. |

#### SQLite (Highly Relevant)

| Project | What Was Investigated |
|---------|----------------------|
| **sqlite-query-linter** | Drop-in `sqlite3` wrapper with configurable linting rules. Detects invalid CAST, unsupported functions, SELECT *, missing WHERE, string quoting. Extensible API. |
| **sqlite-ripgrep-function** | Ripgrep as a SQL function. Python JSON version + C extension virtual table. Time limits, glob filtering. |
| **sqlite-permissions-poc** | Hierarchical permission system in pure SQL (CTEs + JSON). Child > parent > global precedence. DENY beats ALLOW. Token scoping via INTERSECT. |
| **absurd-in-sqlite** | Durable execution workflows using SQLite. Pull-based task queue with replay model. |
| **sqlite-hamming-extension** | Hamming distance as SQLite extension — scalar vs virtual table. |
| **sqlite-time-limit-extension** | Time limits for SQLite queries. |
| **sqlite-tags-benchmark** | Tag storage benchmarking. |
| **sqlite-wal-docker-containers** | WAL mode behavior in Docker containers. |
| **sqlite-wasm-library** | SQLite compiled to WASM. |

#### Datasette Ecosystem

| Project | What Was Investigated |
|---------|----------------------|
| **datasette-plugin-skill** | Comprehensive SKILL.md for writing Datasette plugins. Covers all hooks, testing, deployment. |
| **datasette-sql-permissions-review** | Architecture review of Datasette's SQL permissions system. Performance good but implementation complex. |
| **datasette-lite-js-init** | Problem: `innerHTML` doesn't execute JS. Solution: `datasette_init` event after content updates. |
| **datasette-lite-npm-package** | Self-hostable NPM package for Datasette Lite (~13KB). |
| **self-host-datasette-lite** | Offline bundle: 20-25 MB minimal, 350 MB full Pyodide. |

#### AI / Skills

| Project | What Was Investigated |
|---------|----------------------|
| **openai-api-skills** | OpenAI's Skills API: SKILL.md manifest + scripts. Demo with csv_insights_skill and greeter_skill. |
| **starlette-1-skill** | SKILL.md for Starlette 1.0: routing, middleware, WebSockets, auth, templates, testing. |
| **blog-tags-scikit-learn** | Multi-label text classification for blog tags. LinearSVC best (F1=0.68). |
| **deepseek-ocr-nvidia-spark** | Deployed DeepSeek-OCR on NVIDIA GB10 (ARM64 + CUDA 13.0). |

---

## 4. The Research Methodology

### 4.1 The Pattern

Every research project follows the same pattern:

```
1. Question → "Can SQLite be used for durable execution workflows?"
2. Investigation → Read code, build prototype, test
3. Notes → Track what was tried, what failed, what worked
4. Report → README.md with findings, code, key findings bullets
5. Code → Minimal working prototype or diff
```

### 4.2 AI-Assisted Research

Simon's workflow uses LLMs (Claude via the `llm` CLI tool) as:
- **Research assistant**: Read code, summarize findings, explain architectures
- **Code generator**: Write prototypes, tests, benchmarks
- **Report writer**: Generate README.md reports with AI-generated notes
- **Summary generator**: Auto-generate `_summary.md` descriptions

Every AI-generated report carries this notice:

```html
<!-- AI-GENERATED-NOTE -->
> [!NOTE]
> This is an AI-generated research report. All text and code in this report
> was created by an LLM (Large Language Model).
```

### 4.3 The SKILL.md Pattern

Skills are markdown files with YAML frontmatter that define structured workflows:

```markdown
---
name: starlette
description: Build async web applications with Starlette 1.0...
---

# Starlette 1.0
## Installation
pip install starlette
...
```

This is the **same pattern used by Dexter** (`SOUL.md` + `SKILL.md`). Simon's research on OpenAI Skills and Starlette skills directly influenced Dexter's skill system.

---

## 5. What This Means for Elephant Rock

### 5.1 This Is NOT a Competitor

simonw/research is a **methodology demonstration**, not a tool. It doesn't:
- Generate research proposals
- Score novelty
- Identify gaps
- Synthesize papers
- Run autonomous pipelines

It shows HOW a human+AI team conducts research investigations.

### 5.2 The Methodology IS the Value

The key insight is the **research journal pattern**:

1. **Every investigation is self-contained** — a folder with README, notes, and code
2. **Notes track the journey** — what was tried, what failed, what worked
3. **README is the deliverable** — a structured report with findings
4. **Code is minimal** — only what was built, not what was read
5. **AI writes the reports** — but human validates and curates
6. **Research compounds** — 88 projects over months create a knowledge base

### 5.3 Elephant Rock Should Adopt This Pattern

The "research journal" pattern should be applied to pipeline runs:

```
pipeline_run_2026-05-06/
├── README.md          # Auto-generated research report
├── notes.md           # Stage-by-stage notes
├── gaps.json          # Identified gaps
├── ideas.json         # Generated ideas with novelty scores
├── proposals/         # Generated proposals
└── artifacts/         # Supporting data
```

Each pipeline run becomes a research investigation in the simonw/research style.

### 5.4 Key Projects Worth Studying in Detail

For Elephant Rock specifically, these research projects contain relevant patterns:

| Project | Relevance | What to Study |
|---------|-----------|---------------|
| **sqlite-query-linter** | High | Configurable rule-based analysis — same pattern as proposal quality checks |
| **sqlite-permissions-poc** | High | Hierarchical rules with DENY > ALLOW — same as quality gates |
| **quickjs-async-sandbox** | High | Sandboxed code execution with memory/time limits — for experiment execution |
| **codex-sandbox-investigation** | Medium | How OpenAI sandboxes AI agents — security model for Elephant Rock |
| **absurd-in-sqlite** | Medium | Durable execution workflows — pipeline state management |
| **offline-notes-sync** | Medium | CRDT-based conflict resolution — for concurrent pipeline runs |
| **openai-api-skills** | Medium | SKILL.md manifest pattern — for defining pipeline skills |
| **starlette-1-skill** | Low | SKILL.md format reference |

---

## 6. Assessment

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Methodology** | 10/10 | Best-documented AI-assisted research methodology |
| **Breadth** | 9/10 | 88 projects across 10+ domains |
| **Depth** | 8/10 | Each project goes deep (notes + code + report) |
| **Documentation** | 9/10 | Every project has README + notes |
| **Reproducibility** | 7/10 | Code included but not always self-contained |
| **Relevance to ER** | 5/10 | Methodology is relevant, content is not |

---

## 7. Key Takeaways

1. **This is a methodology, not a tool** — Simon demonstrates how to use LLMs for research. The pattern is: question → investigate → note → report → archive.

2. **88 research projects in one repo** — The scale is impressive. Each project is small (a few files) but focused. This is how research should accumulate.

3. **The AGENTS.md pattern is Claude Code's convention** — `CLAUDE.md` and `AGENTS.md` are Claude Code's instruction files. This entire repo is structured for Claude-assisted research.

4. **AI-generated reports with honest labeling** — Every report carries an `AI-GENERATED-NOTE` badge. This is the honesty standard Elephant Rock should follow.

5. **The SKILL.md format originates here** — Simon's investigation of OpenAI Skills and his own Starlette skill demonstrate the pattern that Dexter adopted.

6. **Sandboxing is the most investigated topic** — 7 projects on JavaScript/WASM/OS sandboxing. This tells us sandboxed code execution is a hard problem that many researchers are tackling.

7. **SQLite is the second most investigated topic** — 15 projects on SQLite extensions, permissions, linting, durability. SQLite as a research tool backbone.

8. **The `notes.md` pattern is essential** — Tracking what was tried and failed is as important as what succeeded. Elephant Rock pipeline runs should produce similar stage-by-stage notes.

9. **Research compounds over time** — 88 small investigations create a knowledge base that no single tool could produce. This is the argument for Elephant Rock's "knowledge library" feature (from LDR).

10. **Position in the landscape**: simonw/research is the **gold standard for AI-assisted research documentation**. It's not a competitor to Elephant Rock — it's a **mentor**. The methodology should be adopted directly: every pipeline run produces a research journal entry with README, notes, and artifacts.
