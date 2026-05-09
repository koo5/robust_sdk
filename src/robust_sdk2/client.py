"""HTTP client for submitting requests to a Robust deployment."""
from __future__ import annotations

from typing import Optional

import requests

from .builder import build_request_rdf
from .domain import LedgerRequest


class JobHandle:
    """Handle for a calculator job scheduled via `submit`.

    Carries the URLs returned by `/upload`'s job_handle response shape and
    provides convenience methods for polling state. Does not retain any
    open HTTP connection.
    """

    def __init__(
        self,
        base_url: str,
        auth: Optional[tuple[str, str]],
        response: dict,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
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

    def __repr__(self) -> str:
        return f"JobHandle(id={self.id!r}, view_url={self.view_url!r})"


def submit(
    req: LedgerRequest,
    base_url: str,
    auth: Optional[tuple[str, str]] = None,
) -> JobHandle:
    """Build the RDF for `req`, POST it to `base_url`/upload, return a `JobHandle`.

    `base_url` is the Robust deployment root (e.g. "https://example.com"). HTTP
    Basic auth is passed through as a (user, password) tuple when provided.

    The call returns immediately with a handle; poll the handle to track progress.
    """
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
