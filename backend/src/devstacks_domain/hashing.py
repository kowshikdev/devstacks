import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data into a stable representation for hashing."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def content_hash(value: Any) -> str:
    """Return the SHA-256 hash of a canonical JSON representation."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()