"""
Run the full 16-stage deep_research pipeline against z.ai (glm-4.6).

This is the TRUE end-to-end test: real LLM calls, real paper search,
real gap analysis, real idea generation, real synthesis, real citation
audit, real quarantine — if any fabricated citations appear in the output,
they should be quarantined.
"""
import os
# These MUST be set before any backend imports — the shell env var
# EROCK_EMBEDDING_MODEL has a stale value that overrides .env
os.environ["EROCK_EMBEDDING_MODEL"] = "text-embedding-qwen3-embedding-0.6b"
os.environ["EROCK_EMBEDDING_BASE_URL"] = "http://100.64.0.2:1234"
os.environ.setdefault("EROCK_DATABASE_URL", "sqlite:///./data/elephant_rock.db")

import asyncio
import json
import sys

from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.db.database import get_session
from backend.db.models import QuarantinedCitation, Proposal, Idea
from sqlalchemy import select


async def main():
    print("=" * 60)
    print("FULL PIPELINE RUN — deep_research strategy")
    print("Provider: z.ai (glm-4.6)")
    print("=" * 60)
    print()

    # Use the default provider (now z.ai via openai-compatible API)
    orchestrator = PipelineOrchestrator(strategy="deep_research")

    strategy_config = orchestrator._load_yaml_strategy("deep_research")
    stages = [s for s in strategy_config.stages.keys() if strategy_config.stages[s].enabled]
    print(f"Strategy: deep_research ({len(stages)} stages)")
    print(f"Stages: {', '.join(stages)}")
    print(f"citation_audit enabled: {strategy_config.stages.get('citation_audit') and strategy_config.stages['citation_audit'].enabled}")
    print()

    domain = "transformer attention mechanisms for low-resource languages translation"
    print(f"Domain: {domain}")
    print(f"Rounds: 1, Ideas per round: 1")
    print()
    print("Running pipeline... (this may take several minutes)")
    print()

    try:
        result = await orchestrator.run(
            domain=domain,
            generation_rounds=1,
            ideas_per_round=1,
            max_gaps=3,
            export_format="markdown",
        )

        print()
        print("=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Ideas generated: {len(result.ideas)}")
        print(f"Gaps identified: {len(result.gaps)}")
        print(f"Proposals generated: {len(result.proposals)}")
        print()

        # Show stage report
        print("Stage Report:")
        for sr in result.stage_report:
            status_icon = "✓" if sr.status == "executed" else "⚠" if "skipped" in sr.status else "✗"
            elapsed = f" ({sr.elapsed_s}s)" if sr.elapsed_s else ""
            print(f"  {status_icon} {sr.name}: {sr.status}{elapsed}")

        print()

        # Show proposals with citation info
        if result.proposals:
            print("Proposals:")
            for idx, proposal in result.proposals.items():
                md = proposal.to_markdown() if hasattr(proposal, "to_markdown") else str(proposal)
                # Count SOURCE markers
                import re
                source_markers = re.findall(r'\[SOURCE-(\d+)\]', md)
                unique_sources = set(source_markers)
                max_source = max(int(s) for s in source_markers) if source_markers else 0
                print(f"  Proposal {idx}: {len(unique_sources)} unique citations, max=[SOURCE-{max_source}]")
                print(f"    Title: {proposal.sections.get('title', 'untitled')[:80]}")
                print(f"    Word count: {len(md.split())}")
                print(f"    Source indices: {sorted(int(s) for s in unique_sources)}")

                # Check metadata for citation audit
                metadata = {}
                if hasattr(proposal, 'metadata'):
                    if isinstance(proposal.metadata, str):
                        try:
                            metadata = json.loads(proposal.metadata)
                        except:
                            pass
                    elif isinstance(proposal.metadata, dict):
                        metadata = proposal.metadata

                audit = metadata.get("citation_audit", {})
                if audit:
                    print(f"    Citation audit: trust_score={audit.get('trust_score')}, "
                          f"fabricated={audit.get('fabricated_citations', 0)}, "
                          f"status={audit.get('status')}")
                    quarantined = audit.get("quarantined", [])
                    if quarantined:
                        print(f"    QUARANTINED: {quarantined}")
        else:
            print("No proposals generated.")

        print()

        # Check DB for quarantine rows
        print("DB Quarantine Check:")
        with get_session() as session:
            q_rows = session.execute(
                select(QuarantinedCitation).order_by(QuarantinedCitation.id.desc()).limit(20)
            ).scalars().all()

            print(f"  Total quarantine rows in DB: {len(q_rows)}")
            for q in q_rows[:10]:
                print(f"    proposal_id={q.proposal_id} section={q.section_key} ref_index={q.ref_index}")

        print()

        # Check DB for the latest ideas/proposals
        print("DB Ideas/Proposals Check:")
        with get_session() as session:
            ideas = session.execute(
                select(Idea).order_by(Idea.id.desc()).limit(5)
            ).scalars().all()
            print(f"  Recent ideas: {len(ideas)}")
            for i in ideas:
                print(f"    id={i.id} title={i.title[:60]}")

            proposals = session.execute(
                select(Proposal).order_by(Proposal.id.desc()).limit(5)
            ).scalars().all()
            print(f"  Recent proposals: {len(proposals)}")
            for p in proposals:
                sections = json.loads(p.sections_json) if p.sections_json else {}
                import re
                sources = re.findall(r'\[SOURCE-(\d+)\]', json.dumps(sections))
                print(f"    id={p.id} idea_id={p.idea_id} sources={sorted(set(int(s) for s in sources)) if sources else 'none'}")

    except Exception as e:
        print(f"Pipeline error: {type(e).__name__}: {str(e)[:300]}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
