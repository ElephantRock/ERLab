"""Certification runner — orchestrates the full certification pipeline.

Flow:
    1. Validate manifest
    2. Probe hardware
    3. Run smoke test
    4. If smoke fails → report rejected, write report, return
    5. Run schema eval
    6. Estimate safe context
    7. Apply admission policy
    8. Write report (always — even rejected cases)
    9. If promotion_allowed AND auto_promote → promote with scoped stages
    10. Return report
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.pipeline.model_certification.manifest import CandidateModelManifest
from backend.pipeline.model_certification.hardware_probe import probe_model
from backend.pipeline.model_certification.smoke_test import run_smoke_test
from backend.pipeline.model_certification.schema_eval import run_schema_eval
from backend.pipeline.model_certification.context_stress import estimate_safe_context
from backend.pipeline.model_certification.admission_policy import decide_admission
from backend.pipeline.model_certification.report import CapabilityReport
from backend.pipeline.model_certification.registries import ProductionModelRegistry

logger = logging.getLogger(__name__)

# Default paths
_CONFIG_DIR = Path(__file__).parent / "config"
_SCHEMA_DIR = _CONFIG_DIR / "schemas"
_POLICY_PATH = _CONFIG_DIR / "admission_policy.yaml"
_REPORTS_DIR = Path("data/model_certification/reports")


class CertificationRunner:
    """Orchestrates the certification pipeline for a candidate model."""

    def __init__(
        self,
        provider: Any,
        schema_dir: str | Path | None = None,
        policy_path: str | Path | None = None,
        reports_dir: str | Path | None = None,
        production_registry: ProductionModelRegistry | None = None,
        lmstudio_base_url: str | None = None,
    ) -> None:
        self._provider = provider
        self._schema_dir = Path(schema_dir) if schema_dir else _SCHEMA_DIR
        self._policy_path = Path(policy_path) if policy_path else _POLICY_PATH
        self._reports_dir = Path(reports_dir) if reports_dir else _REPORTS_DIR
        self._production_registry = production_registry
        self._lmstudio_base_url = lmstudio_base_url

    async def certify(
        self,
        manifest: CandidateModelManifest,
        *,
        auto_promote: bool = False,
        cases_per_schema: int = 5,
    ) -> CapabilityReport:
        """Run the full certification pipeline.

        Args:
            manifest: The candidate model manifest.
            auto_promote: If True and model is approved, promote to production registry.
            cases_per_schema: Number of test cases per schema.

        Returns:
            CapabilityReport with results (always written to file).
        """
        logger.info("Certification starting: %s", manifest.model_id)

        # 1. Validate manifest
        errors = manifest.validate()
        if errors:
            logger.error("Invalid manifest: %s", errors)
            report = CapabilityReport(
                model_id=manifest.model_id,
                status="rejected",
                manifest_hash=manifest.content_hash,
                known_failure_modes=[f"Invalid manifest: {'; '.join(errors)}"],
            )
            report.write_to(self._reports_dir)
            return report

        # 2. Probe hardware
        logger.info("Probing hardware: %s", manifest.model_id)
        hardware = await probe_model(
            model_id=manifest.model_id,
            provider=manifest.provider,
            advertised_context_window=manifest.advertised_context_window,
            advertised_max_output_tokens=manifest.advertised_max_output_tokens,
            base_url=self._lmstudio_base_url,
        )

        # 3. Run smoke test
        logger.info("Running smoke test: %s", manifest.model_id)
        smoke = await run_smoke_test(self._provider, manifest.model_id)

        # 4. If smoke fails → rejected report
        if not smoke.passed:
            logger.warning("Smoke test FAILED: %s — stopping", smoke.error)
            context = estimate_safe_context(hardware, manifest.advertised_context_window)
            report = CapabilityReport(
                model_id=manifest.model_id,
                status="rejected",
                safe_context_window=context.safe_tokens,
                safe_output_tokens=hardware.safe_output_tokens or 0,
                hardware=hardware.__dict__,
                smoke_test=smoke.__dict__,
                manifest_hash=manifest.content_hash,
                known_failure_modes=[f"Smoke test failed: {smoke.error}"],
            )
            report.write_to(self._reports_dir)
            return report

        # 5. Run schema eval
        logger.info("Running schema eval: %s", manifest.model_id)
        schema_result = await run_schema_eval(
            self._provider,
            manifest.model_id,
            self._schema_dir,
            supports_json_mode=manifest.supports_json_mode,
            cases_per_schema=cases_per_schema,
        )

        # 6. Estimate safe context
        context = estimate_safe_context(hardware, manifest.advertised_context_window)

        # 7. Apply admission policy
        logger.info("Applying admission policy: %s", manifest.model_id)
        decision = decide_admission(
            smoke_passed=smoke.passed,
            hardware_stable=hardware.stable,
            schema_valid_rate=schema_result.schema_valid_rate,
            valid_json_rate=schema_result.recoverable_json_rate,
            safe_context_window=context.safe_tokens,
            native_json_mode=manifest.supports_json_mode,
        )

        logger.info(
            "Admission decision: %s (promotion_allowed=%s)",
            decision.status.value,
            decision.promotion_allowed,
        )

        # 8. Write report
        report = CapabilityReport(
            model_id=manifest.model_id,
            status=decision.status.value,
            safe_context_window=context.safe_tokens,
            safe_output_tokens=hardware.safe_output_tokens or 0,
            hardware=hardware.__dict__,
            smoke_test=smoke.__dict__,
            schema_eval={
                "total_cases": schema_result.total_cases,
                "raw_json_valid_rate": schema_result.raw_json_valid_rate,
                "recoverable_json_rate": schema_result.recoverable_json_rate,
                "schema_valid_rate": schema_result.schema_valid_rate,
                "schema_valid_after_repair_rate": schema_result.schema_valid_after_repair_rate,
                "repair_attempted_count": schema_result.repair_attempted_count,
                "repair_success_rate": schema_result.repair_success_rate,
                "markdown_contamination_rate": schema_result.markdown_contamination_rate,
                "native_json_mode_support": schema_result.native_json_mode_support,
                "per_schema": schema_result.per_schema,
            },
            stage_eligibility=decision.stage_eligibility,
            promotion_allowed=decision.promotion_allowed,
            scores={
                "schema_valid_rate": schema_result.schema_valid_rate,
                "raw_json_valid_rate": schema_result.raw_json_valid_rate,
                "recoverable_json_rate": schema_result.recoverable_json_rate,
                "repair_success_rate": schema_result.repair_success_rate,
                "safe_context_tokens": context.safe_tokens,
            },
            known_failure_modes=_collect_failure_modes(smoke, schema_result, hardware),
            router_recommendation={
                "context_confidence": context.confidence,
                "preferred_tasks": _infer_preferred_tasks(decision),
            },
            manifest_hash=manifest.content_hash,
            schema_versions=_get_schema_versions(self._schema_dir),
        )

        report_path = report.write_to(self._reports_dir)
        logger.info("Report written: %s", report_path)

        # 9. Promote if applicable
        if auto_promote and decision.promotion_allowed and self._production_registry:
            try:
                self._production_registry.promote(
                    model_id=manifest.model_id,
                    status=decision.status.value,
                    stage_eligibility=decision.stage_eligibility,
                    promotion_allowed=decision.promotion_allowed,
                    report_path=str(report_path),
                )
                logger.info("Promoted to production: %s", manifest.model_id)
            except Exception as e:
                logger.warning("Promotion failed: %s", e)

        return report


def _collect_failure_modes(
    smoke: Any,
    schema_result: Any,
    hardware: Any,
) -> list[str]:
    """Collect known failure modes from sub-results."""
    modes = []
    if not smoke.passed:
        modes.append(f"Smoke test: {smoke.error}")
    if schema_result.truncation_rate > 0.1:
        modes.append(f"High truncation rate: {schema_result.truncation_rate:.0%}")
    if schema_result.markdown_contamination_rate > 0.5:
        modes.append("Frequent markdown contamination in JSON output")
    if hardware.warnings:
        modes.extend(hardware.warnings[:3])  # cap at 3
    return modes


def _infer_preferred_tasks(decision: Any) -> list[str]:
    """Infer preferred tasks from stage eligibility."""
    eligible = [
        stage for stage, status in decision.stage_eligibility.items()
        if status in ("approved", "limited")
    ]
    return eligible[:5]  # cap at 5


def _get_schema_versions(schema_dir: Path) -> dict[str, str]:
    """Read version info from schema files (currently all "1.0")."""
    versions = {}
    for f in schema_dir.glob("*.schema.json"):
        name = f.stem.replace(".schema", "")
        versions[name] = "1.0"
    return versions
