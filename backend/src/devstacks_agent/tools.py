from typing import Protocol

from langchain_core.tools import tool


class EvidenceReader(Protocol):
    """Structural boundary between devstacks_agent and whatever repository the
    caller wires in (kept decoupled from devstacks_api's Supabase specifics)."""

    async def get_evidence_version(
        self,
        profile_id: str,
        evidence_version_id: str,
    ) -> dict[str, object] | None:
        """Return one evidence version's normalized payload and provenance, or None."""


def build_evidence_tools(reader: EvidenceReader, profile_id: str):
    """Read-only tools for the extractor/verifier subagents. Never expose a
    write-capable method — this module only imports read methods by
    construction, so there is nothing here an agent could use to mutate
    evidence, claims, or publication state."""

    @tool
    async def get_evidence_version(evidence_version_id: str) -> dict[str, object] | str:
        """Fetch one evidence version's normalized payload, source type/ref,
        assurance class, and validity. Returns an error string if the
        evidence version does not belong to this profile."""
        record = await reader.get_evidence_version(profile_id, evidence_version_id)
        if record is None:
            return "evidence version not found or does not belong to this profile"
        return record

    return [get_evidence_version]
