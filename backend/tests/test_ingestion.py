import pytest

from devstacks_domain import EvidenceVersionOutcome, plan_evidence_version


def test_new_observation_creates_first_evidence_version():
    plan = plan_evidence_version(
        source_artifact_id="artifact-1",
        observed_payload={"commit": "abc123", "files": 4},
        latest_content_hash=None,
        latest_version_number=None,
    )

    assert plan.outcome is EvidenceVersionOutcome.CREATE_VERSION
    assert plan.version_number == 1
    assert plan.canonical_payload == '{"commit":"abc123","files":4}'


def test_unchanged_observation_is_an_explicit_no_op():
    initial = plan_evidence_version(
        source_artifact_id="artifact-1",
        observed_payload={"files": 4, "commit": "abc123"},
        latest_content_hash=None,
        latest_version_number=None,
    )

    plan = plan_evidence_version(
        source_artifact_id="artifact-1",
        observed_payload={"commit": "abc123", "files": 4},
        latest_content_hash=initial.content_hash,
        latest_version_number=1,
    )

    assert plan.outcome is EvidenceVersionOutcome.NO_OP
    assert plan.version_number is None
    assert plan.idempotency_key == initial.idempotency_key


def test_changed_observation_creates_next_immutable_version():
    plan = plan_evidence_version(
        source_artifact_id="artifact-1",
        observed_payload={"commit": "def456", "files": 5},
        latest_content_hash="a" * 64,
        latest_version_number=3,
    )

    assert plan.outcome is EvidenceVersionOutcome.CREATE_VERSION
    assert plan.version_number == 4


@pytest.mark.parametrize(
    ("latest_content_hash", "latest_version_number"),
    [(None, 1), ("a" * 64, None), ("a" * 64, 0)],
)
def test_inconsistent_existing_version_state_is_rejected(
    latest_content_hash,
    latest_version_number,
):
    with pytest.raises(ValueError):
        plan_evidence_version(
            source_artifact_id="artifact-1",
            observed_payload={"commit": "abc123"},
            latest_content_hash=latest_content_hash,
            latest_version_number=latest_version_number,
        )