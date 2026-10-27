"""A small, polite HTTP client shared by all data sources.

Why not just call `requests.get` everywhere?
- We want the same User-Agent on every request (so server admins know who we are).
- We want a pause between requests, so we never hammer a server.
- We want automatic retries when a server has a temporary hiccup (HTTP 5xx).
"""

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from roque_forecast import config


class PoliteSession:
    """Wraps `requests.Session` adding a minimum delay between requests."""

    def __init__(self, min_interval_s: float = config.MIN_SECONDS_BETWEEN_REQUESTS):
        self.min_interval_s = min_interval_s
        self._last_request_at = 0.0

        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT

        # Retry up to 3 times on temporary server errors, waiting 2 s, 4 s, 8 s.
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _wait_turn(self) -> None:
        """Sleep just long enough to respect `min_interval_s`."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET a URL politely. Raises an error if the server answers 4xx/5xx."""
        self._wait_turn()
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT_S)
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response
