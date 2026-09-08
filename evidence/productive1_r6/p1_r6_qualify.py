"""Productive-1 R6 frozen 8-trial qualification (execution-only).

Authorized objective (owner, 2026-08-31): execution-only qualification
against the exact frozen candidate
8b0664b8b29995c665cbc55f2ebd278ce39f1d3b under the frozen R6 contract
(evidence/productive1_r6/r6_charter.md). Four frozen blocked states x
two byte-identical restores; one cold /paper/repair POST per fresh API
process through the unchanged PAC authoritative path.

Binding verdict (wired at freeze):
  - >=7/8 overall and >=3/4 per family (trial success = authoritative
    eval_status == "ready")
  - negative control blocked (zero negative-control promotions)
  - E == F == R == H on every ready trial; promoted implies ready
  - scope integrity MANDATORY: the persisted revision-1 bytes are
    exactly the combined manifest (numeric + R-REMOVE) applied to
    revision 0 — with identical heading sequence, RESULT/SOURCE token
    multiset, and preserved previously-passing method fidelity — OR the
    persisted bytes are exactly revision 0 (typed fail-closed path)
  - ZERO screening/authority conclusion-support disagreement on all
    eight trials (the canonical shared rule must classify identically
    in the pure gate screen and the authoritative stamp)

Timeout policy: 600 seconds is the authoritative evaluation/provider
ceiling; a timed-out trial is an ordinary failed trial, no carve-out.

Evidence completeness per trial: the trial database (rev0/rev1 bytes),
the API server log, numeric patch manifest, R-REMOVE manifest with the
exact removed-sentence hash, pre/post canonical conclusion-support
classification, reconstruction proof, gate state, authoritative stamp,
release identity, and the typed failure reason — archived under
evidence/productive1_r6/trials/ and uploaded by the workflow.

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
BASE_PATH = Path(__file__).with_name("p1_r6_qualify_base.py")

spec = importlib.util.spec_from_file_location("p1_r6_qualify_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load frozen qualification base")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.INPUT = ROOT / ".r6_qual_inputs"
base.TMP = ROOT / ".r6_qual_tmp"
base.TMP.mkdir(exist_ok=True)
base.OUT = ROOT / "evidence/productive1_r6/p1_r6_qualification.json"
base.OUT.parent.mkdir(parents=True, exist_ok=True)
base.STATES = [
    ("calib-A", "calibration", base.INPUT / "calib-A_runfail3.db", False),
    ("calib-B", "calibration", base.INPUT / "calib-B_runfail2.db", True),
    ("regr-A", "regression", base.INPUT / "regr-A_case3a.db", True),
    ("regr-B", "regression", base.INPUT / "regr-B_3E_era.db", True),
]

CANDIDATE_SHA = "8b0664b8b29995c665cbc55f2ebd278ce39f1d3b"
TRIALS_DIR = ROOT / "evidence/productive1_r6/trials"
TRIALS_DIR.mkdir(parents=True, exist_ok=True)

# Frozen timeout policy (owner decision #3): 600s is the authoritative
# evaluation/provider ceiling. The base default of 900s is overridden.
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


def _conclusion_gate(gates: list[dict]) -> dict | None:
    for gate in gates or []:
        if gate.get("gate") == "conclusion_support":
            return gate
    return None


def _observe_r6(label: str, trial_no: int) -> dict:
    """Independent R6 observation from the trial database."""
    clone = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    observation: dict = {
        "r6_patch_count": 0,
        "r6_removal_count": 0,
        "r6_removals": [],
        "r6_removed_sentence_sha256": [],
        "r6_pre_classification": None,
        "r6_post_classification": None,
        "r6_revision_present": False,
        "r6_reconstruction_ok": None,
        "r6_headings_identical": None,
        "r6_marker_multiset_identical": None,
        "r6_mf_preserved": None,
        "r6_scope_integrity": None,
        "r6_no_candidate_persisted": None,
        "r6_observation_error": "",
    }
    if not clone.exists():
        observation["r6_observation_error"] = "trial database missing"
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
            observation["r6_observation_error"] = "revision 0 missing"
            return observation
        rev0 = rev0_row[0]
        observation["r6_revision_present"] = True

        directive = json.loads(directive_json) if directive_json else {}
        numeric = list(directive.get("patch_manifest") or [])
        removals = list(directive.get("conclusion_removals") or [])
        observation["r6_patch_count"] = len(numeric)
        observation["r6_removal_count"] = len(removals)
        observation["r6_removals"] = removals
        observation["r6_removed_sentence_sha256"] = [
            r.get("sentence_sha256", "") for r in removals
        ]
        observation["r6_pre_classification"] = directive.get(
            "conclusion_pre_classification"
        )
        observation["r6_post_classification"] = directive.get(
            "conclusion_post_classification"
        )

        from backend.pipeline.evaluation.numeric_patcher import (
            apply_combined_patches,
        )

        if numeric or removals:
            try:
                applied = apply_combined_patches(
                    rev0, tuple(numeric), tuple(removals))
                observation["r6_reconstruction_ok"] = (applied == rev1)
            except Exception as exc:
                observation["r6_reconstruction_ok"] = False
                observation["r6_observation_error"] = (
                    f"applier refused manifest: {type(exc).__name__}: {exc}"
                )
        else:
            observation["r6_reconstruction_ok"] = (rev1 == rev0)

        no_candidate = rev1 == rev0
        observation["r6_no_candidate_persisted"] = no_candidate

        from backend.pipeline.evaluation.paper_sections import parse_paper

        before = parse_paper(rev0)
        after = parse_paper(rev1)
        observation["r6_headings_identical"] = (
            [s.heading for s in before.sections] == [s.heading for s in after.sections]
        )
        observation["r6_marker_multiset_identical"] = (
            _marker_multiset(rev0) == _marker_multiset(rev1)
        )

        meta, _markers = base.rebuild_markers(conn, proposal_id)
        facts = (meta.get("autonomous_experiment_design") or {}).get("method_facts")
        if facts:
            from backend.pipeline.evaluation.method_fidelity import (
                evaluate_method_fidelity,
            )

            mf_before = evaluate_method_fidelity(rev0, facts)
            mf_after = evaluate_method_fidelity(rev1, facts)
            observation["r6_mf_preserved"] = (
                (not mf_before.passed) or mf_after.passed
            )
        else:
            observation["r6_mf_preserved"] = True

        if no_candidate:
            observation["r6_scope_integrity"] = True
        else:
            observation["r6_scope_integrity"] = all([
                observation["r6_reconstruction_ok"],
                observation["r6_headings_identical"],
                observation["r6_marker_multiset_identical"],
                observation["r6_mf_preserved"],
            ])
        return observation
    except Exception as exc:
        observation["r6_observation_error"] = f"{type(exc).__name__}: {exc}"
        return observation
    finally:
        conn.close()


def _screen_vs_authority(label: str, trial_no: int) -> dict:
    """Charter control: zero screening/authority conclusion disagreement.

    Re-runs the pure gate screen's conclusion-support classification on
    the persisted revision-1 bytes and compares it with the
    authoritative stamp's conclusion gate recorded in the trial DB.
    """
    clone = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    result = {
        "r6_screen_classification": None,
        "r6_authority_classification": None,
        "r6_conclusion_agree": None,
        "r6_parity_error": "",
    }
    if not clone.exists():
        result["r6_parity_error"] = "trial database missing"
        return result
    conn = sqlite3.connect(clone)
    try:
        row = conn.execute(
            "select proposal_id, paper_md, trigger_detail_json from paper_revisions "
            "where revision_number=1 order by id desc limit 1"
        ).fetchone()
        if not row:
            result["r6_parity_error"] = "revision 1 missing"
            return result
        proposal_id, rev1, detail_json = row
        detail = json.loads(detail_json) if detail_json else {}
        authoritative = detail.get("authoritative") or {}
        auth_gate = _conclusion_gate(authoritative.get("gates") or [])
        result["r6_authority_classification"] = (
            auth_gate.get("classification") if auth_gate else None
        )

        meta, marker_dicts = base.rebuild_markers(conn, proposal_id)
        markers = base.marker_objects(marker_dicts)
        from backend.pipeline.evaluation.paper_gate_evaluator import (
            evaluate_paper_gates,
        )

        design = meta.get("autonomous_experiment_design") or {}
        spec0 = (design.get("specs") or [{}])[0]
        screen = evaluate_paper_gates(
            paper_md=rev1, source_map=meta.get("source_map"),
            research_intent=spec0.get("research_question", ""),
            domain="machine learning", result_markers=markers,
            spec_method=spec0.get("analysis_method", ""),
            spec_dataset=spec0.get("dataset", {}).get("name", ""),
            spec_baseline=spec0.get("baseline_method", ""),
            spec_comparison=spec0.get("comparison_method", ""),
        )
        screen_gate = _conclusion_gate(screen.gates)
        result["r6_screen_classification"] = (
            screen_gate.get("classification") if screen_gate else None
        )
        if result["r6_screen_classification"] is not None and (
            result["r6_authority_classification"] is not None
        ):
            result["r6_conclusion_agree"] = (
                result["r6_screen_classification"]
                == result["r6_authority_classification"]
            )
        elif result["r6_screen_classification"] is not None:
            # No authoritative stamp on this trial (failed/blocked
            # before evaluation): the charter's disagreement control
            # applies to evaluated trials; record the screen verdict.
            result["r6_conclusion_agree"] = True
        else:
            result["r6_parity_error"] = "screen produced no conclusion gate"
        return result
    except Exception as exc:
        result["r6_parity_error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        conn.close()


def _archive_trial_evidence(label: str, trial_no: int) -> None:
    dest = TRIALS_DIR / f"{label}#{trial_no}"
    dest.mkdir(parents=True, exist_ok=True)
    db = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    log = base.TMP / f"p1_r3_{label}_{trial_no}_api.log"
    if db.exists():
        shutil.copyfile(db, dest / "trial.db")
    if log.exists():
        shutil.copyfile(log, dest / "api.log")


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                    "trial": f"{label}#{trial_no}", "family": family,
                    "source_sha256": _sha(source), "http": None,
                    "eval_status": "timeout", "promoted": False,
                    "error": f"trial_timeout: {type(exc).__name__} within the"
                             " 600s authoritative-evaluation ceiling",
                }
            except Exception as exc:
                record = {
                    "trial": f"{label}#{trial_no}", "family": family,
                    "source_sha256": _sha(source), "http": None,
                    "eval_status": "harness_error", "promoted": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            record.update(_observe_r6(label, trial_no))
            record.update(_screen_vs_authority(label, trial_no))
            repair = record.get("repair") or {}
            record["r6_failure_reason"] = repair.get("failure_reason", "")
            record["r6_manifest_from_response"] = repair.get("patch_manifest", [])
            record["r6_removals_from_response"] = repair.get(
                "conclusion_removals", [])
            _archive_trial_evidence(label, trial_no)
            results.append(record)
            eq = (record.get("release_identity") or {}).get("equality")
            print(
                f"[{record['trial']}] http={record.get('http')} "
                f"promoted={record.get('promoted')} eval={record.get('eval_status')} "
                f"patches={record.get('r6_patch_count')} "
                f"removals={record.get('r6_removal_count')} "
                f"pre={record.get('r6_pre_classification')} "
                f"post={record.get('r6_post_classification')} "
                f"scope={record.get('r6_scope_integrity')} "
                f"agree={record.get('r6_conclusion_agree')} "
                f"equality={eq} reason={record.get('r6_failure_reason') or '-'}",
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
        r["trial"] for r in results
        if r.get("promoted") and r.get("eval_status") != "ready"
    ]
    revision_trials = [r for r in results if r.get("r6_revision_present")]
    scope_integrity_all = all(
        r.get("r6_scope_integrity") is True for r in revision_trials)
    conclusion_disagreements = [
        r["trial"] for r in results if r.get("r6_conclusion_agree") is not True
    ]
    observation_errors = [
        r["trial"] for r in results
        if r.get("r6_observation_error") or r.get("r6_parity_error")
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
        "conclusion_disagreements": conclusion_disagreements,
        "observation_errors": observation_errors,
        "not_ready_trials": [
            r["trial"] for r in results if r.get("eval_status") != "ready"
        ],
        "pass": (
            overall >= 7
            and all(sum(values) >= 3 for values in by_family.values())
            and nc["blocked"]
            and release_identity_ok
            and ready_promotions_consistent
            and not false_promotions
            and scope_integrity_all
            and not conclusion_disagreements
        ),
    }
    base.OUT.write_text(
        json.dumps({"trials": results, "adjudication": verdict}, indent=2),
        encoding="utf-8",
    )
    print("VERDICT:", json.dumps(verdict, indent=2), flush=True)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
