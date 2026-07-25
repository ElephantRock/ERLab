# ERLab Recent Work Timeline

> **Companion to** `ERLAB_CURRENT_STATE_REPORT.md` Part 4.
> **Window:** 2026-07-15 → 2026-07-25 (HEAD `cea3ea16378ef7bbf7848cc31febf93af2478841`).
> **Commits reviewed:** 228.
> **Source:** `git log --since=2026-07-15 --until=2026-07-25T04:00:00"` + per-commit `git show`.
> **Timestamps:** local (+0300). All values VERIFIED from git unless marked.
>
> This timeline reports what happened. It does not criticize or defend.

---

## A. The Requested Chain: `c1fa554` → `cea3ea1`

Eleven commits. The chain begins mid-P1E.0 (after the diagnosis was measured) and runs through the P1E.1 extension close. Eight of the eleven are P1E.1; three complete P1E.0.

| # | Hash | Timestamp | Subject | Parent | Type |
|---|---|---|---|---|---|
| 1 | `c1fa5541a5efa9a57a2c6bc10ab3d0832ac29fa3` | 2026-07-24 06:40:09 | fix(p1e): correct top1-optimal empirical resolution | `063d060ce00006a6218c83a0e1116c1b240943bd` | Correction (P1E.0) |
| 2 | `d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a` | 2026-07-24 23:26:52 | docs(p1e1): freeze benchmark extension protocol | `c1fa5541…` | Governance (P1E.1 protocol v1) |
| 3 | `42ff0e661f2acfa15ccefbd94f2770dcaa3f353d` | 2026-07-24 23:57:19 | fix(p1e1): ground near-duplicate threshold in v2 references | `d2e16ae6…` | Correction (threshold) |
| 4 | `00c6ffdc87e2e5057d205af6ee7de1db5e94cfad` | 2026-07-25 00:41:08 | feat(p1e1): construct and seal grade-free v3 candidate corpus + provenance | `42ff0e66…` | Planned work (artifact) |
| 5 | `679bc0052d0851bef48ab87663166b7a08f85bd6` | 2026-07-25 01:03:14 | docs(p1e1): disclose calibration custody breach (protocol v3) | `00c6ffdc…` | Governance patch (v3) |
| 6 | `36bbbc9d9275c342c0f7cb6cd486b9d9162aadf1` | 2026-07-25 01:09:37 | fix(p1e1): canonicalize candidate artifact protocol identity + disclose breach | `679bc005…` | Correction + governance |
| 7 | `2a32254a66bacec492493d9655b61a81525fb3ad` | 2026-07-25 01:26:01 | feat(p1e1): cal/dev adjudication, blind held-out, extension identity | `36bbbc9d…` | Planned work (Commit 3) |
| 8 | `3e6d09e73972d24a070e7e98079126be5fb06d73` | 2026-07-25 01:35:16 | docs(p1e1): seal adjudication provenance and custody status | `2a32254a…` | Governance |
| 9 | `af2f131f2851ae1064750e54b29278d2ce8d3028` | 2026-07-25 02:07:56 | docs(p1e1): authorize preserved-v2 judgment inheritance (protocol v4) | `3e6d09e7…` | Governance patch (v4 — EFFECTIVE) |
| 10 | `a6c35e670f67a0331cc71074caf229e52b02b9c2` | 2026-07-25 02:13:00 | docs(p1e1): close inheritance deviation and complete custody transfer | `af2f131f…` | Governance (custody relocation) |
| 11 | `cea3ea16378ef7bbf7848cc31febf93af2478841` | 2026-07-25 03:09:49 | docs(p1e1): close benchmark extension diagnosis | `a6c35e67…` | Governance (HEAD) |

**No commits exist after `cea3ea1`** at the time of this report.

### Per-commit detail

