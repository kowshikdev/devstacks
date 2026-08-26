from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .hashing import canonical_json, content_hash


class EvidenceVersionOutcome(StrEnum):
    CREATE_VERSION = "create_version"
    NO_OP = "no_op"


@dataclass(frozen=True)
class EvidenceVersionPlan:
    source_artifact_id: str
    canonical_payload: str
    content_hash: str
    idempotency_key: str
    outcome: EvidenceVersionOutcome
    version_number: int | None


def plan_evidence_version(
    *,
    source_artifact_id: str,
    observed_payload: Any,
    latest_content_hash: str | None,
    latest_version_number: int | None,
) -> EvidenceVersionPlan:
    """Plan an append-only evidence write without performing database I/O."""
    if not source_artifact_id.strip():
        raise ValueError("source artifact id is required")
    if latest_version_number is not None and latest_version_number < 1:
        raise ValueError("latest version number must be positive")
    if latest_content_hash is None and latest_version_number is not None:
        raise ValueError("latest version number requires a latest content hash")
    if latest_content_hash is not None and latest_version_number is None:
        raise ValueError("latest content hash requires a latest version number")

    payload = canonical_json(observed_payload)
    observed_hash = content_hash(observed_payload)
    idempotency_key = content_hash(
        {
            "source_artifact_id": source_artifact_id,
            "content_hash": observed_hash,
        }
    )

    if observed_hash == latest_content_hash:
        return EvidenceVersionPlan(
            source_artifact_id=source_artifact_id,
            canonical_payload=payload,
            content_hash=observed_hash,
            idempotency_key=idempotency_key,
            outcome=EvidenceVersionOutcome.NO_OP,
            version_number=None,
        )

    return EvidenceVersionPlan(
        source_artifact_id=source_artifact_id,
        canonical_payload=payload,
        content_hash=observed_hash,
        idempotency_key=idempotency_key,
        outcome=EvidenceVersionOutcome.CREATE_VERSION,
        version_number=(latest_version_number or 0) + 1,
    )