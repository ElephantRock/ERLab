# P0.4 — Embedding Capability Handshake (Revised Entry Contract)

> **Status:** APPROVED WITH MINOR AMENDMENT at the architectural level.
> Implementation remains BLOCKED pending the preconditions in §1.
> The §16 dispositions are frozen in this document (no longer deferred to P0.4A0).

This document is the **entry contract** for P0.4. It is binding: implementation
may begin only after every precondition in §1 is satisfied and every correction
in §§3–10 is reflected in the implementing waves. The decisions in §16 are
frozen here — P0.4A0 verifies their implementation surface, it does not choose
their architectural disposition.

The original P0.4 draft was reviewed against the repository at `90d2ebb`
(P0.3.6 head, clean tree). Its invariants are sound, but its repository fit is
incomplete. This document records the corrections and freezes the corrected
behavior.

## Corrected status

```text
P0.3 implementation       CLOSED, subject to baseline repair
P0.4 specification        APPROVED WITH MINOR AMENDMENT (this document)
P0.4 implementation       BLOCKED on §1 preconditions
P0.4-pre baseline repair  READY
P0.4A0 expanded audit     follows successful baseline
P0.4B0                    blocked pending A0 inventory
Frontend regression       OPEN — 101 TypeScript errors (unchanged, not in scope)
```

## Approval posture

```text
Architectural direction     sound
Completion invariant        strong
Repository fit              incomplete (this document closes the gaps)
Implementation readiness    no — blocked on §1
```

P0.4 becomes implementation-ready only after:

```text
reproducible backend baseline established
embedding audit covers both provider surfaces
side-channel collection policy decided
provider identity-capture feasibility proven
GovernedVectorRuntime migration explicitly specified
version axes resolved
lease recovery frozen
SQLite activation serialization frozen
```

---

# 1. Mandatory preconditions

These three preconditions must be satisfied and recorded before any P0.4A1/B0
work is merged. They are not editorial; each one unblocks a downstream wave.

## 1.1 Repair and seal the regression baseline

The original P0.4 draft asserted a "285 passing" canonical baseline. That count
is **not reproducible** on the current head. A committed syntax error prevents
pytest from collecting five modules under `backend/tests/test_api/`.

Confirmed failure at `90d2ebb` (clean tree):

```text
$ python -m pytest backend/tests --tb=no -q
ERROR backend/tests/test_api/test_error_standardization.py
ERROR backend/tests/test_api/test_knowledge_graph.py
ERROR backend/tests/test_api/test_knowledge_ingest.py
ERROR backend/tests/test_api/test_literature.py
ERROR backend/tests/test_api/test_route_annotation.py
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!
5 errors in 27.01s
```

Root cause, `backend/api/routes/knowledge.py:256-261`:

```python
outcome = await query_vectors(
    session_factory=runtime.session_factory,
    backend=runtime.backend,   # line 258
    backend=backend,           # line 259  ← SyntaxError: keyword argument repeated
    request=request,
)
```

This is a hard `SyntaxError`. Any test module that imports `backend.api.app`
fails to collect. The P0.3.5 closeout (`docs/p0_3_5_legacy_reindex_closeout.md`)
records the canonical gate as **271 passed** over an explicit file list — that
narrower gate sidesteps the import chain through `backend.api.app` and is
internally consistent. The original P0.4 draft's broader "285 passing" figure is
neither file-scoped nor currently reproducible.

### Required action

Fix the duplicate `backend=` argument in `knowledge.py`, then run and record:

```text
python -m pytest backend/tests
```

The revised specification, before P0.4 implementation begins, must state:

```text
exact commit at which the baseline was recorded
exact command used
number of tests collected
number passing
number skipped or deselected, with reasons
whether adapter retry suites are included
```

P0.4 must not inherit an asserted count from a narrower targeted gate while
describing it as the whole backend baseline. The baseline is established at the
moment `knowledge.py:259` is repaired and the full `backend/tests` invocation is
captured end-to-end.

## 1.2 Expand the embedding audit boundary

The original §2 audit taxonomy was framed around the `EmbeddingProvider` ABC.
The repository has **three** classes of embedding operation, not one:

```text
EmbeddingProvider implementations        (embedding_providers.py hierarchy)
LLMProvider.embed() and its wrappers     (every chat provider + cache/gateway/resilience proxies)
side-channel vector collections          (kg_entity_embeddings, tool_embeddings, llm_cache)
```

### Revised taxonomy

```text
governed_paper_embedding                  — produces vectors written to vector_index_records
governed_query_embedding                  — produces query vectors for scoped retrieval
side_channel_persistent_embedding         — writes to governed/allowlisted non-paper collections
ephemeral_or_rebuildable_cache_embedding  — provider embeddings used transiently (e.g. cache key); discardable on binding change
legacy_embedding                          — used only by legacy P0.3.5 migration paths
provider_wrapper                          — embedding proxy or wrapper around an underlying provider
dead_embedding_surface                    — never instantiated in production
confirmed_non_embedding_model             — model that returns relevance scores only, no reusable vectors (e.g. scoring cross-encoder); out of P0.4 scope
```

`kg_entity_embeddings`, `tool_embeddings`, and `llm_cache` cannot remain
silently capability-ungoverned while being described as governed collections.
Their dispositions are **frozen in §16** of this contract (INCLUDED,
INCLUDED, and capability-gated-without-cutover respectively). P0.4A0 verifies
the implementation surface that realizes each disposition; it does not choose
the architectural posture.

