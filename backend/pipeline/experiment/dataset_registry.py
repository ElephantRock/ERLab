"""Phase 5 — dataset registry: load and verify registered datasets.

A registered dataset has a dataset_meta.json with name, version, source,
license, raw_filename, and raw_sha256. The registry verifies the hash at
load time and returns a DatasetIdentity for the manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.pipeline.experiment.manifest import DatasetIdentity, compute_sha256

_DATASETS_DIR = Path(__file__).resolve().parents[3] / "data" / "datasets"


def load_dataset(name: str, datasets_dir: Path | None = None) -> tuple[DatasetIdentity, Path]:
    """Load a registered dataset by name.

    Returns (identity, absolute_path_to_raw_file).
    Raises FileNotFoundError if the dataset or its meta file is missing.
    Raises ValueError if the hash does not match.
    """
    base = datasets_dir or _DATASETS_DIR
    dataset_dir = base / name
    meta_path = dataset_dir / "dataset_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Dataset '{name}' not found: {meta_path} does not exist")

    with open(meta_path) as f:
        meta = json.load(f)

    raw_path = dataset_dir / meta["raw_filename"]
    if not raw_path.exists():
        raise FileNotFoundError(f"Dataset raw file missing: {raw_path}")

    # Verify hash
    actual_sha256 = compute_sha256(raw_path)
    expected_sha256 = meta["raw_sha256"]
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Dataset hash mismatch for {name}/{meta['raw_filename']}: "
            f"expected {expected_sha256}, got {actual_sha256}"
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
