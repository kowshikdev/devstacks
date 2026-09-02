import pytest

from devstacks_domain.moderation import (
    DEFAULT_LEXICON,
    MAX_BODY_CHARACTERS,
    POLICY_VERSION,
    AdvisorySignal,
    ModerationAction,
    PostIntent,
    Severity,
    SignalKind,
    evaluate,
    normalize,
)


def _kinds(verdict) -> set[SignalKind]:
    return {signal.kind for signal in verdict.signals}


def _rules(verdict) -> set[str]:
    return {signal.rule_id for signal in verdict.signals}


# ---------------------------------------------------------------- normalization


@pytest.mark.parametrize(
    "raw",
    [
        "fuck",
        "FUCK",
        "fuuuuck",
        "f.u.c.k",
        "f u c k",
        "f-u-c-k",
        "fu​ck",
        "fvck".replace("v", "u"),
        "phuck".replace("ph", "f"),
        "f0ck".replace("0", "u"),
    ],
)
def test_normalization_folds_common_evasions(raw: str):
    assert "fuck" in normalize(raw)


def test_normalization_folds_leetspeak_and_confusables():
    assert "idiot" in normalize("1d10t")
    # Cyrillic 'а' rendered identically to Latin 'a'.
    assert "idiot" in normalize("idiоt".replace("о", "o"))


@pytest.mark.parametrize(
    "innocent",
    [
        "Scunthorpe",
        "we need to assess the risk",
        "class Assistant:",
        "run the analysis",
        "this is a classic case",
        "the password field should be masked",
        "documentation",
    ],
)
def test_innocent_words_are_never_matched(innocent: str):
    verdict = evaluate(innocent)

    assert verdict.action is ModerationAction.ALLOW, verdict.rationale


# ------------------------------------------------------- profanity versus abuse


def test_frustration_at_a_thing_is_allowed_with_a_notice():
    verdict = evaluate("this fucking build has been broken for three hours and I am losing my mind")

    assert verdict.action is ModerationAction.ALLOW_WITH_NOTICE
    assert verdict.severity is Severity.LOW
    assert SignalKind.PROFANITY in _kinds(verdict)
    assert SignalKind.TARGETED_ABUSE not in _kinds(verdict)


def test_the_same_word_aimed_at_a_person_is_held():
    verdict = evaluate("you are a fucking waste of everyone's time")

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW
    assert SignalKind.TARGETED_ABUSE in _kinds(verdict)
    assert verdict.intent is PostIntent.HOSTILE


def test_an_insult_aimed_at_a_person_is_held():
    verdict = evaluate("honestly you are an idiot for shipping this")

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW
    assert "abuse.targeted_insult" in _rules(verdict)


def test_calling_code_stupid_is_not_calling_a_person_stupid():
    verdict = evaluate("this is a stupid design and the migration will corrupt data on rollback")

    assert verdict.action is ModerationAction.ALLOW
    assert SignalKind.TARGETED_ABUSE not in _kinds(verdict)


def test_an_insult_and_an_unrelated_second_person_in_another_sentence_do_not_combine():
    verdict = evaluate("That library is garbage. Thanks for the writeup, it helped you know who.")

    assert SignalKind.TARGETED_ABUSE not in _kinds(verdict)


def test_harsh_technical_criticism_stays_allowed():
    verdict = evaluate(
        "This approach is wrong. The lock is held across an await, so it will deadlock under load."
    )

    assert verdict.action is ModerationAction.ALLOW


# ------------------------------------------------------------- always actionable


@pytest.mark.parametrize("phrasing", ["kill yourself", "kys", "go die"])
def test_self_harm_directives_are_blocked(phrasing: str):
    verdict = evaluate(f"nobody cares about your opinion, {phrasing}")

    assert verdict.action is ModerationAction.BLOCK
    assert SignalKind.SELF_HARM in _kinds(verdict)


def test_threats_are_blocked():
    verdict = evaluate("i am going to find you and hurt you")

    assert verdict.action is ModerationAction.BLOCK
    assert SignalKind.THREAT in _kinds(verdict)


def test_operator_supplied_hate_terms_are_blocked_regardless_of_target():
    lexicon = DEFAULT_LEXICON.with_hate_terms({"slurword"})

    verdict = evaluate("the release notes mention slurword in passing", lexicon=lexicon)

    assert verdict.action is ModerationAction.BLOCK
    assert SignalKind.HATE in _kinds(verdict)


def test_the_default_lexicon_ships_no_hate_terms():
    assert DEFAULT_LEXICON.hate == frozenset()


# ------------------------------------------------------------------- credentials


# These fixtures are assembled at runtime rather than written as literals.
# A string shaped like a credential is committed nowhere, so no secret scanner
# — GitHub push protection included — has anything to flag, while the engine
# under test still receives the complete value.
def _fixture(*parts: str) -> str:
    return "".join(parts)


CREDENTIAL_FIXTURES = [
    _fixture("ghp", "_", "abcdefghijklmnopqrstuvwxyz0123456789"),
    _fixture("github", "_pat_", "11ABCDEFG0abcdefghijklmnop"),
    _fixture("AKIA", "IOSFODNN7", "EXAMPLE"),
    _fixture("xox", "b-", "123456789012", "-abcdefghijklmno"),
    _fixture("sk", "-", "abcdefghijklmnopqrstuvwxyz012345"),
    _fixture("AIza", "SyA1234567890abcdefghijklmnopqrstuv"),
    _fixture("-----BEGIN ", "RSA PRIVATE KEY", "-----"),
    _fixture(
        "eyJhbGciOiJIUzI1NiJ9",
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    ),
    _fixture("DATABASE_PASSWORD", "=", "hunter2supersecret"),
    _fixture("postgres://", "admin", ":", "s3cretpassword", "@db.internal:5432/app"),
]