A scoring-only reranker is not an embedding surface. Reranker classification
is frozen in §16.7.

## 1.3 Add P0.4B0 before the handshake schema becomes actionable

A new prerequisite sub-wave is required before the binding/check/activation
schema of the original §4 can produce a real activation-eligible binding:

```text
P0.4B0 — Provider identity capture and embedding-surface consolidation
```

P0.4B0 must cover:

```text
response-model / deployment identity capture in every embedding adapter
provider-specific resolution posture (exact_revision | stable_deployment | alias_only)
adapter contract-version increment
consolidation of the three private _EmbeddingAdapter implementations
resolution or removal of LLMProvider.embed()
extraction of vector schema literals into shared constants
```

### Critical refinement on identity capture

Capturing the provider's returned `model` field is necessary, but it does not
automatically make the identity stable. A returned model name may still be a
mutable alias. Each provider adapter must explicitly classify the evidence as:

```text
exact_revision      — immutable provider model revision, artifact hash, or version id
stable_deployment   — deployment identity contractually pinned to a stable model version
alias_only          — mutable alias only, no stable revision or deployment identity
```

No adapter may upgrade an alias to a stable identity merely because the provider
echoed the requested model name. The posture classification is a per-adapter
responsibility, not a generic inference.

### Why this is a precondition, not a normal wave

Every provider today is functionally `alias_only`:

```text
OpenAIEmbeddingProvider   discards the response.model field
LMStudioEmbeddingProvider uses /v1/models once at orchestrator init; result discarded
OllamaEmbeddingProvider   does not read the model field
GeminiEmbeddingProvider   does not surface model identity
```

Under the original §3 rule, `alias_only` bindings cannot be activated. Without
P0.4B0, P0.4D–E (cutover and activation) are unreachable. The schema may be
designed before B0 is implemented, but B0 must be proven before claiming that
any real provider can produce an activation-eligible binding.

---

# 2. Scope and invariants (unchanged from original)

The governing invariant is:

> Every governed embedding operation must be authorized by a current capability
> check against the actual configured runtime. Every generated vector must
> identify the stable resolved capability that produced it. Retrieval may rank
> only vectors generated by the same active capability binding as the query
> vector.

Load-bearing distinctions (unchanged from original §1):

```text
EmbeddingProfile              declared contract — what ERLab expects
EmbeddingCapabilityBinding    stable semantic-space identity — what is actually running
EmbeddingCapabilityCheck      expiring runtime-health evidence — timestamped probe result
```

A binding is stable across repeated health checks of the same capability. A
check can expire without invalidating vectors already generated under the same
binding. Expiration blocks **new embedding operations**, not historical vector
identity.

---

# 3. `GovernedVectorRuntime` — breaking migration

The original §16 described `GovernedVectorRuntime` as if it were a new
addition. It is not. It exists and is heavily used. The migration must be
explicit.

## 3.1 Current shape (committed at `90d2ebb`)

`backend/pipeline/vector_runtime.py:18-32`:

```python
@dataclass(frozen=True)
class GovernedVectorRuntime:
    backend: Any
    embedding_provider: Any           # raw provider escapes here
    embedding_profile_id: str
    profile_dict: dict[str, Any]      # untyped profile snapshot
    session_factory: Any
    db_engine: Any
```

## 3.2 Required transitional shape

```python
@dataclass(frozen=True)
class GovernedVectorRuntime:
    backend: GovernedVectorBackend
    session_factory: SessionFactory
    db_engine: Engine

    embedding_profile_id: str
    profile: EmbeddingProfileSnapshot     # typed, not dict[str, Any]

    capability_service: EmbeddingCapabilityService
    indexer: VectorIndexer
    retrieval_service: ScopedVectorService
```

It must not contain:

```text
raw embedding_provider
untyped profile_dict
```

`EmbeddingProfileSnapshot` is a typed, frozen projection of the profile fields
the runtime actually needs. It is not the ORM model — it is a contract surface
that survives the runtime's lifetime.

## 3.3 Caller migration list (exhaustive)

The following callers must be migrated in the same wave. Each currently reads
one of the dropped fields:

```text
backend/pipeline/stages.py              IngestionStage (lines 628, 634)
backend/pipeline/novelty/novelty_checker.py   _retrieve_governed (lines 148-149)
backend/api/routes/knowledge.py          /search/governed (lines 215, 217, 256-261)
backend/cli/legacy_vector_cli.py         erlab vectors reindex-legacy (lines 39, 284)
backend/pipeline/vector_runtime.py       build_governed_vector_runtime_from_settings (line 88)
```

The migration is part of P0.4C, not optional cleanup. Any caller left
un-migrated will silently bypass capability verification, which is exactly
what §10.2 of the original draft forbids.

---

# 4. Settings/profile reconciliation

The original draft treated `EmbeddingProfile` as the source of truth for
runtime embedding configuration. The repository does not work that way:

```text
backend/config.py:62-64        Settings.embedding_provider, .embedding_model, .embedding_dimension
backend/db/models.py:1270-1296 EmbeddingProfile (provider, model_identifier, dimension, ...)
```

