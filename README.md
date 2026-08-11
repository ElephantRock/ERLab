# Elephant Rock Research

**v1.0.3** ![status](https://img.shields.io/badge/status-research/engineering%20release-blue) ![roadmap](https://img.shields.io/badge/roadmap-complete-brightgreen)

**Elephant Rock** (ERLab) is an AI-powered research platform that automates the entire lifecycle of academic research — from literature discovery and gap analysis through novel idea generation, feasibility scoring, structured proposal synthesis, **frozen empirical experiment execution**, and **evidence-bound paper composition** with citation and result provenance.

## What ERLab can do

- **Literature pipeline**: Search, ingest, cluster, and analyze research papers with full [SOURCE-N] provenance tracking
- **Idea generation**: Generate research gaps and novel ideas from the literature
- **Proposal synthesis**: Expand ideas into structured research proposals with adversarial review
- **Empirical experiments**: Execute frozen, checked-in analyses (logistic regression, linear regression, random forest) on registered datasets
- **Evidence-bound papers**: Compose papers where titles, methods facts, observed values, metric interpretations, and RESULT attributions are generated deterministically from persisted evidence — not by the LLM
- **Evaluation gates**: Provenance, scope, conclusion support, experiment alignment, and claim-to-RESULT semantic validation
- **Durable persistence**: Full evidence chain (experiment → metrics → RESULT markers → paper → evaluation) survives restart

> **Important:** ERLab is a research/engineering release, not validated autonomous science. Papers produced by ERLab have been reviewed by independent computational review (GPT-5.3 LLM), not human peer review. ERLab does not establish publication-ready scientific validity autonomously. Datasets (UCI Iris, Wine Quality, Concrete Strength) must be obtained separately — see [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

---

## 30-Second Quick Start

```bash
# 1. Install (Python ≥ 3.11 required)
pip install -e ".[dev]"

# 2. Configure — interactive wizard validates your API key
erock setup

# 3. Run the dev environment (backend :8000 + frontend :3000)
erock dev

# 4. Generate your first research ideas
erock generate --domain "AI/NLP" --rounds 2 --ideas 3
```

> **Tip:** `erock setup` creates your `.env` file and optionally runs a test pipeline.
> Use `erock dev` to start both the FastAPI backend and React frontend with live reload.

---

## Trust & Quality Layer

Elephant Rock produces research outputs that are traceable, verifiable, and reviewable:

- **Schema-Backed Provenance**: Every idea links to supporting papers via a junction table (`IdeaPaperLink`) with role tracking (supporting vs cited). References are resolved against the same-run paper corpus using DOI → arXiv → title match (Jaccard ≥ 0.8) → author-year cascade.
- **Quality Checks**: Each proposal section is checked for word count, citation markers, and structural completeness — deterministically, at read time, with no pipeline re-run needed.
- **Citation Integrity**: Shared surname extraction utility handles comma format, space format, Chinese family-name ordering, and `et al.` suffixes. The sanitizer and verifier use the same extraction logic.
- **Remediation UX**: Failing sections show inline hints with deterministic suggestions. The remediation banner provides click-to-jump navigation to failing sections.
- **Section Regeneration**: Users can trigger LLM-based section refinement with revision tracking (append-only). Every refinement is recorded with quality before/after snapshots, model receipts, and optimistic concurrency via content hashes.
- **Governance Decisions**: Append-only decisions (approved / denied / needs_changes) with reviewer identity from auth context. Unified audit timeline aggregates decisions, section revisions, and comments into a chronological feed.
- **Operational Dashboard**: Read-only observability at `/ops` — run health, model usage, source health, and quality trends with bounded time windows.

---

## Architecture

Elephant Rock runs a multi-stage research pipeline that transforms raw literature into evidence-bound proposals and papers. The current stage order (`backend/pipeline/orchestrator/_orchestrator.py::_STAGE_ORDER`) is:

```
literature_search   →   ingestion   →   trimmer
   →   gap_analysis   →   gap_reflection
   →   idea_generation   →   idea_reflection
   →   novelty_checking   →   feasibility_scoring   →   mechanical_metrics
   →   proposal_synthesis   →   adversarial_review   →   evaluation
   →   experiment_execution   (opt-in; spec-driven, no-op unless an
       experiment_spec_id is supplied — not run on literature-only cycles)
   →   paper_synthesis   →   citation_audit   →   proposal_deepening   →   export
```

What each stage does:

- **literature search** — discover papers from Semantic Scholar, arXiv, and OpenAlex
- **ingestion** — parse, chunk, and index full-text PDFs
- **trimmer** — paper reranking and truncation before analysis
- **gap analysis / reflection** — identify unsolved problems via multi-agent reasoning with clustering, then reflect
- **idea generation / reflection** — generate novel research ideas via a DAG of specialised agents, then reflect
- **novelty checking** — score ideas against the knowledge base (method, problem, domain transfer)
- **feasibility scoring** — assess data, compute, and method viability with counterfactual analysis
- **mechanical metrics** — deterministic engineering/scaling metrics alongside feasibility
- **proposal synthesis** — synthesize structured proposals with references and governance validation
- **adversarial review** — critique and stress-test proposals
- **evaluation** — provenance, scope, conclusion-support, and claim-to-RESULT semantic gates
- **experiment execution** — *optional*: execute frozen, checked-in analyses on registered datasets, only when a spec is supplied
- **paper synthesis** — compose evidence-bound papers with deterministic RESULT provenance
- **citation audit** — verify citation markers resolve against the same-run corpus
- **proposal deepening** — final elaboration pass on proposals
- **export** — output to Markdown or LaTeX

   ┌─────────────────┐   ┌──────────────┐   ┌───────────────────┐
   │  Tiered Memory   │   │  Governance  │   │  Cost Router &    │
   │  (Semantic +     │   │  Validator   │   │  Budget Manager   │
   │   Episodic +     │   │  & Audit Log │   │  (token tracking) │
   │   Procedural)    │   │              │   │                   │
   └─────────────────┘   └──────────────┘   └───────────────────┘

### Key Design Principles

- **Multi-Agent Architecture**: Ideas are generated and critiqued by specialised agents coordinated via a DAG executor, with configurable topologies.
- **Hybrid Knowledge Base**: Semantic (ChromaDB) + lexical (BM25) retrieval with Reciprocal Rank Fusion.
- **Tiered Memory**: The platform retains lessons across runs via semantic, episodic, and procedural memory tiers.
- **Governance Layer**: All outputs pass through a configurable validator with audit logging for responsible research automation.

### Provider & Cost Accounting (v1.0.3)

**Providers.** The OpenAI-compatible cloud path has been live-validated end-to-end. Anthropic, Gemini, Ollama, and LiteLLM now conform to the shared usage-attribution contract (`complete_with_usage` and `structured_output_with_usage` carry `stage` and `run_id`), but those additional providers have **not** all been live E2E validated for this release — conformance to the contract is verified by the provider-usage test suite, not by live calls.

**Cost accounting.** v1.0.3 provides:

- **run-isolated accounting** — ledger, summary, and aggregation views are scoped per `run_id`; a process-lived tracker cannot leak one run's events into another;
- **stage/run attribution** — every billable call carries the pipeline stage and run identity into its cost event;
- **structured-output accounting** — schema calls route through the usage-aware boundary so each structured request produces an authoritative token receipt;
- **explicit reconciliation posture** — persisted summaries carry one of `partial` (a known unaccounted provider call exists), `reconciled` (events captured, no known gap), or `no_events`.

Tool-call accounting (e.g. `complete_with_tools`) is **not** claimed by this release and remains an open improvement.

---

## Interfaces

### CLI (`erock`)

The CLI provides full access to every pipeline stage and utility:

| Command | Description |
|---|---|
| `erock setup` | Interactive setup wizard — configure provider, API key, and generate `.env` |
| `erock dev` | Start backend (port 8000) and frontend (port 3000) dev servers |
| `erock generate` | Run the full research pipeline (literature search → export) |
| `erock search <query>` | Search academic literature across Semantic Scholar, arXiv, OpenAlex |
| `erock ingest <file>` | Ingest a PDF into the knowledge base |
| `erock novelty-check <text>` | Check novelty of a research idea |
| `erock feasibility-score <text>` | Score feasibility of a research idea |
| `erock autonomous` | Run autonomous research cycles |
| `erock ideas` | List stored research ideas |
| `erock gaps` | List identified research gaps |
| `erock runs` | List pipeline run history |
| `erock knowledge search <query>` | Search the knowledge base |
| `erock status` | Show system status and configuration |
| `erock config` | Display key configuration settings |

All commands accept `--debug` for verbose tracebacks.

### Web UI

Start with `erock dev` and open **http://localhost:3000**. The React frontend provides a visual interface for running pipelines, browsing ideas, and exploring the knowledge base.

### REST API

The backend exposes a FastAPI server at **http://localhost:8000** with full Swagger docs at **http://localhost:8000/docs**.

**Key endpoints** (all under `/api/v1`, authenticated via `EROCK_API_KEY` if set):

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/pipeline/run` | Start a pipeline run |
| `GET` | `/api/v1/pipeline/runs` | List pipeline runs |
| `GET` | `/api/v1/pipeline/runs/detail/{id}` | Get run details |
| `POST` | `/api/v1/pipeline/resume/{id}` | Resume a paused run |
| `POST` | `/api/v1/pipeline/autonomous` | Start autonomous cycle |
| `GET` | `/api/v1/ideas` | List research ideas |
| `GET` | `/api/v1/ideas/{id}` | Get idea details with quality checks + provenance |
| `POST` | `/api/v1/ideas/{id}/feedback` | Submit idea feedback |
| `POST` | `/api/v1/ideas/{id}/refine` | Refine an idea |
| `POST` | `/api/v1/ideas/{id}/sections/{key}/refine` | Regenerate a proposal section |
| `POST` | `/api/v1/ideas/{id}/sections/{key}/restore` | Restore a previous section version |
| `GET` | `/api/v1/ideas/{id}/sections/{key}/revisions` | Section revision history |
| `POST` | `/api/v1/ideas/{id}/governance/decision` | Create governance decision |
| `GET` | `/api/v1/ideas/{id}/governance/decisions` | List governance decisions |
| `GET` | `/api/v1/ideas/{id}/governance/timeline` | Unified audit timeline |
| `GET` | `/api/v1/gaps` | List research gaps |
| `GET` | `/api/v1/knowledge/stats` | Knowledge base statistics |
| `POST` | `/api/v1/knowledge/search` | Search the knowledge base |
| `GET` | `/api/v1/status` | System status |
| `GET` | `/api/v1/ops/dashboard` | Operational dashboard metrics |
| `GET` | `/health` | Health check (unauthenticated) |

> See the full interactive API reference at `http://localhost:8000/docs` when the server is running.

---

## Configuration

All settings are managed via environment variables with the `EROCK_` prefix. Copy the included template and add your keys:

```bash
cp .env.example .env
# Or use the guided wizard:
erock setup
```

**Essential variables** (see `.env.example` for the full list):

| Variable | Default | Description |
|---|---|---|
| `EROCK_DEFAULT_PROVIDER` | `openai` | LLM provider (`openai`, `anthropic`, `gemini`, `ollama`) |
| `EROCK_OPENAI_API_KEY` | — | OpenAI API key |
| `EROCK_ANTHROPIC_API_KEY` | — | Anthropic API key |
| `EROCK_GEMINI_API_KEY` | — | Google Gemini API key |
| `EROCK_DATABASE_URL` | `sqlite:///./data/elephant_rock.db` | Database connection string |
| `EROCK_CHROMA_PERSIST_DIR` | `./data/chroma` | Vector store directory |
| `EROCK_GENERATION_ROUNDS` | `2` | Number of idea generation rounds |
| `EROCK_IDEAS_PER_ROUND` | `3` | Ideas produced per round |

> **Important:** Never commit real API keys. Use placeholder format like `sk-your-key-here` in examples.

Full configuration reference: [`backend/config.py`](backend/config.py) · [`.env.example`](.env.example)

---

## Contributing

Contributions are welcome. To get started:

1. **Fork** the repository and create a feature branch.
2. **Install** with dev dependencies: `pip install -e ".[dev]"`
3. **Run tests**: `pytest backend/tests` (backend) + `cd frontend && npx vitest run` (frontend). Run the v1.0.3 reconciliation suite with `pytest backend/tests/test_v103_release_reconciliation.py backend/tests/test_v103_structured_usage.py`.
4. **Lint**: `ruff check backend/`
5. **Type-check**: `mypy backend/`
6. **Submit** a pull request with a clear description of the change.

### Project Structure

```
elephant-rock-platform/
├── backend/
│   ├── api/            # FastAPI routes and middleware
│   ├── cli/            # Typer CLI commands
│   ├── config.py       # Central configuration (pydantic-settings)
│   ├── db/             # SQLAlchemy models and CRUD
│   ├── pipeline/       # research pipeline implementation
│   │   ├── literature/    # literature search + ingestion
│   │   ├── knowledge/     # vector store + knowledge graph
│   │   ├── gap_analysis/  # gap identification + reflection
│   │   ├── generation/    # multi-agent idea generation + reflection
│   │   ├── novelty/       # novelty checking
│   │   ├── feasibility/   # feasibility scoring + mechanical metrics
│   │   ├── synthesis/     # proposal synthesis + adversarial review
│   │   ├── evaluation/    # evaluation gates (incl. paper synthesis + citation audit)
│   │   ├── experiment/    # opt-in frozen experiment execution
│   │   └── export/        # export (Markdown/LaTeX)
│   ├── providers/      # LLM provider abstraction (LiteLLM)
│   └── tests/          # Test suite
├── frontend/           # React + TypeScript web UI
├── docs/               # Documentation and AIV batch records
├── pyproject.toml      # Project metadata and build config
└── .env.example        # Configuration template
```

---

## License

MIT
