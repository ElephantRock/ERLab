"""Boundary contracts for pipeline output validation.

ESAA-inspired declarative contracts that define what constitutes
valid output for each pipeline stage.
"""

from enum import Enum

from pydantic import BaseModel


class OutputVerdict(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class BoundaryContract(BaseModel):
    """Declarative constraints for pipeline outputs."""
    name: str
    constraint_type: str    # "no_harmful_content", "citation_required", "max_length", etc.
    params: dict = {}


class GovernanceCheck(BaseModel):
    contract_name: str
    verdict: OutputVerdict
    reason: str


# Default contracts for research output
DEFAULT_CONTRACTS = [
    BoundaryContract(
        name="no_harmful_content",
        constraint_type="no_harmful_content",
        params={},
    ),
    BoundaryContract(
        name="citation_integrity",
        constraint_type="citation_required",
        params={"max_unsupported_claims": 3},
    ),
    BoundaryContract(
        name="max_output_length",
        constraint_type="max_length",
        params={"max_chars": 50000},
    ),
]
