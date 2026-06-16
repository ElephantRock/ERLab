# Phase 3 Deferred: Live Parity Validation

**Date:** 2026-06-16
**Status:** Deferred — requires LM Studio running

## What

Phase 3 parity gate was **structural only**, not output parity. The stage loop extraction preserves identical logic for strategy skip, doom detection, policy gate, checkpoint timing, heartbeat, and cancellation checks. However, no live pipeline run was executed to compare actual outputs (idea counts, novelty scores, export artifacts).

## Why deferred

LM Studio was not available during Phase 3 execution. A live run requires a loaded model and sufficient VRAM.

## What to validate when LM Studio is available

1. Run the same domain + config through both the old project (`elephant-rock-platform`) and new project (`Elephant-Rock-Research-Lab`)
2. Compare stage completion (all stages reach same status)
3. Compare generated idea counts
4. Compare novelty outputs
5. Compare exported artifacts
6. Record intentional differences caused by fail-closed behavior (e.g., served_model conformance rejection)

## Risk

Low — the RunCoordinator extraction is a behavior-preserving move (code was moved, not redesigned). The only behavioral change is the removal of direct `_client` access in `_gateway_provider_fn`, which now delegates to `provider.structured_output()` that handles `json_schema` natively.
