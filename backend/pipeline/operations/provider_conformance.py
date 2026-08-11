"""Provider conformance layer — validates LLM responses against the receipt contract.

This module sits between the provider wrappers and the operation executor.
It inspects every model-backed response and either:
1. Constructs a ModelReceipt from the response, or
2. Raises a typed error (MissingModelReceiptError, WrongModelServedError)

The conformance unit is ModelReceipt, not the served_model field on
LLMResponse. The served_model field is a compatibility mechanism that
allows receipt construction during migration. Once all providers
natively return receipts, this layer will simplify.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.pipeline.operations.types import (
    MissingModelReceiptError,
    ModelReceipt,
    WrongModelServedError,
)
from backend.providers.base import LLMResponse

logger = logging.getLogger(__name__)


def build_receipt_from_response(
    response: LLMResponse,
    requested_model: str,
    provider_name: str,
    endpoint: str,
) -> ModelReceipt:
    """Construct a ModelReceipt from an LLMResponse.

    Raises:
        MissingModelReceiptError: If served_model is not present on the response.
        WrongModelServedError: If served_model differs from requested_model.

    Note:
        ``served_model`` on ``LLMResponse`` is a compatibility field.
        The real conformance unit is ``ModelReceipt`` itself.
    """
    if response.served_model is None:
        raise MissingModelReceiptError(
            f"Provider '{provider_name}' returned no served_model for a call "
            f"requesting '{requested_model}'. The response cannot be verified."
        )

    if response.served_model != requested_model:
        raise WrongModelServedError(requested_model, response.served_model)

    return ModelReceipt(
        requested_model=requested_model,
        served_model=response.served_model,
        provider=provider_name,
        endpoint=endpoint,
        timestamp=datetime.now(UTC).isoformat(),
    )


def build_receipt_from_provider(
    provider,
    endpoint: str = "",
) -> ModelReceipt:
    """Construct a ModelReceipt from a provider's default_model.

    This is used for providers whose complete() returns raw strings
    (not LLMResponse). The provider's default_model property is the
    authoritative model identifier.

    Args:
        provider: An LLMProvider instance with default_model and provider_name.
        endpoint: The endpoint URL (optional, for logging).
    """
    model = getattr(provider, "default_model", "unknown")
    provider_name = getattr(provider, "provider_name", "unknown")
    return ModelReceipt(
        requested_model=model,
        served_model=model,
        provider=provider_name,
        endpoint=endpoint,
        timestamp=datetime.now(UTC).isoformat(),
    )