The DB profile is a registration ledger populated at indexing time from
whatever `Settings` happened to be. It is not runtime truth. Treating it as
runtime truth would let drift between `Settings` and the profile go unnoticed.

## 4.1 Canonical reconciliation operation

The revised specification must define exactly one operation:

```text
effective Settings embedding configuration
+ registered EmbeddingProfile declaration
→ exact agreement check
→ runtime configuration fingerprint
```

## 4.2 Required drift behavior

```text
settings provider/model/dimension disagree with profile
→ handshake fails with configuration drift or profile mismatch
→ no provider probe authorizes governed work
```

The database profile must not be treated as runtime truth when the application
is actually configured elsewhere. The handshake verifies the *effective*
configuration (from `Settings`), and the profile is the *declared* expectation.
Disagreement is a hard failure category `configuration`.

## 4.3 Runtime configuration fingerprint inputs

The fingerprint is computed over the effective configuration, not the declared
profile alone:

```text
provider kind
sanitized endpoint identity
requested model
document task
query task
declared output dimension
normalization setting
application post-processing contract
adapter contract version
retry-policy version
```

Secrets, credentials, tokens, query strings, and volatile process details are
excluded. A passed check authorizes work only when:

```text
current runtime_config_fingerprint = check.runtime_config_fingerprint
```

Changed configuration requires a new handshake.

---

# 5. Two version axes

The original draft left the relationship between `index_schema_version` and
`embedding_contract_version` ambiguous. This section freezes them.

## 5.1 Definitions

```text
index_schema_version
  governs vector identity, registry lifecycle,
  backend collection layout and collection metadata.

embedding_contract_version
  governs capability provenance and the authorization
  under which the embedding was generated.
```

These are orthogonal axes on the same row, not aliases.

## 5.2 Allowed combinations (frozen)

```text
vector_index_v1 + pre_capability_v0
  historical P0.3 record.
  binding_id NULL, generation_capability_check_id NULL.
  ineligible for capability_v1 retrieval after activation.

vector_index_v2 + capability_v1
  P0.4 binding-specific record.
  binding_id NOT NULL, generation_capability_check_id NOT NULL.
  the only posture eligible for governed retrieval after activation.
```

## 5.3 Disallowed combinations

```text
vector_index_v1 + capability_v1
vector_index_v2 + pre_capability_v0
```

Both are forbidden by CHECK constraints at the `vector_index_records` level and
also enforced in application validation as a second boundary.

## 5.4 Transitional sequencing

Governed document generation must **not** be switched to the verified runtime
until the v2 record contract is available. Query-only probing may occur
earlier (it produces no persistent vector), but no intermediate persistent
vector posture may be created. Specifically:

```text
P0.4C2 (require verified runtime at governed call sites)
must land together with, or after,
P0.4D1 (vector identity v2 and binding-specific collections)
```

This closes the gap in the original §22 sequence, which placed C2 before D1
without describing the transitional contract version that would result.

---

# 6. Schema constants (extracted before v2)

A pure refactor must land before P0.4D adds any v2 branching. The current
`"vector_index_v1"` literal is scattered across at least six sites with no
shared symbol:

```text
backend/pipeline/vector_contracts.py:249   (id payload)
backend/pipeline/vector_indexer.py:108     (profile registration)
backend/pipeline/vector_indexer.py:171     (collection metadata write)
backend/pipeline/vector_indexer.py:197     (collection metadata verify)
backend/pipeline/vector_backend.py:67      (collection metadata key)
backend/db/models.py:1316                  (CHECK constraint)
backend/pipeline/scoped_vector_service.py:139 (retrieval filter)
```

## 6.1 Required constants

```python
VECTOR_INDEX_V1 = "vector_index_v1"
VECTOR_INDEX_V2 = "vector_index_v2"

EMBEDDING_CONTRACT_PRE_CAPABILITY_V0 = "pre_capability_v0"
EMBEDDING_CONTRACT_CAPABILITY_V1     = "capability_v1"
```

All scattered literals are replaced by these constants before any v2 branching
logic is added. This is a no-behavior-change refactor committed independently.

## 6.2 Schema-version discipline

Every domain table continues to carry a `<domain>_schema_version` column
CHECK-pinned to exactly one value, matching the convention established in
migrations `017`, `021`, `022`, `024`. The new tables introduced by P0.4
(`embedding_capability_bindings`, `embedding_capability_checks`,
`embedding_profile_binding_activations`, and later
`embedding_binding_cutovers`, `embedding_binding_cutover_items`) follow the same
pattern: a `binding_schema_version` / `check_schema_version` /
`activation_schema_version` / `cutover_schema_version` column with a CHECK
constraint.

---

# 7. Lease behavior (frozen)

The original §4.4/§4.5 left open whether stale-check recovery is automatic or
manual. This section picks one model.

## 7.1 Chosen model

```text
automatic stale-check recovery: ENABLED (default)
```

Operation:

```text
running check with valid lease
→ second worker rejected
→ EmbeddingCapabilityCheckAlreadyRunning

running check with expired lease
→ one worker atomically marks it abandoned
→ the same worker creates the replacement check
→ the replacement becomes the single running check
```

The `abandon-stale-check` CLI command from §17 remains in the surface, but as
an **administrative repair tool**, not the normal recovery path. The default
behavior does not require operator intervention.

## 7.2 Atomicity