#### 1. `c1fa554` — fix(p1e): correct top1-optimal empirical resolution
- **Purpose:** correct the empirical resolution of the `top1_optimal` metric in the P1E.0 audit.
- **Triggering problem:** the prior resolution (`25d56df` / `063d060`) mis-resolved top1-optimal empirical cases.
- **Resulting artifact:** corrected P1E.0 diagnosis values; final P1E.0 chain anchored here.
- **Behavior change:** benchmark test/audit only; no runtime behavior change.
- **Benchmark content change:** NO (correction to metric resolution, not to corpus).
- **Metadata/governance only:** partial — fixes a measurement bug.
- **Later superseded:** NO (final P1E.0 resolution).

#### 2. `d2e16ae` — docs(p1e1): freeze benchmark extension protocol (v1)
- **Purpose:** freeze the initial P1E.1 benchmark extension protocol.
- **Resulting artifact:** `docs/research/p1e1_benchmark_extension_protocol.md` (v1).
- **Behavior change:** NONE.
- **Benchmark content change:** NONE (protocol only).
- **Metadata/governance only:** YES.
- **Later superseded:** YES — by v2 (`42ff0e6`), v3 (`679bc00`), v4 (`af2f131`).

#### 3. `42ff0e6` — fix(p1e1): ground near-duplicate threshold in v2 references
- **Purpose:** re-derive the near-duplicate detection threshold from v2 benchmark references instead of an unjustified value.
- **Triggering problem:** the v1 threshold was not grounded in v2 references.
- **Resulting artifact:** `docs/research/p1e1_benchmark_extension_protocol_v2.md`; final threshold `0.861630662`.
- **Behavior change:** NONE (design parameter for corpus construction).
- **Benchmark content change:** YES (threshold determines which candidates count as near-duplicates).
- **Metadata/governance only:** NO — changes a construction parameter.
- **Later superseded:** NO — this threshold is final.

#### 4. `00c6ffd` — feat(p1e1): construct and seal grade-free v3 candidate corpus + provenance
- **Purpose:** build the 576-candidate v3 corpus and seal its provenance.
- **Resulting artifacts:** `data/evaluation/p1e1_candidate_package.json`, `p1e1_candidate_provenance.json`, `p1e1_candidate_mining_scores.json`, `p1e1_construction_provenance.json`, `p1e1_prejudgment_diagnostics.json`, `p1e1_split_manifest.json`.
- **Behavior change:** NONE (benchmark corpus, not runtime).
- **Benchmark content change:** YES — creates the v3 corpus.
- **Metadata/governance only:** NO — major artifact production.
- **Later superseded:** NO (candidate corpus is sealed; only adjudication was added later).

#### 5. `679bc00` — docs(p1e1): disclose calibration custody breach (protocol v3) — **Commit 2**
- **Purpose:** disclose that calibration had historically accessed held-out material (2 cases, 4 candidate texts, 0 judgments) and redefine admissible calibration.
- **Triggering problem:** historical access to held-out material during threshold calibration.
- **Resulting artifact:** `docs/research/p1e1_benchmark_extension_protocol_v3.md`.
- **Behavior change:** NONE.
- **Benchmark content change:** NONE.
- **Metadata/governance only:** YES — disclosure + admissibility redefinition.
- **Later superseded:** YES — by v4 (`af2f131`).

#### 6. `36bbbc9` — fix(p1e1): canonicalize candidate artifact protocol identity + disclose breach
- **Purpose:** re-canonicalize the candidate artifact's protocol identity so that candidate-layer artifacts reference the correct (v3) protocol version, and disclose the breach in the artifact metadata itself.
- **Triggering problem:** candidate-layer artifacts were referencing the wrong protocol version after v3 superseded v1/v2.
- **Resulting artifact:** updated candidate-package/provenance metadata.
- **Behavior change:** NONE.
- **Benchmark content change:** NO (identity rebinding, not content).
- **Metadata/governance only:** YES.
- **Later superseded:** NO.

