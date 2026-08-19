"""Case 4: bounded serial operational repeatability — sealed harness.

Frozen charter: evidence/case4_charter.md (owner plan, verbatim) with a
freeze-record header. Product under test R2 = 7e5462637bff4ea83a4141e6149ea04c049e80b8
(R0 d4e3125 -> R1 2ce7a874 PR #38 persistence fail-closed -> R2 7e546263
PR #39 transport-identity propagation; per the frozen charter's
GENERIC_PRODUCT_DEFECT path the whole matrix restarts on the current head,
and launches additionally await the owner's provider-entitlement ruling).
No production code changes; this harness drives only existing production
entry points, exactly as the qualified Case-3E harness (v2, f2e19cb0…)
did, parameterized per matrix entry.

Matrix (C–R–R–C, frozen):
  R1  Case-2 input  tabular_calibration_selective_v1
  R2  Case-3 input  tabular_robust_regression_v1
  R3  Case-3 input  tabular_robust_regression_v1
  R4  Case-2 input  tabular_calibration_selective_v1

Modes:
  --mode launch     one zero-intervention invocation: preflight, then matrix
  --mode preflight  C4-4 hard gates + establish fresh Class-1 state + baseline
  --mode matrix     C4-5 coordinator: serial R1..R4, fresh worker process each,
                    archive specimen, restore fresh state, fail fast
  --mode worker     single run lifecycle (spawned by the coordinator); the
                    Case-3E-v2 policy with a per-run contract fact ledger
  --mode controls   C4-2 bounded synthetic positive/negative controls
  --mode verify     C4-6 independent recomputation from preserved specimens

Zero-intervention boundary: from `--mode launch` start to its exit code,
every continuation, archive, reset, and fail-fast decision is made by this
sealed file. The per-run hang watchdog (9,500 s ≈ 3× the longest prior
qualifying run) exists solely to convert a non-terminating worker into a
preserved RUN_FAIL(watchdog_hang) specimen; it is not a latency criterion.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("EROCK_EMBEDDING_MODEL", "text-embedding-qwen3-embedding-0.6b")
os.environ.setdefault("EROCK_EMBEDDING_DIMENSION", "1024")
os.environ.setdefault("EROCK_EMBEDDING_PROVIDER", "lmstudio")

ROOT = Path(__file__).resolve().parent.parent
HARNESS_PATH = Path(__file__).resolve()

PRODUCT_HEAD = "7e5462637bff4ea83a4141e6149ea04c049e80b8"
# Lineage: R0 = d4e3125786f23c710d794d741e792aab24dd0f06 (original
# freeze) -> R1 = 2ce7a874fc0612d162a37519fdc9282148b65d86 (PR #38,
# fail-closed on initial run-record creation failure) -> R2 =
# 7e5462637bff4ea83a4141e6149ea04c049e80b8 (PR #39, GatewayTransportError
# propagation through post-ideation fail-soft paths). Both product moves
# adjudicated GENERIC_PRODUCT_DEFECT 2026-08-18 from Case-4 specimens.
DB_PATH = "data/elephant_rock.db"
API_BASE = "http://127.0.0.1:8768"
API_PORT = 8768

MANIFEST_PATH = "evidence/case4_manifest.json"
SEAL_PATH = "evidence/case4_manifest.sha256"
CHARTER_PATH = "evidence/case4_charter.md"
CONTROLS_PATH = "evidence/case4_controls_result.json"
PREFLIGHT_PATH = "evidence/case4_preflight.json"
MATRIX_RESULT_PATH = "evidence/case4_matrix_result.json"
MATRIX_LOG_PATH = "evidence/case4_matrix_run.log"
VERIFICATION_PATH = "evidence/case4_verification.json"

RUNTIME_DIR = "evidence/case4_runtime"           # local-only (self-gitignored)
BASELINE_DIR = RUNTIME_DIR + "/baseline"
PREFLIGHT_ARCHIVE_DIR = RUNTIME_DIR + "/preflight_archive"
SPECIMEN_ARCHIVE_DIR = RUNTIME_DIR + "/specimens"
SANDBOX_DIR = RUNTIME_DIR + "/controls_sandbox"
BASELINE_MANIFEST_PATH = RUNTIME_DIR + "/baseline_manifest.json"
PRESERVED_FINGERPRINT_PATH = RUNTIME_DIR + "/preserved_fingerprint.json"

WATCHDOG_S = 9500

# Class-1 research state (empirical Case-3E write set, 2026-08-17 run): every
# path the 3E lifecycle created or mutated under data/. Archived, then reset.
RESET_SET = [
    "data/elephant_rock.db",
    "data/chroma",
    "data/checkpoints",
    "data/runs",
    "data/knowledge",
    "data/bm25",
    "data/error_knowledge.db",
    "data/knowledge_graph.json",
    "data/knowledge_graph.changes.jsonl",
    "data/memory",
    "data/goals.json",
    "data/world_model.json",
    "data/governance_audit.jsonl",
    "data/experiments",
    "data/costs",
    "data/exports",
]
# Class-2 operating state: preserved, fingerprinted, must not drift.
PRESERVED_SET = [
    "data/model_certification",
    "data/model_assignments.json",
    "data/datasets",
]
EXPECTED_DATASETS = [
    "airfoil_self_noise", "concrete_strength", "iris", "wine_quality",
]

SIX_GATES = {
    "provenance",
    "scope_alignment",
    "conclusion_support",
    "experiment_alignment",
    "numeric_fidelity",
    "method_fidelity",
}

# Subtype groups per the charter failure taxonomy (RUN_FAIL subtypes).
SUBTYPE_GROUPS = {
    "provider_readiness": "provider_availability_transport",
    "orchestration": "orchestration",
    "design": "autonomous_design",
    "capability": "autonomous_design",
    "specs": "experiment_execution",
    "experiments": "experiment_execution",
    "persistence": "persistence",
    "evaluation": "synthesis",
    "remediation": "assurance_remediation",
    "final_ready": "assurance_remediation",
    "gates": "assurance_remediation",
    "revisions": "persistence",
    "freeze": "freeze",
    "release_identity": "release_identity",
    "harness_exception": "invalid_attempt",
    "watchdog_hang": "orchestration",
}

RUN_CONFIGS = [
    {
        "label": "R1",
        "family": "case2_calibration",
        "expected_capability": "tabular_calibration_selective_v1",
        "domain": "Robust confidence estimation under dataset shift",
        "research_question": (
            "Are calibration-method rankings stable as covariate-shift"
            " severity increases, or do rank reversals occur in accuracy,"
            " positive-class expected calibration error, and selective AURC"
            " across tabular classification datasets?"
        ),
    },
    {
        "label": "R2",
        "family": "case3_regression",
        "expected_capability": "tabular_robust_regression_v1",
        "domain": "Robust regression under distribution shift",
        "research_question": (
            "Are robust-regression method rankings stable as covariate"
            " perturbation severity increases, or do rank reversals occur in"
            " MAE, RMSE, and R² across tabular regression datasets?"
        ),
    },
    {"label": "R3", "family": "case3_regression",
     "expected_capability": "tabular_robust_regression_v1",
     "domain": "Robust regression under distribution shift",
     "research_question": (
         "Are robust-regression method rankings stable as covariate"
         " perturbation severity increases, or do rank reversals occur in"
         " MAE, RMSE, and R² across tabular regression datasets?"
     )},
    {"label": "R4", "family": "case2_calibration",
     "expected_capability": "tabular_calibration_selective_v1",
     "domain": "Robust confidence estimation under dataset shift",
     "research_question": (
         "Are calibration-method rankings stable as covariate-shift"
         " severity increases, or do rank reversals occur in accuracy,"
         " positive-class expected calibration error, and selective AURC"
         " across tabular classification datasets?"
     )},
]
RUN_BY_LABEL = {c["label"]: c for c in RUN_CONFIGS}

LOG_LINES: list[str] = []


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()[11:19]}Z] {msg}"
    LOG_LINES.append(line)
    print(line, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Per-run contract: one ordered decision function shared by the worker and
# the synthetic controls. `first_failure` evaluates checks up to and
# including facts["phase"]; the worker advances phase per milestone, so it
# fails fast, and the controls exercise the full order.
# ---------------------------------------------------------------------------

CHECK_ORDER = [
    ("provider_readiness", lambda f: bool(f["provider_ready"])),
    ("orchestration", lambda f: bool(f["outcome_is_success"])),
    ("design", lambda f: f["design_status"] == "designed"),
    ("capability", lambda f: f["capability_id"] == f["expected_capability"]),
    ("specs", lambda f: f["n_specs"] > 0 and bool(f["spec_ids_complete"])),
    ("experiments", lambda f: (
        f["n_specs"] > 0 and f["experiments_success"] == f["n_specs"]
    )),
    ("persistence", lambda f: f["method_facts_count"] > 0),
    ("evaluation", lambda f: f["eval_state"] in ("ready", "blocked")),
    ("remediation", lambda f: (
        not f["repair_invoked"] or f["final_eval_status"] == "ready"
    )),
    ("final_ready", lambda f: f["final_eval_status"] == "ready"),
    ("gates", lambda f: bool(f["gates_set_ok"]) and bool(f["gates_all_passed"])),
    # Case-4 checker repair (runfail_2 adjudication, 2026-08-19): the
    # revisions check needs the frozen revision id and the post-freeze
    # row set — a strictly post-freeze data dependency. It previously
    # sat BEFORE freeze, so the freeze-milestone assertion evaluated a
    # default-False fact and falsely failed a run whose freeze had
    # succeeded. Freeze now precedes revisions in both the check order
    # and the worker's milestones.
    ("freeze", lambda f: (
        f["freeze_state"] == "frozen" and bool(f["release_eligible"])
    )),
    ("revisions", lambda f: bool(f["revisions_preserved"])),
    ("release_identity", lambda f: (
        f["E"] == f["F"] == f["R"] == f["H"]
        and bool(f["release_equals_current"])
        and f["frozen_eval_status"] == "ready"
    )),
]
CHECK_INDEX = {name: i for i, (name, _) in enumerate(CHECK_ORDER)}

# Fact inputs each check reads; the availability guard uses this map.
FACT_INPUTS = {
    "provider_readiness": ["provider_ready"],
    "orchestration": ["outcome_is_success"],
    "design": ["design_status"],
    "capability": ["capability_id", "expected_capability"],
    "specs": ["n_specs", "spec_ids_complete"],
    "experiments": ["experiments_success", "n_specs"],
    "persistence": ["method_facts_count"],
    "evaluation": ["eval_state"],
    "remediation": ["repair_invoked", "final_eval_status"],
    "final_ready": ["final_eval_status"],
    "gates": ["gates_set_ok", "gates_all_passed"],
    "freeze": ["freeze_state", "release_eligible"],
    "revisions": ["revisions_preserved", "pre_freeze_revision_rows"],
    "release_identity": ["E", "F", "R", "H", "release_equals_current",
                         "frozen_eval_status"],
}


def require_facts(facts: dict, *check_names: str) -> None:
    """Availability guard (runfail_2 repair): raise BEFORE a milestone's
    mutation or assertion if any fact required to adjudicate the named
    checks has not been collected. The worker marks collected fact keys
    in facts["_collected"] as it sets them."""
    missing = []
    for name in check_names:
        for key in FACT_INPUTS[name]:
            if key not in facts.get("_collected", []):
                missing.append(f"{name}.{key}")
    if missing:
        raise RuntimeError(
            "checker fact-availability guard: required facts not yet"
            f" collected: {missing} — refusing to adjudicate a milestone"
            " on uncollected facts (runfail_2 repair)"
        )


def first_failure(facts: dict) -> str | None:
    upto = CHECK_INDEX[facts["phase"]]
    for i, (name, check) in enumerate(CHECK_ORDER):
        if i > upto:
            break
        if not check(facts):
            return name
    return None


def default_facts(cfg: dict) -> dict:
    return {
        "phase": "provider_readiness",
        "label": cfg["label"],
        "expected_capability": cfg["expected_capability"],
        "provider_ready": False,
        "outcome": None,
        "outcome_is_success": False,
        "design_status": None,
        "capability_id": None,
        "n_specs": 0,
        "spec_ids": [],
        "spec_ids_complete": False,
        "experiments_success": 0,
        "method_facts_count": 0,
        "method_facts_keys": [],
        "eval_state": None,
        "repair_invoked": False,
        "final_eval_status": None,
        "gates_raw": {},
        "gates_set_ok": False,
        "gates_all_passed": False,
        "revision_rows": [],
        "revisions_preserved": False,
        "pre_freeze_revision_rows": [],
        "_collected": [],
        "freeze_state": None,
        "release_eligible": False,
        "E": "", "F": "", "R": "", "H": "",
        "release_equals_current": False,
        "frozen_eval_status": None,
    }


# ---------------------------------------------------------------------------
# State manifests (path-parameterized so the controls can sandbox them).
# ---------------------------------------------------------------------------

def compute_state_manifest(paths: list[str], base: Path) -> dict:
    entries: dict[str, dict] = {}
    for rel in paths:
        p = base / rel
        if not p.exists():
            entries[rel] = {"type": "absent"}
        elif p.is_file():
            entries[rel] = {"type": "file", "sha256": sha256_file(p)}
        elif p.is_dir():
            files = {}
            for q in sorted(p.rglob("*")):
                if q.is_file():
                    files[str(q.relative_to(p)).replace("\\", "/")] = (
                        sha256_file(q)
                    )
            entries[rel] = {"type": "dir", "files": files}
    return entries


def diff_state_manifest(
    recorded: dict, paths: list[str], base: Path,
) -> list[str]:
    current = compute_state_manifest(paths, base)
    diffs = []
    for rel in paths:
        a, b = recorded.get(rel), current.get(rel)
        if a != b:
            diffs.append(rel)
    return diffs


def restore_state(
    manifest: dict, snapshot_dir: Path, paths: list[str], base: Path,
) -> None:
    for rel in paths:
        entry = manifest[rel]
        p = base / rel
        snap = snapshot_dir / rel
        if entry["type"] == "absent":
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            continue
        if entry["type"] == "file":
            if p.is_dir():
                shutil.rmtree(p)
            p.parent.mkdir(parents=True, exist_ok=True)
            if not snap.is_file():
                raise FileNotFoundError(f"baseline snapshot missing: {snap}")
            shutil.copy2(snap, p)
            continue
        # dir
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        if snap.is_dir():
            shutil.copytree(snap, p)
        else:
            p.mkdir(parents=True, exist_ok=True)


def snapshot_state(
    manifest: dict, snapshot_dir: Path, paths: list[str], base: Path,
) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for rel in paths:
        entry = manifest[rel]
        p, snap = base / rel, snapshot_dir / rel
        if entry["type"] == "absent":
            continue
        if entry["type"] == "file":
            snap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, snap)
        else:
            if snap.exists():
                shutil.rmtree(snap)
            shutil.copytree(p, snap)


# ---------------------------------------------------------------------------
# Worker: the Case-3E-v2 lifecycle, parameterized per matrix entry.
# ---------------------------------------------------------------------------

def http(method: str, path: str, body: dict | None = None,
         timeout: float = 900.0):
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


def http_status(method: str, path: str, body: dict | None = None,
                timeout: float = 900.0):
    """Like http(), but non-2xx responses return (code, headers, body)
    instead of raising, so call sites can fail with their contract
    subtype rather than a generic harness exception (review P1-2)."""
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read()
        except Exception:  # noqa: BLE001 - best effort
            error_body = b""
        return e.code, dict(e.headers or {}), error_body


def safe_json(payload: bytes) -> dict:
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001 - error bodies may not be JSON
        return {}


def header_get(headers: dict, name: str) -> str:
    if name in headers:
        return headers[name]
    low = name.lower()
    for k, v in headers.items():
        if k.lower() == low:
            return v
    return ""


def wait_health(deadline_s: float = 120.0) -> bool:
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            status, _, _ = http("GET", "/health", timeout=5)
            if status == 200:
                return True
        except Exception:
            time.sleep(2)
    return False


def wait_port_free(port: int, deadline_s: float = 60.0) -> bool:
    end = time.time() + deadline_s
    while time.time() < end:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            time.sleep(2)
        except OSError:
            s.close()
            return True
    return False


def port_in_use(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        s.close()
        return False


def read_design_state() -> dict:
    conn = sqlite3.connect(ROOT / DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {}
        run_id = row[0]
        cur.execute(
            "SELECT id FROM ideas WHERE pipeline_run_id=?", (run_id,)
        )
        idea_ids = [r[0] for r in cur.fetchall()]
        if not idea_ids:
            return {"run_id": run_id}
        q = (
            "SELECT id, idea_id, paper_md, paper_meta_json FROM proposals"
            f" WHERE idea_id IN ({','.join('?' * len(idea_ids))})"
            " ORDER BY id"
        )
        best = None
        for pid, iid, paper_md, meta in cur.execute(q, idea_ids).fetchall():
            m = json.loads(meta) if meta else {}
            if "autonomous_experiment_design" in m:
                if best is None or (paper_md and paper_md.strip()):
                    best = {
                        "run_id": run_id, "proposal_id": pid,
                        "idea_id": iid, "paper_md": paper_md, "meta": m,
                    }
        return best or {"run_id": run_id}
    finally:
        conn.close()


def gate_snapshot(final_eval: dict) -> tuple[bool, bool, dict]:
    raw = {}
    for g in final_eval.get("gates", []):
        if not isinstance(g, dict):
            continue
        name = g.get("gate") or g.get("name")
        if not name:
            continue
        raw[name] = g.get("passed", g.get("classification"))
    falsy = {"", "false", "off_scope", "unsupported", "blocked",
             "failed", "no", "none"}
    all_passed = all(
        v is True or (
            isinstance(v, str) and v.strip().lower() not in falsy
        )
        for v in raw.values()
    )
    return set(raw) == SIX_GATES, all_passed and set(raw) == SIX_GATES, raw


def revision_rows_for(proposal_id: int) -> list[tuple]:
    conn = sqlite3.connect(ROOT / DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, revision_number, parent_revision_id, eval_status,"
            " source FROM paper_revisions WHERE proposal_id=? ORDER BY id",
            (proposal_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def revisions_preserved(pre_rows, post_rows, frozen_id) -> bool:
    """runfail_2 repair: the immutable pre-freeze snapshot must be an
    exact prefix of the post-freeze rows (freeze may append the frozen
    revision; it must never alter or remove history), numbering must be
    contiguous from 0, and the frozen revision must be present."""
    if not post_rows or frozen_id is None:
        return False
    numbers = [r[1] for r in post_rows]
    if numbers != list(range(len(numbers))):
        return False
    if [tuple(r) for r in pre_rows] != [
        tuple(r) for r in post_rows[: len(pre_rows)]
    ]:
        return False
    return frozen_id in {r[0] for r in post_rows}


async def run_orchestrator(cfg: dict) -> dict:
    from backend.pipeline.orchestrator._orchestrator import (
        PipelineOrchestrator,
    )
    from backend.pipeline.result import PipelineOutcome

    orchestrator = PipelineOrchestrator(strategy="deep_research")
    start = time.time()
    result = await orchestrator.run(
        domain=cfg["domain"],
        research_question=cfg["research_question"],
        max_gaps=3,
        generation_rounds=1,
        ideas_per_round=1,
        autonomous_experiment_enabled=True,
    )
    params = result.params_used or {}
    return {
        "run_id": result.run_id,
        "outcome": (
            result.outcome.value
            if hasattr(result.outcome, "value") else str(result.outcome)
        ),
        "outcome_is_success": result.outcome == PipelineOutcome.SUCCEEDED,
        "elapsed_s": round(time.time() - start, 1),
        "params_keys": sorted(params.keys()),
        "auto_design_status": (
            (params.get("autonomous_experiment_design") or {}).get("status")
        ),
    }


def worker_enforce_readiness() -> dict:
    """Contract item 1: Q2 production readiness, configured endpoint.

    The production gate signals not-ready by RAISING
    ProviderUnavailableError; that is translated here into
    ready=False so the failure keeps its provider subtype instead of
    collapsing into a generic harness exception (review P1-1)."""
    from backend.config import get_settings
    from backend.pipeline.orchestrator.readiness import (
        ProviderUnavailableError,
        enforce_required_provider_readiness,
        lmstudio_required_for_run,
    )

    try:
        settings = get_settings()
        required = lmstudio_required_for_run(settings)
    except ProviderUnavailableError as e:
        return {
            "required": None, "ready": False,
            "errors": [f"requirement determination failed: {e}"],
        }
    info: dict = {"required": required}
    if required:
        try:
            mgr, preflight = enforce_required_provider_readiness(settings)
        except ProviderUnavailableError as e:
            info["ready"] = False
            info["errors"] = [str(e)]
            return info
        info["ready"] = bool(getattr(preflight, "ready", False))
        info["errors"] = list(getattr(preflight, "errors", []) or [])
        info["model"] = getattr(mgr, "model_id", "")
    else:
        info["ready"] = True
    return info


REQUIRED_TABLES = [
    "pipeline_runs", "ideas", "proposals", "paper_revisions",
    "experiment_results",
]


def missing_required_tables(db_path: str = DB_PATH) -> list[str]:
    p = ROOT / db_path
    if not p.exists():
        return list(REQUIRED_TABLES)
    conn = sqlite3.connect(p)
    try:
        have = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    return [t for t in REQUIRED_TABLES if t not in have]


def ensure_schema(db_path: str = DB_PATH) -> None:
    """Initialize the empty DB schema through the production initializer
    and VERIFY the required tables exist.

    Two defects from the invalidated attempt are closed here. First,
    nothing in the in-process orchestrator path creates tables
    (create_run_record swallows the OperationalError; review P0-1).
    Second, init_db() only creates tables for model modules that have
    been IMPORTED — the API app imports them at startup, a cold caller
    does not, so a naive init_db() call produced the 0-byte zero-table
    file that passed the preflight's file-exists check and let R1 run
    unpersisted. The models import, the initializer, and the direct
    table assertion together pin the qualified 'new DB (0 runs)' state."""
    import backend.db.models  # noqa: F401 — populates Base.metadata
    from backend.db.database import init_db

    init_db()
    missing = missing_required_tables(db_path)
    if missing:
        raise RuntimeError(
            "schema initialization did not produce the required tables:"
            f" {sorted(missing)} — refusing to run against a schema-less"
            " database"
        )


def run_worker(label: str) -> int:
    cfg = RUN_BY_LABEL[label]
    result_path = ROOT / f"evidence/case4_{label.lower()}_result.json"
    release_path = ROOT / f"evidence/case4_{label.lower()}_release.md"
    api_log_path = ROOT / f"evidence/case4_{label.lower()}_api.log"
    facts = default_facts(cfg)
    result: dict = {
        "case": f"Case 4 — matrix run {label} ({cfg['family']})",
        "frozen_head": PRODUCT_HEAD,
        "config": {
            "label": label,
            "family": cfg["family"],
            "expected_capability": cfg["expected_capability"],
            "domain": cfg["domain"],
            "research_question": cfg["research_question"],
            "activation": "autonomous_experiment_enabled=True only",
        },
        "started_at": now_iso(),
        "steps": [],
        "operator_interventions": 0,
    }
    accepted = False
    failure_type: str | None = None
    server = None
    try:
        # Contract 1: production readiness before research execution
        log(f"{label} STEP1 provider readiness (production Q2 gate)")
        readiness = worker_enforce_readiness()
        facts["provider_ready"] = bool(readiness.get("ready"))
        facts["phase"] = "provider_readiness"
        result["steps"].append({"step": "1", "readiness": readiness})
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"required provider not ready: {readiness}"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # Contract 2: orchestrator, REQUIRED SUCCEEDED. The empty DB
        # schema is ensured first (production init_db; idempotent).
        ensure_schema()
        log(f"{label} STEP2 orchestrator launch (frozen input)")
        orch = asyncio.run(run_orchestrator(cfg))
        facts["outcome"] = orch["outcome"]
        facts["outcome_is_success"] = bool(orch["outcome_is_success"])
        facts["phase"] = "orchestration"
        result["steps"].append({"step": "2", "orchestrator": orch})
        log(f"{label} STEP2 outcome={orch['outcome']}"
            f" elapsed={orch['elapsed_s']}s")
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"orchestrator outcome != SUCCEEDED ({orch['outcome']})"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # Contracts 3-6: persisted design, capability, specs, facts
        state = read_design_state()
        design = (state.get("meta") or {}).get(
            "autonomous_experiment_design", {}
        )
        specs = design.get("specs") or []
        method_facts = design.get("method_facts") or {}
        facts["design_status"] = design.get("status")
        facts["capability_id"] = design.get("capability_id")
        facts["n_specs"] = len(specs)
        facts["spec_ids"] = [s.get("experiment_spec_id") for s in specs]
        facts["spec_ids_complete"] = (
            facts["n_specs"] > 0
            and all(sid for sid in facts["spec_ids"])
        )
        facts["method_facts_count"] = len(method_facts)
        facts["method_facts_keys"] = sorted(method_facts.keys())
        facts["phase"] = "specs"
        result["proposal_id"] = state.get("proposal_id")
        result["idea_id"] = state.get("idea_id")
        result["pipeline_run_id"] = state.get("run_id")
        result["steps"].append({
            "step": "3-6",
            "design_status": design.get("status"),
            "capability_id": design.get("capability_id"),
            "n_specs": facts["n_specs"],
            "spec_ids": facts["spec_ids"],
            "method_facts_count": facts["method_facts_count"],
            "method_facts_persisted_pre_remediation": (
                facts["method_facts_count"] > 0
            ),
        })
        log(
            f"{label} STEP3-6 design={design.get('status')}"
            f" cap={design.get('capability_id')} specs={facts['n_specs']}"
            f" facts={facts['method_facts_count']}"
        )
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"design/capability/spec/persistence gate failed: {f}"
                f" (design={design.get('status')},"
                f" cap={design.get('capability_id')},"
                f" specs={facts['n_specs']},"
                f" facts={facts['method_facts_count']})"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # Contract 5 (execution) + 7 precondition (evaluation state)
        conn = sqlite3.connect(ROOT / DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM experiment_results WHERE proposal_id=?"
            " AND success=1",
            (state["proposal_id"],),
        )
        facts["experiments_success"] = cur.fetchone()[0]
        eval_state = (
            (state["meta"].get("paper_evaluation")) or {}
        ).get("status")
        facts["eval_state"] = eval_state
        markers = len(state["meta"].get("result_markers", []) or [])
        conn.close()
        facts["phase"] = "experiments"
        result["steps"].append({
            "step": "5-7",
            "experiments_success": facts["experiments_success"],
            "experiments_expected": facts["n_specs"],
            "initial_eval_status": eval_state,
            "markers": markers,
        })
        log(
            f"{label} STEP5 experiments={facts['experiments_success']}"
            f"/{facts['n_specs']} eval={eval_state} markers={markers}"
        )
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"experiment/evaluation gate failed: {f}"
                f" ({facts['experiments_success']}/{facts['n_specs']},"
                f" eval={eval_state!r})"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # Contract 8: continuation via a fresh API process
        if not wait_port_free(API_PORT):
            failure_type = "harness_exception"
            result["failure"] = f"API port {API_PORT} still in use"
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=failure_type)
        log(f"{label} STEP8 starting fresh API process")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.api.app:app",
             "--host", "127.0.0.1", "--port", str(API_PORT)],
            cwd=str(ROOT),
            stdout=open(api_log_path, "w"),
            stderr=subprocess.STDOUT,
        )
        if not wait_health():
            failure_type = "harness_exception"
            result["failure"] = "API server failed to start"
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=failure_type)

        # Contract 7: ready -> direct; blocked -> cold repair EXACTLY ONCE;
        # anything else fails (v2 eval-None policy, made explicit).
        remediation = {"invoked": False}
        facts["phase"] = "evaluation"
        if eval_state == "ready":
            log(f"{label} policy: ready -> no remediation (Path A)")
        elif eval_state == "blocked":
            log(f"{label} policy: blocked -> cold repair ONCE")
            status, _, payload = http_status(
                "POST",
                f"/api/v1/ideas/{state['idea_id']}/paper/repair",
            )
            body = safe_json(payload)
            if status != 200:
                remediation = {
                    "invoked": True, "http": status,
                    "error_body": payload.decode("utf-8", "replace")[:400],
                }
                facts["repair_invoked"] = True
                result["steps"].append(
                    {"step": "7", "remediation": remediation}
                )
                result["failure"] = (
                    f"cold repair route returned HTTP {status}"
                )
                return worker_finish(result, facts, result_path,
                                     release_path, accepted=False,
                                     failure="remediation")
            remediation = {
                "invoked": True,
                "http": status,
                "promoted": body.get("repair", {}).get("promoted"),
                "eval_status": body.get("evaluation", {}).get("status"),
            }
            facts["repair_invoked"] = True
            log(f"{label} repair: {json.dumps(remediation)[:200]}")
        else:
            result["failure"] = (
                f"no usable paper evaluation exists (eval_state="
                f"{eval_state!r}) — nothing to repair, nothing to freeze"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure="evaluation")
        result["steps"].append({"step": "7", "remediation": remediation})

        # Contracts 9-10: final evaluation, six gates, preserved revisions
        conn = sqlite3.connect(ROOT / DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_meta_json FROM proposals WHERE id=?",
            (state["proposal_id"],),
        )
        final_eval = (
            json.loads(cur.fetchone()[0]).get("paper_evaluation") or {}
        )
        conn.close()
        facts["final_eval_status"] = final_eval.get("status")
        set_ok, all_ok, raw = gate_snapshot(final_eval)
        facts["gates_raw"] = raw
        facts["gates_set_ok"] = set_ok
        facts["gates_all_passed"] = all_ok
        facts["phase"] = "gates"
        result["final_eval_status"] = final_eval.get("status")
        result["final_gates"] = raw
        log(f"{label} final eval={final_eval.get('status')}"
            f" gates_ok={set_ok and all_ok}")
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"final evaluation/gates gate failed: {f}"
                f" (status={final_eval.get('status')}, gates={raw})"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # runfail_2 repair: capture the pre-freeze revision history as an
        # immutable observation BEFORE the freeze mutation commits, and
        # fail closed if the snapshot is not collectable.
        pre_rows = revision_rows_for(state["proposal_id"])
        facts["pre_freeze_revision_rows"] = [
            {"id": r[0], "revision_number": r[1], "parent": r[2],
             "eval_status": r[3], "source": r[4]}
            for r in pre_rows
        ]
        facts["_collected"] += ["pre_freeze_revision_rows"]

        # Contract 11: freeze
        log(f"{label} freeze")
        status, _, payload = http_status(
            "POST",
            f"/api/v1/ideas/{state['idea_id']}/paper/freeze",
            timeout=120,
        )
        release = safe_json(payload).get("release", {})
        if status != 200:
            result["failure"] = (
                f"freeze route returned HTTP {status}:"
                f" {payload.decode('utf-8', 'replace')[:400]}"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure="freeze")
        facts["freeze_state"] = release.get("state")
        facts["release_eligible"] = bool(release.get("release_eligible"))
        facts["_collected"] += ["freeze_state", "release_eligible"]
        frozen_revision_id = release.get("frozen_revision_id")
        result["freeze"] = {
            "http": status, "state": release.get("state"),
            "frozen_revision_id": frozen_revision_id,
            "release_eligible": release.get("release_eligible"),
        }
        facts["phase"] = "freeze"
        require_facts(facts, "freeze")
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"freeze did not produce a release-eligible frozen revision"
                f" ({release.get('state')!r},"
                f" eligible={release.get('release_eligible')})"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        rows = revision_rows_for(state["proposal_id"])
        facts["revision_rows"] = [
            {"id": r[0], "revision_number": r[1], "parent": r[2],
             "eval_status": r[3], "source": r[4]}
            for r in rows
        ]
        facts["revisions_preserved"] = revisions_preserved(
            pre_rows, rows, frozen_revision_id
        )
        facts["_collected"] += ["revisions_preserved"]
        facts["phase"] = "revisions"
        require_facts(facts, "revisions")
        f = first_failure(facts)
        if f:
            failure_type = f
            result["failure"] = (
                f"revision history not preserved: {facts['revision_rows']}"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure=f)

        # Contract 12: release + E == F == R == H
        log(f"{label} release + E==F==R==H")
        status, headers, payload = http_status(
            "GET",
            f"/api/v1/export/paper/release/markdown/{state['idea_id']}",
            timeout=120,
        )
        if status != 200:
            result["failure"] = (
                f"release export returned HTTP {status}:"
                f" {payload.decode('utf-8', 'replace')[:400]}"
            )
            return worker_finish(result, facts, result_path, release_path,
                                 accepted=False, failure="release_identity")
        facts["H"] = header_get(headers, "x-erlab-paper-hash")
        conn = sqlite3.connect(ROOT / DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_md, paper_meta_json FROM proposals WHERE id=?",
            (state["proposal_id"],),
        )
        paper_md, meta = cur.fetchone()
        facts["E"] = (
            (json.loads(meta).get("paper_evaluation") or {})
            .get("paper_hash", "")
        )
        cur.execute(
            "SELECT paper_hash, eval_status FROM paper_revisions WHERE id=?",
            (frozen_revision_id,),
        )
        f_hash, frozen_eval = cur.fetchone()
        conn.close()
        facts["F"] = f_hash
        facts["frozen_eval_status"] = frozen_eval
        facts["R"] = sha256_bytes(payload)
        facts["release_equals_current"] = (
            payload.decode("utf-8").strip() == paper_md.strip()
        )
        facts["_collected"] += ["E", "F", "R", "H",
                                "release_equals_current",
                                "frozen_eval_status"]
        facts["phase"] = "release_identity"
        require_facts(facts, "release_identity")
        result["verification"] = {
            "E": facts["E"], "F": facts["F"], "R": facts["R"],
            "H": facts["H"],
            "equality": facts["E"] == facts["F"] == facts["R"] == facts["H"],
            "frozen_eval_status": frozen_eval,
            "release_equals_current_bytes": facts["release_equals_current"],
        }
        release_path.write_bytes(payload)
        f = first_failure(facts)
        accepted = f is None
        if not accepted:
            failure_type = f
            result["failure"] = (
                f"release identity verification failed: {result['verification']}"
            )
        return worker_finish(result, facts, result_path, release_path,
                             accepted=accepted, failure=f)
    except Exception as exc:  # noqa: BLE001 — sealed harness must not crash
        failure_type = "harness_exception"
        result["failure"] = f"harness exception: {exc!r}"
        return worker_finish(result, facts, result_path, release_path,
                             accepted=False, failure=failure_type)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except Exception:
                server.kill()


def worker_finish(result: dict, facts: dict, result_path: Path,
                  release_path: Path, accepted: bool,
                  failure: str | None) -> int:
    result["finished_at"] = now_iso()
    result["decision"] = "ACCEPTED" if accepted else "FAIL"
    result["failure_type"] = failure
    result["subtype_group"] = SUBTYPE_GROUPS.get(failure or "", "")
    result["facts"] = {
        k: v for k, v in facts.items()
        if k not in ("phase", "_collected")
    }
    result["log"] = LOG_LINES
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[CASE4-{facts.get('label')}] DECISION: {result['decision']}",
          flush=True)
    if not accepted:
        print(
            f"[CASE4-{facts.get('label')}] FAILURE ({failure}):"
            f" {result.get('failure')}",
            flush=True,
        )
    return 0 if accepted else 1


# ---------------------------------------------------------------------------
# Preflight (C4-4): hard gates, fresh-state establishment, baseline.
# ---------------------------------------------------------------------------

# Allowed delta vs the product head on the evidence branch: evidence material plus
# exactly ".gitattributes" (byte-exact round-trip for sealed files; the
# same companion change the owner's plan records in the Q2→main delta).
ALLOWED_DELTA_PREFIXES = ("evidence/",)
ALLOWED_DELTA_FILES = {".gitattributes"}


def delta_is_allowed(path: str) -> bool:
    return (
        path.startswith(ALLOWED_DELTA_PREFIXES)
        or path in ALLOWED_DELTA_FILES
    )


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


async def probe_embedding() -> dict:
    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_providers import (
        create_embedding_provider,
    )

    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider or "lmstudio",
        model=settings.embedding_model,
        base_url=settings.embedding_base_url or None,
        dimension=int(settings.embedding_dimension or 0) or None,
    )
    vectors = await asyncio.wait_for(provider.embed(["case4-preflight"]), 30.0)
    dim = len(vectors[0]) if vectors else 0
    expected = int(settings.embedding_dimension or 0)
    return {
        "ok": bool(vectors) and dim > 0 and (not expected or dim == expected),
        "dimension": dim,
        "expected_dimension": expected,
        "model": settings.embedding_model,
    }


async def probe_evaluator() -> dict:
    import time as _t

    from backend.providers.provider_factory import create_provider

    start = _t.time()
    provider = create_provider("openai")
    response = await asyncio.wait_for(
        provider.complete(
            [{"role": "user", "content": "Reply with exactly: OK"}]
        ),
        60.0,
    )
    return {
        "ok": bool(response and response.strip()),
        "model": getattr(provider, "_model", ""),
        "latency_s": round(_t.time() - start, 1),
    }


def establish_fresh_state(archive_dir: Path) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / stamp
    archived: dict[str, str | None] = {}
    for rel in RESET_SET:
        p = ROOT / rel
        if p.exists():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dst))
            archived[rel] = "archived"
        else:
            archived[rel] = "absent"
    manifest = {
        "archived_at": now_iso(),
        "entries": archived,
        "hashes": compute_state_manifest(RESET_SET, target),
    }
    (target / "archive_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {"archived_to": str(target), "entries": archived}


def run_preflight() -> int:
    record: dict = {
        "phase": "C4-4 preflight (Case 4 reliability qualification)",
        "captured_at": now_iso(),
        "gates": {},
        "class_state": {},
    }

    def gate(name: str, ok: bool, detail=None) -> bool:
        entry: dict = {"ok": bool(ok)}
        if detail is not None:
            entry["detail"] = detail
        record["gates"][name] = entry
        log(f"PREFLIGHT {name}: {'OK' if ok else 'FAIL'}"
            + (f" — {detail}" if detail and not ok else ""))
        return bool(ok)

    ok_all = True

    # 1. exact product bytes at HEAD (the product head itself, or an
    #    evidence-branch HEAD descending from it with only the allowed delta)
    try:
        ph_ok, ph_detail = verify_product_head()
        ok_all &= gate("product_head", ph_ok, ph_detail)
    except Exception as exc:
        ok_all &= gate("product_head", False, repr(exc))

    # 2. clean tracked tree
    try:
        status = git_output("status", "--porcelain")
        tracked = [l for l in status.splitlines()
                   if not l.startswith("??")]
        untracked_outside = [
            l[3:] for l in status.splitlines()
            if l.startswith("??") and not l[3:].startswith("evidence/")
        ]
        ok_all &= gate("clean_tracked_tree", not tracked, tracked)
        ok_all &= gate(
            "untracked_only_evidence", not untracked_outside,
            untracked_outside,
        )
    except Exception as exc:
        ok_all &= gate("clean_tracked_tree", False, repr(exc))

    # 3. no production delta vs the product head
    try:
        changed = [
            l for l in git_output("diff", "--name-only", PRODUCT_HEAD, "HEAD").splitlines()
            if l
        ]
        illegal = [l for l in changed if not delta_is_allowed(l)]
        ok_all &= gate("no_product_delta_vs_product_head", not illegal,
                       {"changed": changed, "illegal": illegal})
    except Exception as exc:
        ok_all &= gate("no_product_delta_vs_product_head", False, repr(exc))

    # 4-6. seals: manifest, harness, controls record
    manifest_ok = False
    manifest: dict = {}
    try:
        mbytes = (ROOT / MANIFEST_PATH).read_bytes()
        seal = (ROOT / SEAL_PATH).read_text().strip()
        manifest = json.loads(mbytes)
        manifest_ok = (
            sha256_bytes(mbytes) == seal
            and manifest.get("product_head") == PRODUCT_HEAD
        )
        ok_all &= gate("manifest_seal", manifest_ok,
                       {"seal": seal, "product_head": manifest.get("product_head")})
    except Exception as exc:
        ok_all &= gate("manifest_seal", False, repr(exc))
    try:
        harness_sha = sha256_file(HARNESS_PATH)
        expected = (manifest.get("harness") or {}).get("sha256", "")
        ok_all &= gate("harness_seal", harness_sha == expected, harness_sha)
    except Exception as exc:
        ok_all &= gate("harness_seal", False, repr(exc))
    try:
        cbytes = (ROOT / CONTROLS_PATH).read_bytes()
        expected = (manifest.get("controls") or {}).get("sha256", "")
        ok_all &= gate("controls_seal",
                       sha256_bytes(cbytes) == expected,
                       sha256_bytes(cbytes))
    except Exception as exc:
        ok_all &= gate("controls_seal", False, repr(exc))

    # 7. API port free (no stale process holding research state)
    ok_all &= gate("api_port_free", not port_in_use(API_PORT))

    # 8. required-provider readiness through production configuration
    try:
        readiness = worker_enforce_readiness()
        ok_all &= gate("provider_readiness_production",
                       bool(readiness.get("ready")), readiness)
    except Exception as exc:
        ok_all &= gate("provider_readiness_production", False, repr(exc))

    # 9. certification / assignment identity (Class-2 fingerprint)
    try:
        reg = ROOT / "data/model_certification/production_registry.yaml"
        reg_text = reg.read_text(encoding="utf-8")
        assignments = json.loads(
            (ROOT / "data/model_assignments.json").read_text("utf-8")
        )
        ok_all &= gate(
            "certification_assignment_identity",
            "model_id: qwen3-4b-2507" in reg_text
            and isinstance(assignments, dict),
        )
    except Exception as exc:
        ok_all &= gate("certification_assignment_identity", False, repr(exc))

    # 10. embedding availability through the production factory
    try:
        emb = asyncio.run(probe_embedding())
        ok_all &= gate("embedding_availability", emb["ok"], emb)
    except Exception as exc:
        ok_all &= gate("embedding_availability", False, repr(exc))

    # 11. evaluator availability through the production provider stack
    try:
        ev = asyncio.run(probe_evaluator())
        ok_all &= gate("evaluator_availability", ev["ok"], ev)
    except Exception as exc:
        ok_all &= gate("evaluator_availability", False, repr(exc))

    # 12. governed capability registration (production listing)
    try:
        from backend.pipeline.experiment.spec_designer import (
            list_supported_capabilities,
        )
        ids = {c.capability_id for c in list_supported_capabilities()}
        need = {c["expected_capability"] for c in RUN_CONFIGS}
        ok_all &= gate("capability_registration", need <= ids,
                       sorted(ids))
    except Exception as exc:
        ok_all &= gate("capability_registration", False, repr(exc))

    # 13. governed dataset registration
    try:
        have = {
            d.name for d in (ROOT / "data/datasets").iterdir()
            if d.is_dir()
        }
        ok_all &= gate("dataset_registration",
                       set(EXPECTED_DATASETS) <= have, sorted(have))
    except Exception as exc:
        ok_all &= gate("dataset_registration", False, repr(exc))

    if not ok_all:
        record["decision"] = "PREFLIGHT_FAIL"
        (ROOT / PREFLIGHT_PATH).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        log("PREFLIGHT FAILED — no state was touched")
        return 1

    # 14. establish fresh Class-1 state (archive, never delete), then
    # initialize the empty DB schema through the production initializer
    # (the Case-3E 'new DB (0 runs)' baseline; review P0-1).
    archive = establish_fresh_state(ROOT / PREFLIGHT_ARCHIVE_DIR)
    ensure_schema()
    record["class_state"]["preflight_archive"] = archive

    # 15. fresh-state baseline: schema-initialized empty DB (file,
    # hashed) + every other Class-1 entry absent.
    baseline_manifest = compute_state_manifest(RESET_SET, ROOT)
    db_entry = baseline_manifest.get(DB_PATH)
    others_absent = all(
        e["type"] == "absent"
        for rel, e in baseline_manifest.items() if rel != DB_PATH
    )
    fresh_ok = bool(
        others_absent
        and db_entry
        and db_entry.get("type") == "file"
        and db_entry.get("sha256")
        and not missing_required_tables()
    )
    record["class_state"]["fresh_class1"] = {
        "ok": fresh_ok,
        "basis": (
            "empty schema-initialized DB (file entry, hashed) + all other"
            " Class-1 entries absent"
        ),
        "manifest": baseline_manifest,
    }
    if not fresh_ok:
        record["decision"] = "PREFLIGHT_FAIL"
        (ROOT / PREFLIGHT_PATH).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        log("PREFLIGHT FAILED — Class-1 state not fresh after reset")
        return 1
    snapshot_state(baseline_manifest, ROOT / BASELINE_DIR, RESET_SET, ROOT)
    (ROOT / BASELINE_MANIFEST_PATH).write_text(
        json.dumps(
            {"captured_at": now_iso(), "entries": baseline_manifest,
             "basis": (
                 "schema-initialized empty DB as file entry; all other"
                 " Class-1 entries absent; restore copies the DB back"
                 " before each run"
             )},
            indent=2,
        ),
        encoding="utf-8",
    )

    # 16. Class-2 fingerprint (preserved operating state)
    preserved = compute_state_manifest(PRESERVED_SET, ROOT)
    (ROOT / PRESERVED_FINGERPRINT_PATH).write_text(
        json.dumps({"captured_at": now_iso(), "entries": preserved},
                   indent=2),
        encoding="utf-8",
    )
    record["class_state"]["class2_preserved_fingerprint"] = (
        PRESERVED_FINGERPRINT_PATH
    )

    record["decision"] = "PREFLIGHT_PASS"
    (ROOT / PREFLIGHT_PATH).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    log("PREFLIGHT PASS — fresh state established, baseline snapshotted")
    return 0


# ---------------------------------------------------------------------------
# Coordinator (C4-5): serial matrix, archive, restore, fail fast.
# ---------------------------------------------------------------------------

def verify_seals() -> tuple[bool, str]:
    try:
        mbytes = (ROOT / MANIFEST_PATH).read_bytes()
        seal = (ROOT / SEAL_PATH).read_text().strip()
        if sha256_bytes(mbytes) != seal:
            return False, "manifest bytes do not match seal"
        manifest = json.loads(mbytes)
        if manifest.get("product_head") != PRODUCT_HEAD:
            return False, "manifest product_head mismatch"
        harness_sha = sha256_file(HARNESS_PATH)
        expected = (manifest.get("harness") or {}).get("sha256", "")
        if harness_sha != expected:
            return False, "harness bytes do not match manifest seal"
        return True, harness_sha
    except Exception as exc:
        return False, f"seal verification error: {exc!r}"


def verify_product_head() -> tuple[bool, str]:
    """Exact product bytes at HEAD.

    Two launch layouts prove it: HEAD IS the product head (Case-3 style,
    evidence untracked), or HEAD is an evidence-branch commit that
    descends from it and whose entire diff is the allowed evidence delta
    (sealed-branch style). Anything else fails closed."""
    try:
        head = git_output("rev-parse", "HEAD")
        status = git_output("status", "--porcelain")
        tracked = [l for l in status.splitlines() if not l.startswith("??")]
        if tracked:
            return False, f"tracked tree dirty: {tracked}"
        if head != PRODUCT_HEAD:
            base = git_output("merge-base", PRODUCT_HEAD, "HEAD")
            if base != PRODUCT_HEAD:
                return False, (
                    f"HEAD {head} is not the product head and does not"
                    f" descend from it (merge-base {base})"
                )
        changed = [
            l for l in git_output("diff", "--name-only", PRODUCT_HEAD, "HEAD").splitlines()
            if l and not delta_is_allowed(l)
        ]
        if changed:
            return False, f"product delta vs product head: {changed}"
        return True, head
    except Exception as exc:
        return False, f"product verification error: {exc!r}"


def load_baseline() -> dict:
    return json.loads(
        (ROOT / BASELINE_MANIFEST_PATH).read_text("utf-8")
    )["entries"]


def verify_fresh(baseline: dict) -> tuple[bool, list[str]]:
    diffs = diff_state_manifest(baseline, RESET_SET, ROOT)
    return not diffs, diffs


def verify_preserved() -> tuple[bool, list[str]]:
    recorded = json.loads(
        (ROOT / PRESERVED_FINGERPRINT_PATH).read_text("utf-8")
    )["entries"]
    diffs = diff_state_manifest(recorded, PRESERVED_SET, ROOT)
    return not diffs, diffs


def archive_specimen(label: str, run_entry: dict) -> dict:
    spec_dir = ROOT / SPECIMEN_ARCHIVE_DIR / label
    if spec_dir.exists():
        shutil.rmtree(spec_dir)
    spec_dir.mkdir(parents=True, exist_ok=True)
    db_src = ROOT / DB_PATH
    db_committed_name = f"evidence/case4_{label.lower()}_specimen.db"
    if db_src.exists():
        shutil.copy2(db_src, ROOT / db_committed_name)
        shutil.copy2(db_src, spec_dir / "elephant_rock.db")
    write_set = compute_state_manifest(RESET_SET, ROOT)
    snapshot_state(write_set, spec_dir / "write_set", RESET_SET, ROOT)
    manifest = {
        "archived_at": now_iso(),
        "specimen_db": (
            {"path": db_committed_name,
             "sha256": sha256_file(ROOT / db_committed_name)}
            if db_src.exists() else None
        ),
        "write_set_manifest": write_set,
    }
    (spec_dir / "specimen_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    run_entry["specimen"] = manifest["specimen_db"]
    run_entry["specimen_archive"] = str(spec_dir)
    return manifest


def kill_port_holder(port: int) -> list[int]:
    """Best-effort cleanup of an orphaned process holding `port` (Windows).

    Used only after the watchdog kills a hung worker whose API child may
    survive. The outcome is recorded; it never changes a verdict.
    """
    killed: list[int] = []
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if (
                len(parts) >= 5
                and parts[1].endswith(f":{port}")
                and parts[3] == "LISTENING"
            ):
                pid = int(parts[4])
                if pid <= 0:
                    continue
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True, timeout=30,
                )
                killed.append(pid)
    except Exception:
        pass
    return killed


def run_matrix() -> int:
    matrix: dict = {
        "case": "Case 4 — bounded serial operational repeatability (C-R-R-C)",
        "frozen_head": PRODUCT_HEAD,
        "started_at": now_iso(),
        "runs": [],
        "intervention_ledger": {
            "operator_interventions": 0,
            "human_decisions_after_launch": 0,
            "basis": (
                "single sealed invocation; the harness performed every"
                " continuation, archive, reset, and fail-fast decision"
            ),
        },
        "coordinator_log": [],
    }
    log_path = ROOT / MATRIX_LOG_PATH

    def mlog(msg: str) -> None:
        log(msg)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).isoformat() + " " + msg + "\n")

    def finish(verdict: str, subtype: str | None = None) -> int:
        matrix["finished_at"] = now_iso()
        matrix["verdict"] = verdict
        matrix["failure_subtype"] = subtype
        matrix["coordinator_log"] = LOG_LINES.copy()
        (ROOT / MATRIX_RESULT_PATH).write_text(
            json.dumps(matrix, indent=2), encoding="utf-8"
        )
        mlog(f"MATRIX VERDICT: {verdict}"
             + (f" ({subtype})" if subtype else ""))
        return 0 if verdict == "PASS" else 1

    # Sealed-conditions verification (INVALID_ATTEMPT class on failure)
    ok, detail = verify_seals()
    if not ok:
        matrix["invalid_reason"] = detail
        return finish("INVALID_ATTEMPT", "seal_verification")
    matrix["harness_sha256"] = detail
    ok, detail = verify_product_head()
    if not ok:
        matrix["invalid_reason"] = detail
        return finish("INVALID_ATTEMPT", "product_head")
    if not (ROOT / BASELINE_MANIFEST_PATH).exists():
        matrix["invalid_reason"] = "no preflight baseline; run preflight first"
        return finish("INVALID_ATTEMPT", "missing_preflight")
    baseline = load_baseline()

    for cfg in RUN_CONFIGS:
        label = cfg["label"]
        entry: dict = {
            "label": label, "family": cfg["family"],
            "expected_capability": cfg["expected_capability"],
        }

        # Contract 14: demonstrably fresh research state before the run
        fresh, diffs = verify_fresh(baseline)
        preserved_ok, pdiffs = verify_preserved()
        if not fresh:
            entry["verdict"] = "INVALID"
            entry["fresh_state_diffs"] = diffs
            matrix["runs"].append(entry)
            return finish("INVALID_ATTEMPT", "fresh_state")
        if not preserved_ok:
            entry["verdict"] = "INVALID"
            entry["preserved_state_diffs"] = pdiffs
            matrix["runs"].append(entry)
            return finish("INVALID_ATTEMPT", "operating_state_drift")
        if port_in_use(API_PORT):
            entry["verdict"] = "INVALID"
            matrix["runs"].append(entry)
            return finish("INVALID_ATTEMPT", "api_port_occupied")
        mlog(f"{label}: fresh state verified (empty-schema DB intact,"
             " other Class-1 absent, Class-2 intact)")

        # Fresh-process worker (charter: no long-lived interpreter reuse)
        started = time.time()
        mlog(f"{label}: launching worker subprocess")
        run_log = ROOT / f"evidence/case4_{label.lower()}_run.log"
        with open(run_log, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(HARNESS_PATH),
                 "--mode", "worker", "--run", label],
                cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT,
            )
            try:
                code = proc.wait(timeout=WATCHDOG_S)
                watchdog = False
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=30)
                watchdog = True
        elapsed = round(time.time() - started, 1)
        entry["elapsed_s"] = elapsed

        if watchdog:
            killed = kill_port_holder(API_PORT)
            entry.update({
                "verdict": "RUN_FAIL",
                "failure_type": "watchdog_hang",
                "subtype_group": SUBTYPE_GROUPS["watchdog_hang"],
                "detail": f"worker exceeded {WATCHDOG_S}s hang watchdog",
                "orphan_cleanup_pids": killed,
            })
            matrix["runs"].append(entry)
            archive_specimen(label, entry)
            return finish("RUN_FAIL", "watchdog_hang")

        # Worker verdict + record must agree
        result_path = ROOT / f"evidence/case4_{label.lower()}_result.json"
        try:
            record = json.loads(result_path.read_text("utf-8"))
        except Exception as exc:
            entry.update({
                "verdict": "INVALID", "failure_type": "harness_exception",
                "detail": f"worker result unreadable: {exc!r}",
            })
            matrix["runs"].append(entry)
            archive_specimen(label, entry)
            return finish("INVALID_ATTEMPT", "harness_integrity")
        decision = record.get("decision")
        if (code == 0) != (decision == "ACCEPTED"):
            entry.update({
                "verdict": "INVALID", "failure_type": "harness_exception",
                "detail": (
                    f"worker exit code {code} disagrees with decision"
                    f" {decision!r}"
                ),
            })
            matrix["runs"].append(entry)
            archive_specimen(label, entry)
            return finish("INVALID_ATTEMPT", "harness_integrity")

        facts = record.get("facts", {})
        entry.update({
            "verdict": decision,
            "failure_type": record.get("failure_type"),
            "subtype_group": record.get("subtype_group"),
            "failure_detail": record.get("failure"),
            "capability_id": facts.get("capability_id"),
            "spec_ids": facts.get("spec_ids"),
            "initial_eval_status": facts.get("eval_state"),
            "repair_invoked": facts.get("repair_invoked"),
            "final_eval_status": facts.get("final_eval_status"),
            "gates": facts.get("gates_raw"),
            "revision_sequence": facts.get("revision_rows"),
            "release": record.get("verification"),
            "diagnostics": {
                "orchestrator_elapsed_s": next(
                    (s.get("orchestrator", {}).get("elapsed_s")
                     for s in record.get("steps", [])
                     if s.get("step") == "2"),
                    None,
                ),
                "run_id": record.get("pipeline_run_id"),
                "failure_subtype_preserved": record.get("failure_type"),
            },
        })
        matrix["runs"].append(entry)

        if decision != "ACCEPTED":
            archive_specimen(label, entry)
            return finish(
                "RUN_FAIL",
                record.get("subtype_group") or record.get("failure_type"),
            )

        # Contract 14: archive, then restore fresh state for the next run
        archive_specimen(label, entry)
        mlog(f"{label}: ACCEPTED in {elapsed}s; specimen archived;"
             " restoring fresh state")
        restore_state(baseline, ROOT / BASELINE_DIR, RESET_SET, ROOT)
        fresh, diffs = verify_fresh(baseline)
        if not fresh:
            entry["post_restore_fresh_diffs"] = diffs
            return finish("INVALID_ATTEMPT", "restore_failed")
        mlog(f"{label}: fresh state restored and verified")

    return finish("PASS")


# ---------------------------------------------------------------------------
# Controls (C4-2): synthetic qualification of the sealed decision logic.
# No production imports, no providers, no real research state.
# ---------------------------------------------------------------------------

def positive_facts_repair() -> dict:
    f = default_facts(RUN_CONFIGS[1])
    f.update({
        "phase": "release_identity",
        "provider_ready": True,
        "outcome": "SUCCEEDED", "outcome_is_success": True,
        "design_status": "designed",
        "capability_id": f["expected_capability"],
        "n_specs": 2, "spec_ids": ["s1", "s2"], "spec_ids_complete": True,
        "experiments_success": 2,
        "method_facts_count": 5, "method_facts_keys": ["m1"],
        "eval_state": "blocked",
        "repair_invoked": True,
        "final_eval_status": "ready",
        "gates_raw": {
            "provenance": True, "scope_alignment": "on_scope",
            "conclusion_support": "supported_by_paper",
            "experiment_alignment": True, "numeric_fidelity": True,
            "method_fidelity": True,
        },
        "gates_set_ok": True, "gates_all_passed": True,
        "revision_rows": [
            {"id": 1, "revision_number": 0, "parent": None,
             "eval_status": "blocked", "source": "pipeline"},
            {"id": 2, "revision_number": 1, "parent": 1,
             "eval_status": "ready", "source": "auto_remediation"},
            {"id": 3, "revision_number": 2, "parent": 2,
             "eval_status": "ready", "source": "release"},
        ],
        "pre_freeze_revision_rows": [
            {"id": 1, "revision_number": 0, "parent": None,
             "eval_status": "blocked", "source": "pipeline"},
            {"id": 2, "revision_number": 1, "parent": 1,
             "eval_status": "ready", "source": "auto_remediation"},
        ],
        "revisions_preserved": True,
        "freeze_state": "frozen", "release_eligible": True,
        "E": "a" * 64, "F": "a" * 64, "R": "a" * 64, "H": "a" * 64,
        "release_equals_current": True,
        "frozen_eval_status": "ready",
    })
    return f


def positive_facts_ready() -> dict:
    f = positive_facts_repair()
    f["eval_state"] = "ready"
    f["repair_invoked"] = False
    return f


def run_controls() -> int:
    results: list[dict] = []
    all_ok = True

    def control(name: str, ok: bool, detail=None) -> None:
        nonlocal all_ok
        results.append({
            "control": name, "expected": "fail_closed" if "negative" in name
            else "pass", "ok": bool(ok), "detail": detail,
        })
        if not ok:
            all_ok = False

    # Positive branches
    control("positive_ready_without_repair",
            first_failure(positive_facts_ready()) is None)
    control("positive_blocked_one_repair",
            first_failure(positive_facts_repair()) is None)

    # Phase semantics: early milestones must not fire on later defaults,
    # and must fire on their own violation at that phase.
    early = positive_facts_repair()
    early["phase"] = "design"
    early["freeze_state"] = "failed"  # later-phase default violation
    control("phase_no_premature_failure", first_failure(early) is None,
            {"phase": "design", "got": first_failure(early)})
    early["design_status"] = "failed_design"
    control("phase_fails_own_violation",
            first_failure(early) == "design",
            {"phase": "design", "got": first_failure(early)})

    # Negative controls: exactly one contract item falsified per case
    def negative(name: str, expected_check: str, **overrides) -> None:
        f = positive_facts_repair()
        f.update(overrides)
        got = first_failure(f)
        control(f"negative_{name}", got == expected_check,
                {"expected": expected_check, "got": got})

    negative("orchestrator_nonsuccess", "orchestration",
             outcome="FAILED", outcome_is_success=False)
    negative("missing_design", "design", design_status=None)
    negative("wrong_capability", "capability", capability_id="other_v1")
    negative("incomplete_specs", "specs", spec_ids_complete=False)
    negative("unsuccessful_experiment_count", "experiments",
             experiments_success=1)
    negative("missing_method_facts", "persistence", method_facts_count=0)
    negative("missing_evaluation", "evaluation", eval_state=None)
    negative("repair_failure", "remediation",
             repair_invoked=True, final_eval_status="blocked")
    negative("final_not_ready_without_repair", "final_ready",
             eval_state="ready", repair_invoked=False,
             final_eval_status="blocked")
    negative("gate_missing", "gates", gates_set_ok=False,
             gates_all_passed=False)
    negative("gate_failed", "gates",
             gates_raw={**positive_facts_repair()["gates_raw"],
                        "provenance": False},
             gates_all_passed=False)
    negative("revisions_deleted", "revisions", revisions_preserved=False)
    negative("freeze_not_frozen", "freeze", freeze_state="failed")
    negative("efrh_mismatch", "release_identity", R="b" * 64)
    negative("release_bytes_differ", "release_identity",
             release_equals_current=False)
    negative("provider_not_ready", "provider_readiness",
             provider_ready=False)

    # State-manifest controls in a sandbox
    sandbox = ROOT / SANDBOX_DIR
    if sandbox.exists():
        shutil.rmtree(sandbox)
    base = sandbox / "state"
    (base / "d/sub").mkdir(parents=True)
    (base / "d/sub" / "f1.txt").write_text("one")
    (base / "f.txt").write_text("hello")
    paths = ["d", "f.txt", "gone"]
    manifest = compute_state_manifest(paths, base)
    snap = sandbox / "snap"
    snapshot_state(manifest, snap, paths, base)
    control("state_verify_intact",
            not diff_state_manifest(manifest, paths, base))
    (base / "d" / "extra.txt").write_text("x")
    control("state_detect_extra_file",
            bool(diff_state_manifest(manifest, paths, base)))
    (base / "d" / "extra.txt").unlink()
    (base / "f.txt").write_text("tampered")
    control("state_detect_modified_file",
            bool(diff_state_manifest(manifest, paths, base)))
    restore_state(manifest, snap, paths, base)
    control("state_restore_recovers",
            not diff_state_manifest(manifest, paths, base))
    (base / "f.txt").unlink()
    control("state_detect_deleted_file",
            bool(diff_state_manifest(manifest, paths, base)))
    restore_state(manifest, snap, paths, base)

    # Subtype map covers every check
    uncovered = [
        name for name, _ in CHECK_ORDER if name not in SUBTYPE_GROUPS
    ]
    control("subtype_map_complete", not uncovered, uncovered)

    # ── runfail_2 checker-repair controls ──────────────────────────
    # (1) Alignment invariant: at every phase, facts collected exactly
    # through that phase (all later-check inputs at their defaults)
    # must produce NO failure. The old order (revisions before freeze)
    # failed exactly this at phase='freeze' with a default-False
    # revisions fact — the preserved false-failure shape.
    base = positive_facts_repair()
    defaults = default_facts(RUN_CONFIGS[1])
    ordered_inputs = [(name, FACT_INPUTS[name]) for name, _ in CHECK_ORDER]
    alignment_bad = []
    for idx, (phase_name, _) in enumerate(CHECK_ORDER):
        f = dict(base)
        current_keys = {k for _n, keys in ordered_inputs[:idx + 1]
                        for k in keys}
        for _later, keys in ordered_inputs[idx + 1:]:
            for k in keys:
                if k not in current_keys:
                    f[k] = defaults.get(k)
        f["phase"] = phase_name
        got = first_failure(f)
        if got is not None:
            alignment_bad.append(f"{phase_name}->{got}")
    control("phase_alignment_no_premature_failure",
            not alignment_bad, alignment_bad)

    # (2) Availability guard: a missing pre-freeze snapshot raises
    # BEFORE the freeze milestone commits, instead of producing a
    # post-freeze false failure.
    guard_facts = positive_facts_repair()
    guard_facts["_collected"] = []
    try:
        require_facts(guard_facts, "revisions")
        guard_raised = False
    except RuntimeError:
        guard_raised = True
    control("guard_missing_facts_raise_before_milestone", guard_raised)

    # (3) Prefix-preservation semantics: the immutable pre-freeze
    # snapshot must be an exact prefix of the post-freeze rows.
    pre_rows = [(1, 0, None, "blocked", "pipeline"),
                (2, 1, 1, "ready", "auto_remediation")]
    post_rows = pre_rows + [(3, 2, 2, "ready", "release")]
    tampered_pre = [(1, 0, None, "ready", "pipeline"),
                    (2, 1, 1, "ready", "auto_remediation")]
    control("revisions_prefix_preserved_ok",
            revisions_preserved(pre_rows, post_rows, 3))
    control("revisions_prefix_tampered_fails",
            not revisions_preserved(tampered_pre, post_rows, 3))
    control("revisions_frozen_id_missing_fails",
            not revisions_preserved(pre_rows, pre_rows, 99))

    # Behavioral control (mandatory per the 2026-08-18 adjudication): a
    # REAL temporary SQLite database, cold process, through the exact
    # production initialization path the harness uses — the mechanism
    # that actually failed in the invalidated attempt.
    selfcheck_db = sandbox / "schema_selfcheck.db"
    proc = subprocess.run(
        [sys.executable, "-u", str(HARNESS_PATH),
         "--mode", "schema-selfcheck", "--db", str(selfcheck_db)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    control(
        "behavioral_cold_init_creates_schema",
        proc.returncode == 0
        and not missing_required_tables(str(selfcheck_db)),
        {
            "exit": proc.returncode,
            "stdout_tail": proc.stdout.strip()[-200:],
            "stderr_tail": proc.stderr.strip()[-200:],
            "db": str(selfcheck_db),
        },
    )

    record = {
        "phase": "C4-2 harness qualification — synthetic controls",
        "captured_at": now_iso(),
        "controls": results,
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r["ok"]),
        },
        "decision": "CONTROLS_PASS" if all_ok else "CONTROLS_FAIL",
    }
    (ROOT / CONTROLS_PATH).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    print(f"[CASE4-CONTROLS] {record['decision']}"
          f" ({record['summary']['ok']}/{record['summary']['total']})",
          flush=True)
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# Independent verification (C4-6): recompute from preserved specimens.
# ---------------------------------------------------------------------------

def verify_run_record(label: str, cfg: dict) -> dict:
    low = label.lower()
    out: dict = {"label": label, "checks": {}}
    result = json.loads(
        (ROOT / f"evidence/case4_{low}_result.json").read_text("utf-8")
    )
    matrix = json.loads(
        (ROOT / MATRIX_RESULT_PATH).read_text("utf-8")
    )
    entry = next(
        (r for r in matrix["runs"] if r["label"] == label), None
    )
    specimen_db = ROOT / f"evidence/case4_{low}_specimen.db"
    release_file = ROOT / f"evidence/case4_{low}_release.md"

    def check(name: str, ok: bool, detail=None) -> bool:
        entry_out: dict = {"ok": bool(ok)}
        if detail is not None:
            entry_out["detail"] = detail
        out["checks"][name] = entry_out
        return bool(ok)

    ok = True
    ok &= check("matrix_entry_accepted",
                bool(entry) and entry.get("verdict") == "ACCEPTED")
    ok &= check("result_decision_accepted",
                result.get("decision") == "ACCEPTED")
    ok &= check("interventions_zero",
                result.get("operator_interventions") == 0)

    if specimen_db.exists():
        conn = sqlite3.connect(
            f"file:{specimen_db.as_posix()}?mode=ro", uri=True
        )
        try:
            cur = conn.cursor()
            pid = result.get("proposal_id")
            cur.execute(
                "SELECT paper_meta_json FROM proposals WHERE id=?", (pid,)
            )
            row = cur.fetchone()
            meta = json.loads(row[0]) if row and row[0] else {}
            design = meta.get("autonomous_experiment_design") or {}
            ok &= check("capability_expected",
                        design.get("capability_id")
                        == cfg["expected_capability"],
                        design.get("capability_id"))
            ok &= check("design_designed",
                        design.get("status") == "designed")
            ok &= check("method_facts_present",
                        bool(design.get("method_facts")))
            n_specs = len(design.get("specs") or [])
            cur.execute(
                "SELECT COUNT(*) FROM experiment_results WHERE"
                " proposal_id=? AND success=1",
                (pid,),
            )
            n_success = cur.fetchone()[0]
            ok &= check("experiments_all_success",
                        n_success == n_specs,
                        {"success": n_success, "expected": n_specs})
            ev = meta.get("paper_evaluation") or {}
            E = ev.get("paper_hash", "")
            gates_raw = {
                (g.get("gate") or g.get("name")):
                g.get("passed", g.get("classification"))
                for g in ev.get("gates", []) if isinstance(g, dict)
            }
            ok &= check("six_gates_present",
                        set(gates_raw) == SIX_GATES, sorted(gates_raw))
            ok &= check("final_eval_ready", ev.get("status") == "ready")
            frozen_id = result.get("freeze", {}).get("frozen_revision_id")
            cur.execute(
                "SELECT paper_hash, eval_status FROM paper_revisions"
                " WHERE id=?",
                (frozen_id,),
            )
            frow = cur.fetchone()
            F = frow[0] if frow else ""
            ok &= check("frozen_revision_ready",
                        bool(frow) and frow[1] == "ready")
            cur.execute(
                "SELECT revision_number FROM paper_revisions WHERE"
                " proposal_id=? ORDER BY revision_number",
                (pid,),
            )
            numbers = [r[0] for r in cur.fetchall()]
            ok &= check("revision_history_contiguous",
                        numbers == list(range(len(numbers))), numbers)
        finally:
            conn.close()
        R = sha256_file(release_file) if release_file.exists() else ""
        H = (result.get("verification") or {}).get("H", "")
        ok &= check("efrh_equality", E == F == R == H and bool(E),
                    {"E": E, "F": F, "R": R, "H": H})
        spec_manifest = json.loads(
            (ROOT / SPECIMEN_ARCHIVE_DIR / label
             / "specimen_manifest.json").read_text("utf-8")
        )
        ok &= check(
            "specimen_db_hash",
            (spec_manifest.get("specimen_db") or {}).get("sha256")
            == sha256_file(specimen_db),
        )
    else:
        ok &= check("specimen_db_present", False)

    out["ok"] = ok
    return out


def run_verify() -> int:
    matrix = json.loads(
        (ROOT / MATRIX_RESULT_PATH).read_text("utf-8")
    )
    runs = [
        verify_run_record(cfg["label"], cfg) for cfg in RUN_CONFIGS
    ]
    all_ok = (
        all(r["ok"] for r in runs)
        and matrix.get("verdict") == "PASS"
        and matrix.get("intervention_ledger", {}).get(
            "operator_interventions"
        ) == 0
    )
    record = {
        "phase": "C4-6 independent verification",
        "captured_at": now_iso(),
        "matrix_verdict": matrix.get("verdict"),
        "runs": runs,
        "decision": "VERIFIED" if all_ok else "VERIFICATION_FAIL",
    }
    (ROOT / VERIFICATION_PATH).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    print(f"[CASE4-VERIFY] {record['decision']}", flush=True)
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def guarded(mode_fn, decision_on_crash: str, path: str) -> int:
    """Fail-closed wrapper: an unexpected exception still writes a verdict
    record instead of exiting with a traceback. Per-run evidence files
    already on disk remain preserved."""
    try:
        return mode_fn()
    except Exception as exc:  # noqa: BLE001 — sealed harness must not crash
        record = {
            "case": "Case 4 — bounded serial operational repeatability",
            "frozen_head": PRODUCT_HEAD,
            "finished_at": now_iso(),
            "verdict": decision_on_crash,
            "invalid_reason": f"{mode_fn.__name__} exception: {exc!r}",
            "note": (
                "unexpected harness exception; per-run evidence files under"
                " evidence/case4_* and specimens remain preserved on disk"
            ),
        }
        (ROOT / path).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        print(f"[CASE4] {decision_on_crash}: {record['invalid_reason']}",
              flush=True)
        return 1


def run_schema_selfcheck(db_path: str) -> int:
    """Cold-process behavioral check against a real SQLite file.

    Sets the database URL BEFORE any backend import so production
    settings resolve to the temporary file, runs the same ensure_schema()
    the preflight and worker run, and verifies the required tables by
    querying the file directly. Exit 0 only when the tables exist."""
    os.environ["EROCK_DATABASE_URL"] = (
        "sqlite:///" + Path(db_path).resolve().as_posix()
    )
    try:
        ensure_schema(db_path)
    except Exception as exc:  # noqa: BLE001 — report, don't crash
        print(f"[SCHEMA-SELFCHECK] FAIL: {exc!r}", flush=True)
        return 1
    missing = missing_required_tables(db_path)
    if missing:
        print(
            f"[SCHEMA-SELFCHECK] FAIL: missing {sorted(missing)}",
            flush=True,
        )
        return 2
    print(
        f"[SCHEMA-SELFCHECK] OK: {len(REQUIRED_TABLES)} required tables"
        f" present in {db_path}",
        flush=True,
    )
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.chdir(ROOT)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=["launch", "preflight", "matrix", "worker", "controls",
                 "verify", "schema-selfcheck"],
    )
    parser.add_argument("--run", choices=[c["label"] for c in RUN_CONFIGS])
    parser.add_argument(
        "--db", help="temp database path for --mode schema-selfcheck"
    )
    args = parser.parse_args()

    if args.mode == "launch":
        if guarded(run_preflight, "PREFLIGHT_FAIL", PREFLIGHT_PATH) != 0:
            return 1
        return guarded(run_matrix, "INVALID_ATTEMPT", MATRIX_RESULT_PATH)
    if args.mode == "preflight":
        return guarded(run_preflight, "PREFLIGHT_FAIL", PREFLIGHT_PATH)
    if args.mode == "matrix":
        return guarded(run_matrix, "INVALID_ATTEMPT", MATRIX_RESULT_PATH)
    if args.mode == "worker":
        if not args.run:
            print("--mode worker requires --run", file=sys.stderr)
            return 2
        return run_worker(args.run)
    if args.mode == "controls":
        return guarded(run_controls, "CONTROLS_FAIL", CONTROLS_PATH)
    if args.mode == "schema-selfcheck":
        if not args.db:
            print("--mode schema-selfcheck requires --db",
                  file=sys.stderr)
            return 2
        return run_schema_selfcheck(args.db)
    return guarded(run_verify, "VERIFICATION_FAIL", VERIFICATION_PATH)


if __name__ == "__main__":
    sys.exit(main())
