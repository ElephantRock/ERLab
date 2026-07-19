"""Elephant Rock Research CLI — command-line interface for the research pipeline."""

import asyncio
import traceback

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="erock",
    help="Elephant Rock Research — AI/NLP Research Idea Generation Platform",
    no_args_is_help=True,
)

console = Console()
_debug = False


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Show full tracebacks on errors"),
):
    """Elephant Rock Research CLI."""
    global _debug
    _debug = debug
    from backend.logging_config import configure_logging

    configure_logging(debug)
    from backend.db.database import init_db

    init_db()


def _run_async(coro):
    """Run an async function from sync CLI context with error handling."""
    try:
        return asyncio.run(coro)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130) from None
    except ImportError as e:
        console.print(
            Panel(
                f"[red]Missing dependency:[/red] {e}\n\n"
                f'Install required packages:\n  pip install -e ".[dev]"',
                title="[red]Import Error[/red]",
            )
        )
        if _debug:
            console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except ConnectionError as e:
        console.print(
            Panel(
                f"[red]Network error:[/red] {e}\n\n"
                f"Check your internet connection and API endpoint URLs.",
                title="[red]Connection Error[/red]",
            )
        )
        if _debug:
            console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(
            Panel(
                f"[red]{type(e).__name__}:[/red] {e}\n\n" f"Run with --debug for full traceback.",
                title="[red]Error[/red]",
            )
        )
        if _debug:
            console.print(traceback.format_exc())
        else:
            console.print("[dim]Use --debug flag for detailed error information.[/dim]")
        raise typer.Exit(1) from e


# --- Literature Commands ---


@app.command("search")
def search_literature(
    query: str = typer.Argument(..., help="Search query"),
    sources: str = typer.Option(
        "semantic_scholar,arxiv", "--sources", "-s", help="Comma-separated sources"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Results per source"),
    year_from: int | None = typer.Option(None, "--from", help="Year from"),
    year_to: int | None = typer.Option(None, "--to", help="Year to"),
):
    """Search academic literature across multiple sources."""
    from backend.pipeline.literature.search_service import SearchService

    async def _search():
        service = SearchService()
        source_list = [s.strip() for s in sources.split(",")]
        papers = await service.search_all(
            query,
            sources=source_list,
            limit_per_source=limit,
            year_from=year_from,
            year_to=year_to,
        )
        return papers

    papers = _run_async(_search())

    table = Table(title=f"Search Results: {query}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold", max_width=60)
    table.add_column("Year", width=6)
    table.add_column("Citations", width=10)
    table.add_column("Source", width=12)

    for i, paper in enumerate(papers, 1):
        table.add_row(
            str(i),
            paper.title[:60],
            str(paper.year or "?"),
            str(paper.citation_count or "?"),
            paper.source,
        )

    console.print(table)
    console.print(f"\nFound {len(papers)} papers")


@app.command("ingest")
def ingest_pdf(
    file_path: str = typer.Argument(..., help="Path to PDF file"),
    paper_id: str | None = typer.Option(
        None, "--id", help="Paper ID (auto-generated if not provided)"
    ),
):
    """Ingest a PDF into the knowledge base."""
    from pathlib import Path

    from backend.config import get_settings
    from backend.pipeline.ingestion.pdf_service import PDFService
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.pipeline.literature.models import Paper
    from backend.providers.provider_factory import create_provider

    settings = get_settings()
    pid = paper_id or Path(file_path).stem

    async def _ingest():
        provider = create_provider()
        pdf = PDFService(mode=settings.s1_parser_mode)
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)

        # Parse PDF
        chunks = await pdf.parse_and_chunk(
            file_path, pid, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
        )

        # Create a paper object for the store
        paper = Paper(id=pid, source="local", title=pid.replace("-", " ").title())

        # Add to knowledge base
        count = await store.add_papers([paper], [chunks])
        return count, len(chunks)

    count, total = _run_async(_ingest())
    console.print(f"[green]Ingested {file_path}[/green]")
    console.print(f"  {count} chunks added to knowledge base (out of {total} total)")


# --- Generation Commands ---


