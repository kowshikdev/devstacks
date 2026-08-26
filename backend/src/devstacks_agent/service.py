from dataclasses import dataclass

from devstacks_domain import (
    AgentRunLease,
    AgentRunRepository,
    AgentRunStatus,
    CandidateClaimRevision,
    ClaimEvidenceLinkDraft,
    ClaimIntakeService,
    ClaimRepository,
    VerificationDecisionService,
    VerificationRepository,
    VerificationStatus,
)

from .agents import build_extractor_agent, build_verifier_agent
from .checkpointer import thread_id_for
from .model import build_model
from .schemas import ExtractorOutput, VerifierOutput
from .tools import EvidenceReader


class AgentStructuredOutputError(RuntimeError):
    """Raised when the model completes a run without producing the required
    structured output — a model/provider reliability failure, not a
    legitimate uncertainty verdict (which is expressed through the schema's
    own status values instead)."""


@dataclass(frozen=True)
class ClaimExtractionOutcome:
    claim_revision_ids: tuple[str, ...]
    verification_decision_ids: tuple[str, ...]


class ClaimExtractionAgentService:
    """Runs the extractor then the verifier for one evidence version, and
    records their output through the deterministic domain services — the
    agents themselves never call a write-capable repository method."""

    def __init__(
        self,
        agent_run_repository: AgentRunRepository,
        claim_repository: ClaimRepository,
        verification_repository: VerificationRepository,
        evidence_reader: EvidenceReader,
        checkpointer=None,
    ) -> None:
        self._agent_run_repository = agent_run_repository
        self._claim_intake = ClaimIntakeService(claim_repository)
        self._verification = VerificationDecisionService(verification_repository)
        self._evidence_reader = evidence_reader
        self._checkpointer = checkpointer

    async def run(self, lease: AgentRunLease) -> ClaimExtractionOutcome:
        if lease.source_artifact_id is None or lease.evidence_version_id is None:
            await self._agent_run_repository.complete(
                lease,
                AgentRunStatus.FAILED,
                "agent run is missing its source artifact or evidence version",
            )
            return ClaimExtractionOutcome((), ())

        try:
            outcome = await self._extract_and_verify(lease)
        except Exception as error:  # noqa: BLE001 - convert any agent/model failure to a terminal run state
            await self._agent_run_repository.complete(lease, AgentRunStatus.FAILED, str(error))
            raise
        await self._agent_run_repository.complete(lease, AgentRunStatus.SUCCEEDED)
        return outcome

    async def _extract_and_verify(self, lease: AgentRunLease) -> ClaimExtractionOutcome:
        model = build_model()
        thread_id = thread_id_for(lease.profile_id, lease.source_artifact_id, lease.evidence_version_id)
        config = {"configurable": {"thread_id": thread_id}}

        extractor = build_extractor_agent(
            model, self._evidence_reader, lease.profile_id, self._checkpointer
        )
        extractor_result = await extractor.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Propose claim revisions grounded in evidence version "
                            f"{lease.evidence_version_id}."
                        ),
                    }
                ]
            },
            config=config,
        )
        if "structured_response" not in extractor_result:
            raise AgentStructuredOutputError(
                "extractor completed without producing structured output"
            )
        extractor_output = ExtractorOutput.model_validate(extractor_result["structured_response"])

        claim_revision_ids: list[str] = []
        verification_decision_ids: list[str] = []
        for candidate_output in extractor_output.claims:
            record = await self._claim_intake.submit_candidate(
                lease.profile_id,
                CandidateClaimRevision(
                    category=candidate_output.category,
                    statement=candidate_output.statement,
                    evidence_links=(
                        ClaimEvidenceLinkDraft(lease.evidence_version_id, candidate_output.relation),
                    ),
                ),
            )
            claim_revision_ids.append(record.claim_revision_id)

            verifier = build_verifier_agent(
                model, self._evidence_reader, lease.profile_id, self._checkpointer
            )
            verifier_result = await verifier.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Verify this claim against evidence version "
                                f"{lease.evidence_version_id}: {candidate_output.statement}"
                            ),
                        }
                    ]
                },
                config={"configurable": {"thread_id": f"{thread_id}:{record.claim_revision_id}"}},
            )
            if "structured_response" not in verifier_result:
                raise AgentStructuredOutputError(
                    "verifier completed without producing structured output"
                )
            verifier_output = VerifierOutput.model_validate(verifier_result["structured_response"])

            decision_id = await self._verification.record(
                lease.profile_id,
                record.claim_revision_id,
                VerificationStatus(verifier_output.status),
                verifier_score=verifier_output.verifier_score,
                agent_run_id=lease.id,
                rationale=verifier_output.rationale,
            )
            verification_decision_ids.append(decision_id)

        return ClaimExtractionOutcome(tuple(claim_revision_ids), tuple(verification_decision_ids))
