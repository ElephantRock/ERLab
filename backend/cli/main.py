"""Elephant Rock Research CLI — command-line interface for the research pipeline."""

import asyncio
import json
import sys

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


def _run_async(coro):
    """Run an async function from sync CLI context."""
    return asyncio.run(coro)


# --- Literature Commands ---

@app.command("search")
def search_literature(
    query: str = typer.Argument(..., help="Search query"),
    sources: str = typer.Option("semantic_scholar,arxiv", "--sources", "-s", help="Comma-separated sources"),
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
    paper_id: str | None = typer.Option(None, "--id", help="Paper ID (auto-generated if not provided)"),
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
        chunks = await pdf.parse_and_chunk(file_path, pid, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)

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
    queries: str | None = typer.Option(None, "--queries", "-q", help="Comma-separated search queries"),
    gaps: int = typer.Option(5, "--gaps", "-g", help="Max gaps to identify"),
    rounds: int = typer.Option(2, "--rounds", "-r", help="Generation rounds"),
    ideas: int = typer.Option(3, "--ideas", "-i", help="Ideas per round"),
    novelty: bool = typer.Option(True, "--novelty/--no-novelty", help="Run novelty checking"),
    feasibility: bool = typer.Option(True, "--feasibility/--no-feasibility", help="Run feasibility scoring"),
    export: str | None = typer.Option("markdown", "--export", "-e", help="Export format (markdown/latex)"),
):
    """Run the full research idea generation pipeline."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    from backend.providers.provider_factory import create_provider

    query_list = [q.strip() for q in queries.split(",")] if queries else None

    console.print(Panel(
        f"[bold]Elephant Rock Research Pipeline[/bold]\n"
        f"Domain: {domain}\n"
        f"Gaps: {gaps} | Rounds: {rounds} | Ideas/round: {ideas}\n"
        f"Novelty: {novelty} | Feasibility: {feasibility} | Export: {export}",
        title="Starting Pipeline",
    ))

    async def _run():
        orchestrator = PipelineOrchestrator()
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
        )

    result = _run_async(_run())

    # Display results
    console.print(f"\n[bold green]Pipeline Complete[/bold green]")
    console.print(f"Papers found: {result.papers_found}")
    console.print(f"Research gaps: {len(result.gaps)}")
    console.print(f"Ideas generated: {len(result.ideas)}")

    for i, idea in enumerate(result.ideas, 1):
        novelty_score = result.novelty_reports.get(id(idea))
        feas_score = result.feasibility_reports.get(id(idea))

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


# --- Individual Idea Commands ---

@app.command("novelty-check")
def check_novelty(
    idea_text: str = typer.Argument(..., help="Idea text to check"),
):
    """Check the novelty of a research idea against the knowledge base."""
    from backend.config import get_settings
    from backend.pipeline.generation.models import ResearchIdea
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

        idea = ResearchIdea(
            title=idea_text[:100],
            problem_statement=idea_text,
            proposed_method="",
            expected_contributions="",
            novelty_rationale="",
            evaluation_approach="",
        )
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
):
    """Score the feasibility of a research idea."""
    from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
    from backend.pipeline.generation.models import ResearchIdea
    from backend.providers.provider_factory import create_provider

    async def _score():
        provider = create_provider()
        scorer = FeasibilityScorer(provider)

        idea = ResearchIdea(
            title=idea_text[:100],
            problem_statement=idea_text,
            proposed_method="",
            expected_contributions="",
            novelty_rationale="",
            evaluation_approach="",
        )
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

    console.print(Panel(
        f"[bold]Elephant Rock Research Platform[/bold]\n"
        f"Provider: {settings.default_provider}\n"
        f"Knowledge Base: {settings.chroma_persist_dir}\n"
        f"Database: {settings.database_url}",
        title="Configuration",
    ))

    try:
        async def _stats():
            provider = create_provider()
            embedding = EmbeddingService(provider)
            store = VectorStore(settings.chroma_persist_dir, embedding)
            return store.get_stats()

        stats = _run_async(_stats())
        console.print(f"\nKnowledge Base: {stats['document_count']} documents in collection '{stats['collection']}'")
    except Exception as e:
        console.print(f"\n[yellow]Knowledge base not initialized: {e}[/yellow]")


if __name__ == "__main__":
    app()
