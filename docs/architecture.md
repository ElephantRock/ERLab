# Architecture

Elephant Rock is built around a **9-stage pipeline** that transforms raw literature
into scored, cited research proposals.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Elephant Rock 9-Stage Pipeline                   │
│                                                                      │
│  1. Literature Search ──► Discover papers from Semantic Scholar,     │
│                            arXiv, and OpenAlex                        │
│                          │                                           │
│  2. Gap Detection     ──► Identify methodological, empirical, and    │
│                            theoretical gaps in the literature         │
│                          │                                           │
│  3. Idea Generation   ──► Generate novel research ideas targeting    │
│                            detected gaps                              │
│                          │                                           │
│  4. Novelty Check     ──► Verify ideas against existing literature   │
│                            to ensure originality                      │
│                          │                                           │
│  5. Feasibility Score ──► Assess practical feasibility of each idea  │
│                          │                                           │
│  6. Synthesis         ──► Combine top ideas into coherent proposals  │
│                          │                                           │
│  7. Evaluation        ──► Multi-dimensional scoring and ranking      │
│                          │                                           │
│  8. Reporting         ──► Generate structured reports and exports    │
│                          │                                           │
│  9. Memory Store      ──► Persist learnings for future runs          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|:------|:-----------|:--------|
| API | FastAPI | REST API with OpenAPI docs |
| Database | SQLite (SQLAlchemy) | Data persistence |
| Vector Store | ChromaDB | Semantic search / embeddings |
| LLM | LiteLLM | Multi-provider LLM abstraction |
| Frontend | React | Web UI |
| Migrations | Alembic | Database schema versioning |
| Auth | JWT (python-jose) | Authentication & RBAC |
| Observability | Custom tracing | Distributed traces & metrics |

---

## Backend Architecture

### API Layer (`backend/api/`)

The API layer is built with FastAPI and organized into route modules:

```
backend/api/
├── app.py              # FastAPI application factory
├── auth.py             # JWT authentication & password hashing
├── errors.py           # Standardized error handling
├── schemas.py          # Pydantic request/response schemas
└── routes/
    ├── auth.py         # Registration, login, user management
    ├── collaboration.py # Comments and sharing
    ├── costs.py        # Cost tracking endpoints
    ├── exports.py      # PDF and ZIP export
    ├── gaps.py         # Research gap endpoints
    ├── governance.py   # Human-in-the-loop approvals
    ├── ideas.py        # Research idea CRUD
    ├── knowledge.py    # Knowledge base management
    ├── knowledge_graph.py # Entity-relationship graph
    ├── literature.py   # Literature search and ingest
    ├── memory.py       # Agent memory system
    ├── pipeline.py     # Pipeline orchestration & sessions
    ├── plugins.py      # Plugin management
    └── traces.py       # Observability endpoints
```

### Pipeline Layer (`backend/pipeline/`)

Each pipeline stage is a self-contained module:

```
backend/pipeline/
├── orchestrator.py     # Pipeline execution engine
├── literature/         # Stage 1: Literature search
├── gaps/               # Stage 2: Gap detection
├── generation/         # Stage 3: Idea generation
├── novelty/            # Stage 4: Novelty checking
├── feasibility/        # Stage 5: Feasibility scoring
├── synthesis/          # Stage 6: Proposal synthesis
├── evaluation/         # Stage 7: Multi-dimensional scoring
├── reporting/          # Stage 8: Report generation
├── memory/             # Stage 9: Memory persistence
├── knowledge/          # Knowledge graph & retrieval
├── governance/         # Approval workflow
└── observability/      # Tracing & metrics
```

### Provider Layer (`backend/providers/`)

The provider layer abstracts LLM access through LiteLLM:

```
backend/providers/
├── provider_factory.py # Provider registry & factory
├── routing/            # Cost-aware model routing
└── task_router.py      # Task-specific model selection
```

---

## Data Flow

### Pipeline Execution

```
CLI / API Request
       │
       ▼
┌──────────────┐
│ Orchestrator  │  Creates run, dispatches async task
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Stage Runner  │  Executes stages sequentially
└──────┬───────┘
       │
       ├──► Literature Search (Semantic Scholar, arXiv, OpenAlex)
       ├──► Gap Detection (LLM-powered analysis)
       ├──► Idea Generation (LLM-powered synthesis)
       ├──► Novelty Check (embedding similarity)
       ├──► Feasibility Scoring (multi-criteria assessment)
       ├──► Synthesis (proposal generation)
       ├──► Evaluation (scoring & ranking)
       ├──► Reporting (structured output)
       └──► Memory Store (persist learnings)
              │
              ▼
        Database / SSE Stream
```

### Authentication Flow

```
POST /api/v1/auth/register → Creates user, returns JWT
POST /api/v1/auth/login    → Validates credentials, returns JWT
GET  /api/v1/auth/me       → Returns current user (requires JWT)
```

JWT tokens are passed via the `Authorization: Bearer <token>` header.
API key auth is also supported via the `X-API-Key` header.

---

## Database Schema

The platform uses SQLAlchemy ORM with Alembic migrations. Key models:

| Model | Description |
|:------|:------------|
| `PipelineRun` | Tracks pipeline execution state and metadata |
| `Idea` | Generated research ideas with scores |
| `Gap` | Detected research gaps |
| `User` | User accounts with role-based access |
| `Comment` | Collaboration comments on ideas |
| `CostEvent` | Token usage and cost records |
| `MemoryEntry` | Persisted agent memories |

---

## Configuration

Settings are managed via `pydantic-settings` and can be configured through
environment variables or `.env` file:

```python
from backend.config import get_settings

settings = get_settings()
# settings.default_provider, settings.memory_enabled, etc.
```

See [Getting Started](getting-started.md) for the full list of configuration options.
