"""Multi-key vault with per-provider rotation and health tracking.

Adapted from Frona's credential vault pattern. Stores multiple encrypted API
keys per provider and supports automatic rotation on auth failures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.providers.secrets.crypto import CryptoUtils
from backend.providers.secrets.errors import AllKeysUnhealthyError
from backend.providers.secrets.secret_model import Secret

logger = logging.getLogger(__name__)


class KeyVault:
    """Multi-key vault with per-provider rotation and health tracking."""

    def __init__(
        self,
        master_password: str,
        persist_path: str = "./data/secrets/vault.json",
    ) -> None:
        self._master_password = master_password
        self._persist_path = Path(persist_path)
        # provider -> list of Secret instances
        self._keys: dict[str, list[Secret]] = {}
        # provider -> index of active key
        self._active_index: dict[str, int] = {}
        # provider -> set of unhealthy key hashes (last 8 chars of encrypted value)
        self._unhealthy: dict[str, set[str]] = {}

    def add_key(self, provider: str, api_key: str) -> None:
        encrypted = CryptoUtils.encrypt(api_key, self._master_password)
        secret = Secret(
            key=f"{provider}_api_key",
            encrypted_value=encrypted,
            provider=provider,
        )
        if provider not in self._keys:
            self._keys[provider] = []
            self._active_index[provider] = 0
        self._keys[provider].append(secret)

    def get_active_key(self, provider: str) -> str | None:
        keys = self._keys.get(provider, [])
        if not keys:
            return None
        idx = self._active_index.get(provider, 0)
        if idx >= len(keys):
            return None
        secret = keys[idx]
        return secret.decrypt(self._master_password)

    def _hint(self, secret: Secret) -> str:
        return secret.encrypted_value[-8:]

    async def rotate_key(self, provider: str) -> str:
        """Advance to next healthy key. Raises AllKeysUnhealthyError if none left."""
        keys = self._keys.get(provider, [])
        if not keys:
            raise AllKeysUnhealthyError(f"No keys registered for provider '{provider}'")

        current_idx = self._active_index.get(provider, 0)
        unhealthy = self._unhealthy.get(provider, set())

        # Mark current key as unhealthy
        if current_idx < len(keys):
            unhealthy.add(self._hint(keys[current_idx]))
            self._unhealthy[provider] = unhealthy

        # Find next healthy key
        for offset in range(1, len(keys) + 1):
            candidate = (current_idx + offset) % len(keys)
            if self._hint(keys[candidate]) not in unhealthy:
                self._active_index[provider] = candidate
                key = keys[candidate].decrypt(self._master_password)
                logger.info(
                    "Rotated '%s' from key %d to %d",
                    provider, current_idx, candidate,
                )
                self.persist()
                return key

        raise AllKeysUnhealthyError(
            f"All keys unhealthy for provider '{provider}'"
        )

    def mark_key_unhealthy(self, provider: str, key_hint: str) -> None:
        unhealthy = self._unhealthy.setdefault(provider, set())
        unhealthy.add(key_hint[-8:])

    def load(self) -> None:
        if not self._persist_path.exists():
            return
        with open(self._persist_path, encoding="utf-8") as f:
            data = json.load(f)
        for provider, key_list in data.get("keys", {}).items():
            self._keys[provider] = [Secret(**s) for s in key_list]
        self._active_index = data.get("active_index", {})
        self._unhealthy = {
            p: set(h) for p, h in data.get("unhealthy", {}).items()
        }

    def persist(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "keys": {
                p: [s.model_dump(mode="json") for s in secrets]
                for p, secrets in self._keys.items()
            },
            "active_index": self._active_index,
            "unhealthy": {p: list(h) for p, h in self._unhealthy.items()},
        }
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    @property
    def provider_names(self) -> list[str]:
        return list(self._keys.keys())

    def key_count(self, provider: str) -> int:
        return len(self._keys.get(provider, []))
