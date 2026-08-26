from collections.abc import Mapping
from enum import StrEnum

from .states import (
    ConnectionStatus,
    ContestStatus,
    EvidenceValidity,
    IngestionStatus,
    PublicationStatus,
    ReviewStatus,
    VerificationStatus,
)


class TransitionError(ValueError):
    """Raised when an audited lifecycle transition is not allowed."""


TransitionMap = Mapping[StrEnum, frozenset[StrEnum]]


CONNECTION_TRANSITIONS: dict[ConnectionStatus, frozenset[ConnectionStatus]] = {
    ConnectionStatus.PENDING: frozenset(
        {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.REVOKED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.ACTIVE: frozenset(
        {
            ConnectionStatus.DEGRADED,
            ConnectionStatus.REVOKED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.DEGRADED: frozenset(
        {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.REVOKED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.REVOKED: frozenset(),
    ConnectionStatus.DISCONNECTED: frozenset(),
}

INGESTION_TRANSITIONS: dict[IngestionStatus, frozenset[IngestionStatus]] = {
    IngestionStatus.QUEUED: frozenset({IngestionStatus.RUNNING}),
    IngestionStatus.RUNNING: frozenset(
        {
            IngestionStatus.SUCCEEDED,
            IngestionStatus.PARTIAL,
            IngestionStatus.FAILED,
            IngestionStatus.NO_OP,
        }
    ),
    IngestionStatus.SUCCEEDED: frozenset(),
    IngestionStatus.PARTIAL: frozenset(),
    IngestionStatus.FAILED: frozenset(),
    IngestionStatus.NO_OP: frozenset(),
}

EVIDENCE_VALIDITY_TRANSITIONS: dict[EvidenceValidity, frozenset[EvidenceValidity]] = {
    EvidenceValidity.CURRENT: frozenset(
        {
            EvidenceValidity.STALE,
            EvidenceValidity.UNAVAILABLE,
            EvidenceValidity.INVALID,
            EvidenceValidity.SUPERSEDED,
        }
    ),
    EvidenceValidity.STALE: frozenset(
        {
            EvidenceValidity.UNAVAILABLE,
            EvidenceValidity.INVALID,
            EvidenceValidity.SUPERSEDED,
        }
    ),
    EvidenceValidity.UNAVAILABLE: frozenset(
        {
            EvidenceValidity.STALE,
            EvidenceValidity.INVALID,
            EvidenceValidity.SUPERSEDED,
        }
    ),
    EvidenceValidity.INVALID: frozenset({EvidenceValidity.SUPERSEDED}),
    EvidenceValidity.SUPERSEDED: frozenset(),
}

REVIEW_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.NOT_REQUIRED: frozenset({ReviewStatus.PENDING}),
    ReviewStatus.PENDING: frozenset({ReviewStatus.APPROVED, ReviewStatus.REJECTED}),
    ReviewStatus.APPROVED: frozenset(),
    ReviewStatus.REJECTED: frozenset(),
}

VERIFICATION_TRANSITIONS: dict[VerificationStatus, frozenset[VerificationStatus]] = {
    VerificationStatus.UNVERIFIED: frozenset(
        {
            VerificationStatus.VERIFIED,
            VerificationStatus.AMBIGUOUS,
            VerificationStatus.UNSUPPORTED,
            VerificationStatus.CONTRADICTED,
        }
    ),
    VerificationStatus.VERIFIED: frozenset(),
    VerificationStatus.AMBIGUOUS: frozenset(),
    VerificationStatus.UNSUPPORTED: frozenset(),
    VerificationStatus.CONTRADICTED: frozenset(),
}

PUBLICATION_TRANSITIONS: dict[PublicationStatus, frozenset[PublicationStatus]] = {
    PublicationStatus.UNPUBLISHED: frozenset({PublicationStatus.PUBLISHED}),
    PublicationStatus.PUBLISHED: frozenset({PublicationStatus.WITHDRAWN}),
    PublicationStatus.WITHDRAWN: frozenset(),
}

CONTEST_TRANSITIONS: dict[ContestStatus, frozenset[ContestStatus]] = {
    ContestStatus.OPEN: frozenset({ContestStatus.INVESTIGATING}),
    ContestStatus.INVESTIGATING: frozenset(
        {
            ContestStatus.UPHELD,
            ContestStatus.REJECTED,
            ContestStatus.RESOLVED,
        }
    ),
    ContestStatus.UPHELD: frozenset(),
    ContestStatus.REJECTED: frozenset(),
    ContestStatus.RESOLVED: frozenset(),
}


def validate_transition(
    *,
    current: StrEnum,
    target: StrEnum,
    transitions: TransitionMap,
) -> None:
    """Validate a one-way lifecycle transition before recording an audit event."""
    if type(current) is not type(target):
        raise TransitionError("lifecycle states must share the same type")
    if current not in transitions:
        raise TransitionError(f"state {current} is not configured")
    if target not in transitions[current]:
        raise TransitionError(f"transition from {current} to {target} is not allowed")