#### 7. `2a32254` — feat(p1e1): cal/dev adjudication, blind held-out, extension identity — **Commit 3**
- **Purpose:** produce the cal/dev adjudication (444 grade records), the blind held-out package, and the extension identity record.
- **Resulting artifacts:** `p1e1_caldev_adjudication.json` (180 inherited + 264 fresh = 444), `p1e1_blind_heldout_package.json`, `p1e1_benchmark_extension.json`.
- **Behavior change:** NONE.
- **Benchmark content change:** YES — adds the grade judgments.
- **Metadata/governance only:** NO — major artifact production.
- **Later superseded:** NO.

#### 8. `3e6d09e` — docs(p1e1): seal adjudication provenance and custody status
- **Purpose:** seal the adjudication provenance and record custody status.
- **Resulting artifacts:** `p1e1_adjudication_provenance.json`, updated custody receipt.
- **Behavior change:** NONE.
- **Benchmark content change:** NO.
- **Metadata/governance only:** YES.
- **Later superseded:** partial — custody status updated by `a6c35e6`.

#### 9. `af2f131` — docs(p1e1): authorize preserved-v2 judgment inheritance (protocol v4) — **EFFECTIVE**
- **Purpose:** authorize bounded inheritance of 180 byte-identical v2 cal/dev judgments (instead of re-adjudicating them) and formalize this as protocol v4.
- **Triggering problem:** v3 had disclosed the custody breach but left the inheritance question unresolved; v4 resolves it.
- **Resulting artifact:** `docs/research/p1e1_benchmark_extension_protocol_v4.md` (EFFECTIVE protocol).
- **Behavior change:** NONE.
- **Benchmark content change:** NO.
- **Metadata/governance only:** YES.
- **Later superseded:** NO — this is the final effective protocol.

#### 10. `a6c35e6` — docs(p1e1): close inheritance deviation and complete custody transfer
- **Purpose:** close the deviation opened by the inheritance decision and complete the custody transfer (reconciliation map moved outside the repo).
- **Resulting artifacts:** updated `p1e1_reconciliation_map_custody_receipt.json` (`transfer_status: accepted`); reconciliation map relocated to `C:\Next-Era-Erlab-Custody\p1e1_reconciliation_map.json` (outside repo).
- **Behavior change:** NONE.
- **Benchmark content change:** NO.
- **Metadata/governance only:** YES.
- **Later superseded:** NO.

#### 11. `cea3ea1` — docs(p1e1): close benchmark extension diagnosis (HEAD)
- **Purpose:** final closeout of the P1E.1 diagnosis.
- **Resulting artifact:** `docs/research/p1e1_benchmark_extension.md` + `data/evaluation/p1e1_benchmark_extension_diagnosis.json`.
- **Behavior change:** NONE.
- **Benchmark content change:** NO.
- **Metadata/governance only:** YES.
- **Later superseded:** NO (HEAD).

---

## B. Immediately Preceding Context (`063d060` and earlier P1E.0 chain)

The requested chain begins at `c1fa554`, whose parent is `063d060`. For completeness, the P1E.0 chain that produces `c1fa554` is:

| Hash | Timestamp | Subject |
|---|---|---|
| `2032579b5c5e1e2e0edc8b89c6ff295f623e5bca` | 2026-07-24 05:16:23 | docs(p1e): freeze benchmark discrimination audit protocol |
| `2f9031d40473a62e6a184eca30c9594bdc7c9932` | 2026-07-24 05:57:59 | fix(p1e): correct split-manifest case→split mapping; strengthen cross-check |
| `25d56df296ff9c135c1fcff16194eb69121bea69` | 2026-07-24 06:05:40 | feat(p1e): measure benchmark ceiling and policy separability |
| `d3420d69f6131dbff136fccbd82d3711f8fd1a31` | 2026-07-24 06:09:30 | test(p1e): seal frozen corpus and original evaluator usage |
| `063d060ce00006a6218c83a0e1116c1b240943bd` | 2026-07-24 06:15:50 | docs(p1e): publish benchmark discrimination diagnosis |
| `c1fa5541a5efa9a57a2c6bc10ab3d0832ac29fa3` | 2026-07-24 06:40:09 | fix(p1e): correct top1-optimal empirical resolution |

