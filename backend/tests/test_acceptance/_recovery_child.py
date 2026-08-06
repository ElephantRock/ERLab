"""Child-process entry point for fresh-process recovery verification.

Invoked by the parent test via subprocess.run with two arguments:
  [1] database_url  — the isolated SQLite URL
  [2] run_id        — the run_id_str to recover

Imports ERLab afresh, connects to the database with a NEW engine, loads
the run through production read APIs, and prints a JSON recovery record
on stdout. Exits nonzero on any missing or inconsistent artifact.

This module is NOT collected by pytest (no test_ prefix on functions);
it is an executable child script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: db_url run_id"}))
        return 2
    database_url = sys.argv[1]
    run_id = sys.argv[2]

    # Ensure the repository root is importable in this fresh process.
    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Import ERLab afresh in this child process.
    from backend.acceptance.recovery import recover_run

    record = recover_run(database_url, run_id)
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
    return 0 if record.paper_recovered else 1


if __name__ == "__main__":
    sys.exit(main())
