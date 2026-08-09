"""Focused 12-cell live matrix: role/direction behavioral obedience.

Scope (frozen before run):
  - metric_direction/correct (control, 6 cells)
  - metric_direction/reversed_attribution (attack, 6 cells)
  - Both paths: monolithic + section_wise
  - 3 reps per condition
  - 2 x 2 x 3 = 12 cells total

Hard requirements per cell (all four, frozen):
  1. marker present (verbatim [RESULT-N] tokens)
  2. numeric value preserved
  3. role preserved (checker-attribution heuristic)
  4. no explicit metric-direction reversal

Decision rule (frozen, no relaxation during run):
  12/12 PASS (automated)        -> candidate-complete
  then semantic audit of any    -> confirm genuine pass vs checker artifact
  disputed cell
  12/12 semantically correct    -> ground-truth enforcement COMPLETE

Outputs:
  evidence/role_matrix_<YYYYMMDD_HHMMSS>/
      <cell_id>_paper.md
      <cell_id>_prompt.txt
      <cell_id>_result.json
      role_matrix_summary.json
      role_matrix_summary.md
      artifact_hashes.json (last)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

os.environ.setdefault("EROCK_EMBEDDING_PROVIDER", "lmstudio")
os.environ.setdefault("EROCK_EMBEDDING_MODEL", "text-embedding-bge-m3-embeddings")

from dotenv import load_dotenv
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.providers.openai_provider import OpenAIProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("role_matrix")

# Load the harness module (same loader pattern as the test files)
import importlib.util
_hp = REPO_ROOT / "scripts" / "stress_ground_truth.py"
_spec = importlib.util.spec_from_file_location("stress_ground_truth", _hp)
stress = importlib.util.module_from_spec(_spec)
sys.modules["stress_ground_truth"] = stress
_spec.loader.exec_module(stress)


# Frozen scope: only the two metric_direction levels, both paths, 3 reps.
FIXTURES = [
    stress.fixture_metric_correct,
    stress.fixture_metric_reversed_attribution,
]
PATHS = ["monolithic", "section_wise"]
REPS = 3


@dataclass
class CellResult:
    cell_id: str
    dimension: str
    level: str
    path: str
    rep: int
    paper: str = ""
    prompt: str = ""
    hard_verdict: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    error: str | None = None


async def run_monolithic(provider, fixture: dict) -> tuple[str, str]:
    from backend.pipeline.synthesis.paper_synthesizer import (
        PaperSynthesizer, SynthesisSession,
    )
    synth = PaperSynthesizer(provider)
    session = SynthesisSession(
        proposal_text=fixture["proposal_text"],
        source_papers=stress.SOURCE_PAPERS,
        domain="machine learning",
        experiment_context=fixture.get("experiment_context"),
        result_markers=tuple(fixture["result_markers"]) if fixture.get("result_markers") else (),
    )
    prompt_sent = PaperSynthesizer._build_user_prompt(
        session.proposal_text,
        list(session.source_papers),
        session.domain,
        experiment_context=session.experiment_context,
        result_markers=list(session.result_markers),
    )
    result = await synth.synthesize_session(session)
    paper = result.paper_markdown if result else ""
    return paper, prompt_sent


async def run_section_wise(provider, fixture: dict) -> tuple[str, str]:
    from backend.pipeline.synthesis.section_wise_synthesizer import (
        SectionWiseSynthesizer,
    )
    synth = SectionWiseSynthesizer(provider, context_window=8192)
    gt_block = synth._render_ground_truth_block(
        experiment_context=fixture.get("experiment_context"),
        result_markers=fixture.get("result_markers"),
    )
    prompt_sent = (
        "[Section-wise path — ground-truth block prepended to every section prompt]\n"
        + gt_block
    )
    result = await synth.synthesize(
        proposal_text=fixture["proposal_text"],
        source_papers=list(stress.SOURCE_PAPERS),
        domain="machine learning",
        experiment_context=fixture.get("experiment_context"),
        result_markers=fixture.get("result_markers"),
    )
    paper = result.paper_markdown if result else ""
    return paper, prompt_sent


async def run_cell(cell_id, fixture, path, rep, provider, account) -> CellResult:
    res = CellResult(
        cell_id=cell_id,
        dimension=fixture["dimension"],
        level=fixture["level"],
        path=path,
        rep=rep,
    )
    projected = 500 / 1_000_000 * stress.ZAI_INPUT_PER_1M + 4000 / 1_000_000 * stress.ZAI_OUTPUT_PER_1M
    if not account.can_spend(projected):
        res.error = f"BudgetExhausted: projected ${projected:.4f} would breach ceiling"
        return res

    spent_before = account.spent_usd
    try:
        if path == "monolithic":
            paper, prompt = await asyncio.wait_for(
                run_monolithic(provider, fixture), timeout=900,
            )
        else:
            paper, prompt = await asyncio.wait_for(
                run_section_wise(provider, fixture), timeout=1800,
            )
        res.paper = paper
        res.prompt = prompt
        last_usage = getattr(provider, "last_usage", None) or {}
        res.usage = {
            "input_tokens": last_usage.get("input_tokens", 0),
            "output_tokens": last_usage.get("output_tokens", 0),
            "served_model": last_usage.get("served_model", "unknown"),
            "cost_usd": round(account.spent_usd - spent_before, 6),
            "note_for_section_wise": (
                "token counts reflect the LAST call only; cost_usd is cumulative "
                "across all calls in this cell"
            ),
        }
        if paper:
            res.hard_verdict = stress.check_hard_invariants(paper, fixture)
            res.diagnostics = stress.check_diagnostics(paper, fixture)
        else:
            res.hard_verdict = {"all_hard_pass": False, "checks": {}, "note": "empty paper"}
            res.diagnostics = {"alerts": []}
    except asyncio.TimeoutError:
        res.error = f"Timeout ({path})"
    except Exception as e:
        res.error = f"{type(e).__name__}: {str(e)[:300]}\n{traceback.format_exc()[:500]}"
    return res


def write_cell(run_dir: Path, res: CellResult) -> None:
    (run_dir / f"{res.cell_id}_paper.md").write_text(
        res.paper or "[NO PAPER — error or empty]", encoding="utf-8",
    )
    (run_dir / f"{res.cell_id}_prompt.txt").write_text(
        res.prompt or "[NO PROMPT CAPTURED]", encoding="utf-8",
    )
    payload = {
        "cell_id": res.cell_id,
        "dimension": res.dimension,
        "level": res.level,
        "path": res.path,
        "rep": res.rep,
        "hard_verdict": res.hard_verdict,
        "diagnostics": res.diagnostics,
        "usage": res.usage,
        "error": res.error,
    }
    (run_dir / f"{res.cell_id}_result.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8",
    )


def write_summary(run_dir: Path, results: list[CellResult], account) -> None:
    summary: dict[str, Any] = {
        "spend": {
            "total_usd": round(account.spent_usd, 4),
            "ceiling_usd": account.ceiling_usd,
            "calls": account.calls,
            "input_tokens": account.input_tokens,
            "output_tokens": account.output_tokens,
        },
        "decision_rule_frozen": (
            "12/12 PASS required (automated); then semantic audit of any "
            "disputed cell to distinguish model defect from checker artifact"
        ),
        "cells": [],
        "dimensions": {},
    }
    for res in results:
        c = {
            "cell_id": res.cell_id,
            "dimension": res.dimension,
            "level": res.level,
            "path": res.path,
            "rep": res.rep,
            "hard_pass": res.hard_verdict.get("all_hard_pass", False),
            "error": res.error,
            "checks": res.hard_verdict.get("checks", {}),
            "diagnostic_alert_count": len(res.diagnostics.get("alerts", [])),
        }
        summary["cells"].append(c)
        key = f"{res.dimension}/{res.level}/{res.path}"
        if key not in summary["dimensions"]:
            summary["dimensions"][key] = {"total": 0, "hard_pass": 0, "errors": 0}
        summary["dimensions"][key]["total"] += 1
        if res.error:
            summary["dimensions"][key]["errors"] += 1
        elif res.hard_verdict.get("all_hard_pass"):
            summary["dimensions"][key]["hard_pass"] += 1

    (run_dir / "role_matrix_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )

    md = [
        "# Role/Direction Live Matrix (12 cells)",
        "",
        f"**Spend:** ${account.spent_usd:.4f} of ${account.ceiling_usd:.2f} ceiling",
        f"**Calls:** {account.calls}  |  Input: {account.input_tokens}  |  Output: {account.output_tokens}",
        "",
        "**Decision rule (frozen before run):**",
        "- Correct attribution controls: monolithic 3/3 + section-wise 3/3 PASS required",
        "- Reversed attribution attack: monolithic 3/3 + section-wise 3/3 PASS required",
        "- Hard requirements per cell: marker present, value preserved, role preserved, no explicit direction reversal",
        "",
        "## Automated matrix verdict",
        "",
        "| Cell | Level | Path | Hard | Role | Direction | Error |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in summary["cells"]:
        checks = c.get("checks", {})
        role = checks.get("result_roles_preserved", "?")
        direction = checks.get("metric_direction_preserved", "?")
        md.append(
            f"| {c['cell_id']} | {c['level']} | {c['path']} | "
            f"{'PASS' if c['hard_pass'] else 'FAIL'} | "
            f"{'Y' if role is True else 'N' if role is False else '?'} | "
            f"{'Y' if direction is True else 'N' if direction is False else '?'} | "
            f"{c['error'] or ''} |"
        )
    md.append("")
    md.append("## By dimension/level/path (pass/total)")
    md.append("")
    md.append("| Dimension/Level/Path | Pass rate | Errors |")
    md.append("|---|---|---|")
    for key, agg in summary["dimensions"].items():
        md.append(f"| {key} | {agg['hard_pass']}/{agg['total']} | {agg['errors']} |")
    md += [
        "",
        "## Two-layer report",
        "",
        "If automated verdict and semantic reading of the paper disagree on any "
        "cell, audit that cell: distinguish model defect (paper wrong) from "
        "checker defect (paper right, heuristic wrong). The raw paper files are "
        "the ground truth for adjudicating disputes.",
    ]
    (run_dir / "role_matrix_summary.md").write_text("\n".join(md), encoding="utf-8")


def write_hashes(run_dir: Path) -> None:
    targets = [p for p in run_dir.iterdir()
               if p.is_file() and p.name != "artifact_hashes.json"]
    hashes = {}
    for p in sorted(targets, key=lambda x: x.name):
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (run_dir / "artifact_hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8",
    )


async def main_async() -> int:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / "evidence" / f"role_matrix_{timestamp}"
    if run_dir.exists():
        logger.error("Run dir exists: %s", run_dir)
        return 1
    run_dir.mkdir(parents=True)
    logger.info("Run directory: %s", run_dir)

    settings = get_settings()
    logger.info("Model: %s @ %s", settings.openai_model, settings.openai_base_url)

    fixtures = [f() for f in FIXTURES]
    total_cells = len(fixtures) * len(PATHS) * REPS
    logger.info(
        "Frozen matrix: %d fixtures x %d paths x %d reps = %d cells",
        len(fixtures), len(PATHS), REPS, total_cells,
    )

    manifest = {
        "run_id": timestamp,
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "ceiling_usd": 50.0,
        "pricing_assumption": {
            "input_per_1m": stress.ZAI_INPUT_PER_1M,
            "output_per_1m": stress.ZAI_OUTPUT_PER_1M,
            "source": "cost_estimator.py:20 (glm-5.1); glm-5.2 assumed parity",
        },
        "total_cells_planned": total_cells,
        "decision_rule_frozen": True,
        "scope": "metric_direction only (correct + reversed_attribution)",
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    account = stress.SpendAccount(ceiling_usd=50.0)
    provider = stress.AccountedOpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        account=account,
    )

    results: list[CellResult] = []
    n = 0
    budget_broken = False
    try:
        for fixture in fixtures:
            if budget_broken:
                break
            for path in PATHS:
                if budget_broken:
                    break
                for rep in range(1, REPS + 1):
                    n += 1
                    cell_id = f"{fixture['dimension']}_{fixture['level']}_{path}_rep{rep}"
                    logger.info("[%d/%d] %s (spent=$%.4f)", n, total_cells, cell_id, account.spent_usd)
                    res = await run_cell(cell_id, fixture, path, rep, provider, account)
                    results.append(res)
                    write_cell(run_dir, res)
                    if res.error:
                        logger.warning("  ERROR: %s", res.error[:140])
                        if "BudgetExhausted" in res.error:
                            budget_broken = True
                            break
                    elif res.hard_verdict.get("all_hard_pass"):
                        logger.info("  HARD PASS")
                    else:
                        logger.info("  HARD FAIL")
    except KeyboardInterrupt:
        logger.warning("Interrupted — writing partial summary.")

    write_summary(run_dir, results, account)
    write_hashes(run_dir)
    logger.info("Done. Spent $%.4f across %d calls.", account.spent_usd, account.calls)
    logger.info("Outputs in: %s", run_dir)

    # Print summary to stdout
    print("\n=== AUTOMATED MATRIX VERDICT ===")
    pass_n = sum(1 for r in results if r.hard_verdict.get("all_hard_pass"))
    fail_n = sum(1 for r in results if not r.error and not r.hard_verdict.get("all_hard_pass"))
    err_n = sum(1 for r in results if r.error)
    print(f"{pass_n} PASS, {fail_n} FAIL, {err_n} ERROR (of {len(results)} cells)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
