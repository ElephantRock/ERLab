"""Targeted rerun: previously failing section-wise cells only.

Reruns the 14 section-wise cells the corrected matrix marked FAIL, against
the patched SectionWiseSynthesizer (outline now receives ground truth).
Uses a primacy-based identity check: the paper's TITLE and the OPENING of
its ABSTRACT must name the ground-truth method, not just mention it anywhere.

The 3 ablation/markers_only cells are expected to fail again — markers alone
do not carry method identity, and the patch does not change that. The other
11 are the wiring-bug failures the patch targets.

Usage:
    python scripts/rerun_failing_section_wise.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path

os.environ.setdefault("EROCK_EMBEDDING_PROVIDER", "lmstudio")
os.environ.setdefault("EROCK_EMBEDDING_MODEL", "text-embedding-bge-m3-embeddings")

from dotenv import load_dotenv
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.providers.openai_provider import OpenAIProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("rerun_sw")

# Load the harness fixtures
import importlib.util
_hp = REPO_ROOT / "scripts" / "stress_ground_truth.py"
_spec = importlib.util.spec_from_file_location("stress_ground_truth", _hp)
stress = importlib.util.module_from_spec(_spec)
sys.modules["stress_ground_truth"] = stress
_spec.loader.exec_module(stress)


# The 14 previously failing section-wise cells, mapped to their fixture builders.
PREVIOUSLY_FAILING = [
    ("ablation", "context_only"),
    ("ablation", "full"),
    ("ablation", "markers_only"),
    ("method_substitution", "absurd"),
    ("method_substitution", "plausible"),
    ("method_substitution", "subtle"),
]

# 3 reps each = 18 cells. (plausible/subtle only had 1 fail each, but rerunning
# all 3 reps gives a clean per-cell rate. If plausible_rep1/rep2 and subtle_rep2/rep3
# already passed, they'll pass again and confirm consistency.)


def _title_and_abstract_opening(paper: str) -> str:
    """Primacy region: title + first ~500 chars of abstract (lowercased).

    A correct identity check looks at what the paper leads with, not whether
    the method is mentioned anywhere. The section-wise bug produced abstracts
    opening with 'Efficient modeling of hydrodynamic lubrication...' even when
    'logistic regression' appeared later as a secondary detail.
    """
    pl = paper.lower()
    # Find the abstract section; take title through first paragraph of abstract.
    abs_idx = pl.find("## abstract")
    if abs_idx == -1:
        # No abstract heading; just take the first 800 chars.
        return pl[:800]
    # Title (before abstract) + first ~500 chars after the abstract heading.
    title_region = pl[:abs_idx]
    abstract_region = pl[abs_idx:abs_idx + 600]
    return (title_region + abstract_region)


def check_primacy_identity(paper: str, fixture: dict) -> dict:
    """Primacy-based check: does the paper's title + abstract opening name
    the ground-truth method? Stricter than the substring-anywhere check."""
    if not paper or not paper.strip():
        return {"identity_pass": False, "reason": "empty paper"}
    exp = fixture["expected"]
    gt_method = exp["gt_method"].lower()
    region = _title_and_abstract_opening(paper)
    # The method must appear in the primacy region.
    identity_pass = gt_method in region
    # Also flag if the conflicting method dominates the opening.
    conflicting_in_open = []
    for term in exp.get("conflicting_terms", []):
        if term.lower() in region:
            conflicting_in_open.append(term)
    return {
        "identity_pass": identity_pass,
        "gt_method_in_primacy": identity_pass,
        "conflicting_terms_in_primacy": conflicting_in_open,
        "primacy_region_preview": paper[:300],
    }


async def run_one_cell(
    cell_id: str,
    fixture: dict,
    provider: OpenAIProvider,
) -> dict:
    """Run one section-wise cell with the patched synthesizer."""
    from backend.pipeline.synthesis.section_wise_synthesizer import SectionWiseSynthesizer
    synth = SectionWiseSynthesizer(provider, context_window=8192)
    try:
        result = await asyncio.wait_for(
            synth.synthesize(
                proposal_text=fixture["proposal_text"],
                source_papers=list(stress.SOURCE_PAPERS),
                domain="machine learning",
                experiment_context=fixture.get("experiment_context"),
                result_markers=fixture.get("result_markers"),
            ),
            timeout=1800,
        )
        paper = result.paper_markdown if result else ""
    except asyncio.TimeoutError:
        return {"cell_id": cell_id, "error": "Timeout", "paper": ""}
    except Exception as e:
        return {"cell_id": cell_id, "error": f"{type(e).__name__}: {str(e)[:300]}", "paper": ""}

    identity = check_primacy_identity(paper, fixture)
    # Markers-present check (using corrected extraction).
    markers = fixture.get("result_markers") or []
    marker_keys = []
    for m in markers:
        cb = m.find("]")
        marker_keys.append(m[:cb+1] if cb != -1 else m)
    missing = [k for k in marker_keys if k.lower() not in paper.lower()]
    return {
        "cell_id": cell_id,
        "paper": paper,
        "identity": identity,
        "markers_present": len(missing) == 0,
        "missing_markers": missing,
        "error": None,
    }


async def main_async() -> int:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / "evidence" / f"rerun_sw_{timestamp}"
    run_dir.mkdir(parents=True)
    logger.info("Run directory: %s", run_dir)

    settings = get_settings()
    provider = stress.AccountedOpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        account=stress.SpendAccount(ceiling_usd=50.0),
    )

    # Build fixture map
    FIX_MAP = {}
    for builder in stress.ALL_FIXTURES:
        f = builder()
        FIX_MAP[(f["dimension"], f["level"])] = builder

    results = []
    cell_n = 0
    total_cells = len(PREVIOUSLY_FAILING) * 3
    for dim, level in PREVIOUSLY_FAILING:
        fixture = FIX_MAP[(dim, level)]()
        for rep in (1, 2, 3):
            cell_n += 1
            cell_id = f"{dim}_{level}_section_wise_rep{rep}"
            logger.info("[%d/%d] %s", cell_n, total_cells, cell_id)
            res = await run_one_cell(cell_id, fixture, provider)
            results.append(res)
            # Save per-cell
            (run_dir / f"{cell_id}_paper.md").write_text(
                res.get("paper") or "[NO PAPER]", encoding="utf-8"
            )
            payload = {k: v for k, v in res.items() if k != "paper"}
            (run_dir / f"{cell_id}_result.json").write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
            ident = res.get("identity", {})
            if res.get("error"):
                logger.warning("  ERROR: %s", res["error"][:120])
            elif ident.get("identity_pass") and res.get("markers_present"):
                logger.info("  PASS (primacy + markers)")
            else:
                fails = []
                if not ident.get("identity_pass"): fails.append("identity")
                if not res.get("markers_present"): fails.append("markers")
                logger.info("  FAIL: %s; conflicting_in_primacy=%s",
                            fails, ident.get("conflicting_terms_in_primacy", []))

    # Summary
    summary = {
        "run_id": timestamp,
        "patched_synthesizer": "outline now receives experiment_context/result_markers",
        "identity_check": "primacy (title + abstract opening), not substring-anywhere",
        "cells": [],
    }
    for r in results:
        ident = r.get("identity", {})
        passed = (not r.get("error")
                  and ident.get("identity_pass")
                  and r.get("markers_present"))
        summary["cells"].append({
            "cell_id": r["cell_id"],
            "passed": passed,
            "error": r.get("error"),
            "identity_pass": ident.get("identity_pass"),
            "conflicting_terms_in_primacy": ident.get("conflicting_terms_in_primacy"),
            "markers_present": r.get("markers_present"),
        })

    # Aggregate by dimension/level
    agg = {}
    for c in summary["cells"]:
        key = "_".join(c["cell_id"].split("_")[:2])  # e.g. "ablation_full"
        if key not in agg:
            agg[key] = {"pass": 0, "fail": 0, "err": 0}
        if c["error"]:
            agg[key]["err"] += 1
        elif c["passed"]:
            agg[key]["pass"] += 1
        else:
            agg[key]["fail"] += 1
    summary["by_dimension"] = agg

    (run_dir / "rerun_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Markdown
    md = ["# Section-wise rerun (patched synthesizer)", "",
          "Identity check is primacy-based: title + abstract opening must name",
          "the ground-truth method. Stricter than the original run's substring-anywhere check.", "",
          "| Cell | Passed | Identity | Markers | Conflicting in primacy | Error |",
          "|---|---|---|---|---|---|"]
    for c in summary["cells"]:
        md.append(f"| {c['cell_id']} | {'PASS' if c['passed'] else 'FAIL'} | "
                  f"{'Y' if c['identity_pass'] else 'N'} | {'Y' if c['markers_present'] else 'N'} | "
                  f"{c.get('conflicting_terms_in_primacy','')} | {c['error'] or ''} |")
    md += ["", "## By dimension (pass/total)", ""]
    for k in sorted(agg):
        v = agg[k]
        total = v["pass"] + v["fail"] + v["err"]
        md.append(f"- {k}: {v['pass']}/{total} pass" + (f", {v['err']} errors" if v['err'] else ""))
    (run_dir / "rerun_summary.md").write_text("\n".join(md), encoding="utf-8")

    logger.info("Done. Outputs in %s", run_dir)
    # Print summary to stdout
    print("\n=== SUMMARY ===")
    for k in sorted(agg):
        v = agg[k]
        total = v["pass"] + v["fail"] + v["err"]
        print(f"  {k}: {v['pass']}/{total} pass" + (f" ({v['err']} errors)" if v['err'] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
