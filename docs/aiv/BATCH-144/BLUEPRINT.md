# BATCH-144 Blueprint — Pipeline Config UX: Reduce Form Density

**Batch ID:** BATCH-144
**Cycle Mode:** STANDARD (Lead Override §5.3)
**Lead:** ivory-wolf
**Date:** 2026-05-10
**AIV Version:** v5.3
**Preceding Batch:** BATCH-143 (CLOSED)

## Strategic Bet
First-time users see 2 essential fields (Domain + Strategy) instead of 7. All tuning knobs (Max Gaps, Ideas Per Round, Generation Rounds, Export Format, Search Queries, Session ID, Run Toggles) collapsed into "Advanced Options". Cognitive load drops from 7±2 to 3±1.

## Change
Moved 5 fields (Max Gaps, Ideas Per Round, Generation Rounds, Export Format, Search Queries) from top-level into the existing Advanced Options collapsible section in run-config-form.tsx. Added data-testid attributes to domain input and search queries input.

## Commit
`[pending]`
