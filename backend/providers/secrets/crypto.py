"""AES-256-GCM encryption with PBKDF2 key derivation.

Adapted from Letta's crypto_utils.py. Uses the cryptography library for
AES-256-GCM authenticated encryption with PBKDF2-HMAC-SHA256 key derivation.
"""

from __future__ import annotations

import base64
import functools
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_SALT_SIZE = 16
_NONCE_SIZE = 12
_KDF_ITERATIONS = 100_000


@functools.lru_cache(maxsize=4)
def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


class CryptoUtils:
    """AES-256-GCM encryption utilities."""

    @staticmethod
    def encrypt(plaintext: str, password: str) -> str:
        salt = os.urandom(_SALT_SIZE)
        nonce = os.urandom(_NONCE_SIZE)
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Format: base64(salt + nonce + ciphertext) — ciphertext includes auth tag
        return base64.b64encode(salt + nonce + ciphertext).decode("ascii")

    @staticmethod
    def decrypt(token: str, password: str) -> str:
        raw = base64.b64decode(token)
        salt = raw[:_SALT_SIZE]
        nonce = raw[_SALT_SIZE : _SALT_SIZE + _NONCE_SIZE]
        ciphertext = raw[_SALT_SIZE + _NONCE_SIZE :]
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
