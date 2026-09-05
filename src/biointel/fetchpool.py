# C:\Users\JB\Documents\dev\bioindustry\src\biointel\fetchpool.py
"""Parallel SEC fetching under one shared rate ceiling.

Decisions of record (operator, 2026-09-05): ceiling 5 requests/second
aggregate (half SEC's published 10/s fair-access limit, so a hiccup never
earns the ban that would stop every feeder); on any 429 or 403 the pool
pauses for a cooling period and halves its ceiling for the rest of the run,
recording both; a 200-request probe at the chosen ceiling runs before any
full pass uses the pool.

HOW THE CEILING IS ENFORCED. One token bucket, shared by every worker, refills
at `rate` tokens per second and holds at most ONE token, so grants are spaced
at least 1/rate apart and the ceiling holds in every one-second window with no
start-up burst. A worker must take a token before it sends. N workers therefore never exceed `rate`
requests per second in aggregate, whatever N is; N only decides how much
latency is overlapped. This is the property the tests assert with a fake
server: the observed rate never exceeds the ceiling.

WHAT THE POOL DOES NOT DO. It does not write. Results come back to the
caller in submission order and the caller writes through `store` on its own
thread (P21); the single-writer DuckDB constraint is untouched.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import requests

from biointel.efts import _headers

log = logging.getLogger(__name__)

DEFAULT_RATE = 5.0  # requests/second, aggregate (operator decision 2026-09-05)
DEFAULT_WORKERS = 6
COOLING_SECONDS = 60.0  # pause after a 429/403 before resuming at half rate
BACKOFF_STATUSES = (429, 403)
RETRY_STATUSES = (500, 502, 503, 504)


class TokenBucket:
    """Thread-safe token bucket: `take()` blocks until a token is available."""

    def __init__(self, rate: float):
        # Capacity is 1: strict spacing of 1/rate between grants, so the
        # ceiling holds in EVERY one-second window with no start-up burst.
        # (A capacity of `rate` allowed ~2x the ceiling in the first second,
        # which is exactly the burst SEC's limiter flags.)
        self.rate = float(rate)
        self.capacity = 1.0
        self._tokens = 1.0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def set_rate(self, rate: float) -> None:
        with self._lock:
            self.rate = max(0.1, float(rate))

    def take(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self.rate
            time.sleep(wait)


@dataclass
class FetchResult:
    url: str
    status: int | None
    content: bytes | None
    content_type: str
    latency_s: float
    error: str = ""


@dataclass
class PoolStats:
    requests: int = 0
    ok: int = 0
    not_found: int = 0
    backoffs: int = 0
    retries: int = 0
    errors: int = 0
    rate_start: float = DEFAULT_RATE
    rate_end: float = DEFAULT_RATE
    started: float = field(default_factory=time.monotonic)

    def observed_rate(self) -> float:
        elapsed = time.monotonic() - self.started
        return self.requests / elapsed if elapsed > 0 else 0.0

    def as_params(self) -> dict:
        return {
            "requests": self.requests,
            "ok": self.ok,
            "not_found": self.not_found,
            "backoffs": self.backoffs,
            "retries": self.retries,
            "errors": self.errors,
            "rate_start": self.rate_start,
            "rate_end": self.rate_end,
            "observed_rate": round(self.observed_rate(), 3),
        }


class FetchPool:
    """Fetch many URLs in parallel under one aggregate rate ceiling."""

    def __init__(
        self,
        rate: float = DEFAULT_RATE,
        workers: int = DEFAULT_WORKERS,
        cooling_s: float = COOLING_SECONDS,
        session_factory=requests.Session,
        timeout: float = 60.0,
        headers_factory=_headers,
    ):
        self.bucket = TokenBucket(rate)
        self._headers = headers_factory
        self.workers = max(1, int(workers))
        self.cooling_s = cooling_s
        self.timeout = timeout
        self.stats = PoolStats(rate_start=rate, rate_end=rate)
        self._session_factory = session_factory
        self._local = threading.local()
        self._pause_until = 0.0
        self._pause_lock = threading.Lock()

    def _session(self):
        s = getattr(self._local, "session", None)
        if s is None:
            s = self._session_factory()
            self._local.session = s
        return s

    def _respect_pause(self) -> None:
        while True:
            with self._pause_lock:
                until = self._pause_until
            now = time.monotonic()
            if now >= until:
                return
            time.sleep(min(until - now, 1.0))

    def _back_off(self, status: int) -> None:
        with self._pause_lock:
            if time.monotonic() >= self._pause_until:  # first worker to notice acts
                new_rate = max(0.5, self.bucket.rate / 2.0)
                self.bucket.set_rate(new_rate)
                self.stats.rate_end = new_rate
                self.stats.backoffs += 1
                self._pause_until = time.monotonic() + self.cooling_s
                log.warning(
                    f"SEC returned {status}: pausing {self.cooling_s:.0f}s and halving the "
                    f"ceiling to {new_rate:.2f}/s for the rest of this run"
                )

    def fetch_one(self, url: str) -> FetchResult:
        last_err = ""
        for attempt in range(4):
            self._respect_pause()
            self.bucket.take()
            t0 = time.monotonic()
            try:
                r = self._session().get(url, headers=self._headers(), timeout=self.timeout)
            except requests.RequestException as e:
                last_err = str(e)[:200]
                self.stats.requests += 1
                self.stats.retries += 1
                time.sleep(min(2.0 * (attempt + 1), 10.0))
                continue
            latency = time.monotonic() - t0
            self.stats.requests += 1
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if r.status_code == 200:
                self.stats.ok += 1
                return FetchResult(url, 200, r.content, ctype, latency)
            if r.status_code in BACKOFF_STATUSES:
                self._back_off(r.status_code)
                self.stats.retries += 1
                continue
            if r.status_code in RETRY_STATUSES:
                self.stats.retries += 1
                time.sleep(min(2.0 * (attempt + 1), 10.0))
                continue
            if r.status_code == 404:
                self.stats.not_found += 1
            else:
                self.stats.errors += 1
            return FetchResult(url, r.status_code, None, ctype, latency)
        self.stats.errors += 1
        return FetchResult(url, None, None, "", 0.0, error=last_err or "retries exhausted")

    def fetch_all(self, urls: list[str]) -> list[FetchResult]:
        """Results in submission order."""
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            return list(ex.map(self.fetch_one, urls))


def probe(
    urls: list[str],
    rate: float = DEFAULT_RATE,
    workers: int = DEFAULT_WORKERS,
    session_factory=requests.Session,
    headers_factory=_headers,
) -> dict:
    """Rule 4.20 for a rate: run the pool over a small real URL list and
    return the stats plus a status histogram. Nothing is stored."""
    pool = FetchPool(
        rate=rate, workers=workers, session_factory=session_factory, headers_factory=headers_factory
    )
    results = pool.fetch_all(urls)
    hist: dict[str, int] = {}
    for res in results:
        key = str(res.status) if res.status is not None else "error"
        hist[key] = hist.get(key, 0) + 1
    out = pool.stats.as_params()
    out["status_histogram"] = hist
    out["mean_latency_s"] = round(
        sum(r.latency_s for r in results if r.status) / max(1, sum(1 for r in results if r.status)),
        3,
    )
    return out
