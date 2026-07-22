from src.infrastructure.rate_limit import SlidingWindowCounter, _RULES


def test_ia_routes_have_stricter_limits():
    by_prefix = {prefix: (limit, window) for prefix, limit, window in _RULES}
    assert by_prefix["/api/v1/documents/"][0] <= 15
    assert by_prefix["/api/v1/quizzes/"][0] <= 15


def test_sliding_window_blocks_when_exceeded():
    counter = SlidingWindowCounter()
    assert counter.allow("k", 2, 60.0)
    assert counter.allow("k", 2, 60.0)
    assert not counter.allow("k", 2, 60.0)
