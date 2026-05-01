"""Interactive ``erock setup`` CLI wizard.

Guides a new user from zero configuration to a validated ``.env`` file
and (optionally) a successful test pipeline run.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

MIN_PYTHON = (3, 11)

PROVIDERS: dict[str, dict[str, str | None]] = {
    "openai": {
        "label": "OpenAI",
        "model_default": "gpt-4o",
        "key_env": "EROCK_OPENAI_API_KEY",
        "key_prompt": "OpenAI API key (sk-...)",
    },
    "anthropic": {
        "label": "Anthropic",
        "model_default": "claude-sonnet-4-20250514",
        "key_env": "EROCK_ANTHROPIC_API_KEY",
        "key_prompt": "Anthropic API key (sk-ant-...)",
    },
    "gemini": {
        "label": "Gemini",
        "model_default": "gemini-2.0-flash",
        "key_env": "EROCK_GEMINI_API_KEY",
        "key_prompt": "Google/Gemini API key",
    },
    "ollama": {
        "label": "Ollama (local)",
        "model_default": "llama3",
        "key_env": None,
        "key_prompt": None,
    },
}

# 18 core variables the wizard explicitly manages (TEST-07-01-05).
REQUIRED_ENV_VARS: list[str] = [
    "EROCK_DEFAULT_PROVIDER",
    "EROCK_OPENAI_API_KEY",
    "EROCK_ANTHROPIC_API_KEY",
    "EROCK_GEMINI_API_KEY",
    "EROCK_OLLAMA_BASE_URL",
    "EROCK_OPENAI_MODEL",
    "EROCK_ANTHROPIC_MODEL",
    "EROCK_GEMINI_MODEL",
    "EROCK_OLLAMA_MODEL",
    "EROCK_EMBEDDING_PROVIDER",
    "EROCK_EMBEDDING_MODEL",
    "EROCK_DATABASE_URL",
    "EROCK_CHROMA_PERSIST_DIR",
    "EROCK_GENERATION_ROUNDS",
    "EROCK_IDEAS_PER_ROUND",
    "EROCK_NOVELTY_TOP_K",
    "EROCK_DEBUG",
    "EROCK_LITELLM_FALLBACK_ENABLED",
]


# ── Helpers ──────────────────────────────────────────────────────────


def check_python_version() -> bool:
    """Return *True* when the running Python is ≥ MIN_PYTHON."""
    return sys.version_info >= MIN_PYTHON


async def _validate_openai(api_key: str) -> bool:
    """Lightweight auth check against OpenAI models endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return r.status_code == 200
    except Exception:
        return False


async def _validate_anthropic(api_key: str) -> bool:
    """Lightweight auth check against Anthropic messages endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            return r.status_code == 200
    except Exception:
        return False


async def _validate_gemini(api_key: str) -> bool:
    """Lightweight auth check against Gemini models endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
            return r.status_code == 200
    except Exception:
        return False


async def validate_api_key(provider: str, api_key: str) -> bool:
    """Validate an API key by making a test call to the provider."""
    validators = {
        "openai": _validate_openai,
        "anthropic": _validate_anthropic,
        "gemini": _validate_gemini,
    }
    validator = validators.get(provider)
    if validator is None:
        return True  # Ollama doesn't need a key
    return await validator(api_key)


async def detect_ollama(base_url: str = "http://localhost:11434") -> bool:
    """Return *True* when an Ollama server is reachable at *base_url*."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ── .env generation ──────────────────────────────────────────────────


def _serialize_default(value: Any) -> str:
    """Convert a Settings default into a .env-safe string."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return str(value)
    if isinstance(value, dict):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if value is None:
        return ""
    return str(value)


def generate_env_content(
    provider: str,
    api_key: str | None = None,
    model_override: str | None = None,
) -> str:
    """Build the complete ``.env`` file content.

    AR-01 compliance: every field in the ``Settings`` class is present.
    """
    from backend.config import Settings

    lines: list[str] = [
        "# Elephant Rock Research Platform Configuration",
        "# Generated by erock setup wizard",
        "",
    ]

    overrides: dict[str, str] = {}

    # Provider selection
    overrides["default_provider"] = provider

    # API key
    key_field = f"{provider}_api_key"
    if provider == "gemini":
        key_field = "gemini_api_key"
    if api_key:
        overrides[key_field] = api_key

    # Model override for chosen provider
    if model_override:
        model_field = f"{provider}_model"
        overrides[model_field] = model_override
    elif provider in PROVIDERS:
        default_model = PROVIDERS[provider].get("model_default")
        if default_model:
            model_field = f"{provider}_model"
            overrides[model_field] = str(default_model)

    # Embedding provider alignment
    if provider in ("openai", "gemini", "anthropic"):
        overrides["embedding_provider"] = provider
        if provider == "openai":
            overrides["embedding_model"] = "text-embedding-3-small"
        elif provider == "gemini":
            overrides["embedding_model"] = "text-embedding-004"
        elif provider == "anthropic":
            overrides["embedding_provider"] = "openai"  # Anthropic doesn't host embeddings
    elif provider == "ollama":
        overrides["embedding_provider"] = "ollama"
        overrides["embedding_model"] = "nomic-embed-text"

    for field_name, field_info in Settings.model_fields.items():
        env_var = f"EROCK_{field_name.upper()}"
        if field_name in overrides:
            value = overrides[field_name]
        else:
            default = getattr(field_info, "default", None)
            if default is None:
                value = ""
            else:
                value = _serialize_default(default)
        lines.append(f"{env_var}={value}")

    lines.append("")
    return "\n".join(lines)


