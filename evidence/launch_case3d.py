"""Case 3D: architectural qualification — harness v2.

Identical policy to the sealed v1 (d6d300c1…) with one correction
from the 3C specimen: an explicit evaluation-None branch. v1 logged
"ready -> no remediation" when no evaluation existed at all; the final
ready check still FAILed correctly, but the policy branch was wrong.
v2 fails immediately with a precise reason when there is no evaluation
(nothing was produced that repair could act on).

Pre-registered continuation policy (frozen in this file BEFORE launch;
no human decision occurs between launch and exit code):

  1. Run PipelineOrchestrator with the frozen Case-3 input
     (domain + question + autonomous_experiment_enabled=True only).
  2. REQUIRE orchestrator outcome == SUCCEEDED.
  3. REQUIRE autonomous design status == designed.
  4. REQUIRE selected capability == tabular_robust_regression_v1.
  5. REQUIRE every designed experiment succeeded
     (successful ExperimentResult rows == len(design.specs)).
  6. Read the persisted paper evaluation; if blocked, invoke the
     production cold-repair route EXACTLY ONCE; if ready, freeze;
     otherwise FAIL with no retries.
  7. Release; verify E == F == R == H and release bytes equal the
     current paper bytes.
  8. Write evidence/case3_result.json; exit 0 on acceptance, 1 on
     defined failure.

Frozen head: a057982845cfeabae55df5e02247748da9ff1c92 (Q0). No
production code changes; the harness drives only existing production
entry points.
"""
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ["EROCK_EMBEDDING_MODEL"] = "text-embedding-qwen3-embedding-0.6b"
os.environ["EROCK_EMBEDDING_DIMENSION"] = "1024"
os.environ["EROCK_EMBEDDING_PROVIDER"] = "lmstudio"

sys.path.insert(0, ".")

DB = "data/elephant_rock.db"
BASE = "http://127.0.0.1:8768"
RESULT_PATH = "evidence/case3_result.json"
RELEASE_PATH = "evidence/case3_release.md"
EXPECTED_CAPABILITY = "tabular_robust_regression_v1"
LOG_LINES: list[str] = []


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()[11:19]}Z] {msg}"
    LOG_LINES.append(line)
    print(line, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http(method: str, path: str, body: dict | None = None, timeout: float = 900.0):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


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


def read_design_state() -> dict:
    conn = sqlite3.connect(DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        )
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
            f"SELECT id, idea_id, paper_md, paper_meta_json"
            f" FROM proposals WHERE idea_id IN"
            f" ({','.join(map(str, idea_ids))}) ORDER BY id"
        )
        best = None
        for pid, iid, paper_md, meta in cur.execute(q).fetchall():
            m = json.loads(meta) if meta else {}
            if "autonomous_experiment_design" in m:
                if best is None or (
                    paper_md and paper_md.strip()
                ):
                    best = {
                        "run_id": run_id,
                        "proposal_id": pid,
                        "idea_id": iid,
                        "paper_md": paper_md,
                        "meta": m,
                    }
        return best or {"run_id": run_id}
    finally:
        conn.close()


def evaluate_acceptance(result: dict) -> dict:
    conn = sqlite3.connect(DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_md, paper_meta_json FROM proposals WHERE id=?",
            (result["proposal_id"],),
        )
        paper_md, meta = cur.fetchone()
        m = json.loads(meta)
        E = (m.get("paper_evaluation") or {}).get("paper_hash", "")
        cur.execute(
            "SELECT paper_hash, eval_status FROM paper_revisions WHERE id=?",
            (result["frozen_revision_id"],),
        )
        F, frozen_eval = cur.fetchone()
        R = hashlib.sha256(result["release_bytes"]).hexdigest()
        H = result["release_header_hash"]
        return {
            "E": E, "F": F, "R": R, "H": H,
            "equality": E == F == R == H,
            "frozen_eval_status": frozen_eval,
            "release_equals_current_bytes": (
                result["release_bytes"].decode("utf-8").strip()
                == paper_md.strip()
            ),
        }
    finally:
        conn.close()