@app.command("generate")
def generate_ideas(
    domain: str = typer.Option("AI/NLP", "--domain", "-d", help="Research domain"),
    queries: str | None = typer.Option(
        None, "--queries", "-q", help="Comma-separated search queries"
    ),
    gaps: int = typer.Option(5, "--gaps", "-g", help="Max gaps to identify"),
    rounds: int = typer.Option(2, "--rounds", "-r", help="Generation rounds"),
    ideas: int = typer.Option(3, "--ideas", "-i", help="Ideas per round"),
    novelty: bool = typer.Option(True, "--novelty/--no-novelty", help="Run novelty checking"),
    feasibility: bool = typer.Option(
        True, "--feasibility/--no-feasibility", help="Run feasibility scoring"
    ),
    export: str | None = typer.Option(
        "markdown", "--export", "-e", help="Export format (markdown/latex)"
    ),
    resume: str | None = typer.Option(
        None, "--resume", help="Resume a prior run by its run ID (e.g. 42)"
    ),
):
    """Run the full research idea generation pipeline."""
    from backend.pipeline.orchestrator import PipelineOrchestrator

    query_list = [q.strip() for q in queries.split(",")] if queries else None

    console.print(
        Panel(
            f"[bold]Elephant Rock Research Pipeline[/bold]\n"
            f"Domain: {domain}\n"
            f"Gaps: {gaps} | Rounds: {rounds} | Ideas/round: {ideas}\n"
            f"Novelty: {novelty} | Feasibility: {feasibility} | Export: {export}"
            + (f"\n[bold yellow]Resuming run: {resume}[/bold yellow]" if resume else ""),
            title="Starting Pipeline",
        )
    )

    from rich.status import Status

    _STAGE_DISPLAY = {
        "literature_search": "Literature Discovery",
        "ingestion": "Knowledge Base Ingestion",
        "gap_analysis": "Gap Analysis",
        "idea_generation": "Idea Generation",
        "novelty_checking": "Novelty Checking",
        "feasibility_scoring": "Feasibility Scoring",
        "proposal_synthesis": "Proposal Synthesis",
        "export": "Export",
    }

    _STAGE_ORDER = [
        "literature_search",
        "ingestion",
        "gap_analysis",
        "idea_generation",
        "novelty_checking",
        "feasibility_scoring",
        "proposal_synthesis",
        "export",
    ]

    status = Status("Initializing...", console=console)

    def on_stage(stage_name, idx, total, elapsed):
        label = _STAGE_DISPLAY.get(stage_name, stage_name)
        status.update(f"[bold]Stage {idx}/{total}:[/bold] {label} ({elapsed:.0f}s)")

    # Resume: load run state from DB and compute skip_stages (HB-02)
    skip_stages: set[str] | None = None
    if resume:
        from sqlalchemy import select
        from backend.db.database import get_session
        from backend.db.models import PipelineRun

        import json

        with get_session() as session:
            try:
                run_id_int = int(resume)
            except ValueError:
                console.print(
                    Panel(
                        f"[red]Invalid RUN_ID:[/red] '{resume}' is not a valid integer ID.\n"
                        f"Use [bold]erock runs[/bold] to see available run IDs.",
                        title="[red]Resume Error[/red]",
                    )
                )
                raise typer.Exit(1) from None

            db_run = session.get(PipelineRun, run_id_int)
            if not db_run:
                console.print(
                    Panel(
                        f"[red]RUN_ID {resume} not found in database.[/red]\n"
                        f"Use [bold]erock runs[/bold] to see available run IDs.",
                        title="[red]Resume Error[/red]",
                    )
                )
                raise typer.Exit(1) from None

            if db_run.status in ("completed", "failed"):
                console.print(
                    Panel(
                        f"[red]Cannot resume run {resume}: status is '{db_run.status}'.[/red]\n"
                        f"Only runs with status 'running' can be resumed.",
                        title="[red]Resume Error[/red]",
                    )
                )
                raise typer.Exit(1) from None

            # Determine completed stages from DB (HB-02)
            completed = json.loads(db_run.stages_completed or "[]")
            skip_stages = set(completed)
            console.print(
                f"[yellow]Resuming from stage '{db_run.current_stage}' "
                f"({len(completed)} stages already completed)[/yellow]"
            )

    async def _run():
        orchestrator = PipelineOrchestrator(stage_callback=on_stage)
        return await orchestrator.run(
            domain=domain,
            search_queries=query_list,
            max_gaps=gaps,
            generation_rounds=rounds,
            ideas_per_round=ideas,
            run_novelty=novelty,
            run_feasibility=feasibility,
            run_synthesis=True,
            export_format=export,
            skip_stages=skip_stages,
        )

    with status:
        result = _run_async(_run())

    # Display results
    console.print("\n[bold green]Pipeline Complete[/bold green]")
    console.print(f"Papers found: {result.papers_found}")
    console.print(f"Research gaps: {len(result.gaps)}")
    console.print(f"Ideas generated: {len(result.ideas)}")

    for i, idea in enumerate(result.ideas, 1):
        novelty_score = result.novelty_reports.get(i - 1)
        feas_score = result.feasibility_reports.get(i - 1)

        panel_text = (
            f"{idea.problem_statement[:200]}...\n\n"
            f"[bold]Method:[/bold] {idea.proposed_method[:150]}...\n\n"
        )
        if novelty_score:
            panel_text += f"[cyan]Novelty: {novelty_score.overall_score:.2f}[/cyan]  "
        if feas_score:
            panel_text += f"[yellow]Feasibility: {feas_score.overall_score:.1f}/10[/yellow]"
        if i - 1 in result.export_paths:
            panel_text += f"\n[green]Exported: {result.export_paths[i-1]}[/green]"

        console.print(Panel(panel_text, title=f"Idea {i}: {idea.title}", width=80))

    _print_score_guide()