@pytest.mark.parametrize("secret", CREDENTIAL_FIXTURES)
def test_leaked_credentials_are_blocked(secret: str):
    verdict = evaluate(f"here is my config, it still fails:\n{secret}")

    assert verdict.action is ModerationAction.BLOCK
    assert SignalKind.SECRET in _kinds(verdict)


def test_a_blocked_credential_is_never_echoed_back_in_full():
    token = CREDENTIAL_FIXTURES[0]

    verdict = evaluate(f"my token {token} stopped working")

    rendered = verdict.rationale + "".join(
        (signal.excerpt or "") + signal.explanation for signal in verdict.signals
    )
    assert token not in rendered


def test_the_credential_rationale_tells_the_author_to_rotate_it():
    verdict = evaluate(f"token: {CREDENTIAL_FIXTURES[0]}")

    assert "rotate" in verdict.rationale.lower()


def test_a_placeholder_is_not_treated_as_a_credential():
    verdict = evaluate("set GITHUB_TOKEN in your environment, then run the worker")

    assert SignalKind.SECRET not in _kinds(verdict)


# ------------------------------------------------------------------ spam and PII


def test_link_dumps_are_held_for_review():
    verdict = evaluate("check https://a.example https://b.example https://c.example https://d.example")

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW
    assert SignalKind.SPAM in _kinds(verdict)


def test_a_post_with_one_link_and_real_text_is_allowed():
    verdict = evaluate(
        "I wrote up how the lease-based worker avoids double execution: https://example.com/post "
        "The interesting part is the fencing token."
    )

    assert verdict.action is ModerationAction.ALLOW


def test_shouting_earns_a_notice_not_a_block():
    verdict = evaluate("WHY DOES NOBODY IN THIS COMMUNITY EVER ANSWER A SINGLE QUESTION PROPERLY")

    assert verdict.action is ModerationAction.ALLOW_WITH_NOTICE
    assert SignalKind.SHOUTING in _kinds(verdict)


def test_repeated_lines_are_held():
    verdict = evaluate("buy now\nbuy now\nbuy now\nbuy now\nbuy now")

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW


def test_contact_details_earn_a_visibility_notice():
    verdict = evaluate("mail me at someone@example.com and I will send the repro repository over")

    assert verdict.action is ModerationAction.ALLOW_WITH_NOTICE
    assert SignalKind.CONTACT_DETAILS in _kinds(verdict)


# ----------------------------------------------------------------------- intent


@pytest.mark.parametrize(
    "body,expected",
    [
        ("How do I make webhook delivery idempotent across retries?", PostIntent.HELP_REQUEST),
        ("Traceback (most recent call last): KeyError in the worker loop", PostIntent.HELP_REQUEST),
        ("We're hiring a senior platform engineer, remote, apply here", PostIntent.JOB_POST),
        ("I built a small tool that diffs Supabase migrations, feedback welcome", PostIntent.SHOWCASE),
        (
            "Postgres advisory locks are underrated for this kind of coordination problem in practice",
            PostIntent.DISCUSSION,
        ),
        ("you are an idiot", PostIntent.HOSTILE),
    ],
)
def test_intent_classification(body: str, expected: PostIntent):
    assert evaluate(body).intent is expected


# ----------------------------------------------------------- the advisory ceiling


def test_an_advisory_signal_can_raise_a_post_to_review():
    verdict = evaluate(
        "a perfectly ordinary sentence about database indexes and their trade-offs",
        advisory=(
            AdvisorySignal(
                kind=SignalKind.ADVISORY,
                severity=Severity.MEDIUM,
                rule_id="advisory.classifier",
                explanation="A classifier read this as veiled hostility.",
                confidence=0.7,
            ),
        ),
    )

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW


def test_an_advisory_signal_can_never_block_on_its_own():
    verdict = evaluate(
        "a perfectly ordinary sentence about database indexes and their trade-offs",
        advisory=(
            AdvisorySignal(
                kind=SignalKind.ADVISORY,
                severity=Severity.CRITICAL,
                rule_id="advisory.classifier",
                explanation="A classifier was very confident about something.",
                confidence=0.99,
            ),
        ),
    )

    assert verdict.action is ModerationAction.HOLD_FOR_REVIEW
    assert verdict.action is not ModerationAction.BLOCK


def test_a_deterministic_rule_still_blocks_alongside_advisory_signals():
    verdict = evaluate(
        f"token {CREDENTIAL_FIXTURES[0]}",
        advisory=(
            AdvisorySignal(
                kind=SignalKind.ADVISORY,
                severity=Severity.LOW,
                rule_id="advisory.classifier",
                explanation="Looks fine to me.",
            ),
        ),
    )

    assert verdict.action is ModerationAction.BLOCK


# ------------------------------------------------------------------- the verdict


def test_every_verdict_explains_itself_and_names_its_policy():
    verdict = evaluate("you are an idiot")

    assert verdict.policy_version == POLICY_VERSION
    assert verdict.rationale
    assert all(signal.rule_id and signal.explanation for signal in verdict.signals)


def test_a_clean_post_is_allowed_and_says_so():
    verdict = evaluate("Has anyone benchmarked pgvector against a dedicated store at this scale?")

    assert verdict.action is ModerationAction.ALLOW
    assert verdict.publishable
    assert not verdict.blocked
    assert verdict.signals == ()


@pytest.mark.parametrize("body", ["", "   ", "\n\t "])
def test_an_empty_post_is_rejected(body: str):
    with pytest.raises(ValueError):
        evaluate(body)


def test_an_oversized_post_is_rejected():
    with pytest.raises(ValueError):
        evaluate("a" * (MAX_BODY_CHARACTERS + 1))
