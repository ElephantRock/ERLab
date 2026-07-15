"""MANUAL smoke check: end-to-end quarantine through a live pipeline.

WARNING: This script MUTATES A LIVE DATABASE. It runs the real pipeline
orchestrator against the configured database, inserting pipeline runs, ideas,
proposals, and quarantine rows. Do NOT run it against a production database
unless you intend to.

It is NOT a pytest test. It is a print-oriented manual verification tool for
confirming the full quarantine path works against a live environment:
    1. Pipeline runs through citation_audit
    2. CitationAuditStage detects [SOURCE-99] as fabricated (out of range)
    3. Quarantine row is persisted to the DB
    4. render_quarantined_view redacts [SOURCE-99] from the served proposal

USAGE
-----
    python scripts/manual/e2e_quarantine_smoke.py --allow-db-mutation

ENVIRONMENT
-----------
    EROCK_DATABASE_URL   Target database URL. REQUIRED — there is no silent
                         default. Point this at a throwaway/test DB.

EXIT CODES
----------
    0  All checks passed
    1  Checks failed (fabrication not quarantined or not redacted)
    2  Missing configuration / misuse
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


def _require_config() -> str:
    """Return the database URL from the environment, or abort with exit 2.

    No silent default — the operator must explicitly name the target DB so a
    live/production database is never mutated by accident.
    """
    db_url = os.environ.get("EROCK_DATABASE_URL")
    if not db_url:
        print(
            "ERROR: EROCK_DATABASE_URL is not set. This script mutates the "
            "target database, so the URL must be named explicitly.",
            file=sys.stderr,
        )
        sys.exit(2)
    return db_url


async def _run_checks() -> int:
    """Run the pipeline with a fabrication-injecting provider, then verify.

    Returns 0 on success, 1 on check failure.
    """
    # Imports after config/arg parsing so --help and missing-config exits
    # don't pay the import cost or fail on a broken environment.
    from backend.providers.base import LLMProvider
    from backend.pipeline.orchestrator import PipelineOrchestrator
    from backend.db.database import get_session
    from backend.db.models import QuarantinedCitation, Proposal
    from backend.pipeline.quarantine import render_quarantined_view
    from sqlalchemy import select

    class FabricationTestProvider(LLMProvider):
        """Fake provider that emits proposals with a fabricated [SOURCE-99]."""

        def __init__(self):
            super().__init__()
            self._call_count = 0

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            self._call_count += 1
            prompt_text = json.dumps(messages)
            if "citation" in prompt_text.lower() or "verify" in prompt_text.lower():
                return json.dumps({
                    "context_verified": False,
                    "context_justification": "Source index out of range",
                    "quantitative_claims": [],
                    "quantitative_verified": False,
                    "trust_contribution": 0.0,
                })
            return "This is a test response."

        async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
            yield "Test"

        async def structured_output(self, messages, schema, temperature=0.3, **kwargs):
            prompt_text = json.dumps(messages)

            if "gap" in prompt_text.lower():
                return {"gaps": [{"title": "Test Gap", "description": "A test gap.", "gap_type": "methodological", "confidence": 0.8}]}
            if "idea" in prompt_text.lower() or "novel" in prompt_text.lower():
                return {"ideas": [{"title": "Quarantine E2E Test", "problem_statement": "The problem of X.", "proposed_method": "Method Y.", "expected_contributions": "Contributions.", "evaluation_approach": "Benchmark Z.", "novelty_arguments": "Novel."}]}
            if "novelty" in prompt_text.lower():
                return {"novelty_score": 0.75, "method_novelty": 0.8, "problem_novelty": 0.7, "domain_transfer": 0.6, "combination_novelty": 0.65, "closest_matches": [], "reasoning": "Moderate."}
            if "feasib" in prompt_text.lower():
                return {"feasibility_score": 7.0, "data_availability": 0.7, "compute_feasibility": 0.8, "method_complexity": 0.5, "timeline_risk": 0.4, "reasoning": "Feasible."}

            # Proposal synthesis — THE FABRICATION: [SOURCE-99] doesn't exist.
            if "propos" in prompt_text.lower() or "synth" in prompt_text.lower() or "section" in prompt_text.lower():
                return {
                    "title": "E2E Quarantine Test",
                    "abstract": "We address problem X [SOURCE-1]. Prior work [SOURCE-99] is foundational.",
                    "introduction": "Progress has been made [SOURCE-1]. However, [SOURCE-99] showed limitations. We propose a new method.",
                    "proposed_method": "Our method uses attention [SOURCE-2] and a novel arch inspired by [SOURCE-99].",
                    "related_work": "Several approaches exist [SOURCE-1] [SOURCE-2]. The work [SOURCE-99] is seminal.",
                    "expected_contributions": "A novel architecture.",
                    "evaluation_plan": "Standard benchmarks.",
                    "timeline": "12 weeks.",
                    "risk_mitigation": "Careful design.",
                    "references": [{"authors": "Author A", "year": 2024, "title": "Paper 1", "venue": "ACL"}],
                }
            return {}

        async def embed(self, texts):
            return [[0.1] * 10 for _ in texts]

        async def health_check(self):
            return True

        @property
        def provider_name(self):
            return "fabrication-test"

        @property
        def default_model(self):
            return "fabrication-test-model"

    print("=== E2E Quarantine Pipeline Smoke Check ===")
    print(f"Target DB: {os.environ['EROCK_DATABASE_URL']}")
    print()

    provider = FabricationTestProvider()
    orchestrator = PipelineOrchestrator(provider=provider, strategy="deep_research")

    strategy_config = orchestrator._load_yaml_strategy("deep_research")
    stages = [s for s in strategy_config.stages.keys() if strategy_config.stages[s].enabled]
    print(f"Strategy: deep_research ({len(stages)} stages)")
    audit_enabled = strategy_config.stages.get("citation_audit") and strategy_config.stages["citation_audit"].enabled
    print(f"citation_audit enabled: {audit_enabled}")
    print()
    print("Running pipeline...")
    print()

    try:
        await orchestrator.run(
            domain="AI/NLP Quarantine E2E",
            generation_rounds=1,
            ideas_per_round=1,
            max_gaps=2,
            export_format=None,
        )
    except Exception as e:
        print(f"Pipeline error: {type(e).__name__}: {str(e)[:200]}")

    print()
    print("=== Checking DB ===")

    failures: list[str] = []

    with get_session() as session:
        q_rows = session.execute(
            select(QuarantinedCitation).order_by(QuarantinedCitation.id.desc()).limit(10)
        ).scalars().all()
        print(f"Quarantine rows: {len(q_rows)}")
        for q in q_rows:
            print(f"  proposal={q.proposal_id} section={q.section_key} ref_index={q.ref_index}")

        proposals = session.execute(
            select(Proposal).order_by(Proposal.id.desc()).limit(3)
        ).scalars().all()
        print(f"\nRecent proposals: {len(proposals)}")

        any_redacted = False
        for p in proposals:
            sections = json.loads(p.sections_json) if p.sections_json else {}
            has_99 = any("[SOURCE-99]" in str(v) for v in sections.values())
            print(f"  proposal_id={p.id} has [SOURCE-99] in raw: {has_99}")

            q_for_p = [q for q in q_rows if q.proposal_id == p.id]
            if q_for_p:
                rendered = render_quarantined_view(sections, q_for_p)
                r_99 = any("[SOURCE-99]" in str(v) for v in rendered.values())
                r_marker = any("[removed: fabricated reference]" in str(v) for v in rendered.values())
                print(f"    After render: [SOURCE-99]={r_99}, marker={r_marker}")
                if r_99:
                    failures.append(f"proposal {p.id}: [SOURCE-99] survived render")
                if r_marker:
                    any_redacted = True
            else:
                print(f"    No quarantine for this proposal")

    # Outcome checks (print-oriented tool, but still reports a verdict).
    if not q_rows:
        failures.append("no quarantine rows were persisted")
    if not any_redacted:
        failures.append("no proposal had [SOURCE-99] redacted in its rendered view")

    print()
    if failures:
        print("=== CHECKS FAILED ===")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("=== CHECKS PASSED ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MANUAL quarantine smoke check (mutates a live DB).",
    )
    parser.add_argument(
        "--allow-db-mutation",
        action="store_true",
        help="Required confirmation flag. Without it the script refuses to run, "
             "because it inserts rows into the target database.",
    )
    args = parser.parse_args()

    if not args.allow_db_mutation:
        print(
            "Refusing to run without --allow-db-mutation. This script mutates "
            "the target database. Set EROCK_DATABASE_URL to a throwaway DB and "
            "re-run with the flag.",
            file=sys.stderr,
        )
        return 2

    _require_config()
    return asyncio.run(_run_checks())


if __name__ == "__main__":
    sys.exit(main())
