"""ADR-005 Canonical Hash and Text Identity implementation.

This module implements canonical hashing for Canon persistence:
- raw_text_hash: SHA-256 of UTF-8 encoded raw text
- canonical_hash: SHA-256 of NFC-normalized, deterministically-encoded JSON

Rejects NaN, Infinity, and duplicate keys after NFC normalization.
"""

import hashlib
import json
import unicodedata
from typing import Any


def raw_text_hash(text: str) -> str:
    """Compute SHA-256 hash of raw text as UTF-8 bytes.

    Args:
        text: Raw text string to hash

    Returns:
        Hex-encoded SHA-256 hash (64 characters)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(obj: Any) -> str:
    """Compute SHA-256 hash of canonically-encoded structured data.

    Applies NFC normalization to all string values, validates numeric types,
    checks for duplicate keys after normalization, and serializes with
    deterministic ordering.

    Args:
        obj: JSON-serializable object (dict, list, str, int, float, bool, None)

    Returns:
        Hex-encoded SHA-256 hash (64 characters)

    Raises:
        ValueError: If obj contains NaN, Infinity, or duplicate keys after NFC
        TypeError: If obj is not JSON-serializable or has non-string keys
    """
    normalized = _normalize_for_canonical_hash(obj)
    canonical_json = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _normalize_for_canonical_hash(obj: Any) -> Any:
    """Recursively normalize object for canonical hashing.

    - Applies NFC normalization to all strings
    - Validates numeric types (rejects NaN, Infinity)
    - Preserves structure (dict, list, primitives)
    - Detects duplicate keys after NFC normalization

    Args:
        obj: Object to normalize

    Returns:
        Normalized object with same structure

    Raises:
        ValueError: If obj contains NaN, Infinity, or duplicate keys after NFC
        TypeError: If obj is not JSON-serializable or has non-string keys
    """
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    elif isinstance(obj, dict):
        normalized_dict = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"JSON object keys must be strings, got {type(k).__name__}")
            normalized_key = unicodedata.normalize("NFC", k)
            if normalized_key in normalized_dict:
                raise ValueError(
                    f"Duplicate key after NFC normalization: {normalized_key!r}"
                )
            normalized_dict[normalized_key] = _normalize_for_canonical_hash(v)
        return normalized_dict
    elif isinstance(obj, list):
        return [_normalize_for_canonical_hash(item) for item in obj]
    elif isinstance(obj, float):
        if not (-float("inf") < obj < float("inf")):
            raise ValueError(
                f"Cannot hash float value: {obj} (NaN or Infinity not allowed)"
            )
        return obj
    elif isinstance(obj, (int, bool, type(None))):
        return obj
    else:
        raise TypeError(
            f"Object of type {type(obj).__name__} is not JSON-serializable"
        )
