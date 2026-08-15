"""Phase 5 — dataset registry: load and verify registered datasets.

A registered dataset has a dataset_meta.json with name, version, source,
license, raw_filename, and raw_sha256. The registry verifies the hash at
load time and returns a DatasetIdentity for the manifest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.experiment.manifest import DatasetIdentity, compute_sha256

_DATASETS_DIR = Path(__file__).resolve().parents[3] / "data" / "datasets"


@dataclass(frozen=True)
class DatasetMetadata:
    """Validated metadata for a registered dataset.

    Extends ``DatasetIdentity`` with task-relevant fields (target,
    classes, features) needed by the SpecDesigner.
    """

    name: str
    version: str
    raw_filename: str
    raw_sha256: str
    task_type: str          # "classification" | "regression"
    target: str             # prediction target column name
    classes: list[str]      # empty for regression
    n_features: int
    features: list[str]
    n_rows: int

    @property
    def is_classification(self) -> bool:
        return self.task_type == "classification"


def load_dataset(
    name: str, datasets_dir: Path | None = None,
) -> tuple[DatasetIdentity, Path]:
    """Load a registered dataset by name.

    Returns (identity, absolute_path_to_raw_file).
    Raises FileNotFoundError if the dataset or its meta file is missing.
    Raises ValueError if the hash does not match.
    """
    base = datasets_dir or _DATASETS_DIR
    dataset_dir = base / name
    meta_path = dataset_dir / "dataset_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Dataset '{name}' not found: {meta_path} does not exist",
        )

    with open(meta_path) as f:
        meta = json.load(f)

    raw_path = dataset_dir / meta["raw_filename"]
    if not raw_path.exists():
        raise FileNotFoundError(f"Dataset raw file missing: {raw_path}")

    actual_sha256 = compute_sha256(raw_path)
    expected_sha256 = meta["raw_sha256"]
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Dataset hash mismatch for {name}/{meta['raw_filename']}: "
            f"expected {expected_sha256}, got {actual_sha256}",
        )

    identity = DatasetIdentity(
        name=meta["name"],
        version=meta["version"],
        source=meta.get("source", ""),
        license=meta.get("license", ""),
        relative_path=f"data/datasets/{name}/{meta['raw_filename']}",
        raw_sha256=actual_sha256,
    )
    return identity, raw_path


def load_dataset_metadata(
    name: str, datasets_dir: Path | None = None,
) -> DatasetMetadata:
    """Load validated metadata for a registered dataset.

    Returns a ``DatasetMetadata`` with task-relevant fields derived
    from ``dataset_meta.json``. Verifies the raw file hash.

    Raises FileNotFoundError if dataset or meta is missing.
    Raises ValueError on hash mismatch or malformed metadata.
    """
    base = datasets_dir or _DATASETS_DIR
    dataset_dir = base / name
    meta_path = dataset_dir / "dataset_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Dataset '{name}' not found: {meta_path} does not exist",
        )

    with open(meta_path) as f:
        meta = json.load(f)

    raw_path = dataset_dir / meta["raw_filename"]
    if not raw_path.exists():
        raise FileNotFoundError(f"Dataset raw file missing: {raw_path}")

    actual_sha256 = compute_sha256(raw_path)
    expected_sha256 = meta["raw_sha256"]
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Dataset hash mismatch for {name}/{meta['raw_filename']}: "
            f"expected {expected_sha256}, got {actual_sha256}",
        )

    classes = meta.get("classes") or []
    task_type = "classification" if classes else "regression"
    target = (
        meta.get("target")
        or meta.get("transformed_target")
        or meta.get("original_target")
        or ""
    )
    if not target:
        raise ValueError(
            f"Dataset '{name}' metadata missing 'target' field",
        )

    return DatasetMetadata(
        name=meta["name"],
        version=meta["version"],
        raw_filename=meta["raw_filename"],
        raw_sha256=actual_sha256,
        task_type=task_type,
        target=target,
        classes=classes,
        n_features=meta.get("n_features", 0),
        features=meta.get("features", []),
        n_rows=meta.get("n_rows", 0),
    )


def list_registered_datasets(
    datasets_dir: Path | None = None,
) -> list[str]:
    """Return sorted names of all registered datasets."""
    base = datasets_dir or _DATASETS_DIR
    if not base.exists():
        return []
    return sorted(
        d.name
        for d in base.iterdir()
        if d.is_dir() and (d / "dataset_meta.json").exists()
    )
