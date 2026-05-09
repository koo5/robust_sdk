"""Tests for `robust_sdk2.client` (auth normalisation and JobHandle.wait)."""
import time

import pytest

from robust_sdk2 import JobHandle
from robust_sdk2.client import _normalize_auth


# --- _normalize_auth -----------------------------------------------------

def test_normalize_auth_none():
    assert _normalize_auth(None) is None


def test_normalize_auth_tuple_passthrough():
    assert _normalize_auth(("u", "p")) == ("u", "p")


def test_normalize_auth_string_split():
    assert _normalize_auth("alice:s3cret") == ("alice", "s3cret")


def test_normalize_auth_string_with_colon_in_password():
    assert _normalize_auth("alice:s3:cret") == ("alice", "s3:cret")


def test_normalize_auth_string_without_colon_rejected():
    with pytest.raises(ValueError, match="user:password"):
        _normalize_auth("just-a-user")


def test_normalize_auth_unsupported_type_rejected():
    with pytest.raises(TypeError):
        _normalize_auth(42)  # type: ignore[arg-type]


# --- JobHandle.wait ------------------------------------------------------

def _handle(monkeypatch, states):
    """Build a JobHandle whose .poll() returns each item of `states` in turn."""
    response = {
        "alerts": ["job scheduled."],
        "reports": [
            {"key": "job_api_url", "val": {"url": "https://x/api/job/abc123"}},
            {"key": "job_view_url", "val": {"url": "https://x/view/job/abc123"}},
            {"key": "job_tmp_url", "val": {"url": "https://x/tmp/abc123/"}},
        ],
    }
    job = JobHandle("https://x", None, response)
    seq = iter(states)
    monkeypatch.setattr(job, "poll", lambda: next(seq))
    monkeypatch.setattr(time, "sleep", lambda _s: None)  # no real sleeping
    return job


def test_wait_returns_on_success(monkeypatch):
    job = _handle(monkeypatch, [
        {"status": "Started"},
        {"status": "Started"},
        {"status": "Success", "result": {"reports": []}},
    ])
    final = job.wait(timeout=10, interval=0)
    assert final["status"] == "Success"


def test_wait_returns_on_failure(monkeypatch):
    job = _handle(monkeypatch, [
        {"status": "Started"},
        {"status": "Failure", "result": {"alerts": ["boom"]}},
    ])
    final = job.wait(timeout=10, interval=0)
    assert final["status"] == "Failure"


def test_wait_returns_on_skipped(monkeypatch):
    job = _handle(monkeypatch, [{"status": "Skipped"}])
    final = job.wait(timeout=10, interval=0)
    assert final["status"] == "Skipped"


def test_wait_invokes_on_progress(monkeypatch):
    job = _handle(monkeypatch, [
        {"status": "Started"},
        {"status": "Started"},
        {"status": "Success"},
    ])
    seen = []
    job.wait(timeout=10, interval=0, on_progress=lambda s, t: seen.append(s))
    assert seen == ["Started", "Started", "Success"]


def test_wait_times_out(monkeypatch):
    # Generator of stuck-Started polls; wait() should give up at the deadline.
    def stuck():
        while True:
            yield {"status": "Started"}

    response = {"reports": [{"key": "job_api_url", "val": {"url": "https://x/api/job/t"}}]}
    job = JobHandle("https://x", None, response)
    seq = stuck()
    monkeypatch.setattr(job, "poll", lambda: next(seq))
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    # Force time.monotonic to advance past the deadline on each call so we
    # don't actually sleep in the test.
    fake_now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now.__setitem__(0, fake_now[0] + 0.5) or fake_now[0])

    with pytest.raises(TimeoutError, match="did not reach a terminal status"):
        job.wait(timeout=1.0, interval=0)
