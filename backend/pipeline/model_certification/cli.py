"""CLI for model certification.

Usage:
    python -m backend.pipeline.model_certification.cli profile 
        --model google/gemma-4-12b 
        --base-url http://your-server:1234/v1

    python -m backend.pipeline.model_certification.cli certify \\
        --manifest data/model_certification/candidates/qwen3-4b-2507.yaml \\
        --out data/model_certification/reports \\
        --auto-promote false
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from backend.pipeline.model_certification.manifest import CandidateModelManifest
from backend.pipeline.model_certification.runner import CertificationRunner
from backend.pipeline.model_certification.registries import ProductionModelRegistry

logger = logging.getLogger(__name__)


async def _certify(args) -> None:
    """Run the certification pipeline for a candidate model."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Error: manifest not found: {manifest_path}")
        sys.exit(1)

    manifest = CandidateModelManifest.from_yaml(
        manifest_path.read_text(encoding="utf-8")
    )

    # Build provider from manifest
    from backend.providers.provider_factory import create_provider
    from backend.config import get_settings
    settings = get_settings()

    if manifest.provider == "lmstudio":
        provider = create_provider("lmstudio", settings=settings)
    else:
        provider = create_provider(manifest.provider, settings=settings)

    # Optional production registry
    prod_registry = None
    if args.production_registry:
        prod_registry = ProductionModelRegistry(path=args.production_registry)
    elif args.auto_promote == "true":
        prod_registry = ProductionModelRegistry()

    runner = CertificationRunner(
        provider=provider,
        reports_dir=args.out,
        production_registry=prod_registry,
        lmstudio_base_url=args.lmstudio_url,
    )

    report = await runner.certify(
        manifest,
        auto_promote=(args.auto_promote == "true"),
        cases_per_schema=args.cases_per_schema,
    )

    # Print summary
    print(f"\n{'='*60}")
    print(f"Certification Summary: {report.model_id}")
    print(f"{'='*60}")
    print(f"  Status: {report.status}")
    print(f"  Safe context window: {report.safe_context_window}")
    print(f"  Safe output tokens: {report.safe_output_tokens}")
    print(f"  Schema valid rate: {report.scores.get('schema_valid_rate', 'N/A')}")
    print(f"  Promotion allowed: {report.promotion_allowed}")
    if report.known_failure_modes:
        print(f"  Failure modes: {', '.join(report.known_failure_modes)}")
    print(f"{'='*60}")


async def _profile(args) -> None:
    """Run 3-tier token profiling for a model."""
    from backend.pipeline.model_certification.token_profiler import TokenProfiler

    profiler = TokenProfiler(
        model_id=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    results = await profiler.run_all_tiers()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{args.model.replace('/', '_')}_profile.yaml"
    profiler.save(results, report_path)
    print(f"Profile saved to {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Model Certification Pipeline v0.1"
    )
    sub = parser.add_subparsers(dest="command")

    # profile subcommand (3-tier token profiling)
    prof = sub.add_parser("profile", help="3-tier token profiling for a model")
    prof.add_argument("--model", required=True, help="Model ID (e.g., google/gemma-4-12b)")
    prof.add_argument("--base-url", default="http://localhost:1234/v1", help="API base URL")
    prof.add_argument("--api-key", default="lm-studio", help="API key")
    prof.add_argument("--out", default="data/model_certification/profiles", help="Output directory")
    prof.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # profile subcommand (3-tier token profiling)
    prof = sub.add_parser("profile", help="3-tier token profiling for a model")
    prof.add_argument("--model", required=True, help="Model ID")
    prof.add_argument("--base-url", default="http://localhost:1234/v1")
    prof.add_argument("--api-key", default="lm-studio")
    prof.add_argument("--out", default="data/model_certification/profiles")
    prof.add_argument("--verbose", "-v", action="store_true")

    # certify subcommand
    cert = sub.add_parser("certify", help="Certify a candidate model")
    cert.add_argument(
        "--manifest", required=True,
        help="Path to candidate manifest YAML",
    )
    cert.add_argument(
        "--out", default="data/model_certification/reports",
        help="Output directory for reports",
    )
    cert.add_argument(
        "--auto-promote", default="false",
        choices=["true", "false"],
        help="Auto-promote approved models to production registry",
    )
    cert.add_argument(
        "--lmstudio-url", default=None,
        help="LM Studio base URL (e.g., http://localhost:1234)",
    )
    cert.add_argument(
        "--production-registry", default=None,
        help="Path to production registry YAML",
    )
    cert.add_argument(
        "--cases-per-schema", type=int, default=5,
        help="Number of test cases per schema (default: 5)",
    )
    cert.add_argument(
        "--include-stage-eval", action="store_true",
        help="Include v0.2 stage evaluation (scorecards + eligibility)",
    )
    cert.add_argument(
        "--stage-suite", default="seed",
        choices=["seed", "extended"],
        help="Stage eval case suite (default: seed)",
    )
    cert.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.command == "profile":
        asyncio.run(_profile(args))
    elif args.command == "certify":
        asyncio.run(_certify(args))


