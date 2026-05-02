# Getting Started

This guide walks you through installing, configuring, and running Elephant Rock
for the first time.

---

## Prerequisites

| Requirement | Version |
|:------------|:--------|
| Python | ≥ 3.11 |
| pip | latest |
| Git | any |
| LLM API Key | OpenAI, Anthropic, or other LiteLLM-supported provider |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/elephant-rock-platform/elephant-rock-platform.git
cd elephant-rock-platform
```

### 2. Install dependencies

```bash
# Install with all dev dependencies
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
# Interactive setup wizard — validates your API key
erock setup
```

This creates a `.env` file with your configuration. You can also copy the example
manually:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

#### Required environment variables

| Variable | Description |
|:---------|:------------|
| `OPENAI_API_KEY` | OpenAI API key (or your chosen provider) |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional, for Claude models) |

#### Optional environment variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `DEFAULT_PROVIDER` | `openai` | Default LLM provider |
| `MEMORY_ENABLED` | `true` | Enable/disable memory system |
| `GOVERNANCE_ENABLED` | `false` | Enable/disable governance approvals |
| `AUTONOMY_ENABLED` | `false` | Enable/disable autonomous research |
| `BUDGET_ENABLED` | `false` | Enable/disable budget tracking |

---

## Running the Platform

### Development mode (recommended)

Starts both the FastAPI backend and React frontend with live reload:

```bash
erock dev
```

- **Backend**: `http://localhost:8000`
- **Frontend**: `http://localhost:3000`
- **API Docs (Swagger)**: `http://localhost:8000/docs`
- **API Docs (ReDoc)**: `http://localhost:8000/redoc`

### Backend only

```bash
erock serve
# or directly:
uvicorn backend.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker compose up --build
```

---

## Your First Research Pipeline

### Using the CLI

```bash
erock generate --domain "AI/NLP" --rounds 2 --ideas 3
```

### Using the API

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "AI/NLP",
    "max_gaps": 5,
    "generation_rounds": 2,
    "ideas_per_round": 3,
    "run_novelty": true,
    "run_feasibility": true,
    "run_synthesis": true
  }'
```

The pipeline returns immediately with a `run_id`. Track progress via SSE:

```bash
curl -N "http://localhost:8000/api/v1/pipeline/runs/{run_id}/progress"
```

---

## Project Structure

```
elephant-rock-platform/
├── backend/
│   ├── api/              # FastAPI routes, schemas, auth
│   ├── config/           # Settings and configuration
│   ├── db/               # Database models and CRUD operations
│   ├── pipeline/         # 9-stage research pipeline
│   ├── plugins/          # Plugin system
│   └── providers/        # LLM provider abstraction
├── frontend/             # React UI
├── docs/                 # Documentation (this site)
├── alembic/              # Database migrations
├── mkdocs.yml            # MkDocs configuration
└── pyproject.toml        # Python project metadata
```

---

## Next Steps

- Read the [Architecture](architecture.md) page to understand the pipeline stages
- Explore the [API Reference](api-reference.md) for all available endpoints
- Check the [Endpoints](endpoints/ideas.md) section for detailed request/response examples
