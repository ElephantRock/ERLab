"""Two-registry model management.

CandidateModelRegistry — may contain untested models.
ProductionModelRegistry — may only contain admitted models with explicit stage eligibility.

Hard invariant:
    Production registry may only contain models with explicit stage eligibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from backend.pipeline.model_certification.manifest import CandidateModelManifest

logger = logging.getLogger(__name__)


class PromotionDenied(Exception):
    """Raised when attempting to promote a non-admissible report."""


class CandidateModelRegistry:
    """Registry for candidate (untested) models.

    May contain models with any status. Backed by a YAML file.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._candidates: dict[str, CandidateModelManifest] = {}
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        """Load candidates from backing file."""
        data = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        for model_id, manifest_data in data.get("candidates", {}).items():
            if isinstance(manifest_data, dict):
                self._candidates[model_id] = CandidateModelManifest(
                    **{k: v for k, v in manifest_data.items()
                       if k in CandidateModelManifest.__dataclass_fields__}
                )

    def _save(self) -> None:
        """Persist candidates to backing file."""
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "candidates": {
                mid: m.to_dict() for mid, m in self._candidates.items()
            }
        }
        self._path.write_text(
            yaml.dump(payload, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def add(self, manifest: CandidateModelManifest) -> None:
        """Add a candidate manifest to the registry."""
        errors = manifest.validate()
        if errors:
            raise ValueError(f"Invalid manifest: {'; '.join(errors)}")
        self._candidates[manifest.model_id] = manifest
        self._save()
        logger.info("Added candidate: %s", manifest.model_id)

    def get(self, model_id: str) -> CandidateModelManifest | None:
        """Get a candidate by model_id."""
        return self._candidates.get(model_id)

    def list_candidates(self) -> list[CandidateModelManifest]:
        """List all candidates."""
        return list(self._candidates.values())

    def remove(self, model_id: str) -> bool:
        """Remove a candidate. Returns True if found and removed."""
        if model_id in self._candidates:
            del self._candidates[model_id]
            self._save()
            return True
        return False


class ProductionModelRegistry:
    """Registry for admitted production models.

    Hard invariant: may only contain models with explicit stage eligibility.
    Promotion is stage-scoped based on admission status.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._models: dict[str, dict[str, Any]] = {}
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        """Load production models from backing file."""
        data = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        self._models = data.get("models", {})

    def _save(self) -> None:
        """Persist production models to backing file."""
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"models": self._models}
        self._path.write_text(
            yaml.dump(payload, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def promote(
        self,
        model_id: str,
        status: str,
        stage_eligibility: dict[str, str],
        promotion_allowed: bool,
        report_path: str | None = None,
    ) -> None:
        """Promote a model to the production registry with scoped stages.

        Args:
            model_id: The model to promote.
            status: Admission status string.
            stage_eligibility: Stage → eligibility mapping from the report.
            promotion_allowed: Explicit promotion permission from admission decision.
            report_path: Path to the capability report.

        Raises:
            PromotionDenied: If promotion is not allowed or status is non-admissible.
        """
        if not promotion_allowed:
            raise PromotionDenied(
                f"Promotion denied for {model_id}: promotion_allowed=False "
                f"(status={status})"
            )

        _NON_PROMOTABLE = {"rejected", "requires_manual_review"}
        if status.lower() in _NON_PROMOTABLE:
            raise PromotionDenied(
                f"Promotion denied for {model_id}: status '{status}' is not promotable"
            )

        # Filter to only eligible stages (not "not_approved" or "blocked")
        eligible = {
            stage: eligibility
            for stage, eligibility in stage_eligibility.items()
            if eligibility not in ("not_approved", "blocked")
        }

        if not eligible:
            raise PromotionDenied(
                f"Promotion denied for {model_id}: no promotable stages "
                f"(all stages are not_approved or blocked)"
            )

        entry = {
            "model_id": model_id,
            "status": status,
            "allowed_stages": eligible,
            "report_path": report_path,
        }
        self._models[model_id] = entry
        self._save()
        logger.info(
            "Promoted %s (%s) with stages: %s",
            model_id, status, list(eligible.keys()),
        )

    def get_allowed_models(self, stage: str | None = None) -> list[dict[str, Any]]:
        """Get models allowed for production use.

        Args:
            stage: If set, filter to models allowed for this specific stage.

        Returns:
            List of model entries with allowed stages.
        """
        if stage is None:
            return list(self._models.values())

        results = []
        for entry in self._models.values():
            allowed = entry.get("allowed_stages", {})
            if stage in allowed:
                results.append(entry)
        return results

    def get(self, model_id: str) -> dict[str, Any] | None:
        """Get a production model entry."""
        return self._models.get(model_id)

    def list_models(self) -> list[dict[str, Any]]:
        """List all production models."""
        return list(self._models.values())

    def remove(self, model_id: str) -> bool:
        """Remove a model from production registry."""
        if model_id in self._models:
            del self._models[model_id]
            self._save()
            return True
        return False