# ── Test pipeline ────────────────────────────────────────────────────


async def _run_test_pipeline() -> bool:
    """Attempt a single-idea pipeline run to validate end-to-end."""
    try:
        from backend.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run(
            domain="AI/NLP",
            search_queries=["test setup validation"],
            max_gaps=1,
            generation_rounds=1,
            ideas_per_round=1,
            run_novelty=False,
            run_feasibility=False,
            run_synthesis=False,
            export_format="markdown",
        )
        return len(result.ideas) >= 0  # success if no exception
    except Exception as exc:
        console.print(f"[yellow]Test pipeline failed: {exc}[/yellow]")
        return False


# ── Wizard entry-point ──────────────────────────────────────────────


def setup_wizard(
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="LLM provider (openai/anthropic/gemini/ollama)"
    ),
    key: str | None = typer.Option(
        None, "--key", "-k", help="API key for the chosen provider"
    ),
) -> None:
    """Interactive setup wizard — configure your Elephant Rock installation."""

    # ── 1. Python version check ──────────────────────────────────────
    if not check_python_version():
        console.print(
            Panel(
                f"[red]Python {sys.version_info.major}.{sys.version_info.minor} "
                f"detected.[/red]\n\n"
                f"Elephant Rock requires Python ≥ 3.11.\n"
                f"Please upgrade: [bold]https://www.python.org/downloads/[/bold]",
                title="[red]Incompatible Python[/red]",
            )
        )
        raise typer.Exit(1)

    console.print(
        f"[green]✓[/green] Python {sys.version_info.major}.{sys.version_info.minor} detected"
    )

    # ── 2. Provider selection ────────────────────────────────────────
    if provider is None:
        console.print("\n[bold]Select your LLM provider:[/bold]")
        for idx, key in enumerate(PROVIDERS, 1):
            console.print(f"  {idx}. {PROVIDERS[key]['label']}")
        choice = Prompt.ask("Enter number", choices=[str(i) for i in range(1, len(PROVIDERS) + 1)])
        provider = list(PROVIDERS.keys())[int(choice) - 1]

    if provider not in PROVIDERS:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)

    info = PROVIDERS[provider]
    console.print(f"[green]✓[/green] Provider: {info['label']}")

    # ── 3. Ollama detection ─────────────────────────────────────────
    if provider == "ollama":
        if not asyncio.run(detect_ollama()):
            console.print(
                Panel(
                    "[yellow]Ollama not detected at localhost:11434.[/yellow]\n\n"
                    "Make sure Ollama is running:\n"
                    "  [bold]ollama serve[/bold]\n\n"
                    "Or install: [bold]https://ollama.ai[/bold]",
                    title="[yellow]Ollama Not Found[/yellow]",
                )
            )
            raise typer.Exit(1)
        console.print("[green]✓[/green] Ollama detected at localhost:11434")

    # ── 4. API key ──────────────────────────────────────────────────
    if info["key_prompt"] and not key:
        key = Prompt.ask(str(info["key_prompt"]))

    # ── 5. API key validation ────────────────────────────────────────
    if provider != "ollama" and key:
        console.print("[dim]Validating API key…[/dim]")
        valid = asyncio.run(validate_api_key(provider, key))
        if not valid:
            console.print(
                Panel(
                    "[red]API key validation failed.[/red]\n\n"
                    "Possible causes:\n"
                    "  • Invalid or expired key\n"
                    "  • Network connectivity issue\n"
                    "  • Provider API is temporarily unavailable\n\n"
                    f"Set the correct key in [bold].env[/bold] under "
                    f"[bold]{info['key_env']}[/bold]",
                    title="[red]Invalid API Key[/red]",
                )
            )
            raise typer.Exit(1)
        console.print("[green]✓[/green] API key validated")

    # ── 6. Generate .env ─────────────────────────────────────────────
    env_path = Path(".env")
    model_override: str | None = (
        str(info["model_default"]) if info.get("model_default") else None
    )

    content = generate_env_content(
        provider=provider,
        api_key=key,
        model_override=model_override,
    )
    env_path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓[/green] Configuration written to [bold]{env_path}[/bold]")

    # ── 7. Optional test pipeline ────────────────────────────────────
    try:
        run_test = Confirm.ask("\nRun a test pipeline to verify the setup?", default=False)
    except Exception:
        run_test = False

    if run_test:
        console.print("[dim]Running test pipeline (1 idea, 1 round)…[/dim]")
        success = asyncio.run(_run_test_pipeline())
        if success:
            console.print("[green]✓[/green] Test pipeline completed successfully")
        else:
            console.print("[yellow]⚠ Test pipeline did not complete — check logs[/yellow]")

    # ── 8. Next steps ────────────────────────────────────────────────
    console.print(
        Panel(
            "[bold green]Setup complete![/bold green]\n\n"
            "Next steps:\n"
            "  1. Run: [bold]erock generate --domain 'AI/NLP'[/bold]\n"
            "  2. Or start the web UI: [bold]python -m backend.api.main[/bold]\n"
            "  3. Read the docs: [bold]https://github.com/elephant-rock/docs[/bold]",
            title="🚀 Elephant Rock Research",
        )
    )
