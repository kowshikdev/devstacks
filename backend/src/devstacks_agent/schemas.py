from typing import Literal

from pydantic import BaseModel, Field


class CandidateClaimOutput(BaseModel):
    """One extractor-proposed claim. Never contains publication state."""

    category: str = Field(description="Short claim category, e.g. 'contribution'")
    statement: str = Field(description="The claim statement, grounded only in the given evidence")
    relation: Literal["supports", "contradicts", "context"] = Field(
        description="How the source evidence version relates to this statement"
    )


class ExtractorOutput(BaseModel):
    """Schema-validated output of the extractor subagent. Read-only: never
    writes evidence, claims, or publication state itself."""

    claims: list[CandidateClaimOutput] = Field(
        default_factory=list,
        description="Claims grounded in the evidence. Empty when evidence is insufficient.",
    )


class VerifierOutput(BaseModel):
    """Schema-validated output of the verifier subagent. Defaults to
    'ambiguous' rather than guessing on unclear authorship."""

    status: Literal["verified", "ambiguous", "unsupported", "contradicted"] = Field(
        description="Verification outcome. Never 'unverified' — that is the pre-decision default."
    )
    verifier_score: float = Field(ge=0.0, le=1.0, description="Confidence in the status, 0 to 1")
    rationale: str = Field(description="Why this status was chosen, referencing the evidence")
