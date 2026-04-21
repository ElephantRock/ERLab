"""Pydantic model for encrypted secrets."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from backend.providers.secrets.crypto import CryptoUtils


class Secret(BaseModel):
    """Encrypted secret with metadata. Immutable — rotation creates a new instance."""

    key: str
    encrypted_value: str
    provider: str
    created_at: datetime = datetime.now(timezone.utc)
    rotated_at: datetime | None = None

    model_config = {"frozen": True}

    def decrypt(self, master_password: str) -> str:
        return CryptoUtils.decrypt(self.encrypted_value, master_password)

    def rotate(self, new_api_key: str, master_password: str) -> Secret:
        encrypted = CryptoUtils.encrypt(new_api_key, master_password)
        return Secret(
            key=self.key,
            encrypted_value=encrypted,
            provider=self.provider,
            created_at=self.created_at,
            rotated_at=datetime.now(timezone.utc),
        )
