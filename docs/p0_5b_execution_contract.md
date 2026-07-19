# P0.5B Execution Contract

## Entry state
- Commit: `f1c6420`
- Alembic head: `029`
- Backend: 4482 passed, 25 skipped, clean tree

## Completed
- P0.5A: Configuration Governance Framework — CLOSED
- P0.5B WP2: All 22 material-field fallback defaults removed. Seal absolute (zero).

## Remaining package order
1. WP1 — Production composition migration (service_registry → effective domain configs)
2. WP3 — CLI/API omission-aware propagation
3. WP4 — Durable configuration evidence (migration + DB tables + FK linkage)
4. WP6 — Cross-domain production proof
5. WP5 — Final production seal (absolute gates) + adversarial review + five-run gate + closeout

## Invariants
- All 289 Settings fields remain registered
- Zero material-field fallback defaults in production
- Seal is absolute, not ratcheted
- No second default owner for any registered field

## Stop conditions
1. Material field has incompatible precedence semantics between production paths
2. API contract cannot preserve omission without breaking migration
3. Production service cannot consume effective domain config without redesign
4. Exact durable linkage requires changing operation ownership model
5. Ranking control requires P1 redesign
6. Query control requires P2 redesign
7. Continuation setting requires P3 architecture

## Final closure gate
```
all registered material consumers use effective configs      yes
remaining registered-field fallback defaults                 0
material raw Settings semantic reads                          0
CLI/API material propagation gaps                             0
material fields without executable effect coverage            0
required operations without durable config evidence           0
unresolved false-control findings                             0
five consecutive backend gates                               green
working tree                                                  clean
```