The uniqueness rule and the abandoned transition must occur under **one
serialized database operation** so two workers cannot both replace the same
expired check. The implementation pattern must guarantee:

```text
claim is atomic          (no two workers observe the same expired lease as claimable)
transition is monotonic  (running → abandoned is a one-way state)
replacement is single    (exactly one new running check per replaced lease)
```

## 7.3 SQLite compatibility

`SELECT ... FOR UPDATE` is not used. Recovery is expressed as a conditional
`UPDATE ... WHERE status = 'running' AND lease_expires_at < :now` that returns
the affected row count; the worker that gets `rowcount = 1` is the claimant.
Any worker that gets `rowcount = 0` either observes an already-abandoned check
or a still-valid lease, and re-enters the normal lookup path.

## 7.4 Truthful failure classification

Cancellation must leave the check truthfully `running`. An interrupted row is
**not** mutated to `failed` unless a known provider or validation failure was
actually observed. Only lease expiry (§7.1) or an explicit operator action
(§17 `abandon-stale-check`) transitions a `running` check to `abandoned`.

---

# 8. SQLite-compatible activation serialization

The original §14.6 specified an 11-step activation transaction that locked
multiple rows. Row-level `FOR UPDATE` is not available on SQLite (the project
default DB). P0.4 correctness must not depend on Postgres semantics unless
Postgres becomes an explicit deployment prerequisite.

## 8.1 Activation guard row

For SQLite-compatible activation, use a durable single-row activation guard and
an early write transaction:

```text
BEGIN IMMEDIATE
→ atomically claim profile activation guard
→ verify cutover and registry evidence
→ publish activation
→ commit
```

There is **one activation-guard row per embedding profile**. Claiming it is the
serialization point; everything after the claim runs under that guard.

## 8.2 Required protections

```text
one activation-guard row per embedding profile
conditional status transitions (CHECK-constrained state machine)
unique active-binding constraint (partial unique index — see §8.3)
source-snapshot fingerprint revalidation inside the transaction
no provider or backend I/O inside the activation transaction
bounded transaction duration
retry on database-busy errors
```

## 8.3 Partial unique indexes

P0.4 introduces the codebase's first use of partial unique indexes:

```text
UNIQUE (embedding_profile_id) WHERE status = 'active'   — on embedding_profile_binding_activations
UNIQUE (embedding_profile_id, runtime_config_fingerprint, probe_suite_version)
    WHERE status = 'running'                             — on embedding_capability_checks
```

Both SQLite (3.8+, via `CREATE UNIQUE INDEX ... WHERE`) and PostgreSQL support
partial unique indexes. SQLAlchemy's `Index(..., unique=True,
sqlite_where=..., postgresql_where=...)` form is used so both dialects enforce
the same constraint.

The activation-guard row pattern (§8.1) is the primary serialization mechanism;
the partial unique index is a defense-in-depth backstop, not the primary lock.

## 8.4 Postgres posture

PostgreSQL may later use row locks for finer-grained concurrency, but P0.4
correctness must not depend on them. The SQLite-compatible path is the
canonical implementation.

---

# 9. Binding immutability

Capability bindings are **immutable** after creation.

## 9.1 Canonical rule

```text
persistent_activation_eligible
=
derived at binding creation
persisted at binding creation
never recomputed by consumers
```

All consumers check the persisted field. They do **not** independently rederive
eligibility from `model_resolution_posture`.

## 9.2 Handling later evidence

If later evidence changes the resolution posture (e.g. a deployment that was
believed to be `stable_deployment` is found to be `alias_only`), create a **new
binding** with the corrected posture. Do not mutate the historical binding.

## 9.3 Consequence

A binding's identity (the deterministic SHA-256 over canonical JSON) covers the
posture at creation time. Two bindings that differ only in posture are
distinct bindings with distinct identities, distinct collections, and distinct
vector spaces — exactly as if the underlying model differed.

---

# 10. Activation and cutover linkage

The original §4.6 was ambiguous about whether a binding could exist without a
cutover. This section resolves it.

## 10.1 Allowed lifecycle

```text
binding discovered
→ capability check passed
→ candidate binding registered (no cutover required at this point)

cutover created
→ snapshot taken
→ reindexing
→ verifying
→ ready

activation transaction
→ active
```

## 10.2 Nullability rule

```text
embedding_profile_binding_activations.cutover_id
  nullable  when status = 'candidate'
  NOT NULL  when status = 'active'
```

Enforced by a CHECK constraint on `(status, cutover_id)` co-nullability,
matching the convention used by `GlobalLibraryMembership` (status / removed_at)
in migration `021`.

## 10.3 Pre-cutover state

A binding may exist as `candidate` indefinitely without a cutover. This is the
normal state during initial capability exploration — `alias_only` and
`stable_deployment` bindings alike may sit at `candidate` while an operator
decides whether to remediate and activate.

Activation is the only transition that **requires** a linked, ready cutover.

---

# 11. Revised implementation sequence

The original §22 sequence is revised. Two new prerequisite waves (P0.4-pre and
P0.4A0) are added, P0.4B0 is added, and the original waves are renumbered
where their dependencies shift.

```text
P0.4-pre   Repair syntax error and establish reproducible baseline
           (fix knowledge.py:259; capture full backend/tests run)
           Exit gate: committed fix + recorded baseline in docs

