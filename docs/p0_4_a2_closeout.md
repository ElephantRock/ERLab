# P0.4A2 Closeout — Capability-Bound Vector Lifecycle and Cutover

## 1. Scope

**Wave:** P0.4A2 — capability-bound vector lifecycle and cutover
**Entry commit:** `334b962` (P0.4A1 closeout)
**Final executable commit:** `c1bccb2`

Mission: transition from verified embedding operations to verified
semantic-space ownership — every persistent vector identifies its
capability binding; retrieval uses only same-binding vectors.

## 2. Commit chain

```
c1bccb2 test: seal P0.4A2 capability-bound vector lifecycle
b13ee3e feat: bind side-channel namespaces and add cutover commands
82b5c01 feat: snapshot and regenerate capability cutovers and atomically activate
988c0be feat: index candidate and active binding vectors
80ac6a5 feat: enforce capability-bound scoped retrieval
123e320 feat: add capability-bound vector and collection identities
3a6806f feat: add capability-aware vector and retrieval schema
```

## 3. Architecture

```
VerifiedEmbeddingRuntime
    ├── embed_documents_authorized → AuthorizedEmbeddingBatch
    │       ↓
    │   CapabilityBoundIndexer → VectorIndexRecord v2
    │   (binding_id + generation_check_id)
    │
    └── embed_query_authorized → AuthorizedQueryEmbedding
            ↓
        RetrievalBindingContext
            ↓
        Active binding resolver
            ↓
        Binding-specific collection (binding-equal eligibility)
```

## 4. Migrations

- **028**: capability columns on vector_index_records + vector_retrieval_events
- **029**: activation, cutover, cutover_items, write_guards tables

## 5. Exclusions verified

- No historical vector binding backfill
- No vector_index_v2 production eligibility without activation
- No pre-capability fallback after activation
- No cross-binding cache hits
- No external I/O inside activation transaction

## 6. Five-run gate

(Filled from actual results — see JSON)

## 7. Roadmap

```
P0.4B0   CLOSED
P0.4A1   CLOSED
P0.4A2   CLOSED
P0.4A3   READY — final operator/product integration and end-to-end seal
P0.5     BLOCKED pending complete P0.4
Frontend OPEN
```
