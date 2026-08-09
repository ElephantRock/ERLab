"""``erock open|proposal|export|recover`` — research CLI commands (BATCH-34).

Provides commands for interacting with individual research ideas:
  - ``erock open {id}``     — open idea in browser
  - ``erock proposal {id}`` — generate a proposal for an idea
  - ``erock export {id}``   — export idea to a file
  - ``erock recover {proposal_id} {experiment_id}`` — recover paper from persisted experiment (Phase 6)
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from backend.cli.main import _run_async

console = Console()

research_app = typer.Typer(
    name="research",
    help="Research idea commands: open, proposal, export.",
    no_args_is_help=True,
)


# ── erock open {id} ────────────────────────────────────────────────


@research_app.command("open")
def open_idea(
    idea_id: int = typer.Argument(..., help="Idea database ID"),
    url: str | None = typer.Option(
        None, "--url", "-u", help="Base URL (default: http://localhost:5173)"
    ),
):
    """Open a research idea in the browser."""
    from backend.db.crud import get_idea
    from backend.db.database import get_session

    with get_session() as session:
        idea = get_idea(session, idea_id)

    if not idea:
        console.print(f"[red]Idea {idea_id} not found.[/red]")
        raise typer.Exit(1)

    base = url or "http://localhost:5173"
    idea_url = f"{base}/ideas/{idea_id}"
    console.print(f"[bold]Opening idea {idea_id}:[/bold] {idea.title}")
    console.print(f"[dim]{idea_url}[/dim]")
    webbrowser.open(idea_url)


# ── erock proposal {id} ───────────────────────────────────────────


@research_app.command("proposal")
def generate_proposal(
    idea_id: int = typer.Argument(..., help="Idea database ID"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown or latex"),
):
    """Generate a proposal for a research idea using the LLM."""
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.database import get_session
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
    from backend.providers.provider_factory import create_provider

    with get_session() as session:
        idea = db_get_idea(session, idea_id)

    if not idea:
        console.print(f"[red]Idea {idea_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Generating proposal for:[/bold] {idea.title}")

    research_idea = ResearchIdea(
        title=idea.title,
        problem_statement=idea.problem_statement,
        proposed_method=idea.proposed_method,
        expected_contributions=idea.expected_contributions,
        novelty_rationale="",
        evaluation_approach="",
    )

    async def _generate():
        provider = create_provider()
        synthesizer = ProposalSynthesizer(provider)
        return await synthesizer.synthesize(research_idea)

    proposal = _run_async(_generate())

    console.print(Panel(
        Markdown(proposal.content_md) if format == "markdown" else proposal.content_latex or proposal.content_md,
        title=f"Proposal: {proposal.title}",
        width=100,
    ))
    console.print(f"\n[green]Proposal generated successfully.[/green]")


# ── erock export {id} ─────────────────────────────────────────────


@research_app.command("export")
def export_idea(
    idea_id: int = typer.Argument(..., help="Idea database ID"),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Output file path (default: idea_{id}.md)"
    ),
    format: str = typer.Option("markdown", "--format", "-f", help="Export format: markdown or json"),
):
    """Export a research idea to a file."""
    import json as _json

    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            console.print(f"[red]Idea {idea_id} not found.[/red]")
            raise typer.Exit(1)
        proposal = get_proposal_by_idea(session, idea.id)

    output_path = Path(output or f"idea_{idea_id}.{'md' if format == 'markdown' else 'json'}")

    if format == "json":
        data = {
            "id": idea.id,
            "title": idea.title,
            "problem_statement": idea.problem_statement,
            "proposed_method": idea.proposed_method,
            "expected_contributions": idea.expected_contributions,
            "domain": idea.domain,
            "novelty_score": idea.novelty_score,
            "feasibility_score": idea.feasibility_score,
            "overall_score": idea.overall_score,
            "proposal_md": proposal.content_md if proposal else None,
        }
        output_path.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        lines = [
            f"# {idea.title}\n",
            f"**Domain:** {idea.domain}\n",
            f"## Problem Statement\n\n{idea.problem_statement}\n",
            f"## Proposed Method\n\n{idea.proposed_method}\n",
            f"## Expected Contributions\n\n{idea.expected_contributions}\n",
        ]
        if idea.novelty_score is not None:
            lines.append(f"\n**Novelty Score:** {idea.novelty_score:.2f}\n")
        if idea.feasibility_score is not None:
            lines.append(f"**Feasibility Score:** {idea.feasibility_score:.1f}\n")
        if idea.overall_score is not None:
            lines.append(f"**Overall Score:** {idea.overall_score:.2f}\n")
        if proposal and proposal.content_md:
            lines.append(f"\n## Proposal\n\n{proposal.content_md}\n")
        output_path.write_text("\n".join(lines), encoding="utf-8")

    console.print(f"[green]Exported idea {idea_id} to {output_path}[/green]")


@research_app.command("recover")
def recover_paper(
    proposal_id: int = typer.Argument(..., help="Proposal ID to write a paper for"),
    experiment_id: int = typer.Argument(..., help="ExperimentResult ID with succeeded status"),
    timeout: float = typer.Option(1800.0, "--timeout", help="Synthesis timeout in seconds"),
):
    """Phase 6: Recover a paper from a persisted successful experiment.

    Loads the proposal, literature source map, and experiment results from the
    database, then synthesizes a paper with [RESULT-N] markers. Does NOT rerun
    any pipeline stages or the experiment.
    """
    from backend.pipeline.experiment.paper_recovery import resume_empirical_paper

    console.print(f"[cyan]Recovering paper: proposal={proposal_id} experiment={experiment_id}[/cyan]")

    try:
        result = _run_async(resume_empirical_paper(proposal_id, experiment_id, timeout))
    except Exception as e:
        console.print(f"[red]Recovery failed: {e}[/red]")
        raise typer.Exit(1)

    if not result.get("success"):
        console.print(f"[red]Paper synthesis failed: {result.get('error', 'unknown')}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Paper synthesized: {result['word_count']} words ({result['synthesis_strategy']})[/green]")
    console.print(f"  Sections: {result['sections_generated']}/{result['sections_total']}")
    console.print(f"  Evaluation: {result['eval_status']}")

    if result['blocking_reasons']:
        for r in result['blocking_reasons']:
            console.print(f"  [yellow]Blocked: {r}[/yellow]")

    for gate in result['gates']:
        cls = gate.get('classification', gate.get('passed'))
        console.print(f"  Gate {gate['gate']}: {cls}")

    # Persist to database
    import json as _json
    from backend.db.database import get_session
    from backend.db.models import Proposal as ProposalModel

    with get_session() as session:
        prop = session.get(ProposalModel, proposal_id)
        if prop:
            from backend.pipeline.evaluation.paper_release import (
                compute_paper_hash,
                merge_release_metadata,
            )
            prop.paper_md = result['paper_markdown']
            paper_meta = {
                "status": "ready",
                "word_count": result['word_count'],
                "synthesis_strategy": result['synthesis_strategy'],
                "paper_evaluation": {
                    "status": result['eval_status'],
                    "scope": "paper",
                    "paper_hash": compute_paper_hash(result['paper_markdown']),
                    "gates": result['gates'],
                    **({"blocking_reasons": result['blocking_reasons']} if result['blocking_reasons'] else {}),
                },
                "source_map": result['source_map'],
                "experiment_result_id": result['experiment_result_id'],
            }
            paper_meta = merge_release_metadata(prop, paper_meta) or paper_meta
            prop.paper_meta_json = _json.dumps(paper_meta)
            session.commit()
            console.print(f"[green]Paper persisted to proposal {proposal_id}[/green]")
