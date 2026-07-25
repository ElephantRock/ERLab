# Phase 3 — Live-Environment Preflight (3B)

> **Status: ALL PASS.** Phase 3 proceeded to live execution.

## Authorization (frozen before execution)

| Field | Value |
|---|---|
| Provider/model | **z.ai glm-4.6** (`openai_base_url=https://api.z.ai/api/coding/paas/v4`, `openai_model=glm-4.6`) — current production |
| Hard spend cap | **$100.00** total across all three runs (user-authorized; budget guard enabled via `EROCK_BUDGET_ENABLED=true EROCK_BUDGET_MAX_COST_USD=100.0`) |
| Baseline commit | `6feba96c49483bf83de6dde622d12e1287071380` |
| Branch | `feat/quarantine-and-frontend-redesign` |
| Working tree at preflight | clean |

## Preflight checks

| Dependency | Result | Evidence |
|---|---|---|
| Database reachable | **PASS** | `get_session()` succeeds; `SELECT max(version_num) FROM alembic_version` = `032` |
| Migration current (032 source_reviews) | **PASS** | `alembic current` → `032 (head)` |
| External LLM provider authenticated | **PASS** | `create_provider()` → `ResilientProvider`; `complete(messages=[…])` returned a reply (z.ai glm-4.6 via `.env` key) |
| Crossref reachable | **PASS** | `GET api.crossref.org/works?query=test&rows=1` → 200 |
| PubMed reachable | **PASS** | `GET eutils.ncbi.nlm.nih.gov/…esearch.fcgi` → 200 |
| arXiv reachable | **PASS** | `GET export.arxiv.org/api/query` → 301 (normal API redirect) |
| Embedding service reachable | **PASS** (on recheck) | `POST http://100.64.0.2:1234/v1/embeddings` model=`text-embedding-bge-m3` → 1024-dim non-zero vector. Initial check failed (models still loading onto LM Studio); recheck after operator prompt confirmed all models loaded and serving. |
| Budget guard active | **PASS** | Backend started with `EROCK_BUDGET_ENABLED=true`, `budget_max_cost_usd=100.0`; `/api/v1/status/` confirms `budget_enabled: true` |
| Backend running | **PASS** | `localhost:8000` serving; `/api/v1/status/` → 200 |
| Frontend running | **PASS** | `localhost:3000` serving; `/` → 200 |

## Embedding service note

The initial preflight (two attempts) reported the embedding service unreachable. On operator prompt to recheck, the service was up with 21 models loaded — the initial failure was the LM Studio server still loading models onto `100.64.0.2`, not a persistent outage. The configured model `text-embedding-bge-m3` now responds with 1024-dim vectors matching `embedding_dimension: 1024`. No config change was needed.

## Execution environment record

| Field | Value |
|---|---|
| Baseline commit | `6feba96c49483bf83de6dde622d12e1287071380` |
| Provider/model | z.ai glm-4.6 (OpenAI-compatible endpoint) |
| Embedding model | `text-embedding-bge-m3` (LM Studio, 1024-dim) |
| Literature sources | Crossref, PubMed, arXiv (enabled); Semantic Scholar, OpenAlex (configured) |
| Budget limit | $100.00 (guard active) |
| Migration version | 032 |
| Start timestamp | 2026-07-25T12:25:42Z (Run A submitted) |

---

*Preflight complete. All dependencies green. Run A in progress.*

