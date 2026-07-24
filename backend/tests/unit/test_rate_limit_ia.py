from src.infrastructure.rate_limit import SlidingWindowCounter, _match_rule


def test_ia_routes_have_stricter_limits():
    analyze = _match_rule("/api/v1/documents/x/analyze", "POST")
    ask = _match_rule("/api/v1/documents/x/ask", "POST")
    quiz = _match_rule("/api/v1/documents/x/quiz", "POST")
    docs = _match_rule("/api/v1/documents/", "GET")
    assert analyze is not None and analyze[1] <= 15
    assert ask is not None and ask[1] <= 15
    assert quiz is not None and quiz[1] <= 15
    assert docs is not None and docs[1] <= 30


def test_sliding_window_blocks_when_exceeded():
    counter = SlidingWindowCounter()
    assert counter.allow("k", 2, 60.0)
    assert counter.allow("k", 2, 60.0)
    assert not counter.allow("k", 2, 60.0)
