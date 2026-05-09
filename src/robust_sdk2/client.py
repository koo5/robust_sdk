"""HTTP client for submitting requests to a Robust deployment."""
from __future__ import annotations

import time
from typing import Callable, Optional, Union

import requests

from .builder import build_request_rdf
from .domain import LedgerRequest


# Auth accepted as either a (user, password) tuple or a "user:password" string.
Auth = Union[tuple[str, str], str, None]

# Statuses remoulade reports as "the job is finished, in any way".
TERMINAL_STATUSES = ("Success", "Failure", "Skipped")


def _normalize_auth(auth: Auth) -> Optional[tuple[str, str]]:
    if auth is None or isinstance(auth, tuple):
        return auth
    if isinstance(auth, str):
        if ":" not in auth:
            raise ValueError("auth string must be in 'user:password' form")
        user, _, password = auth.partition(":")
        return (user, password)
    raise TypeError(
        f"auth must be None, (user, password) tuple, or 'user:password' string; "
        f"got {type(auth).__name__}"
    )


class JobHandle:
    """Handle for a calculator job scheduled via `submit`.

    Carries the URLs returned by `/upload`'s job_handle response shape and
    provides methods for polling state and waiting for completion. Does not
    retain any open HTTP connection.
    """

    def __init__(
        self,
        base_url: str,
        auth: Auth,
        response: dict,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = _normalize_auth(auth)
        self._response = response

        urls: dict[str, str] = {}
        for entry in response.get("reports", []):
            url = (entry.get("val") or {}).get("url")
            if url:
                urls[entry.get("key")] = url

        self.tmp_url: Optional[str] = urls.get("job_tmp_url")
        """URL of the per-job tmp directory; result files are written under it."""
        self.api_url: Optional[str] = urls.get("job_api_url")
        """JSON state endpoint; GET it to get the current job state."""
        self.view_url: Optional[str] = urls.get("job_view_url")
        """Human-readable HTML page summarising the job."""
        self.id: Optional[str] = self.api_url.rsplit("/", 1)[-1] if self.api_url else None
        """Job message id, last path segment of api_url."""

    @property
    def alerts(self) -> list[str]:
        """The `alerts` list returned alongside the job urls (e.g. ['job scheduled.'])."""
        return list(self._response.get("alerts", []))

    def poll(self) -> dict:
        """GET the JSON state from `api_url` and return it. Raises on HTTP errors."""
        if not self.api_url:
            raise RuntimeError("JobHandle has no api_url")
        r = requests.get(self.api_url, auth=self._auth)
        r.raise_for_status()
        return r.json()

    def wait(
        self,
        timeout: float = 300.0,
        interval: float = 2.0,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> dict:
        """Block until the job reaches a terminal status and return the final state.

        Polls every `interval` seconds. Terminal statuses are
        `Success`, `Failure`, `Skipped` (per remoulade convention). Raises
        `TimeoutError` if `timeout` seconds elapse without one of those.

        `on_progress`, if given, is called after every poll with
        `(status, elapsed_seconds)` so callers can render whatever UI they want
        (status line, log entry, …) without re-implementing the loop.
        """
        start = time.monotonic()
        deadline = start + timeout
        while True:
            state = self.poll()
            elapsed = time.monotonic() - start
            status = state.get("status", "?")
            if on_progress is not None:
                on_progress(status, elapsed)
            if status in TERMINAL_STATUSES:
                return state
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"job {self.id} did not reach a terminal status within {timeout}s "
                    f"(last status: {status!r})"
                )
            time.sleep(interval)

    def __repr__(self) -> str:
        return f"JobHandle(id={self.id!r}, view_url={self.view_url!r})"


def submit(
    req: LedgerRequest,
    base_url: str,
    auth: Auth = None,
) -> JobHandle:
    """Build the RDF for `req`, POST it to `base_url`/upload, return a `JobHandle`.

    `base_url` is the Robust deployment root (e.g. "https://example.com").
    `auth` is HTTP Basic credentials, given as either a `(user, password)`
    tuple or a `"user:password"` string; pass `None` for no auth.

    Returns immediately with a handle. Use `JobHandle.wait()` to block until
    the job finishes, or `JobHandle.poll()` for one-shot status.
    """
    auth = _normalize_auth(auth)
    graph = build_request_rdf(req)
    serialized = graph.serialize(format="n3")
    if isinstance(serialized, str):
        serialized = serialized.encode("utf-8")

    response = requests.post(
        f"{base_url.rstrip('/')}/upload",
        files={"file1": ("request.n3", serialized, "text/n3")},
        data={"request_format": "rdf"},
        auth=auth,
    )
    response.raise_for_status()
    return JobHandle(base_url, auth, response.json())
