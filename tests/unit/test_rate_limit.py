from concurrent.futures import ThreadPoolExecutor

from app.core.rate_limit import TokenBucketRateLimiter


def test_token_bucket_refills_continuously_with_rounded_retry_after():
    now = [0.0]
    limiter = TokenBucketRateLimiter(2, clock=lambda: now[0])
    assert limiter.check("a").allowed
    assert limiter.check("a").allowed
    now[0] = 0.1
    assert limiter.check("a").retry_after == 30
    now[0] = 29.9
    assert limiter.check("a").retry_after == 1
    now[0] = 30.0
    assert limiter.check("a").allowed
    assert not limiter.check("a").allowed
    now[0] = 600
    assert limiter.check("a").allowed
    assert limiter.check("a").allowed
    assert not limiter.check("a").allowed


def test_identity_bound_cannot_evict_an_exhausted_active_bucket():
    now = [0.0]
    limiter = TokenBucketRateLimiter(1, max_identities=2, clock=lambda: now[0])
    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("c").allowed
    assert not limiter.check("a").allowed
    assert len(limiter._buckets) == 2
    now[0] = 60
    assert limiter.check("c").allowed
    assert len(limiter._buckets) == 1


def test_threads_cannot_double_spend_a_token():
    limiter = TokenBucketRateLimiter(5)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(limiter.check, ["key"] * 100))
    assert sum(result.allowed for result in results) == 5