The full P1E.0 accepted chain (per protocol): `2032579` (Commit 1) → `2f9031d` → `25d56df` (Commit 2) → `d3420d6` (Commit 3) → `c1fa554` → `063d060` (Commit 4).

---

## C. Repeated Correction Cycles Identified in the Chain *[VERIFIED]*

| Cycle | Commits in chain | Nature |
|---|---|---|
| **Protocol v1 → v4** | `d2e16ae` (v1 freeze) → `42ff0e6` (v2 threshold grounding) → `679bc00` (v3 custody-breach disclosure) → `af2f131` (v4 inheritance authorization) | 4 protocol versions in ~2 hours 41 minutes |
| **Near-duplicate threshold recalibration** | `42ff0e6` | Threshold re-derived from v2 references → final value `0.861630662` |
| **Allocation / split correction** (pre-window, carried into chain) | `2f9031d` (P1E.0 split-manifest fix) | case→split mapping corrected |
| **Held-out calibration-access disclosure** | `679bc00` (v3) | Historical held-out access disclosed: 2 cases, 4 texts, 0 judgments |
| **Artifact identity rebinding** | `36bbbc9` | Candidate corpus protocol identity re-canonicalized to v3 |
| **Inherited-judgment authorization** | `af2f131` (v4) | 180 byte-identical v2 cal/dev records authorized to inherit |
| **Custody relocation** | `a6c35e6` | Reconciliation map moved outside repo to `C:\Next-Era-Erlab-Custody\` |
| **Commit 2 governance patch** | `679bc00` (Commit 2 of closeout) | Custody-breach disclosure |
| **Commit 3 governance patch** | `2a32254` + `3e6d09e` (Commit 3 of closeout) | Cal/dev + held-out + provenance seal |

---

## D. Commit Allocation Across the Full 228-Commit Window *[VERIFIED]*

| Category | Count | % |
|---|---|---|
| Commits WITH production code (non-test `.py`/`.ts`/`.tsx`, excluding `scripts/`) | 121 | 53% |
| Commits with ONLY test / script code | 54 | 24% |
| Commits with NO code (docs/data/json/yaml/config/md only) | 53 | 23% |

| Prefix | Count |
|---|---|
| `feat` | 75 |
| `docs` | 63 |
| `test` | 34 |
| `fix` | 29 |
| `refactor` | 17 |
| `data` | 6 |
| `eval` | 3 |
| `chore` | 1 |

---

## E. Major Sub-Phases Within the Window *[VERIFIED]*

| Sub-phase | Commit range (approx) | Outcome |
|---|---|---|
| P0.3 / P0.4 / P0.5 closeouts | early window | All COMPLETE |
| P1 ranking surface audit | `02f9d5d`…`914af0a` | COMPLETE (infra); P1 OPEN |
| P1B baseline experiment | through `540de0c` | CLOSED Gate 2 (genuine negative) |
| P1C LM Studio embeddings | through `910bf2a` | CLOSED Branch D (host failure) |
| F0 frontend TS recovery | `6004001`…`3bcb620` | COMPLETE (101→0 errors) |
| F1.1–F1.7 frontend architecture | `dfcac7d`…`f7de502` | COMPLETE |
| P1D TEI experiment | `2c2a307`…`78a6f19` | CLOSED Outcome B |
| P1D.2 diagnostic / reviewer | `c32730c`…`1e4af03` | BLOCKED (review protocol unsealed) |
| P1D.5 sprint falsification | `c9f8ca9`…`947d349` | CLOSED (candidates dead) |
| P1E.0 discrimination audit | `2032579`…`063d060` + `c1fa554` | CLOSED Outcome M |
| P1E.1 benchmark extension | `d2e16ae`…`cea3ea1` | CLOSED (corpus + cal/dev); eval NOT STARTED |

---

*End of timeline. Generated from git history only; no repository source or product artifact modified.*
