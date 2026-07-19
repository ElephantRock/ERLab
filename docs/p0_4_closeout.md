# P0.4 Closeout — Embedding Governance Program

## 1. Original embedding defects

The codebase began with embedding behavior scattered across LLM chat
providers, side channels, and semantic caches with no governed boundary.

Key defects:
- `LLMProvider.embed()` existed on every chat provider
- Anthropic shimmed embeddings through OpenAI with ambient `OPENAI_API_KEY`
- No embedding profile registration or identity contract
- No capability verification or binding lifecycle
- Historical vectors had no provenance

## 2. P0.4-pre baseline repair

Reproducible baseline established. Frontend TypeScript baseline recorded
at `db4d499` (101 errors, separate track).

## 3. A0 — Embedding-surface audit

Identified all embedding paths. Classified every `embed()` reference.

## 4. B0 — Handshake-readiness architecture

Removed `LLMProvider.embed()` from all chat providers, wrappers, and
`StageContext`. Created `EffectiveEmbeddingConfiguration`, `GovernedVectorRuntime`,
`GovernedEmbeddingAdapter`, `SideChannelEmbeddingRuntime`. Canonical
validation in `embedding_validation.py`.

## 5. A1 — Capability ledger and verified runtime

Check-first lifecycle: pending → running → passed/failed. Immutable
bindings created only after successful dual probe. `VerifiedEmbeddingRuntime`
with per-operation authority validation. Fail-closed from A1.6.

## 6. A2 — Capability-bound vector lifecycle

Migrations 028+029 added capability columns to vector/retrieval tables
and created activation/cutover/guard tables. V2 vector identity with
binding-specific collections. Posture-aware retrieval. Atomic activation
via `BEGIN IMMEDIATE`. Write guard blocks all persistent writes during
cutover. Post-activation v1 writes permanently forbidden.

## 7. A3 — Operator and product integration

Unified lifecycle posture evaluator with 16 readiness phases and 17
blocker codes. `CapabilityLifecycleService` orchestrates all lifecycle
operations. CLI migrated to go through the service (no direct table
mutation). Evidence tracing reconstructs the complete query-to-source
chain. Controlled-provider E2E proof exercises the full lifecycle.

## 8. End-to-end evidence chain

```
retrieval event
→ query capability check
→ query capability binding
→ active activation
→ cutover
→ eligible-vector snapshot
→ returned vector index record
→ generation capability check
→ vector capability binding
→ canonical paper/chunk source
```

Evidence tracer fails closed on binding mismatches.

## 9. Failure and recovery evidence

5 recovery tests: failed probe, expired check, alias-only binding,
source drift, cutover abort. Each produces bounded codes and valid
next actions.

## 10. Production reachability seal

10 architectural seal tests across B0/A1/A2/A3 waves verify:
- No direct CLI table mutation
- Posture evaluator is side-effect-free
- Activation has no external I/O
- Controlled provider not production-selectable
- V1 writes blocked after activation
- Posture-aware retrieval wired into production
- Cache namespace supplied by production composition

## 11. Five-run backend seal

(Filled from actual results)

## 12. Skip accounting

25 skips across 7 groups (WeasyPrint, ChromaDB, LM Studio, Docker,
E2E env vars, live cert, known flake). All predate P0.4. None touch
P0.4 architecture. 0 unexplained.

## 13. External-provider execution status

```
live_provider_certifications: []
production_activation_performed: false
```

No real deployment profile has been cut over. The controlled-provider
proof exercises the complete lifecycle deterministically.

## 14. Known limitations

- Cache namespace uses embedding model name (interim); full capability
  binding namespace wiring is a future enhancement
- Frontend TypeScript baseline (101 errors) remains open
- No real provider certification has been executed

## 15. P0.5 entry posture

```
software_implementation_status: closed
controlled_provider_e2e_status: passed
manual_database_steps_required: 0
```

P0.5 should prove that every material configuration option has a
measurable effect on production behavior.
