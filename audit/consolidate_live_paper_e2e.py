#!/usr/bin/env python3
"""Consolidate the live paper-production E2E into a truthful verdict."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", "evidence/live-paper"))


def load(name: str) -> Any:
    path = EVIDENCE / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def check(name: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "evidence": evidence}


def main() -> int:
    provider = load("provider_selection.json") or {}
    live = load("live_run_result.json") or {}
    assessment = load("generated_paper_assessment.json") or {}
    exports = load("exports_before_restart.json") or {}
    restart = load("restart_verification.json") or {}
    browser = load("browser_verification.json") or {}
    trigger = load("pipeline_trigger_response.json") or {}

    export_ok = bool(exports) and all(
        isinstance(exports.get(fmt), dict)
        and exports[fmt].get("status") == 200
        and exports[fmt].get("bytes", 0) > 0
        for fmt in ("markdown", "latex", "bibtex")
    )
    section_presence = assessment.get("required_section_presence") or {}
    required_sections_ok = all(section_presence.get(name) for name in ("abstract", "introduction", "discussion", "conclusion"))
    checks = [
        check("provider_credential_available", bool(provider.get("credentials_present")), provider),
        check("pipeline_trigger_accepted", trigger.get("status") in {200, 202}, trigger),
        check("pipeline_terminal_completed", live.get("run_status") == "completed", live),
        check("complete_paper_persisted", live.get("status") == "paper_produced" and assessment.get("word_count", 0) >= 500, {
            "status": live.get("status"),
            "word_count": assessment.get("word_count"),
        }),
        check("paper_has_required_structure", required_sections_ok, section_presence),
        check("production_evaluation_persisted", bool(assessment.get("evaluation_present")), {
            "evaluation_present": assessment.get("evaluation_present"),
            "gate_count": assessment.get("gate_count"),
            "meta_status": assessment.get("meta_status"),
            "evaluation": assessment.get("evaluation"),
        }),
        check("all_emitted_source_markers_resolve", not assessment.get("source_markers_unresolved"), {
            "emitted": assessment.get("source_markers_emitted"),
            "unresolved": assessment.get("source_markers_unresolved"),
        }),
        check("paper_exports_succeed", export_ok, exports),
        check("restart_persistence_stable", restart.get("status") == "pass", restart),
        check("browser_retrieval_succeeds", browser.get("status") == "pass", browser),
    ]
    failures = [item for item in checks if item["status"] == "fail"]
    verdict = "MET" if not failures else "NOT_MET"
    result = {
        "verdict": verdict,
        "scope": "live literature-to-paper product E2E without registered empirical execution",
        "product_baseline": "v1.0.1 / 56ff0e69ba787232252d5e9612330531db330e0c",
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
        "explicit_boundaries": [
            "No registered empirical experiment was requested because the sealed release lacks clean-clone-loadable experiment specifications.",
            "This verdict proves or falsifies live paper production and evaluation; it does not repair or waive the prior empirical-path blockers.",
            "Provider credentials were consumed only through GitHub Actions secrets and were not written to evidence artifacts.",
        ],
    }
    (EVIDENCE / "live_paper_e2e_verdict.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# ERLab v1.0.1 Live Paper-Production E2E",
        "",
        f"**Verdict: {verdict}**",
        "",
        f"Product baseline: `{result['product_baseline']}`",
        "",
        "## Acceptance checks",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for item in checks:
        lines.append(f"| {item['name']} | {item['status'].upper()} |")
    lines.extend(["", "## Explicit boundaries", ""])
    for boundary in result["explicit_boundaries"]:
        lines.append(f"- {boundary}")
    if failures:
        lines.extend(["", "## Failed checks", ""])
        for item in failures:
            lines.append(f"- **{item['name']}**")
    (EVIDENCE / "LIVE_PAPER_E2E_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if verdict == "MET" else 1


if __name__ == "__main__":
    raise SystemExit(main())
