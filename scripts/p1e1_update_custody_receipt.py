"""P1E.1.3g-h — Update the custody receipt with completed transfer status.

Does NOT regenerate the blind package or map (those are immutable). Reads the
existing receipt, adds transfer-acceptance fields, and rewrites it.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.p1e1_canon import canonical_json, canonical_json_hash

RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "p1e1_reconciliation_map_custody_receipt.json"
CUSTODIAN_MAP = Path("C:/Next-Era-Erlab-Custody/p1e1_reconciliation_map.json")


def main() -> int:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    # verify the custodian map matches the receipt's recorded SHA
    custodian_map = json.loads(CUSTODIAN_MAP.read_text(encoding="utf-8"))
    custodian_sha = canonical_json_hash(custodian_map)
    assert custodian_sha == receipt["reconciliation_map_sha256"], "custodian map SHA mismatch"

    # add transfer-acceptance fields
    receipt["transfer_status"] = "accepted"
    receipt["accepted_at"] = datetime.now(timezone.utc).isoformat()
    receipt["accepting_role"] = "P1E.2 Reconciliation Custodian"
    receipt["transferred_map_sha256"] = custodian_sha
    receipt["transferred_map_location"] = str(CUSTODIAN_MAP) + " (outside repo + adjudicator workspace)"
    receipt["local_construction_copy_disposition"] = "deleted after transfer"
    receipt["local_copy_removed"] = True
    receipt["map_in_git_index_history"] = False
    receipt["map_in_adjudicator_workspace"] = False
    receipt["operational_blinding_status"] = "operationally blinded: map transferred to custodian outside " \
                                              "the repo and adjudicator workspace; construction copy deleted"

    RECEIPT_PATH.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    print(f"updated {RECEIPT_PATH}")
    print(f"  transfer_status: {receipt['transfer_status']}")
    print(f"  accepted_at: {receipt['accepted_at']}")
    print(f"  transferred_map_sha256: {receipt['transferred_map_sha256']}")
    print(f"  local_copy_removed: {receipt['local_copy_removed']}")
    print(f"  operational_blinding: {receipt['operational_blinding_status'][:60]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
