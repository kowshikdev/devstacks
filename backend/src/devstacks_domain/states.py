from enum import StrEnum


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DEGRADED = "degraded"
    REVOKED = "revoked"
    DISCONNECTED = "disconnected"


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    NO_OP = "no_op"


class EvidenceValidity(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class ReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationStatus(StrEnum):
    UNPUBLISHED = "unpublished"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


class ContestStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    UPHELD = "upheld"
    REJECTED = "rejected"
    RESOLVED = "resolved"
