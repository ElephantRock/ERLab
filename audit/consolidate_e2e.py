#!/usr/bin/env python3
"""Consolidate ERLab v1.0.1 E2E artifacts into bounded audit deliverables."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("EVIDENCE_ROOT", "evidence-collected")).resolve()
OUT = Path(os.environ.get("FINAL_EVIDENCE_DIR", "evidence-final")).resolve()
OUT.mkdir(parents=True, exist_ok=True)


def load_reports() -> list[dict[str, Any]]:
    reports = []
    for path in sorted(ROOT.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and ("scenarios" in data or "commands" in data):
            data["_source_file"] = str(path.relative_to(ROOT))
            reports.append(data)
    return reports


BLOCKER_NAMES = {
    "backend_selected_suite",
    "migration_fresh_database",
    "frontend_tests",
    "frontend_typescript_budget",
    "frontend_build",
    "api_dev_no_auth_startup",
    "api_restart_startup",
    "api_key_boundary",
    "production_default_secret_rejected",
    "registered_spec_inventory",
    "registered_spec_loading",
    "integrated_registered_runner",
    "iris_logistic_reproduction",
    "concrete_linear_reproduction",
    "wine_random_forest_reproduction",
    "secure_entrypoint_integration",
    "provenance_all_emitted_markers_resolve",
    "typed_composer_default_path_wiring",
    "typed_composer_provider_content_rejection",
    "concurrent_run_failure_isolation_static",
    "literature_merge_dedup_state",
    "ui_dashboard_dev_auth",
    "ui_pipeline_new",
    "ui_runtime_errors",
}

IMPROVEMENT_NAMES = {
    "release_version_inventory",
    "api_health_version",
    "cli_version",
    "concrete_dependency_contract",
    "experiment_spec_roundtrip_fields",
}

CLAIM_RULES = {
    "Clean installation and database bootstrap": ["package_install", "migration_fresh_database", "database_schema_inventory"],
    "Selected backend verification suite passes": ["backend_selected_suite"],
    "Frontend tests, type budget, and build pass": ["frontend_tests", "frontend_typescript_budget", "frontend_build"],
    "Core API starts, restarts, and exposes durable state": ["api_dev_no_auth_startup", "api_restart_startup", "api_runs_after_restart"],
    "Authentication boundaries operate as documented": ["api_key_boundary", "production_default_secret_rejected"],
    "Frozen registered experiments execute through the product runner": ["integrated_registered_runner"],
    "Iris, Concrete, and nonlinear Wine analyses reproduce exactly": ["iris_logistic_reproduction", "concrete_linear_reproduction", "wine_random_forest_reproduction"],
    "Every emitted SOURCE marker resolves before ready state": ["provenance_all_emitted_markers_resolve"],
    "Empirical paper values and RESULT attribution enter only through deterministic composition": ["typed_composer_default_path_wiring", "typed_composer_provider_content_rejection"],
    "Registered experiment execution enforces secure frozen entrypoints": ["secure_entrypoint_integration"],
    "Concurrent run failures cannot mutate another run": ["concurrent_run_failure_isolation_static"],
    "Browser routes render without runtime errors": ["ui_dashboard_dev_auth", "ui_pipeline_new", "ui_runtime_errors"],
}


def normalize(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for report in reports:
        source = report.get("_source_file", "unknown")
        for s in report.get("scenarios", []):
            row = dict(s)
            row["source_file"] = source
            rows.append(row)
        for c in report.get("commands", []):
            row = dict(c)
            row.setdefault("classification", "verification")
            row["source_file"] = source
            rows.append(row)
    return rows


def severity(row: dict[str, Any]) -> str:
    if row.get("status") in {"pass"}:
        return "verified"
    name = row.get("name", "")
    if row.get("status") == "skip":
        return "unverified"
    if name in BLOCKER_NAMES:
        return "blocker"
    if name in IMPROVEMENT_NAMES:
        return "improvement"
    return "improvement"


def claim_verdict(rows_by_name: dict[str, list[dict[str, Any]]], required: list[str]) -> tuple[str, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    statuses: list[str] = []
    for name in required:
        candidates = rows_by_name.get(name, [])
        if not candidates:
            statuses.append("missing")
            evidence.append({"name": name, "status": "missing"})
            continue
        # Prefer fail/error over pass so conflicting evidence cannot be hidden.
        order = {"error": 0, "fail": 1, "skip": 2, "pass": 3}
        chosen = sorted(candidates, key=lambda x: order.get(x.get("status", "error"), 0))[0]
        statuses.append(chosen.get("status", "error"))
        evidence.append({"name": name, "status": chosen.get("status"), "source_file": chosen.get("source_file")})
    if any(s in {"fail", "error"} for s in statuses):
        return "contradicted", evidence
    if any(s in {"missing", "skip"} for s in statuses):
        return "unverified", evidence
    return "verified", evidence


def main() -> int:
    reports = load_reports()
    rows = normalize(reports)
    for row in rows:
        row["severity"] = severity(row)

    rows_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_name.setdefault(row.get("name", "unknown"), []).append(row)

    claims = []
    for claim, required in CLAIM_RULES.items():
        verdict, evidence = claim_verdict(rows_by_name, required)
        claims.append({"claim": claim, "verdict": verdict, "evidence": evidence})

    summary = {
        "scenario_count": len(rows),
        "pass": sum(r.get("status") == "pass" for r in rows),
        "fail": sum(r.get("status") == "fail" for r in rows),
        "error": sum(r.get("status") == "error" for r in rows),
        "skip": sum(r.get("status") == "skip" for r in rows),
        "blockers": sum(r.get("severity") == "blocker" for r in rows),
        "improvements": sum(r.get("severity") == "improvement" for r in rows),
        "verified_claims": sum(c["verdict"] == "verified" for c in claims),
        "contradicted_claims": sum(c["verdict"] == "contradicted" for c in claims),
        "unverified_claims": sum(c["verdict"] == "unverified" for c in claims),
    }

    matrix = {
        "baseline_tag": "v1.0.1",
        "baseline_commit": "56ff0e69ba787232252d5e9612330531db330e0c",
        "mode": "read-only product validation from audit-only branch",
        "summary": summary,
        "scenarios": rows,
        "claims": claims,
        "source_reports": [r.get("_source_file") for r in reports],
    }
    (OUT / "E2E_EXECUTION_MATRIX.json").write_text(json.dumps(matrix, indent=2, default=str), encoding="utf-8")

    report = [
        "# ERLab v1.0.1 Comprehensive E2E Verdict",
        "",
        "**Product baseline:** `v1.0.1` / `56ff0e69ba787232252d5e9612330531db330e0c`",
        "",
        "The product tree was not modified. Validation tooling exists only on `audit/v1.0.1-e2e`.",
        "",
        "## Execution summary",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "## Product-claim verdicts",
        "",
        "| Product claim | Verdict |",
        "|---|---:|",
    ]
    report.extend(f"| {c['claim']} | **{c['verdict'].upper()}** |" for c in claims)
    report.extend(["", "## Release decision rule", ""])
    if summary["blockers"]:
        report.append("**E2E acceptance is NOT MET. Development remains paused pending review of the blocker ledger.**")
    elif summary["unverified_claims"] or summary["contradicted_claims"]:
        report.append("**E2E acceptance is PARTIALLY MET. No development should begin until unverified or contradicted claims are dispositioned.**")
    else:
        report.append("**E2E acceptance is MET for the executed matrix.**")
    report.append("")
    (OUT / "E2E_FINAL_REPORT.md").write_text("\n".join(report), encoding="utf-8")

    defects = [r for r in rows if r["severity"] in {"blocker", "improvement"}]
    defect_lines = [
        "# ERLab v1.0.1 Defect Ledger",
        "",
        "| Severity | Scenario | Status | Evidence |",
        "|---|---|---:|---|",
    ]
    for r in defects:
        defect_lines.append(f"| {r['severity'].upper()} | `{r.get('name')}` | {str(r.get('status')).upper()} | `{r.get('source_file')}` |")
    defect_lines.append("")
    (OUT / "DEFECT_LEDGER.md").write_text("\n".join(defect_lines), encoding="utf-8")

    chain_names = [
        "registered_spec_inventory", "registered_spec_loading", "secure_entrypoint_integration",
        "integrated_registered_runner", "iris_logistic_reproduction", "concrete_linear_reproduction",
        "wine_random_forest_reproduction", "typed_composer_default_path_wiring",
        "typed_composer_provider_content_rejection", "provenance_all_emitted_markers_resolve",
        "api_restart_state_readable",
    ]
    chain_lines = [
        "# ERLab v1.0.1 Evidence-Chain Ledger",
        "",
        "| Boundary | Status | Evidence |",
        "|---|---:|---|",
    ]
    for name in chain_names:
        candidates = rows_by_name.get(name, [])
        if not candidates:
            chain_lines.append(f"| `{name}` | **UNVERIFIED** | no scenario result |")
        else:
            chosen = candidates[0]
            chain_lines.append(f"| `{name}` | **{str(chosen.get('status')).upper()}** | `{chosen.get('source_file')}` |")
    chain_lines.append("")
    (OUT / "EVIDENCE_CHAIN_LEDGER.md").write_text("\n".join(chain_lines), encoding="utf-8")

    claim_lines = [
        "# ERLab v1.0.1 Product-Claim Verdict",
        "",
        "| Claim | Verdict | Required scenarios |",
        "|---|---:|---|",
    ]
    for c in claims:
        required = ", ".join(f"`{e['name']}`" for e in c["evidence"])
        claim_lines.append(f"| {c['claim']} | **{c['verdict'].upper()}** | {required} |")
    claim_lines.append("")
    (OUT / "PRODUCT_CLAIM_VERDICT.md").write_text("\n".join(claim_lines), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
