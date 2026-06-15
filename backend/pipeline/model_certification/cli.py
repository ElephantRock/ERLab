"""CLI for model certification.

Usage:
    python -m backend.pipeline.model_certification.cli profile \n        --model google/gemma-4-12b \n        --base-url http://100.64.0.1:1234/v1

    python -m backend.pipeline.model_certification.cli profile \n        --model google/gemma-4-12b \n        --base-url http://100.64.0.1:1234/v1

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
    if args.command == "profile":
        asyncio.run(_profile(args))
    elif args.command == "certify":
        asyncio.run(_certify(args))


