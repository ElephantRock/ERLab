"""Capability authorization errors (P0.4A1.6).

Bounded error codes for capability authorization failures.
"""

from __future__ import annotations


CAPABILITY_CHECK_NOT_FOUND = "capability_check_not_found"
CAPABILITY_CHECK_EXPIRED = "capability_check_expired"
CAPABILITY_CHECK_FAILED = "capability_check_failed"
CAPABILITY_CHECK_ABANDONED = "capability_check_abandoned"
CAPABILITY_RUNTIME_DRIFT = "capability_runtime_drift"
CAPABILITY_BINDING_MISMATCH = "capability_binding_mismatch"
CAPABILITY_AUTHORITY_REVOKED_AT_USE = "capability_authority_revoked_at_use"

BOUNDED_CAPABILITY_ERROR_CODES = frozenset({
    CAPABILITY_CHECK_NOT_FOUND,
    CAPABILITY_CHECK_EXPIRED,
    CAPABILITY_CHECK_FAILED,
    CAPABILITY_CHECK_ABANDONED,
    CAPABILITY_RUNTIME_DRIFT,
    CAPABILITY_BINDING_MISMATCH,
    CAPABILITY_AUTHORITY_REVOKED_AT_USE,
})


class CapabilityAuthorizationError(Exception):
    """Bounded capability authorization failure.

    Raised when a governed embedding operation cannot proceed because
    the capability check does not prove the resolved runtime matches
    the declared contract.
    """

    def __init__(self, code: str, detail: str):
        if code not in BOUNDED_CAPABILITY_ERROR_CODES:
            raise ValueError(f"unbounded capability error code: {code!r}")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
