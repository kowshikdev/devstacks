from devstacks_api.rate_limit import InMemoryRateLimiter


def test_allows_requests_up_to_the_limit_then_blocks():
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60.0)

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False


def test_tracks_separate_keys_independently():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60.0)

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.allow("client-a") is False
