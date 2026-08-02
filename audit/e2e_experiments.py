#!/usr/bin/env python3
"""Read-only experiment reproduction harness for sealed ERLab v1.0.1."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", ROOT / "evidence" / "experiments"))
EVIDENCE.mkdir(parents=True, exist_ok=True)
DATA = EVIDENCE / "datasets"
OUT = EVIDENCE / "outputs"
DATA.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)


@dataclass
class Scenario:
    name: str
    status: str
    details: dict[str, Any]
    classification: str = "verification"


SCENARIOS: list[Scenario] = []


def add(name: str, status: str, details: dict[str, Any], classification: str = "verification") -> None:
    SCENARIOS.append(Scenario(name, status, details, classification))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name: str, cmd: list[str], timeout: int = 600, expected_zero: bool = True) -> subprocess.CompletedProcess[str]:
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        log = EVIDENCE / f"{name}.log"
        log.write_text(cp.stdout or "", encoding="utf-8")
        ok = cp.returncode == 0 if expected_zero else cp.returncode != 0
        add(
            name,
            "pass" if ok else "fail",
            {
                "command": cmd,
                "returncode": cp.returncode,
                "duration_seconds": round(time.time() - started, 3),
                "expected_zero": expected_zero,
                "log": log.name,
            },
        )
        return cp
    except Exception as exc:
        log = EVIDENCE / f"{name}.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        add(name, "error", {"command": cmd, "error": repr(exc), "log": log.name})
        return subprocess.CompletedProcess(cmd, 999, "")


def download(name: str, urls: list[str], target: Path) -> bool:
    errors = []
    for url in urls:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as out:
                shutil.copyfileobj(response, out)
            if target.stat().st_size == 0:
                raise RuntimeError("downloaded zero bytes")
            add(name, "pass", {"url": url, "target": str(target), "bytes": target.stat().st_size, "sha256": sha256(target)}, "dataset_acquisition")
            return True
        except Exception as exc:
            errors.append({"url": url, "error": repr(exc)})
    add(name, "fail", {"target": str(target), "attempts": errors}, "dataset_acquisition")
    return False


def prepare_iris() -> Path | None:
    target = DATA / "iris_raw.csv"
    ok = download(
        "download_iris",
        [
            "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data",
            "https://archive.ics.uci.edu/static/public/53/iris.zip",
        ],
        target,
    )
    if not ok:
        # Deterministic fallback from the installed scikit-learn copy. This is
        # clearly recorded as a fallback, not represented as the UCI raw file.
        try:
            from sklearn.datasets import load_iris
            data = load_iris()
            labels = [f"Iris-{data.target_names[int(i)]}" for i in data.target]
            with target.open("w", encoding="utf-8") as f:
                for row, label in zip(data.data, labels):
                    f.write(",".join(str(float(x)) for x in row) + "," + label + "\n")
            add("prepare_iris_sklearn_fallback", "pass", {"rows": len(labels), "sha256": sha256(target), "source": "sklearn.datasets.load_iris"}, "dataset_acquisition")
            return target
        except Exception as exc:
            add("prepare_iris_sklearn_fallback", "error", {"error": repr(exc)})
            return None

    # A ZIP response at the fallback URL is not a CSV; detect and extract.
    if zipfile.is_zipfile(target):
        with zipfile.ZipFile(target) as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith(("iris.data", ".data", ".csv"))]
            if not candidates:
                add("extract_iris_zip", "fail", {"members": zf.namelist()})
                return None
            content = zf.read(candidates[0])
        target.write_bytes(content)
        add("extract_iris_zip", "pass", {"member": candidates[0], "sha256": sha256(target)})
    # Normalize away the trailing blank line without changing data rows.
    lines = [line.strip() for line in target.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    add("prepare_iris_rows", "pass" if len(lines) == 150 else "fail", {"rows": len(lines), "sha256": sha256(target)})
    return target


def prepare_wine() -> Path | None:
    raw = DATA / "winequality-red-raw.csv"
    processed = DATA / "wine_processed.csv"
    ok = download(
        "download_wine",
        [
            "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv",
            "https://archive.ics.uci.edu/static/public/186/wine+quality.zip",
        ],
        raw,
    )
    if not ok:
        return None
    if zipfile.is_zipfile(raw):
        with zipfile.ZipFile(raw) as zf:
            candidates = [n for n in zf.namelist() if n.endswith("winequality-red.csv")]
            if not candidates:
                add("extract_wine_zip", "fail", {"members": zf.namelist()})
                return None
            raw.write_bytes(zf.read(candidates[0]))
        add("extract_wine_zip", "pass", {"member": candidates[0], "sha256": sha256(raw)})
    cp = run(
        "prepare_wine",
        [sys.executable, "experiments/phase8_g1_wine/prepare.py", "--raw", str(raw), "--output", str(processed)],
    )
    return processed if cp.returncode == 0 and processed.exists() else None


def prepare_concrete() -> tuple[Path | None, dict[str, Any]]:
    archive = DATA / "concrete.zip"
    ok = download(
        "download_concrete",
        [
            "https://archive.ics.uci.edu/static/public/165/concrete+compressive+strength.zip",
            "https://archive.ics.uci.edu/ml/machine-learning-databases/concrete/compressive/Concrete_Data.xls",
        ],
        archive,
    )
    if not ok:
        return None, {}
    xls = DATA / "Concrete_Data.xls"
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx", ".csv"))]
            if not candidates:
                add("extract_concrete", "fail", {"members": zf.namelist()})
                return None, {}
            member = candidates[0]
            suffix = Path(member).suffix.lower()
            extracted = DATA / ("Concrete_Data" + suffix)
            extracted.write_bytes(zf.read(member))
            xls = extracted
        add("extract_concrete", "pass", {"member": member, "target": str(xls), "sha256": sha256(xls)})
    else:
        archive.replace(xls)

    dep_state = {
        "pandas_installed_after_project_install": importlib.util.find_spec("pandas") is not None,
        "xlrd_installed_after_project_install": importlib.util.find_spec("xlrd") is not None,
        "openpyxl_installed_after_project_install": importlib.util.find_spec("openpyxl") is not None,
    }
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dep_state["pandas_declared_in_pyproject"] = '"pandas' in pyproject or "'pandas" in pyproject
    add(
        "concrete_dependency_contract",
        "pass" if dep_state["pandas_installed_after_project_install"] and dep_state["pandas_declared_in_pyproject"] else "fail",
        dep_state,
        "packaging",
    )

    csv_path = DATA / "concrete_raw.csv"
    try:
        import pandas as pd
        if xls.suffix.lower() == ".csv":
            frame = pd.read_csv(xls)
        else:
            frame = pd.read_excel(xls)
        frame.to_csv(csv_path, index=False)
        add("convert_concrete_to_csv", "pass" if len(frame) == 1030 else "fail", {"rows": len(frame), "columns": list(frame.columns), "sha256": sha256(csv_path)})
        return csv_path, dep_state
    except Exception as exc:
        add("convert_concrete_to_csv_initial", "fail", {"error": repr(exc), "traceback": traceback.format_exc()}, "packaging")

    # Audit-only diagnostic remediation: install conversion/runtime dependencies
    # to distinguish a packaging defect from an analysis defect.
    cp = run("install_audit_only_concrete_dependencies", [sys.executable, "-m", "pip", "install", "pandas", "xlrd", "openpyxl"], timeout=600)
    if cp.returncode != 0:
        return None, dep_state
    try:
        import importlib
        pd = importlib.import_module("pandas")
        frame = pd.read_csv(xls) if xls.suffix.lower() == ".csv" else pd.read_excel(xls)
        frame.to_csv(csv_path, index=False)
        add("convert_concrete_to_csv_after_audit_dependency", "pass" if len(frame) == 1030 else "fail", {"rows": len(frame), "columns": list(frame.columns), "sha256": sha256(csv_path)}, "diagnostic_reproduction")
        return csv_path, dep_state
    except Exception as exc:
        add("convert_concrete_to_csv_after_audit_dependency", "error", {"error": repr(exc), "traceback": traceback.format_exc()})
        return None, dep_state


def artifact_snapshot(directory: Path) -> dict[str, Any]:
    files = {}
    if directory.exists():
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            rel = str(path.relative_to(directory))
            files[rel] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    metrics = None
    metrics_path = directory / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {"files": files, "metrics": metrics}


def reproduce(name: str, script: str, input_path: Path | None, required_artifacts: list[str]) -> None:
    if input_path is None or not input_path.exists():
        add(name + "_reproduction", "skip", {"reason": "dataset unavailable"}, "reproducibility")
        return
    run1 = OUT / name / "run1"
    run2 = OUT / name / "run2"
    run1.mkdir(parents=True, exist_ok=True)
    run2.mkdir(parents=True, exist_ok=True)
    cp1 = run(name + "_run1", [sys.executable, script, "--input", str(input_path), "--output", str(run1)], timeout=900)
    cp2 = run(name + "_run2", [sys.executable, script, "--input", str(input_path), "--output", str(run2)], timeout=900)
    snap1 = artifact_snapshot(run1)
    snap2 = artifact_snapshot(run2)
    missing1 = sorted(set(required_artifacts) - set(snap1["files"]))
    missing2 = sorted(set(required_artifacts) - set(snap2["files"]))
    identical_metrics = snap1["metrics"] == snap2["metrics"] and snap1["metrics"] is not None
    common = set(snap1["files"]) & set(snap2["files"])
    identical_hashes = {f: snap1["files"][f]["sha256"] == snap2["files"][f]["sha256"] for f in sorted(common)}
    # observed_at is not written by the analysis scripts; all declared artifacts
    # should therefore be byte-stable if the experiment is deterministic.
    all_identical = bool(identical_hashes) and all(identical_hashes.values())
    ok = cp1.returncode == 0 and cp2.returncode == 0 and not missing1 and not missing2 and identical_metrics and all_identical
    details = {
        "input": str(input_path),
        "input_sha256": sha256(input_path),
        "run1": snap1,
        "run2": snap2,
        "missing_run1": missing1,
        "missing_run2": missing2,
        "metrics_identical": identical_metrics,
        "artifact_hashes_identical": identical_hashes,
    }
    (EVIDENCE / f"{name}_snapshot.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    add(name + "_reproduction", "pass" if ok else "fail", {"snapshot": f"{name}_snapshot.json", "metrics": snap1["metrics"]}, "reproducibility")


def integrated_runner_checks() -> None:
    try:
        from backend.pipeline.experiment.specification import load_spec
        from backend.pipeline.experiment.empirical_runner import execute_experiment
        import asyncio

        ids = ["phase5-pilot-v1", "phase8-g2-concrete", "phase14-rf-wine"]
        outcomes: dict[str, Any] = {}
        for spec_id in ids:
            try:
                spec = load_spec(spec_id)
                target = OUT / "integrated" / spec_id
                manifest, stdout, stderr, exit_code, elapsed = asyncio.run(execute_experiment(spec_id, target))
                outcomes[spec_id] = {
                    "loaded": True,
                    "status": manifest.status,
                    "exit_code": exit_code,
                    "elapsed": elapsed,
                    "results": manifest.results,
                    "artifacts": [a.filename for a in manifest.result_artifacts],
                    "stderr": stderr[:1000],
                }
            except Exception as exc:
                outcomes[spec_id] = {"loaded": False, "error": repr(exc)}
        add("integrated_registered_runner", "pass" if all(v.get("status") == "succeeded" for v in outcomes.values()) else "fail", outcomes, "integrated_evidence_path")
    except Exception as exc:
        add("integrated_registered_runner", "error", {"error": repr(exc), "traceback": traceback.format_exc()})


def failure_checks(iris: Path | None) -> None:
    run(
        "iris_missing_input_failure",
        [sys.executable, "experiments/phase5_pilot_v1/analysis.py", "--input", str(DATA / "missing.csv"), "--output", str(OUT / "failure_missing")],
        expected_zero=False,
    )
    malformed = DATA / "malformed_iris.csv"
    malformed.write_text("1,2,3,4,label\n", encoding="utf-8")
    run(
        "iris_malformed_input_failure",
        [sys.executable, "experiments/phase5_pilot_v1/analysis.py", "--input", str(malformed), "--output", str(OUT / "failure_malformed")],
        expected_zero=False,
    )


def write_reports() -> None:
    payload = {
        "baseline_tag": "v1.0.1",
        "expected_commit": "56ff0e69ba787232252d5e9612330531db330e0c",
        "scenarios": [asdict(s) for s in SCENARIOS],
        "summary": {status: sum(1 for s in SCENARIOS if s.status == status) for status in ["pass", "fail", "error", "skip"]},
    }
    (EVIDENCE / "experiment_report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# ERLab v1.0.1 Experiment E2E Record",
        "",
        "| Scenario | Status | Classification |",
        "|---|---:|---|",
    ]
    for s in SCENARIOS:
        lines.append(f"| `{s.name}` | **{s.status.upper()}** | {s.classification} |")
    lines.extend(["", "## Summary", "", "```json", json.dumps(payload["summary"], indent=2), "```", ""])
    (EVIDENCE / "experiment_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    iris = prepare_iris()
    wine = prepare_wine()
    concrete, _ = prepare_concrete()

    reproduce(
        "iris_logistic",
        "experiments/phase5_pilot_v1/analysis.py",
        iris,
        ["metrics.json", "predictions.csv", "results_table.csv"],
    )
    reproduce(
        "concrete_linear",
        "experiments/phase8_g2_concrete/analysis.py",
        concrete,
        ["metrics.json", "predictions.csv", "results_table.csv", "split_indices.csv"],
    )
    reproduce(
        "wine_random_forest",
        "experiments/phase14_rf_wine/analysis.py",
        wine,
        ["metrics.json", "predictions.csv", "results_table.csv", "split_indices.csv", "feature_importance.csv"],
    )
    integrated_runner_checks()
    failure_checks(iris)
    write_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