P0.4A0     Expanded embedding access audit
           - EmbeddingProvider implementations
           - LLMProvider.embed and its wrappers/proxies (per 16.4, surface to be removed)
           - side-channel collections (kg_entity_embeddings, tool_embeddings, llm_cache)
             with dispositions already frozen in 16.1-16.3
           - private _EmbeddingAdapter implementations (three sites)
           - runtime configuration sources (Settings vs EmbeddingProfile)
           - reranker / cross-encoder models (classified per 16.7)
           Exit gate: docs/p0_4_embedding_access_audit.md committed,
                       every 16 disposition verified against the actual code surface,
                       every surface mapped to a terminal runtime-enforced classification

P0.4B0     Provider identity capture and embedding-surface consolidation
           - adapter response capture (OpenAI/LMStudio/Ollama/Gemini)
           - per-adapter resolution posture (exact_revision|stable_deployment|alias_only)
           - consolidation of three private _EmbeddingAdapter copies into one
           - LLMProvider.embed decision (delete or formally allowlist)
           - extraction of VECTOR_INDEX_V1 / VECTOR_INDEX_V2 / contract constants
           - adapter contract-version increment
           Exit gate: at least one real adapter returns stable_deployment or
                       exact_revision (proving activation eligibility is reachable)

P0.4A1     Binding / check / activation schema (Alembic revision 027)
           - embedding_capability_bindings
           - embedding_capability_checks
           - embedding_profile_binding_activations
           - partial unique indexes (§8.3)
           - state-machine CHECK constraints
           Exit gate: migration green, ORM models committed

P0.4A2     Runtime/profile agreement contract (§4)
           - effective Settings vs EmbeddingProfile reconciliation
           - runtime configuration fingerprint
           - drift detection and failure category configuration
           Exit gate: handshake fails closed on drift

P0.4B1     Capability probes and request accounting
           - probe suite v1 (original §7)
           - request observer (outbound request count, original §6.2)
           - output validation (original §8)
           - failure taxonomy (original §9 + §12 of this contract)
           Exit gate: probes exercise the real adapter path

P0.4C      VerifiedEmbeddingRuntime token
           - breaking migration of GovernedVectorRuntime (§3)
           - all five caller sites migrated in same wave
           - raw-provider prohibition at governed boundaries
           Exit gate: architectural test for raw-provider escape passes

P0.4D      Vector identity v2 and retrieval binding
           - vector_index_v2 record contract (lands with or before C2 if sequenced together)
           - binding-specific collections (erlab_vectors_v2_<binding-prefix>)
           - capability evidence on index records and retrieval events
           - active-binding scoped retrieval
           Exit gate: cross-binding retrieval impossible

P0.4E      Remediation and SQLite-safe activation
           - cutover ledger (embedding_binding_cutovers, embedding_binding_cutover_items, rev 028)
           - canonical pre-capability vector regeneration
           - source-snapshot immutability and drift detection
           - activation transaction under BEGIN IMMEDIATE + activation guard (§8)
           Exit gate: activation atomic under concurrent simulated workers

P0.4F      CLI, production adversarial proof, and closeout
           - operator CLI (§17 of original draft, reconciled with existing erlab vectors)
           - production adversarial tests (§19, §20 of original draft)
           - architectural seal (§18 of original draft)
           - docs/p0_4_embedding_capability_closeout.md
           Exit gate: §13 completion gate satisfied
```

## 11.1 Hard sequencing rule

```text
P0.4-pre and P0.4A0 must complete before any schema work.
P0.4B0 must complete before any binding can be claimed activation-eligible.
P0.4C and P0.4D1 must land together (or D1 before C2) — see §5.4.
Governed retrieval eligibility does not switch until P0.4A–D are green.
```

## 11.2 What is explicitly out of sequence

```text
Frontend TS remediation is not in any P0.4 wave.
Pre-capability vector re-certification by backfill is forbidden in every wave.
Mutation of historical binding rows is forbidden in every wave.
```

---

# 12. Failure category additions

The original §9 taxonomy is augmented with two categories that the repository
forces:

```text
configuration               (original — unchanged)
provider_connectivity       (original — unchanged)
authentication              (original — unchanged)
model_resolution            (original — unchanged)
embedding_output            (original — unchanged)
normalization               (original — unchanged)
contract                    (original — unchanged)
internal                    (original — unchanged)

side_channel_ungoverned     (new) — governed collection used without capability evidence
embedding_surface_drift     (new) — LLMProvider.embed surface diverges from EmbeddingProvider
```

New codes (in addition to original §9):

```text
side_channel_capability_missing
side_channel_collection_unallowlisted
embedding_surface_unmonitored
```

Failure detail sanitization rules from original §9 (strip credentials, tokens,
authorization headers, query strings, provider response bodies, signed URLs,
control characters) apply unchanged.

---

# 13. Completion gate (corrected)

P0.4 is complete when every condition in the original completion gate holds
**and** the six corrected conditions below hold. The side-channel and
activation-I/O gates are sharpened: a written decision is not sufficient, and
ordinary relational reads are not prohibited.

```text
working tree clean

