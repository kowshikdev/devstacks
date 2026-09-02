"""Deterministic content guardrails for community posts.

The architecture rule that governs this module: deterministic application code
owns policy. An agent may contribute an advisory signal, but it can never be the
thing that decides — see `AdvisorySignal` and `evaluate`.

Three judgements shape the design.

**Profanity is not abuse.** A developer writing "this fucking build is broken" is
expressing normal frustration at a machine. "you're a fucking idiot" is aimed at a
person. Communities that conflate the two drive out candour and keep the cruelty,
because the cruel simply stop swearing. So profanity alone is not actionable here;
profanity *directed at a person* is.

**A leaked credential is an emergency, not an offence.** Developers paste tokens
into chat constantly. Blocking that post protects the person who wrote it, so it
is blocked at the highest severity and the rationale says so.

**Every decision explains itself.** A verdict records which rule fired, on what,
and under which policy version, so a moderation decision can be reviewed and
appealed the same way a claim can.

The lexicon is injectable. The default ships ordinary profanity and insults only;
slurs and hate terms are supplied by the operator at deployment rather than
committed to a public repository.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum


POLICY_VERSION = "guardrails/2026-09-01"


class Severity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.NONE: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANK[severity]


class SignalKind(StrEnum):
    PROFANITY = "profanity"
    TARGETED_ABUSE = "targeted_abuse"
    HATE = "hate"
    SELF_HARM = "self_harm"
    THREAT = "threat"
    SECRET = "secret"
    CONTACT_DETAILS = "contact_details"
    SPAM = "spam"
    SHOUTING = "shouting"
    ADVISORY = "advisory"


class ModerationAction(StrEnum):
    ALLOW = "allow"
    ALLOW_WITH_NOTICE = "allow_with_notice"
    HOLD_FOR_REVIEW = "hold_for_review"
    BLOCK = "block"


class PostIntent(StrEnum):
    HELP_REQUEST = "help_request"
    JOB_POST = "job_post"
    SHOWCASE = "showcase"
    DISCUSSION = "discussion"
    HOSTILE = "hostile"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModerationSignal:
    """One thing the engine noticed, and why it matters."""

    kind: SignalKind
    severity: Severity
    rule_id: str
    explanation: str
    excerpt: str | None = None

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("a moderation signal must name the rule that produced it")


@dataclass(frozen=True)
class AdvisorySignal:
    """A model's opinion, admitted as evidence but never as the decision.

    An advisory signal can raise a post to review; on its own it can never block
    one. That ceiling is enforced in `evaluate`, not by convention.
    """

    kind: SignalKind
    severity: Severity
    rule_id: str
    explanation: str
    confidence: float = 0.0


@dataclass(frozen=True)
class ModerationVerdict:
    action: ModerationAction
    severity: Severity
    intent: PostIntent
    signals: tuple[ModerationSignal, ...]
    rationale: str
    policy_version: str = POLICY_VERSION

    @property
    def blocked(self) -> bool:
        return self.action is ModerationAction.BLOCK

    @property
    def publishable(self) -> bool:
        return self.action in (ModerationAction.ALLOW, ModerationAction.ALLOW_WITH_NOTICE)


@dataclass(frozen=True)
class Lexicon:
    """Operator-supplied vocabulary.

    `profanity` is coarse language with no target. `insults` are person-directed
    when they appear near a second-person reference. `hate` is always actionable
    regardless of target and is intentionally empty by default.
    """

    profanity: frozenset[str] = frozenset()
    insults: frozenset[str] = frozenset()
    hate: frozenset[str] = frozenset()

    def with_hate_terms(self, terms: frozenset[str] | set[str]) -> "Lexicon":
        return Lexicon(
            profanity=self.profanity,
            insults=self.insults,
            hate=frozenset(term.lower() for term in terms),
        )


DEFAULT_LEXICON = Lexicon(
    profanity=frozenset(
        {"fuck", "fucking", "shit", "shitty", "bullshit", "bastard", "crap", "damn", "arse", "ass"}
    ),
    insults=frozenset(
        {
            "idiot",
            "idiots",
            "moron",
            "morons",
            "stupid",
            "dumb",
            "clown",
            "clueless",
            "incompetent",
            "pathetic",
            "worthless",
            "braindead",
            "loser",
            "trash",
            "garbage",
        }
    ),
    # Deliberately empty: hate terms are configured at deployment, not committed.
    hate=frozenset(),
)


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))

_CONFUSABLES = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "!": "i",
        "|": "l",
        "а": "a",  # Cyrillic
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
    }
)

_REPEATED = re.compile(r"(.)\1{2,}")
# Letters deliberately broken apart: f.u.c.k, f u c k, f-u-c-k.
_SPACED_LETTERS = re.compile(r"\b(?:[a-z][^a-z0-9\n]{1,2}){2,}[a-z]\b")


@dataclass(frozen=True)
class NormalizedText:
    """The original text plus the forms used for matching."""

    original: str
    text: str
    """Lowercased, confusables folded, repeats collapsed. Word boundaries intact."""

    def __contains__(self, term: str) -> bool:
        return _word_match(self.text, term) is not None


def normalize(raw: str) -> NormalizedText:
    """Fold the tricks people use to slip a word past a matcher.

    Word boundaries are preserved on purpose. Matching a bare substring is how a
    filter ends up rejecting "Scunthorpe" and "assess", so every lexicon lookup
    here is anchored to whole words.
    """
    folded = unicodedata.normalize("NFKC", raw)
    folded = folded.translate(_ZERO_WIDTH)
    folded = "".join(
        character
        for character in folded
        if character in "\n\t" or not unicodedata.category(character).startswith("C")
    )
    folded = folded.lower().translate(_CONFUSABLES)
    folded = _REPEATED.sub(r"\1", folded)
    folded = _SPACED_LETTERS.sub(lambda match: re.sub(r"[^a-z0-9]", "", match.group(0)), folded)
    return NormalizedText(original=raw, text=folded)


def _word_match(haystack: str, term: str) -> re.Match[str] | None:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack)


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------

_SECRET_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("secret.github_pat", "a GitHub personal access token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("secret.github_fine_grained", "a GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("secret.aws_access_key", "an AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("secret.slack_token", "a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("secret.openai_key", "an API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("secret.google_api_key", "a Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("secret.private_key", "a private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("secret.jwt", "a JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    (
        "secret.assignment",
        "a credential assigned in plain text",
        # A prefixed name such as DATABASE_PASSWORD has no word boundary before
        # "PASSWORD", so the leading segment is matched explicitly.
        re.compile(
            r"(?i)(?:^|[^a-z0-9])(?:[a-z0-9]+[_-])?"
            r"(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)"
            r"\s*[:=]\s*[\"']?[^\s\"']{8,}"
        ),
    ),
    ("secret.connection_string", "a database connection string with credentials", re.compile(r"(?i)\b[a-z]+://[^\s:@/]+:[^\s:@/]+@[^\s/]+")),
)

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d{3,4}[\s-]\d{3,4}(?:[\s-]\d{3,4})?(?!\w)")
_URL = re.compile(r"https?://\S+")

_SECOND_PERSON = re.compile(r"(?<![a-z0-9])(?:you|your|you're|youre|yours|yourself|u|ur|@\w+)(?![a-z0-9])")
_SELF_HARM = re.compile(
    r"(?<![a-z0-9])(?:kill\s+(?:yourself|urself)|kys|end\s+your\s+life|go\s+die)(?![a-z0-9])"
)
_THREAT = re.compile(
    r"(?<![a-z0-9])(?:i(?:'m| am|m)?\s+(?:going\s+to|gonna|will)\s+(?:hurt|kill|find|destroy)\s+(?:you|u|your)"
    r"|(?:i'll|ill)\s+(?:hurt|kill|find)\s+(?:you|u))(?![a-z0-9])"
)

#: How close an insult must sit to a second-person reference to count as aimed
#: at someone. Wide enough for "you are being a complete idiot", tight enough
#: that an insult and an unrelated "you" in another sentence do not combine.
_TARGET_WINDOW_CHARS = 60


def _detect_secrets(text: str) -> list[ModerationSignal]:
    signals: list[ModerationSignal] = []
    for rule_id, description, pattern in _SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            signals.append(
                ModerationSignal(
                    kind=SignalKind.SECRET,
                    severity=Severity.CRITICAL,
                    rule_id=rule_id,
                    explanation=(
                        f"This looks like {description}. The post was stopped to keep it out of "
                        "public view — rotate the credential if it is real."
                    ),
                    excerpt=_redact(match.group(0)),
                )
            )
    return signals


def _redact(value: str) -> str:
    """Never echo a credential back in full, not even to its author."""
    stripped = value.strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}…{'*' * 6}"


def _detect_contact_details(text: str) -> list[ModerationSignal]:
    signals: list[ModerationSignal] = []
    if _EMAIL.search(text):
        signals.append(
            ModerationSignal(
                kind=SignalKind.CONTACT_DETAILS,
                severity=Severity.LOW,
                rule_id="pii.email",
                explanation="This post contains an email address, which will be publicly visible.",
            )
        )
    if _PHONE.search(text):
        signals.append(
            ModerationSignal(
                kind=SignalKind.CONTACT_DETAILS,
                severity=Severity.LOW,
                rule_id="pii.phone",
                explanation="This post contains what looks like a phone number, which will be publicly visible.",
            )
        )
    return signals


def _detect_abuse(normalized: NormalizedText, lexicon: Lexicon) -> list[ModerationSignal]:
    """Separate coarse language from language aimed at a person."""
    text = normalized.text
    signals: list[ModerationSignal] = []

    if _SELF_HARM.search(text):
        signals.append(
            ModerationSignal(
                kind=SignalKind.SELF_HARM,
                severity=Severity.CRITICAL,
                rule_id="abuse.self_harm_directive",
                explanation="Telling someone to harm themselves is never acceptable here.",
            )
        )

    if _THREAT.search(text):
        signals.append(
            ModerationSignal(
                kind=SignalKind.THREAT,
                severity=Severity.CRITICAL,
                rule_id="abuse.threat",
                explanation="This reads as a threat of violence against a person.",
            )
        )

    for term in sorted(lexicon.hate):
        if _word_match(text, term):
            signals.append(
                ModerationSignal(
                    kind=SignalKind.HATE,
                    severity=Severity.CRITICAL,
                    rule_id="abuse.hate_term",
                    explanation="This contains a slur. It is not permitted regardless of who it is aimed at.",
                )
            )
            break

    for term in sorted(lexicon.insults):
        match = _word_match(text, term)
        if not match:
            continue
        if _is_directed_at_a_person(text, match.start(), match.end()):
            signals.append(
                ModerationSignal(
                    kind=SignalKind.TARGETED_ABUSE,
                    severity=Severity.HIGH,
                    rule_id="abuse.targeted_insult",
                    explanation=(
                        "This insult is aimed at a person. Criticise the code, the design, or the "
                        "argument as harshly as you like — not the person."
                    ),
                    excerpt=term,
                )
            )
            break

    for term in sorted(lexicon.profanity):
        match = _word_match(text, term)
        if not match:
            continue
        directed = _is_directed_at_a_person(text, match.start(), match.end())
        signals.append(
            ModerationSignal(
                kind=SignalKind.TARGETED_ABUSE if directed else SignalKind.PROFANITY,
                severity=Severity.HIGH if directed else Severity.LOW,
                rule_id="abuse.directed_profanity" if directed else "abuse.profanity",
                explanation=(
                    "Strong language aimed at a person reads as abuse."
                    if directed
                    else "Strong language, not aimed at anyone. Noted, not actioned."
                ),
                excerpt=term,
            )
        )
        break

    return signals


def _is_directed_at_a_person(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - _TARGET_WINDOW_CHARS) : end + _TARGET_WINDOW_CHARS]
    # A sentence boundary between the two means they are separate thoughts.
    before = text[max(0, start - _TARGET_WINDOW_CHARS) : start]
    after = text[end : end + _TARGET_WINDOW_CHARS]
    before = before.rsplit(".", 1)[-1].rsplit("\n", 1)[-1]
    after = after.split(".", 1)[0].split("\n", 1)[0]
    return bool(_SECOND_PERSON.search(before) or _SECOND_PERSON.search(after)) and bool(window)


def _detect_spam(raw: str, normalized: NormalizedText) -> list[ModerationSignal]:
    signals: list[ModerationSignal] = []
    words = normalized.text.split()
    links = _URL.findall(raw)

    if words and len(links) >= 3 and len(links) / max(len(words), 1) > 0.15:
        signals.append(
            ModerationSignal(
                kind=SignalKind.SPAM,
                severity=Severity.MEDIUM,
                rule_id="spam.link_density",
                explanation="Mostly links and very little text reads as promotion rather than a post.",
            )
        )

    letters = [character for character in raw if character.isalpha()]
    if len(letters) >= 40:
        upper_ratio = sum(1 for character in letters if character.isupper()) / len(letters)
        if upper_ratio > 0.7:
            signals.append(
                ModerationSignal(
                    kind=SignalKind.SHOUTING,
                    severity=Severity.LOW,
                    rule_id="spam.shouting",
                    explanation="This is almost entirely capitals, which reads as shouting.",
                )
            )

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) >= 4 and len(set(lines)) == 1:
        signals.append(
            ModerationSignal(
                kind=SignalKind.SPAM,
                severity=Severity.MEDIUM,
                rule_id="spam.repetition",
                explanation="The same line is repeated over and over.",
            )
        )

    return signals


# --------------------------------------------------------------------------
# Intent
# --------------------------------------------------------------------------

_HELP_MARKERS = (
    "how do i", "how can i", "how would i", "why does", "why is", "why do",
    "any idea", "anyone know", "stuck on", "i'm stuck", "im stuck", "need help",
    "help me", "not working", "doesn't work", "does not work", "traceback",
    "stack trace", "error:", "exception", "failing", "any advice", "what am i doing wrong",
)
_JOB_MARKERS = (
    "we're hiring", "were hiring", "we are hiring", "now hiring", "is hiring",
    "job opening", "open role", "open position", "looking to hire", "apply here",
    "send your cv", "send your resume", "salary", "full-time", "part-time", "contract role",
)
_SHOWCASE_MARKERS = (
    "i built", "i made", "i've built", "ive built", "i shipped", "just launched",
    "just released", "i created", "my new project", "showing off", "feedback welcome",
)


def classify_intent(normalized: NormalizedText, signals: list[ModerationSignal]) -> PostIntent:
    """Name what a post is for, so a space can hold people to it.

    Intent is descriptive, not punitive: it lets a help space keep recruiting out
    and a jobs space keep it in. Hostility outranks everything else, because a
    post that attacks someone is not a question no matter how it is phrased.
    """
    if any(
        signal.kind in (SignalKind.TARGETED_ABUSE, SignalKind.HATE, SignalKind.THREAT, SignalKind.SELF_HARM)
        for signal in signals
    ):
        return PostIntent.HOSTILE

    text = normalized.text

    if any(marker in text for marker in _JOB_MARKERS):
        return PostIntent.JOB_POST
    if any(marker in text for marker in _HELP_MARKERS) or (
        "?" in normalized.original and any(marker in text for marker in ("how", "why", "what", "which"))
    ):
        return PostIntent.HELP_REQUEST
    if any(marker in text for marker in _SHOWCASE_MARKERS):
        return PostIntent.SHOWCASE
    if len(text.split()) >= 8:
        return PostIntent.DISCUSSION
    return PostIntent.UNKNOWN


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

_ACTION_BY_SEVERITY: dict[Severity, ModerationAction] = {
    Severity.NONE: ModerationAction.ALLOW,
    Severity.LOW: ModerationAction.ALLOW_WITH_NOTICE,
    Severity.MEDIUM: ModerationAction.HOLD_FOR_REVIEW,
    Severity.HIGH: ModerationAction.HOLD_FOR_REVIEW,
    Severity.CRITICAL: ModerationAction.BLOCK,
}

MAX_BODY_CHARACTERS = 20_000


def evaluate(
    body: str,
    *,
    lexicon: Lexicon = DEFAULT_LEXICON,
    advisory: tuple[AdvisorySignal, ...] = (),
) -> ModerationVerdict:
    """Judge one post and explain the judgement.

    Deterministic rules decide. Advisory signals from a model are recorded and
    can raise a post to human review, but are capped below BLOCK: nothing is
    removed from this community on a model's say-so alone.
    """
    if not body.strip():
        raise ValueError("a post body is required")
    if len(body) > MAX_BODY_CHARACTERS:
        raise ValueError("post body exceeds the maximum length")

    normalized = normalize(body)

    signals: list[ModerationSignal] = []
    signals.extend(_detect_secrets(body))
    signals.extend(_detect_abuse(normalized, lexicon))
    signals.extend(_detect_spam(body, normalized))
    signals.extend(_detect_contact_details(body))

    deterministic_worst = _worst(signals)

    for hint in advisory:
        # Capped at HIGH so an advisory signal can reach review but never block.
        capped = hint.severity if severity_rank(hint.severity) < _SEVERITY_RANK[Severity.CRITICAL] else Severity.HIGH
        signals.append(
            ModerationSignal(
                kind=SignalKind.ADVISORY,
                severity=capped,
                rule_id=hint.rule_id,
                explanation=hint.explanation,
            )
        )

    intent = classify_intent(normalized, signals)
    worst = _worst(signals)
    action = _ACTION_BY_SEVERITY[worst]

    # Belt and braces: only a deterministic rule can produce a block.
    if action is ModerationAction.BLOCK and deterministic_worst is not Severity.CRITICAL:
        action = ModerationAction.HOLD_FOR_REVIEW

    return ModerationVerdict(
        action=action,
        severity=worst,
        intent=intent,
        signals=tuple(signals),
        rationale=_rationale(action, signals),
    )


def _worst(signals: list[ModerationSignal]) -> Severity:
    worst = Severity.NONE
    for signal in signals:
        if severity_rank(signal.severity) > severity_rank(worst):
            worst = signal.severity
    return worst


def _rationale(action: ModerationAction, signals: list[ModerationSignal]) -> str:
    if action is ModerationAction.ALLOW:
        return "No guardrail matched this post."
    leading = max(signals, key=lambda signal: severity_rank(signal.severity))
    if action is ModerationAction.BLOCK:
        return f"Blocked by {leading.rule_id}: {leading.explanation}"
    if action is ModerationAction.HOLD_FOR_REVIEW:
        return f"Held for review by {leading.rule_id}: {leading.explanation}"
    return f"Published with a notice from {leading.rule_id}: {leading.explanation}"