async def run_orchestrator() -> dict:
    from backend.pipeline.orchestrator._orchestrator import (
        PipelineOrchestrator,
    )
    from backend.pipeline.result import PipelineOutcome

    orchestrator = PipelineOrchestrator(strategy="deep_research")
    start = time.time()
    result = await orchestrator.run(
        domain="Robust regression under distribution shift",
        research_question=(
            "Are robust-regression method rankings stable as"
            " covariate perturbation severity increases, or do rank"
            " reversals occur in MAE, RMSE, and R² across tabular"
            " regression datasets?"
        ),
        max_gaps=3,
        generation_rounds=1,
        ideas_per_round=1,
        autonomous_experiment_enabled=True,
    )
    return {
        "run_id": result.run_id,
        "outcome": (
            result.outcome.value
            if hasattr(result.outcome, "value")
            else str(result.outcome)
        ),
        "outcome_is_success": result.outcome == PipelineOutcome.SUCCEEDED,
        "elapsed_s": round(time.time() - start, 1),
        "auto_design_status": (
            (result.params_used.get("autonomous_experiment_design") or {})
            .get("status")
        ),
    }


def main() -> int:
    result: dict = {
        "case": "Case 3 — zero-intervention architectural qualification",
        "frozen_head": "00c1050f7b63e0e5a239ef5670632bcc55532ad0",
        "started_at": now(),
        "steps": [],
    }
    accepted = False
    server = None
    try:
        # Step 1-2: autonomous run + REQUIRED outcome
        log("STEP1-2 orchestrator launch (frozen input); REQUIRE SUCCEEDED")
        orch = asyncio.run(run_orchestrator())
        result["steps"].append({"step": "1-2", "orchestrator": orch})
        log(f"STEP1-2 done: {json.dumps(orch)[:220]}")
        if not orch["outcome_is_success"]:
            result["failure"] = (
                f"orchestrator outcome != SUCCEEDED ({orch['outcome']})"
            )
            return finish(result, accepted=False)

        # Step 3-4: design status + REQUIRED capability
        state = read_design_state()
        design = (state.get("meta") or {}).get(
            "autonomous_experiment_design", {}
        )
        cap = design.get("capability_id")
        n_specs = len(design.get("specs", []))
        log(
            f"STEP3-4 design={design.get('status')} capability={cap}"
            f" specs={n_specs}"
        )
        result["steps"].append({
            "step": "3-4",
            "design_status": design.get("status"),
            "capability_id": cap,
            "n_specs": n_specs,
            "spec_ids": [
                s.get("experiment_spec_id") for s in design.get("specs", [])
            ],
        })
        if design.get("status") != "designed":
            result["failure"] = (
                f"autonomous design status != designed"
                f" ({design.get('status')})"
            )
            return finish(result, accepted=False)
        if cap != EXPECTED_CAPABILITY:
            result["failure"] = (
                f"selected capability {cap!r} != {EXPECTED_CAPABILITY!r}"
            )
            return finish(result, accepted=False)
        result["proposal_id"] = state["proposal_id"]
        result["idea_id"] = state["idea_id"]
        result["pipeline_run_id"] = state["run_id"]

        # Step 5: REQUIRED all experiments succeeded
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM experiment_results WHERE"
            " proposal_id=? AND success=1",
            (state["proposal_id"],),
        )
        n_success = cur.fetchone()[0]
        eval_state = (
            (state["meta"].get("paper_evaluation")) or {}
        ).get("status")
        markers = len(state["meta"].get("result_markers", []))
        conn.close()
        log(
            f"STEP5 experiments success={n_success}/{n_specs}"
            f" eval={eval_state} markers={markers}"
        )
        result["steps"].append({
            "step": "5",
            "experiments_success": n_success,
            "experiments_expected": n_specs,
            "initial_eval_status": eval_state,
            "markers": markers,
        })
        if n_success != n_specs:
            result["failure"] = (
                f"experiments succeeded {n_success} != designed {n_specs}"
            )
            return finish(result, accepted=False)

        # Step 6: production server + bounded remediation policy
        log("STEP6 starting production API process")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.api.app:app",
             "--host", "127.0.0.1", "--port", "8768"],
            stdout=open("evidence/case3_api.log", "w"),
            stderr=subprocess.STDOUT,
        )
        if not wait_health():
            result["failure"] = "API server failed to start"
            return finish(result, accepted=False)

        if eval_state is None:
            result["failure"] = (
                "no paper evaluation exists — paper synthesis produced"
                " nothing; nothing to repair, nothing to freeze"
            )
            return finish(result, accepted=False)

        remediation = {"invoked": False}
        if eval_state == "blocked":
            log("STEP6 policy: blocked -> cold repair ONCE")
            status, _, payload = http(
                "POST",
                f"/api/v1/ideas/{state['idea_id']}/paper/repair",
            )
            body = json.loads(payload)
            remediation = {
                "invoked": True,
                "http": status,
                "promoted": body.get("repair", {}).get("promoted"),
                "eval_status": body.get("evaluation", {}).get("status"),
            }
            log(f"STEP6 repair: {json.dumps(remediation)[:200]}")
        else:
            log("STEP6 policy: ready -> no remediation (Path A)")
        result["steps"].append({"step": "6", "remediation": remediation})

        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT paper_meta_json FROM proposals WHERE id=?",
            (state["proposal_id"],),
        )
        final_eval = (
            json.loads(cur.fetchone()[0]).get("paper_evaluation") or {}
        )
        conn.close()
        result["final_eval_status"] = final_eval.get("status")
        result["final_gates"] = [
            {
                g.get("gate") or g.get("name"): str(
                    g.get("passed", g.get("classification"))
                ),
            }
            for g in final_eval.get("gates", []) if isinstance(g, dict)
        ]
        log(f"STEP6 final evaluation: {result['final_eval_status']}")
        if result["final_eval_status"] != "ready":
            result["failure"] = (
                "paper not ready after bounded remediation policy;"
                " no retries permitted"
            )
            return finish(result, accepted=False)

        # Step 7: freeze + release + verification
        log("STEP7 freeze")
        status, _, payload = http(
            "POST",
            f"/api/v1/ideas/{state['idea_id']}/paper/freeze",
            timeout=120,
        )
        release = json.loads(payload).get("release", {})
        result["freeze"] = {
            "http": status, "state": release.get("state"),
            "frozen_revision_id": release.get("frozen_revision_id"),
            "release_eligible": release.get("release_eligible"),
        }
        if release.get("state") != "frozen":
            result["failure"] = "freeze did not produce frozen state"
            return finish(result, accepted=False)

        log("STEP7 release + E==F==R==H")
        status, headers, payload = http(
            "GET",
            f"/api/v1/export/paper/release/markdown/{state['idea_id']}",
            timeout=120,
        )
        result["release_header_hash"] = headers.get(
            "x-erlab-paper-hash", ""
        )
        result["frozen_revision_id"] = release.get("frozen_revision_id")
        result["release_bytes"] = payload
        verification = evaluate_acceptance(result)
        result["verification"] = verification
        log(
            f"STEP7 equality={verification['equality']}"
            f" bytes={verification['release_equals_current_bytes']}"
        )
        accepted = bool(
            verification["equality"]
            and verification["release_equals_current_bytes"]
            and verification["frozen_eval_status"] == "ready"
        )
        if not accepted:
            result["failure"] = "release identity verification failed"
        return finish(result, accepted=accepted)
    except Exception as exc:
        result["failure"] = f"harness exception: {exc!r}"
        return finish(result, accepted=False)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except Exception:
                server.kill()


def finish(result: dict, accepted: bool) -> int:
    result["finished_at"] = now()
    result["decision"] = "ACCEPTED" if accepted else "FAIL"
    result["operator_interventions"] = 0
    result["log"] = LOG_LINES
    if "release_bytes" in result:
        Path(RELEASE_PATH).write_bytes(result.pop("release_bytes"))
    Path(RESULT_PATH).write_text(json.dumps(result, indent=2))
    print(f"\n[CASE3] DECISION: {result['decision']}", flush=True)
    if not accepted:
        print(f"[CASE3] FAILURE: {result.get('failure')}", flush=True)
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
