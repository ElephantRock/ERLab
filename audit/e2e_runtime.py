#!/usr/bin/env python3
"""Read-only runtime/API E2E harness for sealed ERLab v1.0.1.

This file lives only on the audit branch. It does not patch product code.
All product execution occurs against the v1.0.1 tree plus audit-only files.
"""
from __future__ import annotations

import inspect
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", ROOT / "evidence" / "runtime"))
EVIDENCE.mkdir(parents=True, exist_ok=True)


@dataclass
class Scenario:
    name: str
    status: str
    details: dict[str, Any]
    classification: str = "verification"


SCENARIOS: list[Scenario] = []


def add(name: str, status: str, details: dict[str, Any], classification: str = "verification") -> None:
    SCENARIOS.append(Scenario(name, status, details, classification))


def run_cmd(name: str, cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=ROOT,
            env=merged,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        output_path = EVIDENCE / f"{name}.log"
        output_path.write_text(cp.stdout or "", encoding="utf-8")
        add(
            name,
            "pass" if cp.returncode == 0 else "fail",
            {
                "command": cmd,
                "returncode": cp.returncode,
                "duration_seconds": round(time.time() - started, 3),
                "log": str(output_path.relative_to(EVIDENCE.parent)),
            },
        )
        return cp
    except Exception as exc:
        output_path = EVIDENCE / f"{name}.log"
        output_path.write_text(traceback.format_exc(), encoding="utf-8")
        add(name, "error", {"command": cmd, "error": repr(exc), "log": str(output_path)})
        return subprocess.CompletedProcess(cmd, 999, "")


def wait_http(url: str, proc: subprocess.Popen[str], timeout: float = 40.0) -> tuple[bool, str]:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, f"process exited rc={proc.returncode}"
        try:
            response = httpx.get(url, timeout=2.0)
            return True, f"status={response.status_code}"
        except Exception as exc:
            last = repr(exc)
            time.sleep(0.5)
    return False, last or "timeout"


def start_server(name: str, port: int, env: dict[str, str]) -> tuple[subprocess.Popen[str], Path, bool, str]:
    log_path = EVIDENCE / f"{name}.server.log"
    log_fh = log_path.open("w", encoding="utf-8")
    merged = os.environ.copy()
    merged.update(env)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
        cwd=ROOT,
        env=merged,
        text=True,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    ready, reason = wait_http(f"http://127.0.0.1:{port}/health", proc)
    add(name + "_startup", "pass" if ready else "fail", {"ready": ready, "reason": reason, "pid": proc.pid, "log": str(log_path)})
    return proc, log_path, ready, reason


def stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def http_scenario(name: str, method: str, url: str, **kwargs: Any) -> httpx.Response | None:
    try:
        response = httpx.request(method, url, timeout=30.0, **kwargs)
        body = response.text
        (EVIDENCE / f"{name}.body.txt").write_text(body, encoding="utf-8")
        add(
            name,
            "pass" if response.status_code < 500 else "fail",
            {
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "headers": {k: v for k, v in response.headers.items() if k.lower() not in {"set-cookie", "authorization"}},
                "body_file": f"{name}.body.txt",
            },
        )
        return response
    except Exception as exc:
        add(name, "error", {"method": method, "url": url, "error": repr(exc)})
        return None


def check_versions() -> None:
    try:
        pkg = version("elephant-rock")
    except PackageNotFoundError:
        pkg = "not-installed"
    package_json = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    app_source = (ROOT / "backend" / "api" / "app.py").read_text(encoding="utf-8")
    add(
        "release_version_inventory",
        "pass" if pkg == "1.0.1" else "fail",
        {
            "python_package": pkg,
            "frontend_package": package_json.get("version"),
            "fastapi_contains_0_1_0": 'version="0.1.0"' in app_source,
            "health_contains_0_1_0": '"version": "0.1.0"' in app_source,
        },
        "release_truthfulness",
    )


def check_database() -> None:
    db_url = os.environ.get("EROCK_DATABASE_URL", "")
    path: Path | None = None
    if db_url.startswith("sqlite:///"):
        raw = db_url.removeprefix("sqlite:///")
        path = Path("/" + raw.lstrip("/")) if raw.startswith("/") else ROOT / raw
    if not path or not path.exists():
        add("database_schema_inventory", "fail", {"database_url": db_url, "resolved": str(path) if path else None})
        return
    con = sqlite3.connect(path)
    try:
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
        alembic = list(con.execute("select version_num from alembic_version")) if "alembic_version" in tables else []
        required = {"pipeline_runs", "proposals", "experiment_results", "paper_source_markers", "paper_revisions"}
        add(
            "database_schema_inventory",
            "pass" if required.issubset(set(tables)) else "fail",
            {"path": str(path), "table_count": len(tables), "missing_required": sorted(required - set(tables)), "alembic_version": alembic},
        )
    finally:
        con.close()


def check_specs_and_static_invariants() -> None:
    spec_files = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("data/datasets/**/spec*.json"))
    meta_files = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("data/datasets/**/dataset_meta.json"))
    add(
        "registered_spec_inventory",
        "pass" if spec_files else "fail",
        {"spec_count": len(spec_files), "spec_files": spec_files, "dataset_meta_count": len(meta_files), "dataset_meta_files": meta_files},
        "reproducibility",
    )

    try:
        from backend.pipeline.experiment.specification import ExperimentSpec, load_spec

        known_ids = ["phase5-pilot-v1", "phase8-g1-wine", "phase8-g2-concrete", "phase14-rf-wine"]
        loaded: dict[str, Any] = {}
        for spec_id in known_ids:
            try:
                spec = load_spec(spec_id)
                loaded[spec_id] = {"loaded": True, "dataset": spec.dataset_name, "entrypoint": spec.analysis_entrypoint}
            except Exception as exc:
                loaded[spec_id] = {"loaded": False, "error": repr(exc)}
        add("registered_spec_loading", "pass" if all(v["loaded"] for v in loaded.values()) else "fail", loaded, "reproducibility")

        sample = ExperimentSpec(
            spec_id="audit", description="audit", dataset_name="x", dataset_version="1",
            dataset_raw_filename="x.csv", dataset_raw_sha256="0" * 64,
            split_method="fixed", train_fraction=0.8, test_fraction=0.2, random_seed=42,
            analysis_entrypoint="experiments/x.py", analysis_method="Random Forest",
            declared_metrics=["accuracy"], metric_directions={"accuracy": "higher_better"},
            tolerances={"accuracy": 0.0}, output_artifacts=["metrics.json"],
            research_question="audit", model_family="random_forest", hyperparameters={"n_estimators": 100},
        )
        serialized = sample.to_dict()
        add(
            "experiment_spec_roundtrip_fields",
            "pass" if "model_family" in serialized and "hyperparameters" in serialized else "fail",
            {"serialized_keys": sorted(serialized.keys()), "model_family_present": "model_family" in serialized, "hyperparameters_present": "hyperparameters" in serialized},
            "evidence_contract",
        )
    except Exception as exc:
        add("registered_spec_runtime", "error", {"error": repr(exc), "traceback": traceback.format_exc()})

    try:
        from backend.pipeline.experiment.empirical_runner import execute_experiment, resolve_entrypoint_securely

        exec_source = inspect.getsource(execute_experiment)
        resolver_called = "resolve_entrypoint_securely(" in exec_source
        abs_result = resolve_entrypoint_securely("/tmp/not-allowed.py")
        traversal_result = resolve_entrypoint_securely("../../not-allowed.py")
        add(
            "secure_entrypoint_integration",
            "pass" if resolver_called else "fail",
            {
                "execute_calls_secure_resolver": resolver_called,
                "absolute_rejected": abs_result[0] is None,
                "traversal_rejected": traversal_result[0] is None,
            },
            "security",
        )
    except Exception as exc:
        add("secure_entrypoint_integration", "error", {"error": repr(exc)})

    try:
        from backend.pipeline.stages import LiteratureSearchStage, PaperSynthesisStage

        paper = "# Audit\n\nClaim supported by [SOURCE-99]."
        source_map = [
            {"marker_index": 1, "marker": "SOURCE-1", "source_id": "paper-1", "mapping_status": "mapped"},
            {"marker_index": 99, "marker": "SOURCE-99", "source_id": None, "mapping_status": "unmapped"},
        ]
        gate = PaperSynthesisStage.provenance_precondition(paper, source_map)
        add(
            "provenance_all_emitted_markers_resolve",
            "pass" if not gate.passed else "fail",
            {"gate_passed": gate.passed, "reason": gate.reason, "unmapped_count": gate.unmapped_count},
            "evidence_contract",
        )

        lit_source = inspect.getsource(LiteratureSearchStage.execute)
        uses_seen = "seen.add(" in lit_source or "if key not in seen" in lit_source
        defines_seen = "seen =" in lit_source or "seen:" in lit_source
        add(
            "literature_merge_dedup_state",
            "pass" if not uses_seen or defines_seen else "fail",
            {"uses_seen": uses_seen, "defines_seen": defines_seen, "uses_seen_keys": "seen_keys" in lit_source},
            "runtime_correctness",
        )
    except Exception as exc:
        add("paper_and_literature_static_checks", "error", {"error": repr(exc)})

    try:
        from backend.pipeline.synthesis.typed_claim_composer import validate_provider_output

        cases = {
            "result_marker": "The model performed well [RESULT-1].",
            "achievement": "The model achieved accuracy of 0.95.",
            "bare_decimal": "The measured accuracy was 0.95 on the held-out set.",
        }
        outcomes = {k: validate_provider_output(v) for k, v in cases.items()}
        pass_condition = (not outcomes["result_marker"][0]) and (not outcomes["achievement"][0]) and (not outcomes["bare_decimal"][0])
        add(
            "typed_composer_provider_content_rejection",
            "pass" if pass_condition else "fail",
            {k: {"accepted": ok, "violations": violations} for k, (ok, violations) in outcomes.items()},
            "evidence_contract",
        )

        stage_text = (ROOT / "backend" / "pipeline" / "stages.py").read_text(encoding="utf-8")
        recovery_text = (ROOT / "backend" / "pipeline" / "experiment" / "paper_recovery.py").read_text(encoding="utf-8")
        add(
            "typed_composer_default_path_wiring",
            "pass" if "typed_claim_composer" in stage_text and "typed_claim_composer" in recovery_text else "fail",
            {"stages_imports_typed_composer": "typed_claim_composer" in stage_text, "recovery_imports_typed_composer": "typed_claim_composer" in recovery_text},
            "architecture",
        )
    except Exception as exc:
        add("typed_composer_checks", "error", {"error": repr(exc)})

    try:
        pipeline_route = (ROOT / "backend" / "api" / "routes" / "pipeline.py").read_text(encoding="utf-8")
        failure_selector = '.where(_PipelineRun.status == "running")' in pipeline_route
        exact_selector = "_PipelineRun.run_id_str == run_id" in pipeline_route
        add(
            "concurrent_run_failure_isolation_static",
            "pass" if not failure_selector else "fail",
            {"latest_running_selector_present": failure_selector, "exact_run_selector_present_elsewhere": exact_selector},
            "concurrency",
        )
    except Exception as exc:
        add("concurrent_run_failure_isolation_static", "error", {"error": repr(exc)})


