"""Productive-1 R4 frozen 8-trial qualification.

Execution-only wrapper around the previously frozen R3 qualification harness.
It preserves the same four blocked states, two byte-identical restores per
state, provider/model assignment, one repair POST per fresh API process,
negative control, family thresholds, and E == F == R == H release identity.

R4 adds observation only: which paper sections changed, whether any changed
section falls outside the defect-scoped target set recomputed from the frozen
inputs, and whether a ready candidate still contains an unsupported empirical
claim in Abstract/Conclusion. No product behavior is changed here.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_PATH = Path(__file__).with_name("p1_r4_qualify_base.py")

spec = importlib.util.spec_from_file_location("p1_r4_qualify_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load frozen qualification base")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.INPUT = ROOT / ".r4_qual_inputs"
base.TMP = ROOT / ".r4_qual_tmp"
base.TMP.mkdir(exist_ok=True)
base.OUT = ROOT / "evidence/productive1_r4/p1_r4_qualification.json"
base.OUT.parent.mkdir(parents=True, exist_ok=True)
base.STATES = [
    ("calib-A", "calibration", base.INPUT / "calib-A_runfail3.db", False),
    ("calib-B", "calibration", base.INPUT / "calib-B_runfail2.db", True),
    ("regr-A", "regression", base.INPUT / "regr-A_case3a.db", True),
    ("regr-B", "regression", base.INPUT / "regr-B_3E_era.db", True),
]

CANDIDATE_SHA = "98b7853407cc52ef7836d9edc4c44a2417b4a1e3"


def _section_map(paper_md: str) -> dict[str, str]:
    from backend.pipeline.evaluation.paper_sections import parse_paper

    parsed = parse_paper(paper_md)
    return {section.name: section.full_text for section in parsed.sections}


def _observe_r4(label: str, trial_no: int) -> dict:
    clone = base.TMP / f"p1_r3_{label}_{trial_no}.db"
    observation = {
        "r4_revision_present": False,
        "r4_target_sections": [],
        "r4_changed_sections": [],
        "r4_changed_outside_targets": [],
        "r4_scope_integrity": True,
        "r4_unbacked_empirical_sections": [],
    }
    if not clone.exists():
        observation["r4_observation_error"] = "trial database missing"
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
            observation["r4_observation_error"] = "revision 0 missing"
            return observation
        rev0 = rev0_row[0]
        observation["r4_revision_present"] = True

        before, after = _section_map(rev0), _section_map(rev1)
        names = sorted(set(before) | set(after))
        changed = [name for name in names if before.get(name) != after.get(name)]
        observation["r4_changed_sections"] = changed

        directive = json.loads(directive_json) if directive_json else {}
        meta, markers = base.rebuild_markers(conn, proposal_id)
        design = meta.get("autonomous_experiment_design") or {}
        spec0 = (design.get("specs") or [{}])[0]

        from backend.pipeline.evaluation.claim_alignment import evaluate_claim_alignment
        from backend.pipeline.evaluation.paper_remediator import (
            _derive_repair_sections,
            _unbacked_sections,
        )

        claim_result = evaluate_claim_alignment(
            paper_md=rev0,
            spec_method=spec0.get("analysis_method", ""),
            spec_dataset=spec0.get("dataset", {}).get("name", ""),
            spec_baseline=spec0.get("baseline_method", ""),
            spec_comparison=spec0.get("comparison_method", ""),
        )
        targets = _derive_repair_sections(
            rev0,
            list(directive.get("blocking_findings") or []),
            tuple(directive.get("numeric_repair_targets") or []),
            base.marker_objects(markers),
            claim_result,
        )
        outside = sorted(set(changed) - set(targets))
        observation["r4_target_sections"] = list(targets)
        observation["r4_changed_outside_targets"] = outside
        observation["r4_scope_integrity"] = not outside
        observation["r4_unbacked_empirical_sections"] = sorted(_unbacked_sections(rev1))
        return observation
    except Exception as exc:
        observation["r4_observation_error"] = f"{type(exc).__name__}: {exc}"
        return observation
    finally:
        conn.close()


def main() -> int:
    missing = [str(path) for _, _, path, _ in base.STATES if not path.exists()]
    if missing:
        raise SystemExit("missing frozen inputs: " + ", ".join(missing))

    results = []
    for label, family, source, needs_eval in base.STATES:
        for trial_no in (1, 2):
            record = base.run_trial(label, family, source, needs_eval, trial_no)
            record.update(_observe_r4(label, trial_no))
            results.append(record)
            eq = (record.get("release_identity") or {}).get("equality")
            print(
                f"[{record['trial']}] http={record.get('http')} "
                f"promoted={record.get('promoted')} eval={record.get('eval_status')} "
                f"mismatches={record.get('rev1_numeric_mismatch_count')} "
                f"targets={record.get('directive_target_count')} equality={eq} "
                f"scope={record.get('r4_scope_integrity')} "
                f"unbacked={record.get('r4_unbacked_empirical_sections')} "
                f"error={bool(record.get('error'))}",
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
        (r.get("release_identity") or {}).get("equality") is True
        for r in ready_trials
    )
    ready_promotions_consistent = all(r.get("promoted") is True for r in ready_trials)
    no_runtime_errors = all(not r.get("error") for r in results)

    scoped_observation_ok = all(
        r.get("r4_scope_integrity") is True
        for r in results
        if r.get("r4_revision_present")
    )
    conclusion_observation_ok = all(
        not r.get("r4_unbacked_empirical_sections") for r in ready_trials
    )
    observation_errors = [
        r["trial"] for r in results if r.get("r4_observation_error")
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
        "operator_edits_or_continuation_decisions": 0,
        "runtime_errors": [r["trial"] for r in results if r.get("error")],
        "r4_observation": {
            "scoped_change_integrity": scoped_observation_ok,
            "conclusion_support_on_ready": conclusion_observation_ok,
            "observation_errors": observation_errors,
        },
        "pass": (
            overall >= 7
            and all(sum(values) >= 3 for values in by_family.values())
            and nc["blocked"]
            and release_identity_ok
            and ready_promotions_consistent
            and no_runtime_errors
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
