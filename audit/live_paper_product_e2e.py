#!/usr/bin/env python3
"""Read-only live product E2E for the sealed ERLab v1.0.1 baseline.

The harness triggers the actual public pipeline API, waits for durable state,
extracts the generated paper and its evidence records, exercises the production
paper export routes, and verifies persistence after a backend restart.

It never prints provider credentials and never changes product source code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", ROOT / "evidence" / "live-paper"))
API_BASE = os.environ.get("ERLAB_API_BASE", "http://127.0.0.1:8000").rstrip("/")
POLL_SECONDS = float(os.environ.get("ERLAB_POLL_SECONDS", "10"))
TIMEOUT_SECONDS = float(os.environ.get("ERLAB_PIPELINE_TIMEOUT_SECONDS", "3600"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, data: Any) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def api_request(method: str, path: str, payload: Any | None = None, timeout: float = 60.0) -> tuple[int, bytes, dict[str, str]]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers.items())


def decode_json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return {"raw": data.decode("utf-8", errors="replace")}


def db_file_from_url() -> Path | None:
    url = os.environ.get("EROCK_DATABASE_URL", "")
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    raw = url[len(prefix):]
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def snapshot_sqlite(destination: Path) -> str | None:
    source = db_file_from_url()
    if source is None or not source.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return sha256_bytes(destination.read_bytes())


def durable_run_state(run_id: str) -> dict[str, Any] | None:
    from backend.db.database import get_session
    from backend.db.models import PipelineRun

    with get_session() as session:
        row = session.execute(
            select(PipelineRun).where(PipelineRun.run_id_str == run_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "run_id": row.run_id_str,
            "status": row.status,
            "current_stage": row.current_stage,
            "domain": row.domain,
            "config_json": row.config_json,
            "created_at": row.created_at,
            "completed_at": row.completed_at,
            "error_message": row.error_message,
        }


def extract_product_state(run_id: str) -> dict[str, Any]:
    """Extract all generated paper candidates from the fresh audit database."""
    from backend.db.database import get_session
    from backend.db.models import Idea, PaperSourceMarker, PipelineRun, Proposal

    state: dict[str, Any] = {"run_id": run_id, "captured_at": now(), "proposals": []}
    with get_session() as session:
        run = session.execute(
            select(PipelineRun).where(PipelineRun.run_id_str == run_id)
        ).scalar_one_or_none()
        state["run"] = None if run is None else {
            "id": run.id,
            "status": run.status,
            "current_stage": run.current_stage,
            "domain": run.domain,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "error_message": run.error_message,
        }

        proposals = session.execute(select(Proposal).order_by(Proposal.id)).scalars().all()
        for proposal in proposals:
            idea = session.get(Idea, proposal.idea_id) if proposal.idea_id else None
            source_rows = session.execute(
                select(PaperSourceMarker)
                .where(PaperSourceMarker.proposal_id == proposal.id)
                .order_by(PaperSourceMarker.marker_index)
            ).scalars().all()
            meta_raw = getattr(proposal, "paper_meta_json", None)
            try:
                meta = json.loads(meta_raw) if meta_raw else {}
            except Exception:
                meta = {"_parse_error": True, "raw": meta_raw}
            paper = (getattr(proposal, "paper_md", None) or "").strip()
            state["proposals"].append({
                "proposal_id": proposal.id,
                "idea_id": proposal.idea_id,
                "idea_title": getattr(idea, "title", None),
                "proposal_content_present": bool((getattr(proposal, "content_md", None) or "").strip()),
                "paper_present": bool(paper),
                "paper_word_count": len(paper.split()),
                "paper_sha256": sha256_text(paper) if paper else None,
                "paper_meta": meta,
                "source_map": [
                    {
                        "marker_index": row.marker_index,
                        "marker": row.marker,
                        "source_paper_id": row.source_paper_id,
                        "mapping_status": row.mapping_status,
                    }
                    for row in source_rows
                ],
            })
    return state


def choose_paper(state: dict[str, Any]) -> dict[str, Any] | None:
    papers = [p for p in state.get("proposals", []) if p.get("paper_present")]
    if not papers:
        return None
    return max(papers, key=lambda p: p.get("paper_word_count", 0))


def load_paper_text(proposal_id: int) -> str:
    from backend.db.database import get_session
    from backend.db.models import Proposal

    with get_session() as session:
        proposal = session.get(Proposal, proposal_id)
        return (getattr(proposal, "paper_md", None) or "").strip() if proposal else ""


def assess_paper(paper: str, selected: dict[str, Any]) -> dict[str, Any]:
    source_markers = sorted(set(re.findall(r"\[SOURCE-(\d+)\]", paper)), key=int)
    result_markers = sorted(set(re.findall(r"\[RESULT-(\d+)\]", paper)), key=int)
    source_rows = selected.get("source_map", [])
    mapped_by_marker = {
        str(row.get("marker_index")): row
        for row in source_rows
        if row.get("mapping_status") == "mapped" and row.get("source_paper_id") is not None
    }
    unresolved = [m for m in source_markers if m not in mapped_by_marker]
    headings = re.findall(r"(?m)^#{1,3}\s+(.+?)\s*$", paper)
    lower_headings = [h.lower() for h in headings]
    required = ["abstract", "introduction", "method", "discussion", "conclusion"]
    section_presence = {
        section: any(section in heading for heading in lower_headings)
        for section in required
    }
    meta = selected.get("paper_meta") or {}
    evaluation = meta.get("paper_evaluation") if isinstance(meta, dict) else None
    if not evaluation and isinstance(meta, dict):
        evaluation = meta.get("evaluation")
    gates = []
    if isinstance(evaluation, dict):
        gates = evaluation.get("gates") or []
    return {
        "word_count": len(paper.split()),
        "sha256": sha256_text(paper),
        "headings": headings,
        "required_section_presence": section_presence,
        "source_markers_emitted": [f"SOURCE-{m}" for m in source_markers],
        "source_markers_unresolved": [f"SOURCE-{m}" for m in unresolved],
        "result_markers_emitted": [f"RESULT-{m}" for m in result_markers],
        "evaluation_present": bool(evaluation),
        "evaluation": evaluation,
        "gate_count": len(gates) if isinstance(gates, list) else 0,
        "meta_status": meta.get("status") if isinstance(meta, dict) else None,
    }


def export_paper(idea_id: int, prefix: str) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for fmt, extension in [("markdown", "md"), ("latex", "tex"), ("bibtex", "bib")]:
        status, body, headers = api_request("GET", f"/api/v1/export/paper/{fmt}/{idea_id}", timeout=120)
        path = EVIDENCE / f"{prefix}_paper.{extension}"
        path.write_bytes(body)
        outcomes[fmt] = {
            "status": status,
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "content_type": headers.get("Content-Type"),
            "content_disposition": headers.get("Content-Disposition"),
            "path": path.name,
        }
    return outcomes


def copy_cost_evidence() -> list[str]:
    copied: list[str] = []
    for base in [ROOT / "data" / "costs", ROOT / "data" / "traces"]:
        if not base.exists():
            continue
        target = EVIDENCE / "runtime_evidence" / base.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(base, target)
        copied.append(str(target.relative_to(EVIDENCE)))
    return copied


def run_mode() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    provider = os.environ.get("EROCK_DEFAULT_PROVIDER", "")
    provider_record = {
        "selected_provider": provider or None,
        "selected_model": {
            "openai": os.environ.get("EROCK_OPENAI_MODEL", "gpt-4o"),
            "anthropic": os.environ.get("EROCK_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "gemini": os.environ.get("EROCK_GEMINI_MODEL", "gemini-2.0-flash"),
        }.get(provider),
        "credentials_present": bool(provider),
        "credential_values_recorded": False,
        "budget_max_cost_usd": os.environ.get("EROCK_BUDGET_MAX_COST_USD"),
        "budget_max_tokens": os.environ.get("EROCK_BUDGET_MAX_TOKENS"),
        "budget_max_seconds": os.environ.get("EROCK_BUDGET_MAX_SECONDS"),
    }
    write_json("provider_selection.json", provider_record)
    if not provider:
        write_json("live_run_result.json", {
            "status": "not_executed",
            "reason": "No configured provider credential was available to the workflow.",
        })
        return 2

    health_status, health_body, _ = api_request("GET", "/health")
    write_json("health_before.json", {"status": health_status, "body": decode_json(health_body)})
    if health_status != 200:
        return 3

    payload = {
        "domain": "machine learning evaluation",
        "research_question": (
            "What lightweight, reproducible evaluation practices improve the reliability "
            "of small-data tabular classification studies?"
        ),
        "max_gaps": 1,
        "generation_rounds": 1,
        "ideas_per_round": 1,
        "search_queries": [
            "reproducible evaluation small data tabular classification calibration"
        ],
        "strategy": "deep_research",
        "export_format": "markdown",
        "proposal_depth": "concise",
        "novelty_depth": "light",
        "idea_diversity": "focused",
        "experiment_spec_id": None,
    }
    write_json("pipeline_request.json", payload)
    status, body, headers = api_request("POST", "/api/v1/pipeline/run", payload, timeout=180)
    response = decode_json(body)
    write_json("pipeline_trigger_response.json", {
        "status": status,
        "headers": {k: v for k, v in headers.items() if k.lower() not in {"set-cookie", "authorization"}},
        "body": response,
    })
    if status not in {200, 202} or not isinstance(response, dict) or not response.get("run_id"):
        write_json("live_run_result.json", {
            "status": "trigger_failed",
            "http_status": status,
            "response": response,
        })
        return 4

    run_id = str(response["run_id"])
    (EVIDENCE / "run_id.txt").write_text(run_id, encoding="utf-8")
    history: list[dict[str, Any]] = []
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_state: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        state = durable_run_state(run_id)
        if state != last_state:
            history.append({"observed_at": now(), "state": state})
            write_json("pipeline_poll_history.json", history)
            last_state = state
        if state and state.get("status") in {"completed", "failed", "cancelled"}:
            break
        time.sleep(POLL_SECONDS)
    else:
        write_json("live_run_result.json", {
            "status": "timeout",
            "run_id": run_id,
            "timeout_seconds": TIMEOUT_SECONDS,
            "last_state": last_state,
        })
        return 5

    product_state = extract_product_state(run_id)
    write_json("product_state_before_restart.json", product_state)
    selected = choose_paper(product_state)
    if selected is None:
        write_json("live_run_result.json", {
            "status": "no_paper",
            "run_id": run_id,
            "terminal_state": last_state,
            "proposal_count": len(product_state.get("proposals", [])),
        })
        snapshot_sqlite(EVIDENCE / "database_before_restart.sqlite")
        return 6

    proposal_id = int(selected["proposal_id"])
    idea_id = int(selected["idea_id"])
    paper = load_paper_text(proposal_id)
    (EVIDENCE / "generated_paper.md").write_text(paper, encoding="utf-8")
    write_json("generated_paper_meta.json", selected.get("paper_meta") or {})
    write_json("generated_paper_source_map.json", selected.get("source_map") or [])
    assessment = assess_paper(paper, selected)
    write_json("generated_paper_assessment.json", assessment)
    exports = export_paper(idea_id, "before_restart")
    write_json("exports_before_restart.json", exports)
    db_hash = snapshot_sqlite(EVIDENCE / "database_before_restart.sqlite")
    copied = copy_cost_evidence()

    before = {
        "captured_at": now(),
        "run_id": run_id,
        "run_terminal_state": last_state,
        "proposal_id": proposal_id,
        "idea_id": idea_id,
        "paper_sha256": sha256_text(paper),
        "paper_meta_sha256": sha256_text(json.dumps(selected.get("paper_meta") or {}, sort_keys=True, default=str)),
        "source_map_sha256": sha256_text(json.dumps(selected.get("source_map") or [], sort_keys=True, default=str)),
        "exports": exports,
        "database_snapshot_sha256": db_hash,
        "copied_runtime_evidence": copied,
        "assessment": assessment,
    }
    write_json("state_before_restart.json", before)
    write_json("live_run_result.json", {
        "status": "paper_produced",
        "run_id": run_id,
        "proposal_id": proposal_id,
        "idea_id": idea_id,
        "paper_word_count": assessment["word_count"],
        "evaluation_present": assessment["evaluation_present"],
        "source_markers_unresolved": assessment["source_markers_unresolved"],
        "run_status": (last_state or {}).get("status"),
    })
    return 0


def verify_mode() -> int:
    before_path = EVIDENCE / "state_before_restart.json"
    if not before_path.exists():
        write_json("restart_verification.json", {
            "status": "not_executed",
            "reason": "No paper state existed before restart.",
        })
        return 2
    before = json.loads(before_path.read_text(encoding="utf-8"))
    proposal_id = int(before["proposal_id"])
    idea_id = int(before["idea_id"])
    run_id = str(before["run_id"])

    health_status, health_body, _ = api_request("GET", "/health")
    paper = load_paper_text(proposal_id)
    state = extract_product_state(run_id)
    selected = next(
        (p for p in state.get("proposals", []) if int(p.get("proposal_id")) == proposal_id),
        None,
    )
    if selected is None:
        write_json("restart_verification.json", {
            "status": "failed",
            "reason": "Persisted proposal could not be reloaded after restart.",
            "health_status": health_status,
        })
        return 3
    exports = export_paper(idea_id, "after_restart")
    paper_hash = sha256_text(paper)
    meta_hash = sha256_text(json.dumps(selected.get("paper_meta") or {}, sort_keys=True, default=str))
    source_hash = sha256_text(json.dumps(selected.get("source_map") or [], sort_keys=True, default=str))
    comparisons = {
        "paper_hash_stable": paper_hash == before.get("paper_sha256"),
        "paper_meta_hash_stable": meta_hash == before.get("paper_meta_sha256"),
        "source_map_hash_stable": source_hash == before.get("source_map_sha256"),
        "markdown_export_hash_stable": exports["markdown"]["sha256"] == before["exports"]["markdown"]["sha256"],
        "latex_export_hash_stable": exports["latex"]["sha256"] == before["exports"]["latex"]["sha256"],
        "bibtex_export_hash_stable": exports["bibtex"]["sha256"] == before["exports"]["bibtex"]["sha256"],
    }
    result = {
        "status": "pass" if all(comparisons.values()) and health_status == 200 else "fail",
        "verified_at": now(),
        "health": {"status": health_status, "body": decode_json(health_body)},
        "comparisons": comparisons,
        "paper_sha256_after": paper_hash,
        "paper_meta_sha256_after": meta_hash,
        "source_map_sha256_after": source_hash,
        "exports_after": exports,
    }
    write_json("product_state_after_restart.json", state)
    write_json("restart_verification.json", result)
    return 0 if result["status"] == "pass" else 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["run", "verify"])
    args = parser.parse_args()
    try:
        return run_mode() if args.mode == "run" else verify_mode()
    except Exception as exc:
        write_json(f"{args.mode}_unhandled_error.json", {
            "status": "error",
            "type": type(exc).__name__,
            "message": str(exc),
            "timestamp": now(),
        })
        raise


if __name__ == "__main__":
    sys.exit(main())