def run_api_matrix() -> None:
    base_env = {
        "EROCK_ENV": "development",
        "EROCK_AUTH_ENABLED": "false",
        "EROCK_API_KEY": "",
        "EROCK_DEFAULT_PROVIDER": "openai",
        "EROCK_OPENAI_API_KEY": "",
        "EROCK_LMSTUDIO_ENABLED": "false",
    }
    proc, _, ready, _ = start_server("api_dev_no_auth", 8010, base_env)
    run_id: str | None = None
    try:
        if ready:
            health = http_scenario("api_health", "GET", "http://127.0.0.1:8010/health")
            if health is not None:
                try:
                    body = health.json()
                except Exception:
                    body = {}
                add("api_health_version", "pass" if body.get("version") == "1.0.1" else "fail", body, "release_truthfulness")
            openapi = http_scenario("api_openapi", "GET", "http://127.0.0.1:8010/openapi.json")
            if openapi is not None and openapi.status_code == 200:
                schema = openapi.json()
                paths = sorted(schema.get("paths", {}).keys())
                (EVIDENCE / "openapi_paths.json").write_text(json.dumps(paths, indent=2), encoding="utf-8")
                add("api_route_inventory", "pass", {"path_count": len(paths), "paths_file": "openapi_paths.json"})
            http_scenario("api_list_runs_dev", "GET", "http://127.0.0.1:8010/api/v1/pipeline/runs")
            http_scenario("api_estimate_fast_scan", "GET", "http://127.0.0.1:8010/api/v1/pipeline/estimate?strategy=fast_scan")
            payload = {
                "domain": "machine learning",
                "research_question": "How do deterministic evidence controls affect empirical paper integrity?",
                "strategy": "fast_scan",
                "max_gaps": 1,
                "generation_rounds": 1,
                "ideas_per_round": 1,
            }
            trigger = http_scenario("api_trigger_no_provider", "POST", "http://127.0.0.1:8010/api/v1/pipeline/run", json=payload)
            if trigger is not None:
                try:
                    trigger_body = trigger.json()
                    run_id = trigger_body.get("run_id")
                except Exception:
                    run_id = None
                add(
                    "api_trigger_truthful_no_provider_state",
                    "pass" if trigger.status_code in {202, 503} else "fail",
                    {"status_code": trigger.status_code, "run_id": run_id},
                    "failure_handling",
                )
                time.sleep(3)
                http_scenario("api_runs_after_trigger", "GET", "http://127.0.0.1:8010/api/v1/pipeline/runs")
    finally:
        stop_server(proc)

    # Restart against the same durable DB and confirm API state is readable.
    proc2, _, ready2, _ = start_server("api_restart", 8011, base_env)
    try:
        if ready2:
            runs = http_scenario("api_runs_after_restart", "GET", "http://127.0.0.1:8011/api/v1/pipeline/runs")
            found = False
            if runs is not None and run_id:
                try:
                    found = any(str(r.get("run_id", r.get("id"))) == str(run_id) for r in runs.json().get("runs", []))
                except Exception:
                    found = False
            add("api_restart_state_readable", "pass" if runs is not None and runs.status_code == 200 else "fail", {"triggered_run_id": run_id, "run_found_by_public_shape": found})
    finally:
        stop_server(proc2)

    # API-key mode: protected route must reject missing key and accept the configured key.
    key_env = dict(base_env)
    key_env["EROCK_API_KEY"] = "audit-api-key"
    proc3, _, ready3, _ = start_server("api_key_mode", 8012, key_env)
    try:
        if ready3:
            no_key = http_scenario("api_key_missing", "GET", "http://127.0.0.1:8012/api/v1/pipeline/runs")
            yes_key = http_scenario("api_key_valid", "GET", "http://127.0.0.1:8012/api/v1/pipeline/runs", headers={"X-API-Key": "audit-api-key"})
            add(
                "api_key_boundary",
                "pass" if no_key is not None and no_key.status_code in {401, 403} and yes_key is not None and yes_key.status_code == 200 else "fail",
                {"missing_status": no_key.status_code if no_key else None, "valid_status": yes_key.status_code if yes_key else None},
                "security",
            )
    finally:
        stop_server(proc3)

    # Production with default secret must refuse startup.
    prod_env = dict(base_env)
    prod_env.update({"EROCK_ENV": "production", "EROCK_AUTH_ENABLED": "true", "EROCK_API_KEY": "audit-api-key"})
    proc4, log_path, ready4, reason4 = start_server("api_production_default_secret", 8013, prod_env)
    time.sleep(2)
    exited = proc4.poll() is not None
    stop_server(proc4)
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    add(
        "production_default_secret_rejected",
        "pass" if (not ready4 and (exited or "Insecure JWT secret" in log_text)) else "fail",
        {"ready": ready4, "reason": reason4, "exited": exited, "fatal_message_present": "Insecure JWT secret" in log_text},
        "security",
    )


