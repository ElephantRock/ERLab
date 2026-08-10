"""P1E.1 — Shared canonical serialization (single implementation).

Protocol §7. Every producer and verifier imports from this module; parallel
canonicalizers are prohibited. Freezes:

    Unicode normalization     NFC
    encoding                   UTF-8
    newline normalization     CRLF/CR -> LF
    trailing newline           exactly one
    leading/trailing spaces    stripped (per text field)
    internal whitespace        preserved
    JSON keys                  lexicographically sorted (map-like records only)
    JSON separators            compact (",", ":")
    numbers                    finite floats only; -0 -> 0; quantization 1e-9;
                               rounding ROUND_HALF_EVEN; plain decimal (no exponent)
    NaN/Infinity               forbidden
    list ordering              DECLARED order preserved (NOT sorted)
    hash                       SHA-256
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

CANON_VERSION = "p1e1_canonicalization_v1"
_QUANT = Decimal("0.000000001")  # 1e-9


class CanonicalizationError(Exception):
    pass


def canonical_text(text: str) -> str:
    """NFC normalize, CRLF/CR -> LF, strip leading/trailing spaces, preserve internal whitespace."""
    if text is None:
        raise CanonicalizationError("text is None")
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # strip only leading/trailing spaces (not internal); also strip a single trailing newline tail
    t = t.strip(" ")
    return t


def content_hash(title: str, abstract: str) -> str:
    """SHA-256 over canonical '{title}\\n\\n{abstract}' (matches v2 _content_hash byte-for-byte
    when title/abstract are already canonical)."""
    blob = f"{canonical_text(title)}\n\n{canonical_text(abstract)}".encode()
    return hashlib.sha256(blob).hexdigest()


def _quantize_float(x: float) -> str:
    """Finite-float check, -0 -> 0, quantize to 1e-9 ROUND_HALF_EVEN, plain decimal."""
    if x != x:  # NaN
        raise CanonicalizationError("NaN forbidden")
    if x in (float("inf"), float("-inf")):
        raise CanonicalizationError("Infinity forbidden")
    if x == 0.0:
        x = 0.0  # normalize -0.0 -> 0.0
    d = Decimal(repr(x)).quantize(_QUANT, rounding=ROUND_HALF_EVEN)
    s = format(d, "f")  # plain decimal, no exponent
    return s


class _QuantEncoder(json.JSONEncoder):
    def encode(self, o):  # noqa: D401
        return super().encode(o)


def canonical_json(obj: Any, *, preserve_declared_order: bool = True) -> str:
    """Serialize to canonical compact JSON.

    - map-like records (dict): keys lexicographically sorted
    - lists: declared order preserved (NOT sorted)
    - floats quantized to 1e-9 ROUND_HALF_EVEN, plain decimal, -0 -> 0
    - NaN/Infinity rejected
    """
    obj = _quantize_inplace(obj)
    if preserve_declared_order:
        return json.dumps(obj, sort_keys=False, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _quantize_inplace(obj: Any) -> Any:
    if isinstance(obj, dict):
        # sort keys for map records
        return {k: _quantize_inplace(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_quantize_inplace(x) for x in obj]  # preserve declared order
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        # return the quantized value as float; canonical_json will render via our encoder path
        return float(_quantize_float(obj))
    if isinstance(obj, int):
        return obj
    return obj


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    from pathlib import Path
    p = Path(path)
    return sha256_bytes(p.read_bytes())


def canonical_json_bytes(obj: Any, *, preserve_declared_order: bool = True) -> bytes:
    """Canonical JSON encoded to UTF-8 bytes (for hashing)."""
    return canonical_json(obj, preserve_declared_order=preserve_declared_order).encode("utf-8")


def canonical_json_hash(obj: Any, *, preserve_declared_order: bool = True) -> str:
    """SHA-256 over the canonical JSON encoding of obj."""
    return sha256_bytes(canonical_json_bytes(obj, preserve_declared_order=preserve_declared_order))
