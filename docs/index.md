# Elephant Rock Research

**v0.1.0** — AI-powered research idea generation platform.

Elephant Rock automates the entire lifecycle of academic ideation — from literature
discovery and gap analysis through novel idea generation, feasibility scoring, and
structured proposal export.

---

## Features

- **Literature Search** — Discover papers from Semantic Scholar, arXiv, and OpenAlex
- **Gap Analysis** — Identify methodological, empirical, and theoretical research gaps
- **Idea Generation** — Generate novel research ideas with LLM-powered synthesis
- **Scoring Engine** — Score ideas on novelty, feasibility, and overall quality
- **Pipeline Automation** — 9-stage pipeline with progress streaming (SSE)
- **Cost Tracking** — Track token usage and costs per provider, model, and stage
- **Knowledge Base** — Semantic search over ingested PDF documents
- **Knowledge Graph** — Interactive entity-relationship graph for explored domains
- **Governance** — Human-in-the-loop approval for critical pipeline decisions
- **Observability** — Distributed tracing and metrics for all pipeline operations
- **Auth & RBAC** — JWT authentication with role-based access control
- **Collaboration** — Comments, sharing, and team workflows on research ideas
- **Export** — PDF and bulk ZIP export of ideas and proposals
- **Plugin System** — Extensible plugin architecture for custom integrations

---

## Quick Links

| Resource | Description |
|:---------|:------------|
| [Getting Started](getting-started.md) | Installation, configuration, and first run |
| [Architecture](architecture.md) | System design and pipeline stages |
| [API Reference](api-reference.md) | Complete REST API documentation |
| [Endpoints](endpoints/ideas.md) | Detailed endpoint documentation by route group |

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

!!! tip "What's next?"
    Read the [Getting Started](getting-started.md) guide for a complete walkthrough,
    or jump to the [API Reference](api-reference.md) to start integrating.
