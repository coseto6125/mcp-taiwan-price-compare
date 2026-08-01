"""松果購物 (pcone.com.tw) platform implementation."""

from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate


class PconePlatform(BasePlatform[list[dict]]):
    """松果購物 (pcone.com.tw) platform."""

    __slots__ = ("_client", "_impersonate", "_timeout")

    name = "pcone"
    # The API silently ignores a sort field and returns a seed-randomised order, so the
    # pipeline orders the pool it fetches.
    _SEARCH_URL = "https://webapi.pcone.com.tw/api/products/search"
    # The API host (webapi.pcone.com.tw) only serves requests carrying an
    # Origin/Referer from the storefront; it 302-redirects to "/" otherwise.
    _REFERER = "https://pcone.com.tw/search"
    _ORIGIN = "https://pcone.com.tw"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout
        self._client: primp.AsyncClient | None = None

    def _get_client(self) -> "primp.AsyncClient":
        """
        Return a client whose connection is reused across searches.

        Cloudflare routes this host to a Singapore edge, so its round trip is ~0.2s
        against ~0.07s for the other platforms, and a fresh TCP+TLS handshake per
        search costs about 0.4s. Measured over randomised paired runs: 2.42s with a
        per-call client versus 2.00s reusing one. The other platforms show no such
        gain and are left constructing a client per call.
        """
        if self._client is None:
            self._client = primp.AsyncClient(
                impersonate=self._impersonate,
                impersonate_os="windows",
                timeout=self._timeout,
                http2_only=True,
                pool_idle_timeout=300,
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "referer": self._REFERER,
                    "origin": self._ORIGIN,
                },
            )
        return self._client

    async def aclose(self) -> None:
        """
        Close the reused connection. Idempotent, and a later search reopens one.

        Best-effort: primp runs each request on a worker thread, so a request this
        client was cancelled out of by a caller's timeout can still hold the underlying
        handle. The reference is dropped either way and the handle is freed when that
        thread finishes.
        """
        if self._client is not None:
            client, self._client = self._client, None
            with suppress(Exception):
                await client.close()

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[dict] | None:
        """Request the search API and return its product entries."""
        # Fixed pool rather than max_results: the response order is randomised, so the
        # pipeline needs the whole page to find its cheapest members.
        body = {"count": 100, "page": 1, "seed": None, "kw": query}

        with suppress(Exception):
            resp = await self._get_client().post(self._SEARCH_URL, json=body)
            if resp.status_code != 200:
                return None

            data = msgspec.json.decode(resp.content)
            if data.get("status") != "SUCCESS":
                return None
            return (data.get("data") or {}).get("products")
        return None

    def _extract(self, payload: list[dict]) -> Iterator[Candidate]:
        """Read products out of the decoded response."""
        for item in payload:
            display_id, name, url = item.get("display_id"), item.get("name"), item.get("link_url")
            if not (display_id and name and url):
                continue
            yield Candidate(id=str(display_id), name=name, price=item.get("price"), url=url)
