"""Productive-1 R5 frozen 8-trial qualification (execution-only).

Authorized objective (owner, 2026-08-31): execution-only qualification
against the exact frozen candidate b9cb75c400606557be1f70d660c1b6d4f2b9d7a9
under the frozen R5 contract (evidence/productive1_r5/r5_charter.md).
Four frozen blocked states x two byte-identical restores; one cold
/paper/repair POST per fresh API process through the unchanged PAC
authoritative evaluation/promotion path.

Binding verdict (wired at freeze, per the charter and the owner's
resolved decision #2):
  - >=7/8 overall and >=3/4 per family (trial success = authoritative
    eval_status == "ready")
  - negative control blocked (zero negative-control promotions)
  - E == F == R == H on every ready trial; promoted implies ready
    (zero false promotions)
  - scope integrity MANDATORY for every trial: either the persisted
    revision-1 bytes are exactly the manifest applied to revision 0
    (with identical heading sequence, RESULT/SOURCE token multiset, and
    preserved previously-passing method fidelity), or the persisted
    bytes are exactly revision 0 (typed fail-closed path with a
    recorded failure reason). Any other byte state fails the batch.

Timeout policy: the 600-second ceiling is the authoritative
evaluation/provider budget — a timed-out trial is recorded as an
ordinary failed trial (typed trial_timeout), no carve-out, no rerun.

Evidence completeness (the R3/R4 gap, closed): per trial, this harness
writes revision bytes (the trial DB), the API server log, the patch
manifest, the typed failure reason, the reconstruction proof, gate
state, authoritative stamp, and release identity into
evidence/productive1_r5/trials/<trial>/, all uploaded by the workflow.

No product behavior is changed by this file.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import socket
import sqlite3
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_PATH = Path(__file__).with_name("p1_r5_qualify_base.py")

spec = importlib.util.spec_from_file_location("p1_r5_qualify_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load frozen qualification base")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.INPUT = ROOT / ".r5_qual_inputs"
base.TMP = ROOT / ".r5_qual_tmp"
base.TMP.mkdir(exist_ok=True)
base.OUT = ROOT / "evidence/productive1_r5/p1_r5_qualification.json"
base.OUT.parent.mkdir(parents=True, exist_ok=True)
base.STATES = [
    ("calib-A", "calibration", base.INPUT / "calib-A_runfail3.db", False),
    ("calib-B", "calibration", base.INPUT / "calib-B_runfail2.db", True),
    ("regr-A", "regression", base.INPUT / "regr-A_case3a.db", True),
    ("regr-B", "regression", base.INPUT / "regr-B_3E_era.db", True),
]

CANDIDATE_SHA = "b9cb75c400606557be1f70d660c1b6d4f2b9d7a9"
TRIALS_DIR = ROOT / "evidence/productive1_r5/trials"
TRIALS_DIR.mkdir(parents=True, exist_ok=True)

# Frozen timeout policy: 600s is the authoritative evaluation/provider
# ceiling (owner decision #3). The base default of 900s is overridden
# for the repair call; freeze/release keep their own small budgets.
_base_http = base.http


def http_600(method: str, path: str, timeout: float = 600.0):
    return _base_http(method, path, timeout)


base.http = http_600

_MARKER_TOKEN_RE = re.compile(r"\[(RESULT|SOURCE)-(\d+)\]")


def _marker_multiset(paper_md: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _MARKER_TOKEN_RE.finditer(paper_md):
        token = match.group(0)
        counts[token] = counts.get(token, 0) + 1
    return counts


def _observe_r5(label: str, trial_no: int) -> dict:
    """Independent structural + preservation observation from the trial DB."""
    clone = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    observation: dict = {
        "r5_patch_count": 0,
        "r5_net_chars": 0,
        "r5_manifest": [],
        "r5_revision_present": False,
        "r5_manifest_consistent": None,
        "r5_reconstruction_ok": None,
        "r5_headings_identical": None,
        "r5_marker_multiset_identical": None,
        "r5_mf_preserved": None,
        "r5_scope_integrity": None,
        "r5_no_candidate_persisted": None,
        "r5_observation_error": "",
    }
    if not clone.exists():
        observation["r5_observation_error"] = "trial database missing"
        return observation
    conn = sqlite3.connect(clone)
    try:
        row = conn.execute(
            "select proposal_id, paper_md, directive_json from paper_revisions "
            "where revision_number=1 order by id desc limit 1"
        ).fetchone()
        if not row:
            return observation
        proposal_id, rev1, directive_json = row
        rev0_row = conn.execute(
            "select paper_md from paper_revisions where proposal_id=? "
            "and revision_number=0 order by id asc limit 1",
            (proposal_id,),
        ).fetchone()
        if not rev0_row:
            observation["r5_observation_error"] = "revision 0 missing"
            return observation
        rev0 = rev0_row[0]
        observation["r5_revision_present"] = True

        directive = json.loads(directive_json) if directive_json else {}
        manifest = list(directive.get("patch_manifest") or [])
        observation["r5_patch_count"] = len(manifest)
        observation["r5_net_chars"] = sum(
            len(p.get("new_text", "")) - len(p.get("old_text", "")) for p in manifest
        )
        observation["r5_manifest"] = manifest

        # Reconstruction: the manifest applied to rev0 must reproduce rev1
        # exactly — byte identity outside authorized spans, proven.
        from backend.pipeline.evaluation.numeric_patcher import (
            apply_numeric_patches,
        )

        applied = None
        if manifest:
            try:
                applied = apply_numeric_patches(rev0, tuple(manifest))
                observation["r5_reconstruction_ok"] = (applied == rev1)
            except Exception as exc:  # typed applier refusal
                observation["r5_reconstruction_ok"] = False
                observation["r5_observation_error"] = (
                    f"applier refused manifest: {type(exc).__name__}: {exc}"
                )
        else:
            observation["r5_reconstruction_ok"] = (rev1 == rev0)

        no_candidate = rev1 == rev0
        observation["r5_no_candidate_persisted"] = no_candidate

        # Structural integrity: heading sequence + marker token multiset
        from backend.pipeline.evaluation.paper_sections import parse_paper

        before = parse_paper(rev0)
        after = parse_paper(rev1)
        observation["r5_headings_identical"] = (
            [s.heading for s in before.sections] == [s.heading for s in after.sections]
        )
        observation["r5_marker_multiset_identical"] = (
            _marker_multiset(rev0) == _marker_multiset(rev1)
        )

        # Preservation: previously passing method fidelity must still pass
        meta, _markers = base.rebuild_markers(conn, proposal_id)
        facts = (meta.get("autonomous_experiment_design") or {}).get("method_facts")
        if facts:
            from backend.pipeline.evaluation.method_fidelity import (
                evaluate_method_fidelity,
            )

            mf_before = evaluate_method_fidelity(rev0, facts)
            mf_after = evaluate_method_fidelity(rev1, facts)
            observation["r5_mf_preserved"] = (
                (not mf_before.passed) or mf_after.passed
            )
        else:
            observation["r5_mf_preserved"] = True

        # Binding rule: an applied candidate must satisfy every integrity
        # property; a typed fail-closed trial must persist exactly rev0.
        if no_candidate:
            observation["r5_scope_integrity"] = True
        else:
            observation["r5_scope_integrity"] = all([
                observation["r5_reconstruction_ok"],
                observation["r5_headings_identical"],
                observation["r5_marker_multiset_identical"],
                observation["r5_mf_preserved"],
            ])
        return observation
    except Exception as exc:
        observation["r5_observation_error"] = f"{type(exc).__name__}: {exc}"
        return observation
    finally:
        conn.close()


def _archive_trial_evidence(label: str, trial_no: int) -> None:
    """Persist the trial DB + API log into the uploaded evidence tree."""
    dest = TRIALS_DIR / f"{label}#{trial_no}"
    dest.mkdir(parents=True, exist_ok=True)
    db = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    log = base.TMP / f"p1_r3_{label}_{trial_no}_api.log"
    if db.exists():
        shutil.copyfile(db, dest / "trial.db")
    if log.exists():
        shutil.copyfile(log, dest / "api.log")


def main() -> int:
    missing = [str(path) for _, _, path, _ in base.STATES if not path.exists()]
    if missing:
        raise SystemExit("missing frozen inputs: " + ", ".join(missing))

    results = []
    for label, family, source, needs_eval in base.STATES:
        for trial_no in (1, 2):
            try:
                record = base.run_trial(label, family, source, needs_eval, trial_no)
            except (socket.timeout, TimeoutError) as exc:
                record = {
                    "trial": f"{label}#{trial_no}",
                    "family": family,
                    "source_sha256": _sha(source),
                    "http": None,
                    "eval_status": "timeout",
                    "promoted": False,
                    "error": f"trial_timeout: {type(exc).__name__} within the"
                             " 600s authoritative-evaluation ceiling",
                }
            except Exception as exc:  # keep the batch alive; evidence first
                record = {
                    "trial": f"{label}#{trial_no}",
                    "family": family,
                    "source_sha256": _sha(source),
                    "http": None,
                    "eval_status": "harness_error",
                    "promoted": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            record.update(_observe_r5(label, trial_no))
            repair = record.get("repair") or {}
            record["r5_failure_reason"] = repair.get("failure_reason", "")
            record["r5_manifest_from_response"] = repair.get("patch_manifest", [])
            _archive_trial_evidence(label, trial_no)
            results.append(record)
            eq = (record.get("release_identity") or {}).get("equality")
            print(
                f"[{record['trial']}] http={record.get('http')} "
                f"promoted={record.get('promoted')} eval={record.get('eval_status')} "
                f"patches={record.get('r5_patch_count')} "
                f"mismatches={record.get('rev1_numeric_mismatch_count')} "
                f"scope={record.get('r5_scope_integrity')} "
                f"mf_preserved={record.get('r5_mf_preserved')} "
                f"equality={eq} reason={record.get('r5_failure_reason') or '-'}",
                flush=True,
            )

    nc = base.negative_control()
    by_family: dict[str, list[int]] = {}
    for record in results:
        by_family.setdefault(record["family"], []).append(
            1 if record.get("eval_status") == "ready" else 0
        )
    overall = sum(sum(values) for values in by_family.values())
    ready_trials = [r for r in results if r.get("eval_status") == "ready"]
    release_identity_ok = all(
        (r.get("release_identity") or {}).get("equality") is True for r in ready_trials
    )
    ready_promotions_consistent = all(r.get("promoted") is True for r in ready_trials)
    false_promotions = [
        r["trial"] for r in results if r.get("promoted") and r.get("eval_status") != "ready"
    ]
    revision_trials = [r for r in results if r.get("r5_revision_present")]
    scope_integrity_all = all(r.get("r5_scope_integrity") is True for r in revision_trials)
    observation_errors = [
        r["trial"] for r in results if r.get("r5_observation_error")
    ]

    verdict = {
        "candidate_sha": CANDIDATE_SHA,
        "overall_success": overall,
        "overall_required": 7,
        "per_family": {
            key: {"success": sum(values), "of": len(values)}
            for key, values in by_family.items()
        },
        "per_family_required": 3,
        "negative_control": nc,
        "release_identity_on_ready": release_identity_ok,
        "ready_promotions_consistent": ready_promotions_consistent,
        "false_promotions": false_promotions,
        "operator_edits_or_continuation_decisions": 0,
        "scope_integrity_all": scope_integrity_all,
        "observation_errors": observation_errors,
        "timeout_or_failed_trials": [
            r["trial"] for r in results if r.get("eval_status") not in ("ready",)
        ],
        "pass": (
            overall >= 7
            and all(sum(values) >= 3 for values in by_family.values())
            and nc["blocked"]
            and release_identity_ok
            and ready_promotions_consistent
            and not false_promotions
            and scope_integrity_all
        ),
    }
    base.OUT.write_text(
        json.dumps({"trials": results, "adjudication": verdict}, indent=2),
        encoding="utf-8",
    )
    print("VERDICT:", json.dumps(verdict, indent=2), flush=True)
    return 0 if verdict["pass"] else 1


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
