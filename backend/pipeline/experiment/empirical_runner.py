"""Phase 5 — empirical experiment runner.

Executes a checked-in analysis entrypoint with a registered dataset, captures
structured results (metrics.json), validates the schema, hashes artifacts, and
builds an ExperimentManifest. Does NOT generate code via LLM — the analysis
script is predeclared and frozen.

States:
  not_requested     — no spec provided
  pending           — spec loaded, execution queued
  succeeded         — exit 0 + valid metrics.json
  failed            — nonzero exit code
  invalid_results   — exit 0 but metrics missing/malformed/non-finite
  reproduction_failed — independent reproduction mismatch
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from backend.pipeline.experiment.dataset_registry import load_dataset
from backend.pipeline.experiment.manifest import (
    AnalysisSpec,
    DatasetIdentity,
    EnvironmentRecord,
    ExperimentManifest,
    ResultArtifact,
    SplitSpec,
    compute_sha256,
)
from backend.pipeline.experiment.specification import ExperimentSpec, load_spec

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_entrypoint_securely(
    declared_entrypoint: str,
    expected_code_sha256: str = "",
) -> tuple[Path, str] | tuple[None, str]:
    """Resolve a declared analysis entrypoint through the project root with
    registered-path security validation (Phase 8 / D1).

    Returns (resolved_path, code_snapshot) on success, or (None, error_reason)
    on failure. Rejects:
      * absolute entrypoints
      * ``..`` traversal that escapes the project root
      * symlink escape
      * missing files
      * code-hash mismatch (when expected_code_sha256 is provided)

    The path is resolved canonically (``resolve()`` dereferences symlinks)
    and then checked for containment within ``_PROJECT_ROOT``.
    """
    ep = Path(declared_entrypoint)

    # Reject absolute entrypoints — they must be project-relative.
    if ep.is_absolute():
        return None, f"Entrypoint is absolute (not project-relative): {declared_entrypoint}"

    resolved = (_PROJECT_ROOT / ep).resolve()

    # Containment check: resolved path must be inside _PROJECT_ROOT.
    try:
        resolved.relative_to(_PROJECT_ROOT)
    except ValueError:
        return None, f"Entrypoint escapes project root: {declared_entrypoint} → {resolved}"

    # File must exist.
    if not resolved.exists():
        return None, f"Entrypoint file not found: {resolved}"

    code_snapshot = resolved.read_text()

    # Code-hash verification (when the frozen spec declares a hash).
    if expected_code_sha256:
        actual_hash = compute_sha256(resolved)
        if actual_hash != expected_code_sha256:
            return None, (
                f"Entrypoint code hash mismatch: expected {expected_code_sha256[:16]}..., "
                f"got {actual_hash[:16]}..."
            )

    return resolved, code_snapshot



async def execute_experiment(
    spec_id: str,
    output_dir: Path,
    timeout_seconds: float = 120.0,
) -> tuple[ExperimentManifest, str, str, int, float]:
    """Execute a registered experiment specification.

    Returns (manifest, stdout, stderr, exit_code, execution_time_seconds).
    The manifest.status reflects the execution outcome.

    This is the legacy public entry point: it accepts a registered
    ``spec_id`` string, loads it from disk, and delegates to
    ``execute_experiment_spec``. Callers that already hold an
    ``ExperimentSpec`` object should call ``execute_experiment_spec``
    directly to avoid the registration requirement.
    """
    spec = load_spec(spec_id)
    return await execute_experiment_spec(spec, output_dir, timeout_seconds)


async def execute_experiment_spec(
    spec: ExperimentSpec,
    output_dir: Path,
    timeout_seconds: float = 120.0,
) -> tuple[ExperimentManifest, str, str, int, float]:
    """Execute an experiment from a pre-loaded ``ExperimentSpec``.

    Returns (manifest, stdout, stderr, exit_code, execution_time_seconds).
    The manifest.status reflects the execution outcome.

    This function is the trusted execution body. It does NOT require
    the spec to be registered in ``data/datasets/`` — it operates on
    the in-memory ``ExperimentSpec`` object directly. The spec must
    reference a registered dataset (by name) and a checked-in analysis
    entrypoint (by project-relative path).
    """
    # Load and verify dataset
    try:
        dataset_identity, dataset_path = load_dataset(spec.dataset_name)
    except (FileNotFoundError, ValueError) as e:
        manifest = ExperimentManifest(
            experiment_spec_id=spec.spec_id,
            status="failed",
            analysis=AnalysisSpec(
                entrypoint=spec.analysis_entrypoint,
                code_sha256="",
                command="",
                method=spec.analysis_method,
                declared_metrics=spec.declared_metrics,
            ),
        )
        return manifest, "", str(e), 1, 0.0

    # Resolve the checked-in analysis entrypoint
    entrypoint_path = _PROJECT_ROOT / spec.analysis_entrypoint
    if not entrypoint_path.exists():
        manifest = ExperimentManifest(
            experiment_spec_id=spec.spec_id,
            status="failed",
        )
        return manifest, "", f"Entrypoint not found: {entrypoint_path}", 1, 0.0

    code_sha256 = compute_sha256(entrypoint_path)
    command = f"python {spec.analysis_entrypoint} --input {dataset_path} --output {output_dir}"

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Execute the analysis script in a subprocess
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(entrypoint_path),
            "--input", str(dataset_path),
            "--output", str(output_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
        exit_code = proc.returncode or 0
    except TimeoutError:
        proc.kill()
        await proc.wait()
        elapsed = time.monotonic() - t0
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "failed", f"Execution timed out after {timeout_seconds}s"
        )
        return manifest, "", f"Timed out after {timeout_seconds}s", -1, elapsed
    except Exception as e:
        elapsed = time.monotonic() - t0
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "failed", str(e)
        )
        return manifest, "", str(e), 1, elapsed

    elapsed = time.monotonic() - t0
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    # Nonzero exit = failed
    if exit_code != 0:
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "failed", f"Exit code {exit_code}"
        )
        return manifest, stdout, stderr, exit_code, elapsed

    # Exit 0: validate metrics.json
    metrics_path = output_dir / "metrics.json"
    if not metrics_path.exists():
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "invalid_results", "metrics.json not found after execution"
        )
        return manifest, stdout, stderr, exit_code, elapsed

    try:
        with open(metrics_path) as f:
            metrics_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "invalid_results", f"metrics.json parse error: {e}"
        )
        return manifest, stdout, stderr, exit_code, elapsed

    # Validate metrics schema
    metrics = metrics_data.get("metrics", {})
    declared = set(spec.declared_metrics)
    observed = set(metrics.keys())
    missing = declared - observed
    if missing:
        manifest = _build_manifest(
            spec, dataset_identity, entrypoint_path, code_sha256, command,
            {}, [], "invalid_results", f"Missing declared metrics: {missing}"
        )
        return manifest, stdout, stderr, exit_code, elapsed

    # Validate all metric values are finite
    for name, val in metrics.items():
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            manifest = _build_manifest(
                spec, dataset_identity, entrypoint_path, code_sha256, command,
                {}, [], "invalid_results", f"Metric {name} is non-finite: {val}"
            )
            return manifest, stdout, stderr, exit_code, elapsed

    # Hash all output artifacts
    result_artifacts: list[ResultArtifact] = []
    for artifact_name in spec.output_artifacts:
        artifact_path = output_dir / artifact_name
        if artifact_path.exists():
            artifact_sha = compute_sha256(artifact_path)
            artifact_type = "metrics" if artifact_name == "metrics.json" else \
                           "predictions" if "prediction" in artifact_name else \
                           "feature_importance" if "importance" in artifact_name else \
                           "table" if "table" in artifact_name else "figure"
            result_artifacts.append(ResultArtifact(
                filename=artifact_name,
                sha256=artifact_sha,
                artifact_type=artifact_type,
            ))

    # Build the manifest
    manifest = _build_manifest(
        spec, dataset_identity, entrypoint_path, code_sha256, command,
        metrics, result_artifacts, "succeeded", ""
    )
    return manifest, stdout, stderr, exit_code, elapsed


def _build_manifest(
    spec: ExperimentSpec,
    dataset_identity: DatasetIdentity,
    entrypoint_path: Path,
    code_sha256: str,
    command: str,
    metrics: dict[str, float],
    artifacts: list[ResultArtifact],
    status: str,
    error: str,
) -> ExperimentManifest:
    """Build a complete manifest from the spec and execution results."""
    return ExperimentManifest(
        schema_version="1",
        experiment_spec_id=spec.spec_id,
        dataset=dataset_identity,
        split=SplitSpec(
            method=spec.split_method,
            train_fraction=spec.train_fraction,
            test_fraction=spec.test_fraction,
            random_seed=spec.random_seed,
        ),
        analysis=AnalysisSpec(
            entrypoint=spec.analysis_entrypoint,
            code_sha256=code_sha256,
            command=command,
            method=spec.analysis_method,
            declared_metrics=spec.declared_metrics,
        ),
        environment=EnvironmentRecord(
            python_version=sys.version.split()[0],
            platform=platform.platform(),
        ),
        configuration={
            "random_seed": spec.random_seed,
            "tolerances": spec.tolerances,
        },
        results=metrics,
        result_artifacts=artifacts,
        observed_at=datetime.now(UTC).isoformat(),
        reproduction={"declared_tolerances": spec.tolerances},
        status=status,
    )
