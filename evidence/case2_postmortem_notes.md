# Case 2 Postmortem Notes — Clean-Room State Taxonomy

Owner direction (2026-08-15, frozen before the 2C outcome): the
clean-room procedure revealed three classes of state that were
previously conflated. This note records the evidence collected and is
input to the Case 3 preflight design. It does not mutate Case 2C.

## The three classes, as evidenced

### 1. Research state (must be fresh in a clean room)

What the charter actually isolates: no leftover Case-1 research
records feeding the new run.

Evidence: in every attempt the database, chroma store, checkpoints,
runs, and exports were re-created fresh; 2C's corpus (139 papers) and
ideas were produced within the attempt.

### 2. Required system operating state (must survive a clean room)

Without it the accepted runtime cannot function.

Evidence from 2B (FAIL): `data/model_certification/production_registry.yaml`
(read by `CertifiedCapabilityLookup`) and the served certified model
`qwen3-4b-2507` (LM Studio). Absence degraded every LLM stage to
empty responses — zero "No certified candidates" and zero "Empty LLM
response" in the Case-1 baseline log, both widespread in 2B. Restored
before 2C, which then matched the baseline signature.

Also in this class, from 2A (FAIL): the embedding provider endpoint
must be reachable — on a fresh database, ingestion hard-depends on it.
(On a pre-ingested corpus it is not load-bearing; that asymmetry is
what misled the 2A preflight.)

### 3. Optional / reconstructible / skippable runtime state

The system detects absence, degrades a subsystem, and the qualified
lifecycle still completes.

Evidence from 2C (ACCEPTED): the fresh database has no
`EmbeddingProfile` rows, so `build_governed_vector_runtime_from_settings`
returned None and knowledge indexing was skipped (single warning at
run start). The run then completed the full qualified lifecycle —
design, execution, 74 markers, synthesis, six gates after one bounded
repair, freeze, release, E==F==R==H — with zero empty responses after
the early query-generation burst.

Classification caveat, per the frozen rule: the EmbeddingProfile's
formal class is the owner's call. The 2C evidence supports "optional
for the qualified lifecycle" (it was absent in an accepted run); it
remains "required operating state" for any configuration that needs
knowledge indexing (semantic retrieval over the ingested corpus).
Case 3 preflight should probe it explicitly and record which class
the Case-3 lifecycle assigns it.

## Preflight consequences for Case 3

1. Hard gates must include functional probes of every class-2
   dependency: embedding call, certification lookup, certified-model
   completion.
2. The clean-room procedure must enumerate what it freshens
   (class 1) and what it preserves (class 2), and record any class-3
   absences as diagnostics before launch — not discover them mid-run.
3. `init_db()` creates zero tables unless `backend.db.models` is
   imported first (recorded in 2A/2B forensics; an invocation detail,
   not a code change).

## Observations recorded, deliberately not fixed mid-qualification

- Degraded model routing yields empty LLM responses fail-open (2B).
- A fully-empty pipeline still reports run status completed/succeeded
  despite the export Decision Gate aborting at 0.00 (2A, 2B).
- 19 early empty responses with certified routing (2C) — recovered
  fully; exact per-call cause unresolved without request-level logging.
