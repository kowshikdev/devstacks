from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel

from .schemas import ExtractorOutput, VerifierOutput
from .tools import EvidenceReader, build_evidence_tools

EXTRACTOR_SYSTEM_PROMPT = """You are the DevStacks claim extractor.

You receive one immutable evidence version id. Fetch it with get_evidence_version,
then propose claim revisions strictly grounded in what that evidence actually shows.

Rules:
- Never invent developer experience, ownership, leadership, impact, metrics, or
  skills that cannot be supported by the evidence you fetched.
- If the evidence is insufficient to support any claim, return an empty claims
  list. Do not fill the gap with a plausible-sounding guess.
- You are read-only. You never create evidence, bind identity, authorize
  publication, or mutate history — you only propose candidate claim revisions
  for deterministic application code to record.
"""

VERIFIER_SYSTEM_PROMPT = """You are the DevStacks claim verifier.

You receive one evidence version id and a proposed claim statement. Fetch the
evidence with get_evidence_version and assess whether it actually supports the
statement.

Rules:
- Ambiguous authorship (squash-merged group PRs, pair programming, unclear
  attribution) must default to status 'ambiguous' rather than a guessed
  'verified'.
- When evidence is insufficient to decide, return an explicit uncertainty
  state ('ambiguous' or 'unsupported') rather than filling the gap.
- You are read-only and never decide the actual state transition — your
  output is structured input to deterministic application code that enforces
  the allowed transitions.
"""


def build_extractor_agent(
    model: BaseChatModel,
    reader: EvidenceReader,
    profile_id: str,
    checkpointer=None,
):
    return create_deep_agent(
        model=model,
        tools=build_evidence_tools(reader, profile_id),
        system_prompt=EXTRACTOR_SYSTEM_PROMPT,
        response_format=ExtractorOutput,
        checkpointer=checkpointer,
        name="devstacks-extractor",
    )


def build_verifier_agent(
    model: BaseChatModel,
    reader: EvidenceReader,
    profile_id: str,
    checkpointer=None,
):
    return create_deep_agent(
        model=model,
        tools=build_evidence_tools(reader, profile_id),
        system_prompt=VERIFIER_SYSTEM_PROMPT,
        response_format=VerifierOutput,
        checkpointer=checkpointer,
        name="devstacks-verifier",
    )
