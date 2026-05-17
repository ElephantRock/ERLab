"""CLI for model certification.

Usage:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Model Certification Pipeline v0.1"
    )
    sub = parser.add_subparsers(dest="command")

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
        help="LM Studio base URL (e.g., http://100.64.0.1:1234)",
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

    if args.command == "certify":
        asyncio.run(_certify(args))


async def _certify(args: argparse.Namespace) -> None:
    """Run certification."""
    # Load manifest
    manifest = CandidateModelManifest.from_yaml_file(args.manifest)
    print(f"Candidate: {manifest.model_id}")
    print(f"  Provider:  {manifest.provider}")
    print(f"  Context:   {manifest.advertised_context_window}")
    print(f"  JSON mode: {manifest.supports_json_mode}")

    # Create provider (simplified — uses LM Studio directly)
    provider = _create_provider(manifest, args.lmstudio_url)

    # Production registry (optional)
    prod_registry = None
    if args.production_registry:
        prod_registry = ProductionModelRegistry(path=args.production_registry)

    # Run certification
    runner = CertificationRunner(
        provider=provider,
        reports_dir=args.out,
        production_registry=prod_registry,
        lmstudio_base_url=args.lmstudio_url,
    )

    report = await runner.certify(
        manifest,
        auto_promote=args.auto_promote == "true",
        cases_per_schema=args.cases_per_schema,
    )

    # Print summary
    print()
    print("=" * 60)
    print(f"Model:    {report.model_id}")
    print(f"Status:   {report.status}")
    print(f"Context:  {report.safe_context_window} tokens (safe)")
    print(f"Output:   {report.safe_output_tokens} tokens (safe)")
    if report.schema_eval:
        se = report.schema_eval
        print(f"Schema valid rate:     {se.get('schema_valid_rate', 'N/A'):.0%}" if isinstance(se.get('schema_valid_rate'), float) else f"Schema valid rate:     N/A")
        print(f"Raw JSON valid rate:   {se.get('raw_json_valid_rate', 'N/A'):.0%}" if isinstance(se.get('raw_json_valid_rate'), float) else f"Raw JSON valid rate:   N/A")
        print(f"Repair success rate:   {se.get('repair_success_rate', 'N/A'):.0%}" if isinstance(se.get('repair_success_rate'), float) else f"Repair success rate:   N/A")
    if report.smoke_test:
        st = report.smoke_test
        print(f"Smoke test:            {'passed' if st.get('passed') else 'FAILED'}")
    print(f"Production eligible:   {report.promotion_allowed}")
    if report.stage_eligibility:
        approved = [s for s, v in report.stage_eligibility.items() if v in ("approved", "limited")]
        print(f"Eligible stages:       {', '.join(approved[:8])}")
    print(f"Report:                {report.eval_run_id}")
    print("=" * 60)


def _create_provider(manifest: CandidateModelManifest, base_url: str | None) -> object:
    """Create a minimal LLM provider for certification.

    For LM Studio, creates a simple OpenAI-compatible provider.
    """
    if manifest.provider == "lmstudio":
        url = base_url or "http://localhost:1234/v1"
        from backend.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            base_url=url,
            model=manifest.model_id,
            api_key="lm-studio",
            max_tokens=manifest.advertised_max_output_tokens,
        )
    else:
        raise ValueError(
            f"CLI provider creation not implemented for '{manifest.provider}'. "
            f"Pass a pre-configured provider to CertificationRunner."
        )


if __name__ == "__main__":
    main()
