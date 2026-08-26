from collections.abc import Mapping
from enum import StrEnum

import pytest

from devstacks_domain import (
    CONNECTION_TRANSITIONS,
    CONTEST_TRANSITIONS,
    EVIDENCE_VALIDITY_TRANSITIONS,
    INGESTION_TRANSITIONS,
    PUBLICATION_TRANSITIONS,
    REVIEW_TRANSITIONS,
    VERIFICATION_TRANSITIONS,
    EvidenceValidity,
    PublicationStatus,
    ReviewStatus,
    TransitionError,
    validate_transition,
)


@pytest.mark.parametrize(
    "transitions",
    [
        CONNECTION_TRANSITIONS,
        CONTEST_TRANSITIONS,
        EVIDENCE_VALIDITY_TRANSITIONS,
        INGESTION_TRANSITIONS,
        REVIEW_TRANSITIONS,
        PUBLICATION_TRANSITIONS,
        VERIFICATION_TRANSITIONS,
    ],
)
def test_lifecycle_transition_maps_are_exhaustive_and_enforced(
    transitions: Mapping[StrEnum, frozenset[StrEnum]],
):
    state_type = type(next(iter(transitions)))

    assert set(transitions) == set(state_type)
    for current in state_type:
        for target in state_type:
            is_allowed = target in transitions[current]
            if is_allowed:
                validate_transition(
                    current=current,
                    target=target,
                    transitions=transitions,
                )
            else:
                with pytest.raises(TransitionError):
                    validate_transition(
                        current=current,
                        target=target,
                        transitions=transitions,
                    )


def test_lifecycle_transition_rejects_mixed_state_types():
    with pytest.raises(TransitionError, match="same type"):
        validate_transition(
            current=EvidenceValidity.CURRENT,
            target=ReviewStatus.PENDING,
            transitions=EVIDENCE_VALIDITY_TRANSITIONS,
        )


def test_publication_cannot_be_republished_after_withdrawal():
    with pytest.raises(TransitionError, match="not allowed"):
        validate_transition(
            current=PublicationStatus.WITHDRAWN,
            target=PublicationStatus.PUBLISHED,
            transitions=PUBLICATION_TRANSITIONS,
        )