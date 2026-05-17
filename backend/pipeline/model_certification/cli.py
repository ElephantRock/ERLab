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

    # Stage evaluation (v0.2)
    if args.include_stage_eval:
        try:
            from backend.pipeline.model_certification.stage_runner import (
                StageEvalRunner, aggregate_scorecards,
            )
            from backend.pipeline.model_certification.stage_policy import decide_all_stages
            from backend.pipeline.model_certification.stage_report import extend_report_with_stage_eval

            print("\nRunning stage evaluation (v0.2)...")
            eval_dir = str(Path(args.manifest).parent.parent / "eval_cases")
            stage_runner = StageEvalRunner(provider, manifest.model_id, eval_dir=eval_dir)
            results_by_stage = await stage_runner.run_all()
            scorecards = aggregate_scorecards(results_by_stage)
            eligibility = decide_all_stages(scorecards)
            extend_report_with_stage_eval(report, scorecards, eligibility)
            # Re-write report with v0.2 data
            report.write_to(args.out)
            print(f"  Stages evaluated: {len(scorecards)}")
            for stage, dec in eligibility.items():
                print(f"    {stage}: {dec.eligibility} (score={dec.score:.2f})")
        except Exception as e:
            print(f"  Stage eval failed (non-fatal): {e}")
            logger.warning("Stage eval failed: %s", e, exc_info=True)

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
    if report.stage_eligibility_v2:
        print("Stage eligibility v0.2:")
        for stage, dec in report.stage_eligibility_v2.items():
            if isinstance(dec, dict):
                print(f"    {stage}: {dec.get('eligibility', '?')} ({dec.get('reason', '')[:60]})")
    if report.stage_eval:
        print("Stage scorecards:")
        for stage, card in report.stage_eval.items():
            if isinstance(card, dict):
                print(f"    {stage}: score={card.get('aggregate_score', 0):.2f}, cases={card.get('cases_run', 0)}")
    print(f"Report:                {report.eval_run_id}")
    print("=" * 60)


def _create_provider(manifest: CandidateModelManifest, base_url: str | None) -> object:
    """Create a minimal LLM provider for certification.

    For LM Studio, creates a simple provider that wraps the OpenAI client
    with the LM Studio base URL.
    """
    if manifest.provider == "lmstudio":
        import openai
        url = base_url or "http://localhost:1234/v1"
        client = openai.AsyncOpenAI(
            api_key="lm-studio",
            base_url=url,
        )

        class _LMStudioProvider:
            def __init__(self, client, model_id):
                self._client = client
                self._model_id = model_id
                self.supports_structured_output = True

            @property
            def default_model(self):
                return self._model_id

            async def complete(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.3, **kw):
                # Accept prompt as string (from smoke_test) or messages list
                if isinstance(prompt, str):
                    messages = [{"role": "user", "content": prompt}]
                else:
                    messages = prompt
                resp = await self._client.chat.completions.create(
                    model=self._model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""

            async def structured_complete(
                self,
                prompt: str,
                schema_name: str,
                schema: dict,
                max_tokens: int = 4096,
                temperature: float = 0.3,
            ) -> str:
                """Call LM Studio with response_format json_schema for guaranteed schema compliance."""
                if isinstance(prompt, str):
                    messages = [{"role": "user", "content": prompt}]
                else:
                    messages = prompt
                resp = await self._client.chat.completions.create(
                    model=self._model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": schema,
                            "strict": True,
                        },
                    },
                )
                return resp.choices[0].message.content or ""

        return _LMStudioProvider(client, manifest.model_id)
    else:
        raise ValueError(
            f"CLI provider creation not implemented for '{manifest.provider}'. "
            f"Pass a pre-configured provider to CertificationRunner."
        )


if __name__ == "__main__":
    main()
