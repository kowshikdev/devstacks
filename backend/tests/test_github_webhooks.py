import pytest

from devstacks_api.github_webhooks import GitHubWebhookError, parse_delivery, verify_signature


def test_webhook_signature_matches_github_documented_hmac_vector():
    payload = b"Hello, World!"
    signature = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"

    verify_signature(payload, "It's a Secret to Everybody", signature)


@pytest.mark.parametrize(
    "signature",
    [None, "sha1=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17", "sha256=bad"],
)
def test_webhook_signature_rejects_missing_legacy_and_tampered_values(signature):
    with pytest.raises(GitHubWebhookError, match="signature"):
        verify_signature(b"Hello, World!", "It's a Secret to Everybody", signature)


def test_webhook_delivery_parses_only_required_headers_and_object_payload():
    delivery = parse_delivery(
        b'{"repository":{"id":101}}',
        "delivery-1",
        "push",
        "456",
    )

    assert delivery.delivery_id == "delivery-1"
    assert delivery.hook_id == 456
    assert delivery.payload["repository"] == {"id": 101}


@pytest.mark.parametrize(
    "payload,delivery_id,event_type,hook_id",
    [
        (b"[]", "delivery-1", "push", "456"),
        (b"not-json", "delivery-1", "push", "456"),
        (b"{}", None, "push", "456"),
        (b"{}", "delivery-1", None, "456"),
        (b"{}", "delivery-1", "push", "not-a-number"),
    ],
)
def test_webhook_delivery_rejects_invalid_headers_or_payload(
    payload,
    delivery_id,
    event_type,
    hook_id,
):
    with pytest.raises(GitHubWebhookError):
        parse_delivery(payload, delivery_id, event_type, hook_id)