def write_reports() -> None:
    payload = {
        "baseline_tag": "v1.0.1",
        "expected_commit": "56ff0e69ba787232252d5e9612330531db330e0c",
        "generated_at_epoch": time.time(),
        "scenarios": [asdict(s) for s in SCENARIOS],
        "summary": {
            status: sum(1 for s in SCENARIOS if s.status == status)
            for status in ["pass", "fail", "error", "skip"]
        },
    }
    (EVIDENCE / "runtime_report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# ERLab v1.0.1 Runtime/API E2E Record",
        "",
        f"Expected product commit: `{payload['expected_commit']}`",
        "",
        "| Scenario | Status | Classification |",
        "|---|---:|---|",
    ]
    for s in SCENARIOS:
        lines.append(f"| `{s.name}` | **{s.status.upper()}** | {s.classification} |")
    lines.extend(["", "## Summary", "", "```json", json.dumps(payload["summary"], indent=2), "```", ""])
    (EVIDENCE / "runtime_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    run_cmd("git_exact_tag", ["git", "rev-parse", "v1.0.1^{commit}"])
    run_cmd(
        "git_product_diff",
        [
            "bash", "-lc",
            "git diff --exit-code v1.0.1 -- . ':(exclude)audit/**' ':(exclude).github/workflows/v1_0_1_e2e_audit.yml'",
        ],
    )
    run_cmd("cli_help", ["erock", "--help"], timeout=60)
    run_cmd("cli_version", ["erock", "--version"], timeout=60)
    check_versions()
    check_database()
    check_specs_and_static_invariants()
    run_api_matrix()
    write_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
