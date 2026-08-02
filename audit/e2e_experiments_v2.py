#!/usr/bin/env python3
"""Audit-only wrapper fixing the concrete dependency probe in e2e_experiments."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import traceback
import zipfile
from pathlib import Path

from audit import e2e_experiments as base


def fixed_prepare_concrete():
    archive = base.DATA / "concrete.zip"
    ok = base.download(
        "download_concrete",
        [
            "https://archive.ics.uci.edu/static/public/165/concrete+compressive+strength.zip",
            "https://archive.ics.uci.edu/ml/machine-learning-databases/concrete/compressive/Concrete_Data.xls",
        ],
        archive,
    )
    if not ok:
        return None, {}

    xls = base.DATA / "Concrete_Data.xls"
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx", ".csv"))]
            if not candidates:
                base.add("extract_concrete", "fail", {"members": zf.namelist()})
                return None, {}
            member = candidates[0]
            suffix = Path(member).suffix.lower()
            xls = base.DATA / ("Concrete_Data" + suffix)
            xls.write_bytes(zf.read(member))
        base.add("extract_concrete", "pass", {"member": member, "target": str(xls), "sha256": base.sha256(xls)})
    else:
        archive.replace(xls)

    dep_state = {
        "pandas_installed_after_project_install": importlib.util.find_spec("pandas") is not None,
        "xlrd_installed_after_project_install": importlib.util.find_spec("xlrd") is not None,
        "openpyxl_installed_after_project_install": importlib.util.find_spec("openpyxl") is not None,
    }
    pyproject = (base.ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dep_state["pandas_declared_in_pyproject"] = '"pandas' in pyproject or "'pandas" in pyproject
    base.add(
        "concrete_dependency_contract",
        "pass" if dep_state["pandas_installed_after_project_install"] and dep_state["pandas_declared_in_pyproject"] else "fail",
        dep_state,
        "packaging",
    )

    csv_path = base.DATA / "concrete_raw.csv"

    def convert(label: str):
        pd = importlib.import_module("pandas")
        frame = pd.read_csv(xls) if xls.suffix.lower() == ".csv" else pd.read_excel(xls)
        frame.to_csv(csv_path, index=False)
        base.add(label, "pass" if len(frame) == 1030 else "fail", {
            "rows": len(frame),
            "columns": list(frame.columns),
            "sha256": base.sha256(csv_path),
        }, "diagnostic_reproduction" if "after" in label else "verification")
        return csv_path

    try:
        return convert("convert_concrete_to_csv"), dep_state
    except Exception as exc:
        base.add("convert_concrete_to_csv_initial", "fail", {
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }, "packaging")

    cp = base.run(
        "install_audit_only_concrete_dependencies",
        [sys.executable, "-m", "pip", "install", "pandas", "xlrd", "openpyxl"],
        timeout=600,
    )
    if cp.returncode != 0:
        return None, dep_state
    try:
        return convert("convert_concrete_to_csv_after_audit_dependency"), dep_state
    except Exception as exc:
        base.add("convert_concrete_to_csv_after_audit_dependency", "error", {
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        })
        return None, dep_state


base.prepare_concrete = fixed_prepare_concrete
raise SystemExit(base.main())