# --- Individual Idea Commands ---


def _build_research_idea(
    text: str, provider, method: str | None, contributions: str | None
):
    """Build a ResearchIdea, using LLM to fill missing fields if needed."""
    from backend.pipeline.generation.models import ResearchIdea

    if method and contributions:
        return ResearchIdea(
            title=text[:100],
            problem_statement=text,
            proposed_method=method,
            expected_contributions=contributions,
            novelty_rationale="",
            evaluation_approach="",
        )

    async def _extract():
        prompt = (
            "Extract the following from this research idea description.\n"
            "Return JSON with keys: title, proposed_method, expected_contributions\n\n"
            f"Idea:\n{text}"
        )
        resp = await provider.generate(prompt)
        import json

        try:
            parsed = json.loads(resp)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        return ResearchIdea(
            title=parsed.get("title", text[:100]),
            problem_statement=text,
            proposed_method=method or parsed.get("proposed_method", ""),
            expected_contributions=contributions or parsed.get("expected_contributions", ""),
            novelty_rationale="",
            evaluation_approach="",
        )

    return _run_async(_extract())


@app.command("novelty-check")
def check_novelty(
    idea_text: str = typer.Argument(..., help="Idea text to check"),
    method: str | None = typer.Option(None, "--method", "-m", help="Proposed method"),
    contributions: str | None = typer.Option(
        None, "--contributions", "-c", help="Expected contributions"
    ),
):
    """Check the novelty of a research idea against the knowledge base."""
    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.pipeline.novelty.novelty_checker import NoveltyChecker
    from backend.providers.provider_factory import create_provider

    async def _check():
        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)
        checker = NoveltyChecker(provider, store)

        idea = _build_research_idea(idea_text, provider, method, contributions)
        return await checker.check_novelty(idea)

    report = _run_async(_check())

    table = Table(title="Novelty Report")
    table.add_column("Dimension", style="bold")
    table.add_column("Score", width=10)
    table.add_row("Overall", f"{report.overall_score:.2f}")
    table.add_row("Method Novelty", f"{report.method_novelty:.2f}")
    table.add_row("Problem Novelty", f"{report.problem_novelty:.2f}")
    table.add_row("Domain Transfer", f"{report.domain_transfer:.2f}")
    table.add_row("Combination Novelty", f"{report.combination_novelty:.2f}")
    console.print(table)
    console.print(f"\n[italic]{report.novelty_arguments}[/italic]")


@app.command("feasibility-score")
def score_feasibility(
    idea_text: str = typer.Argument(..., help="Idea text to score"),
    method: str | None = typer.Option(None, "--method", "-m", help="Proposed method"),
    contributions: str | None = typer.Option(
        None, "--contributions", "-c", help="Expected contributions"
    ),
):
    """Score the feasibility of a research idea."""
    from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
    from backend.providers.provider_factory import create_provider

    async def _score():
        provider = create_provider()
        scorer = FeasibilityScorer(provider)

        idea = _build_research_idea(idea_text, provider, method, contributions)
        return await scorer.score_feasibility(idea)

    report = _run_async(_score())

    table = Table(title="Feasibility Report")
    table.add_column("Dimension", style="bold")
    table.add_column("Score (0-10)", width=12)
    table.add_row("Overall", f"{report.overall_score:.1f}")
    table.add_row("Data Availability", f"{report.data_availability:.1f}")
    table.add_row("Compute Requirements", f"{report.computational_requirements:.1f}")
    table.add_row("Method Complexity", f"{report.methodological_complexity:.1f}")
    table.add_row("Evaluation Plan", f"{report.evaluation_plan:.1f}")
    table.add_row("Novelty Grounding", f"{report.novelty_grounding:.1f}")
    table.add_row("Impact Potential", f"{report.impact_potential:.1f}")
    console.print(table)
    console.print(f"\nTimeline: {report.estimated_timeline}")
    console.print(f"Reasoning: {report.reasoning}")


