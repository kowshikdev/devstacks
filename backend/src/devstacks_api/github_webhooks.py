from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest, new
from json import JSONDecodeError, loads
from os import getenv


class GitHubWebhookError(ValueError):
    """Raised when a GitHub webhook delivery is malformed or unauthenticated."""


class GitHubWebhookUnavailableError(RuntimeError):
    """Raised when the server has no configured GitHub webhook secret."""


@dataclass(frozen=True)
class GitHubWebhookSettings:
    secret: str

    @classmethod
    def from_environment(cls) -> "GitHubWebhookSettings":
        secret = getenv("GITHUB_WEBHOOK_SECRET", "")
        if not secret:
            raise GitHubWebhookUnavailableError("GitHub webhook secret is not configured")
        return cls(secret=secret)


@dataclass(frozen=True)
class GitHubWebhookDelivery:
    delivery_id: str
    event_type: str
    hook_id: int
    payload: dict[str, object]


def verify_signature(payload: bytes, secret: str, signature_header: str | None) -> None:
    if not signature_header or not signature_header.startswith("sha256="):
        raise GitHubWebhookError("GitHub webhook signature is missing or invalid")
    expected_signature = "sha256=" + new(secret.encode("utf-8"), payload, sha256).hexdigest()
    if not compare_digest(expected_signature, signature_header):
        raise GitHubWebhookError("GitHub webhook signature does not match")


def parse_delivery(
    payload: bytes,
    delivery_id: str | None,
    event_type: str | None,
    hook_id: str | None,
) -> GitHubWebhookDelivery:
    if not delivery_id or len(delivery_id) > 255:
        raise GitHubWebhookError("GitHub webhook delivery id is invalid")
    if not event_type or len(event_type) > 100:
        raise GitHubWebhookError("GitHub webhook event type is invalid")
    if not hook_id or not hook_id.isdecimal():
        raise GitHubWebhookError("GitHub webhook hook id is invalid")
    try:
        decoded_payload = loads(payload)
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise GitHubWebhookError("GitHub webhook payload is invalid") from error
    if not isinstance(decoded_payload, dict):
        raise GitHubWebhookError("GitHub webhook payload must be an object")
    return GitHubWebhookDelivery(
        delivery_id=delivery_id,
        event_type=event_type,
        hook_id=int(hook_id),
        payload=decoded_payload,
    )