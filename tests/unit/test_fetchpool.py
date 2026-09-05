# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_fetchpool.py
"""The pool's one promise: aggregate requests per second never exceed the
ceiling, whatever the worker count; a 429 pauses and halves the ceiling;
results come back in submission order. Proven with a fake server."""

from __future__ import annotations

import threading
import time

from biointel import fetchpool


class _Resp:
    def __init__(self, status, body=b"ok", ctype="text/plain"):
        self.status_code = status
        self.content = body
        self.headers = {"Content-Type": ctype}


class _FakeSession:
    """Records request timestamps across all threads; optionally returns a
    429 for one specific URL once."""

    calls: list[float] = []
    lock = threading.Lock()
    backoff_url = None
    backoff_done = False

    def get(self, url, headers=None, timeout=None):
        with _FakeSession.lock:
            _FakeSession.calls.append(time.monotonic())
            if url == _FakeSession.backoff_url and not _FakeSession.backoff_done:
                _FakeSession.backoff_done = True
                return _Resp(429)
        time.sleep(0.02)  # simulated latency so workers actually overlap
        if url.endswith("/missing"):
            return _Resp(404)
        return _Resp(200, body=url.encode())


def _reset():
    _FakeSession.calls = []
    _FakeSession.backoff_url = None
    _FakeSession.backoff_done = False


def _max_rate_over_1s_windows(ts: list[float]) -> float:
    ts = sorted(ts)
    best = 0
    j = 0
    for i in range(len(ts)):
        while ts[i] - ts[j] > 1.0:
            j += 1
        best = max(best, i - j + 1)
    return float(best)


def test_aggregate_rate_never_exceeds_ceiling_regardless_of_workers():
    _reset()
    pool = fetchpool.FetchPool(
        rate=20.0, workers=8, session_factory=_FakeSession, headers_factory=dict
    )
    urls = [f"https://x/{i}" for i in range(60)]
    res = pool.fetch_all(urls)
    assert [r.content.decode() for r in res] == urls  # submission order preserved
    assert _max_rate_over_1s_windows(_FakeSession.calls) <= 21  # ceiling 20 (+1: window edge)
    assert pool.stats.ok == 60 and pool.stats.errors == 0


def test_low_ceiling_is_enforced_with_many_workers():
    _reset()
    pool = fetchpool.FetchPool(
        rate=5.0, workers=8, session_factory=_FakeSession, headers_factory=dict
    )
    t0 = time.monotonic()
    pool.fetch_all([f"https://x/{i}" for i in range(15)])
    elapsed = time.monotonic() - t0
    # 15 requests at 5/s with strict spacing: 14 gaps of 0.2 s = at least 2.8 s
    assert elapsed >= 2.6, elapsed
    assert _max_rate_over_1s_windows(_FakeSession.calls) <= 6.0


def test_429_pauses_and_halves_the_ceiling():
    _reset()
    _FakeSession.backoff_url = "https://x/3"
    pool = fetchpool.FetchPool(
        rate=10.0, workers=4, cooling_s=0.3, session_factory=_FakeSession, headers_factory=dict
    )
    res = pool.fetch_all([f"https://x/{i}" for i in range(8)])
    assert all(r.status == 200 for r in res)  # the 429'd URL was retried after the pause
    assert pool.stats.backoffs == 1
    assert pool.stats.rate_end == 5.0  # halved once
    assert pool.bucket.rate == 5.0


def test_404_is_recorded_not_retried():
    _reset()
    pool = fetchpool.FetchPool(
        rate=50.0, workers=2, session_factory=_FakeSession, headers_factory=dict
    )
    res = pool.fetch_all(["https://x/a", "https://x/missing"])
    assert res[0].status == 200 and res[1].status == 404
    assert pool.stats.not_found == 1 and pool.stats.retries == 0


def test_probe_reports_histogram_and_parameters():
    _reset()
    out = fetchpool.probe(
        [f"https://x/{i}" for i in range(5)] + ["https://x/missing"],
        rate=50.0,
        workers=3,
        session_factory=_FakeSession,
        headers_factory=dict,
    )
    assert out["status_histogram"] == {"200": 5, "404": 1}
    assert out["requests"] == 6 and out["rate_start"] == 50.0