# --- Utility Commands ---


@app.command("status")
def show_status():
    """Show current knowledge base and configuration status."""
    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.providers.provider_factory import create_provider

    settings = get_settings()

    console.print(
        Panel(
            f"[bold]Elephant Rock Research Platform[/bold]\n"
            f"Provider: {settings.default_provider}\n"
            f"Knowledge Base: {settings.chroma_persist_dir}\n"
            f"Database: {settings.database_url}",
            title="Configuration",
        )
    )

    try:

        async def _stats():
            provider = create_provider()
            embedding = EmbeddingService(provider)
            store = VectorStore(settings.chroma_persist_dir, embedding)
            return store.get_stats()

        stats = _run_async(_stats())
        console.print(
            f"\nKnowledge Base: {stats['document_count']} documents in collection '{stats['collection']}'"
        )
    except Exception as e:
        console.print(f"\n[yellow]Knowledge base not initialized: {e}[/yellow]")


# --- DB Query Commands ---


@app.command("autonomous")
def autonomous_cycle(
    domain: str = typer.Option("AI/NLP", "--domain", "-d", help="Research domain"),
    max_runs: int = typer.Option(3, "--max-runs", "-r", help="Maximum autonomous runs"),
):
    """Run autonomous research cycles."""
    from backend.pipeline.orchestrator import PipelineOrchestrator

    console.print(
        Panel(
            f"[bold]Autonomous Research Cycle[/bold]\n"
            f"Domain: {domain}\n"
            f"Max runs: {max_runs}",
            title="Starting Autonomous Mode",
        )
    )

    async def _run():
        orchestrator = PipelineOrchestrator()
        return await orchestrator.autonomous_cycle(domain=domain, max_autonomous_runs=max_runs)

    results = _run_async(_run())

    console.print("\n[bold green]Autonomous Cycle Complete[/bold green]")
    console.print(f"Total runs: {len(results)}")
    for i, result in enumerate(results, 1):
        console.print(
            f"\n  Run {i}: {len(result.ideas)} ideas, {len(result.gaps)} gaps, "
            f"{len(result.proposals)} proposals"
        )
        for idea in result.ideas[:3]:
            console.print(f"    - {idea.title}")