governed embedding calls without current check              0
raw providers reaching governed callers                      0
new governed vectors without capability binding              0
new governed vectors without generation check                0
retrievals without query capability evidence                 0
retrievals mixing capability bindings                        0
pre-capability vectors eligible after activation             0
historical vectors falsely backfilled                         0
alias-only bindings activated                                0
expired checks authorizing new work                          0
runtime drift silently accepted                              0
same-dimension cross-model mixing                            0
partial cutovers activated                                   0
secrets persisted in capability evidence                     0
```

## 13.1 Six corrected invariants (hard gates)

| # | Invariant | Required final wording |
|---|---|---|
| 1 | Side-channel disposition | Every persistent or cache embedding surface has a terminal, runtime-enforced classification; no surface remains accidentally ungated |
| 2 | `LLMProvider.embed()` disposition | No production embedding bypass remains through the chat-provider protocol or its wrappers |
| 3 | Dropped runtime-field reads | No migrated caller reads removed raw-provider or untyped-profile fields |
| 4 | Invalid v1/capability combinations | `vector_index_v1 + capability_v1` and `vector_index_v2 + pre_capability_v0` are rejected |
| 5 | Lease-recovery claim races | Exactly one worker abandons an expired check and owns its replacement |
| 6 | External I/O in activation | No provider, embedding, Chroma, or other backend I/O occurs inside the activation publication transaction |

### 13.2 Side-channel gate — implementation, not just decision

A row classified as `excluded` but still reachable through a raw embedding
provider does not satisfy the gate. The classification must be **enforced at
runtime**, not merely recorded in the audit document. Each persistent or cache
embedding surface ends P0.4 in exactly one of these terminal postures:

```text
brought under P0.4   — verified runtime gates every read and write
explicitly excluded  — architectural enforcement prevents ungated reachability
retired              — surface removed from production code
```

A surface that remains reachable through an ungated path fails invariant 1,
regardless of what the audit document records.

### 13.3 Activation-I/O gate — scope of the prohibition

Invariant 6 prohibits **external or unbounded** operations inside the
activation publication transaction. It does not prohibit the ordinary
relational reads and writes required for verification.

Permitted inside the `BEGIN IMMEDIATE` activation transaction:

```text
SELECT / UPDATE / INSERT on relational tables
activation-guard row claim
cutover row verification
vector_index_records eligibility update
binding-activation row update
```

Prohibited inside the activation transaction — must complete before it starts:

```text
provider probes
embedding generation
Chroma reads or writes
network requests
filesystem exports
any other external or unbounded I/O
```

The final closeout document (`docs/p0_4_embedding_capability_closeout.md`)
must record the exact command, the exact commit, and the actual counts for
each line of §13 and §13.1. Inherited counts from narrower gates are not
acceptable.

---

# 14. Files affected (corrected from original §21)

| Area                                              | Action                                                                   |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| `backend/api/routes/knowledge.py:259`             | **P0.4-pre** — repair duplicate `backend=` syntax error                  |
| `docs/p0_4_baseline.md` (new)                     | **P0.4-pre** — record exact command, commit, and collected/passed counts |
| `docs/p0_4_embedding_access_audit.md`             | **P0.4A0** — expanded audit covering all three surfaces + decisions      |
| `backend/pipeline/vector_contracts.py`            | **P0.4B0** — extract `VECTOR_INDEX_V1`/`V2` + contract constants         |
| `backend/pipeline/knowledge/embedding_providers.py` | **P0.4B0** — response capture + posture classification per adapter     |
| Three `_EmbeddingAdapter` sites                   | **P0.4B0** — consolidate into one governed adapter                       |
| `LLMProvider.embed()` surface (every chat provider) | **P0.4B0** — delete or formally allowlist                               |
| Next Alembic migration (`027`)                    | **P0.4A1** — bindings, checks, activations + partial unique indexes      |
| Later Alembic migration (`028`)                   | **P0.4E** — cutover and cutover-item ledger                              |
| `backend/db/models.py`                            | Capability and cutover models (append after `LegacyVectorReindexTarget`) |
| `backend/pipeline/embedding_capability_contracts.py` (new) | Binding, check, runtime contracts, EmbeddingProfileSnapshot     |
| `backend/pipeline/embedding_capability_service.py` (new)   | Check lifecycle, probes, binding creation, lease recovery       |
| `backend/pipeline/verified_embedding_runtime.py` (new)     | Guarded embedding operations                                    |
| Provider adapter modules                          | Capability resolution and request observer (after P0.4B0 baseline)       |
| `backend/pipeline/vector_runtime.py`              | **Breaking migration** of `GovernedVectorRuntime` (§3)                   |
| `backend/pipeline/stages.py`                      | Caller migration (§3.3)                                                   |
| `backend/pipeline/novelty/novelty_checker.py`     | Caller migration (§3.3)                                                   |
| `backend/api/routes/knowledge.py`                 | Caller migration (§3.3) — in addition to the P0.4-pre syntax fix         |
| `backend/cli/legacy_vector_cli.py`                | Caller migration (§3.3) + reconciliation with new `erlab embeddings` CLI  |
| Embedding CLI module (new)                        | `erlab embeddings verify-profile / capability-status / reindex-unbound / activate-binding / abandon-stale-check` |
| `backend/pipeline/vector_indexer.py`              | Require verified runtime for new generation                              |
| `backend/pipeline/vector_contracts.py`            | Capability-aware vector identity v2                                       |
| `backend/pipeline/vector_backend.py`              | Binding-specific collection metadata                                      |
| `backend/pipeline/scoped_vector_service.py`       | Active-binding candidate enforcement                                      |
| `backend/pipeline/legacy_vector_reindex.py`       | Use verified runtime for P0.4 remediation                                 |
| Architectural tests                               | Reject unverified provider use across **both** embedding surfaces         |
| Capability tests                                  | Checks, expiry, drift, concurrency, lease recovery                        |
| Cutover tests                                     | Remediation, activation, isolation, SQLite-concurrent activation          |
| `docs/p0_4_embedding_capability_closeout.md`      | Final evidence + §13 completion gate counts                               |

---

# 15. Commit message conventions

Following the existing P0.3 wave pattern:

```text
fix: P0.4-pre repair governed search route syntax and seal regression baseline