@app.command("ideas")
def list_ideas_cmd(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    min_score: float = typer.Option(0.0, "--min-score", "-s", help="Minimum overall score"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
):
    """List research ideas from the database."""
    from backend.db.crud import list_ideas as db_list_ideas
    from backend.db.database import get_session

    with get_session() as session:
        ideas = db_list_ideas(
            session, limit=limit, domain=domain, min_score=min_score if min_score > 0 else None
        )

    if not ideas:
        console.print("[yellow]No ideas found.[/yellow]")
        return

    table = Table(title="Research Ideas")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Title", style="bold", max_width=50)
    table.add_column("Domain", width=10)
    table.add_column("Novelty", width=8)
    table.add_column("Feasibility", width=10)
    table.add_column("Overall", width=8)
    table.add_column("Rating", width=7)

    for i in ideas:
        table.add_row(
            str(i.id),
            i.title[:50],
            i.domain,
            f"{i.novelty_score:.2f}" if i.novelty_score else "-",
            f"{i.feasibility_score:.1f}" if i.feasibility_score else "-",
            f"{i.overall_score:.2f}" if i.overall_score else "-",
            str(i.user_rating) if i.user_rating else "-",
        )

    console.print(table)
    console.print(f"\n{len(ideas)} ideas")
    _print_score_guide()


@app.command("runs")
def list_runs_cmd(
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
):
    """List pipeline runs from the database."""
    from sqlalchemy import select

    from backend.db.database import get_session
    from backend.db.models import PipelineRun

    with get_session() as session:
        runs = (
            session.execute(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(limit))
            .scalars()
            .all()
        )

    if not runs:
        console.print("[yellow]No pipeline runs found.[/yellow]")
        return

    table = Table(title="Pipeline Runs")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Domain", width=10)
    table.add_column("Status", width=10)
    table.add_column("Stage", width=18)
    table.add_column("Ideas", width=7)
    table.add_column("Created", width=20)

    for r in runs:
        status_style = {"completed": "green", "running": "yellow", "failed": "red"}.get(
            r.status, ""
        )
        table.add_row(
            str(r.id),
            r.domain,
            f"[{status_style}]{r.status}[/{status_style}]" if status_style else r.status,
            r.current_stage or "-",
            str(len(r.ideas)),
            str(r.created_at)[:19] if r.created_at else "-",
        )

    console.print(table)


@app.command("gaps")
def list_gaps_cmd(
    run_id: int | None = typer.Option(None, "--run-id", "-r", help="Pipeline run ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
):
    """List research gaps from the latest (or specified) pipeline run."""
    from sqlalchemy import select

    from backend.db.database import get_session
    from backend.db.models import PipelineRun, ResearchGapDB

    with get_session() as session:
        target_run = run_id
        if target_run is None:
            latest = (
                session.execute(
                    select(PipelineRun)
                    .where(PipelineRun.status == "completed")
                    .order_by(PipelineRun.id.desc())
                    .limit(1)
                )
                .scalar_one_or_none()
            )
            if not latest:
                console.print("[yellow]No completed runs found.[/yellow]")
                return
            target_run = latest.id

        gaps = (
            session.execute(
                select(ResearchGapDB)
                .where(ResearchGapDB.pipeline_run_id == target_run)
                .order_by(ResearchGapDB.confidence.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    if not gaps:
        console.print(f"[yellow]No gaps found for run {target_run}.[/yellow]")
        return

    console.print(f"[bold]Gaps from run {target_run}[/bold]\n")
    for i, g in enumerate(gaps, 1):
        console.print(f"  {i}. [bold]{g.title}[/bold] (confidence: {g.confidence:.2f})")
        if g.description:
            console.print(f"     {g.description[:120]}")
    console.print(f"\n{len(gaps)} gaps")


@app.command("knowledge")
def knowledge_cmd(
    action: str = typer.Argument(..., help='Action: "search"'),
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, "--limit", "-l", help="Max results"),
):
    """Search the knowledge base."""
    if action != "search":
        console.print(f"[red]Unknown action: {action}. Use 'search'.[/red]")
        raise typer.Exit(1)

    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.providers.provider_factory import create_provider

    async def _search():
        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)
        return await store.query(query, n_results=limit)

    results = _run_async(_search())

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for i, r in enumerate(results, 1):
        title = r.get("metadata", {}).get("paper_title", "Unknown")
        distance = r.get("distance", 0)
        text = r.get("text", "")[:200]
        console.print(f"{i}. [bold]{title}[/bold] (distance: {distance:.3f})")
        console.print(f"   {text}...\n")
    console.print(f"{len(results)} results")


@app.command("config")
def show_config():
    """Display key configuration settings."""
    from backend.config import get_settings

    settings = get_settings()

    console.print(
        Panel(
            f"[bold]Elephant Rock Research Platform Configuration[/bold]\n\n"
            f"Provider: {settings.default_provider}\n"
            f"Embedding: {settings.embedding_provider} / {settings.embedding_model}\n"
            f"Knowledge Base: {settings.chroma_persist_dir}\n"
            f"Database: {settings.database_url}\n"
            f"Generation Rounds: {settings.generation_rounds}\n"
            f"Ideas/Round: {settings.ideas_per_round}\n"
            f"Memory: {'enabled' if settings.memory_enabled else 'disabled'}\n"
            f"Self-Improve: {'enabled' if settings.self_improve_enabled else 'disabled'}",
            title="Configuration",
        )
    )


def _print_score_guide():
    """Append score interpretation guide."""
    console.print(
        "\n[dim]Score Guide: "
        "Novelty: 0-0.3 Low / 0.3-0.6 Moderate / 0.6-0.8 High / 0.8-1.0 Very High  |  "
        "Feasibility: 0-3 Difficult / 3-6 Moderate / 6-8 Feasible / 8-10 Very Feasible[/dim]"
    )


from backend.cli.commands.setup import setup_wizard
from backend.cli.commands.dev import dev_command
from backend.cli.commands.db import db_app
from backend.cli.commands.research import research_app
from backend.cli.capability_cli import capability_app
from backend.cli.config_cli import config_app

app.command("setup")(setup_wizard)
app.command("dev")(dev_command)
app.add_typer(db_app, name="db")
app.add_typer(research_app, name="research")
app.add_typer(capability_app, name="capability")
app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()