docs: P0.4A0 expanded embedding access audit with side-channel decisions

feat: P0.4B0 capture provider model identity and consolidate embedding adapters

feat: add embedding capability binding and check ledger            (P0.4A1)

feat: verify provider embedding capability with production probes   (P0.4B1)

refactor: migrate GovernedVectorRuntime to capability-gated shape   (P0.4C)

feat: bind vector index and retrieval evidence to capability        (P0.4D)

feat: remediate pre-capability vectors and activate verified binding (P0.4E)

test: seal embedding capability handshake and cross-binding isolation

docs: close P0.4 embedding capability handshake
```

---

# 16. Frozen dispositions (binding — P0.4A0 verifies implementation surface)

These dispositions were open in the prior revision of this contract. They are
now **frozen**. P0.4A0 records the implementation surface that realizes each
disposition and confirms the runtime enforcement; it does not choose the
architectural posture.

## 16.1 `kg_entity_embeddings` — INCLUDED under P0.4

Classification:

```text
side_channel_persistent_embedding
P0.4 scope: included
```

Required posture:

```text
verified runtime required for writes and queries
dedicated embedding profile and capability binding
binding-specific collection namespace and metadata
different binding → rebuild/reindex before activation
no reuse of the paper vector_index_records ledger
```

Knowledge-graph entity vectors are a distinct semantic space. They do not
share the paper profile or binding merely because they use the same provider
or dimension. They get their own profile, their own binding, and their own
collection namespace.

## 16.2 `tool_embeddings` — INCLUDED under P0.4

Classification:

```text
side_channel_persistent_embedding
P0.4 scope: included
```

Required posture:

```text
verified runtime required
binding-specific collection
binding change requires deterministic rebuild
cross-binding queries rejected
```

Tool descriptions have a different content and lifecycle contract from paper
chunks and from knowledge-graph entities. Tool embeddings use a separate
profile and binding from both paper and KG embeddings.

## 16.3 `llm_cache` — capability-gated, no durable cutover

Classification:

```text
ephemeral_or_rebuildable_cache_embedding
P0.4 scope: capability-gated, no durable cutover ledger required
```

The cache still requires semantic-space isolation, but it does not need the
full historical vector-remediation machinery.

Required design:

```text
verified runtime required for cache-key embeddings
capability_binding_id included in cache namespace or key
binding change makes old cache entries unreachable
expired health check blocks generation of new cache entries
cache may be discarded rather than migrated
```

This keeps the safety invariant without treating cache entries as durable
research evidence.

## 16.4 `LLMProvider.embed()` — REMOVED from production protocol

Disposition:

```text
remove from the production LLMProvider protocol
```

The expanded audit (critique finding B1) found no required live production
callers outside wrappers. P0.4B0 eliminates this second embedding front door
rather than certifying and maintaining two parallel protocols.

Required work:

```text
remove concrete chat-provider embed implementations
remove forwarding methods from cache/gateway/resilience wrappers
remove StageContext forwarding
migrate any surviving caller to the governed embedding provider
add architectural enforcement against reintroduction
```

A temporary compatibility shim is acceptable only inside tests or a narrowly
named migration module, and it must not be reachable from production
composition.

## 16.5 `knowledge.py:259` — REPAIRED, not deleted

Disposition:

```text
fix, do not delete the governed route
```

Remove the duplicated `backend=backend` argument and retain:

```python
backend=runtime.backend
```

The governed knowledge-search route was a deliberate P0.3 production migration
boundary. Deleting it to restore collection would erase proven functionality
rather than repair the defect.

P0.4-pre must then execute and record:

```text
python -m pytest backend/tests
```

The baseline record must include:

```text
repair commit
Python version
pytest version
tests collected
passed
failed
skipped
deselected
collection errors
duration
working-tree status
```

The contract does not assume the result will be 285.

## 16.6 Disposition summary

```text
kg_entity_embeddings    side_channel_persistent_embedding   INCLUDED
tool_embeddings         side_channel_persistent_embedding   INCLUDED
llm_cache               ephemeral_or_rebuildable_cache      capability-gated, no cutover
LLMProvider.embed()     —                                   REMOVED from production protocol
knowledge.py:259        —                                   REPAIRED, route retained
```

## 16.7 Reranker / cross-encoder classification

A reranker or cross-encoder is not automatically an embedding surface. P0.4A0
must classify each reranker model in the codebase according to its actual
output contract:

```text
reranker emits reusable embedding vectors
→ embedding surface; classify under P0.4

reranker returns only relevance scores
→ confirmed_non_embedding_model
```

A scoring-only cross-encoder must not be forced into the embedding-capability
ledger when it does not create a reusable semantic vector. It may need a
**future model-capability handshake**, but that is a different contract and is
explicitly out of scope for P0.4.

The audit record for each reranker must show:

```text
model location (file:line)
output contract (reusable vectors | relevance scores only)
classification (embedding surface | confirmed_non_embedding_model)
disposition (bring under P0.4 | defer to future model-capability contract)
```

---

# Appendix A — Verified findings from the critique

These findings were verified against the repository at `90d2ebb` and are the
factual basis for the corrections above. They are recorded here so the revised
contract is self-contained.

```text
A1  knowledge.py:259 is a committed SyntaxError; full backend/tests run
    cannot collect 5 modules under test_api/. 285-passing claim is not
    reproducible on the current head.

A2  Every embedding adapter today discards the provider's resolved model
    identity. Every binding would be classified alias_only under the
    original §3 rule, making activation unreachable without P0.4B0.

B1  Two parallel embedding surfaces exist: EmbeddingProvider (the ABC the
    spec assumes) and LLMProvider.embed() on every chat provider, plus
    cache/gateway/resilience proxies. The original spec seals only the
    first.

B2  Three side-channel collections (kg_entity_embeddings, tool_embeddings,
    llm_cache) write embeddings to allowlisted ChromaDB collections but
    bypass VectorIndexer lifecycle. Original taxonomy excludes them by
    definition.

B3  GovernedVectorRuntime exists at vector_runtime.py:18-32 and is read by
    at least 5 production callers. Original §16 framed it as new.

B4  EmbeddingProfile (models.py:1270-1296) is CHECK-constrained to
    verification_status='unverified' and is not the runtime config source.
    Runtime config lives in backend/config.py:62-64 (Settings).

B5  "vector_index_v1" appears as a literal in 7 sites with no shared
    constant. Original §11.3 introduces v2 without first extracting v1.

B6  Three private _EmbeddingAdapter implementations (stages.py:676,
    vector_runtime.py:99, legacy_vector_cli.py:289) expose only
    embed_single(text). None can satisfy EmbeddingCapabilityProvider.

C1  Original §11 left index_schema_version vs embedding_contract_version
    relationship ambiguous. Resolved by §5 of this document.

C2  Original §4.4/§4.5 left lease recovery mode ambiguous. Resolved by §7.

C3  Original §10 mixed persistent_activation_eligible with re-derivation
    from posture. Resolved by §9 (binding immutability).

C4  Original §14.6 activation transaction assumed row-level locking not
    available on SQLite. Resolved by §8.
```

## Appendix B — Repository coordinates referenced

All paths absolute under `C:\Next-Era\Elephant-Rock-Research-Lab`.

```text
backend/api/routes/knowledge.py                       (lines 215, 217, 256-261)
backend/cli/legacy_vector_cli.py                      (lines 39, 126, 215, 284, 289-306, 346-379)
backend/config.py                                     (lines 61-64)
backend/db/models.py                                  (lines 1270-1296 EmbeddingProfile, 1316 v1 CHECK)
backend/pipeline/knowledge/embedding_providers.py     (lines 58-83, 131-156, 199-243, 254-278, 357)
backend/pipeline/knowledge/embedding_service.py       (lines 43, 57, 89)
backend/pipeline/knowledge/graph_embeddings.py        (lines 31, 45, 62, 80)
backend/pipeline/knowledge/vector_store.py            (lines 46, 95, 164)
backend/pipeline/memory/embedding_dedup.py            (lines 63, 70, 78)
backend/pipeline/novelty/novelty_checker.py           (lines 148-149, 160, 186)
backend/pipeline/orchestrator/service_registry.py     (lines 62-77, 79, 93-94, 96)
backend/pipeline/preflight.py                         (line 190)
backend/pipeline/scoped_vector_service.py             (lines 116-155, 139, 319, 620)
backend/pipeline/stages.py                            (lines 131, 628, 634, 676-690, 684)
backend/pipeline/tools/tool_index.py                  (lines 38, 55, 73, 98)
backend/pipeline/vector_backend.py                    (lines 44, 66-71, 83)
backend/pipeline/vector_contracts.py                  (lines 35-63, 236-238, 241-257, 249, 260-278)
backend/pipeline/vector_indexer.py                    (lines 52, 108, 171, 197, 208-440, 344)
backend/pipeline/vector_runtime.py                    (lines 18-32, 35-85, 67, 88, 99-104)
backend/providers/cache/semantic_cache.py             (lines 38, 53, 98)
backend/providers/provider_factory.py                 (lines 307, 314)
backend/providers/{openai,anthropic,ollama,gemini,litellm}_provider.py   (.embed methods)

alembic/versions/020_provenance_contract_gating.py   (Flavor B backfill template)
alembic/versions/021_vector_scope_foundation.py      (add-column-with-CHECK template)
alembic/versions/022_vector_index_registry.py        (table being extended by §5)
alembic/versions/024_legacy_vector_migration.py      (table-creation template)
alembic/versions/026_legacy_identity_column.py       (current head; P0.4A1 = 027)

docs/p0_3_4_production_vector_migration_closeout.md   (canonical access-audit format)
docs/p0_3_5_legacy_reindex_closeout.md                (271-passed canonical gate)
docs/frontend-ts-baseline.md                          (101 TS errors, captured not repaired)
```
