"""HTTP client wrapper using never-primp."""

import never_primp as primp
from never_primp import IMPERSONATE, IMPERSONATE_OS


class HttpClient:
    """Async HTTP client with browser impersonation."""

    __slots__ = ("_client",)

    def __init__(
        self,
        impersonate: IMPERSONATE | None = "chrome_131",
        impersonate_os: IMPERSONATE_OS | None = "windows",
        timeout: float = 30.0,
    ) -> None:
        self._client = primp.Client(
            impersonate=impersonate,
            impersonate_os=impersonate_os,
            timeout=timeout,
            http2_only=True,
        )

    def get(self, url: str, **kwargs: object) -> object:
        return self._client.get(url, **kwargs)

    def close(self) -> None:
        pass  # primp.Client handles connection pooling internally


class AsyncHttpClient:
    """Async HTTP client for concurrent requests."""

    __slots__ = ("_impersonate", "_impersonate_os", "_timeout")

    _impersonate: IMPERSONATE | None
    _impersonate_os: IMPERSONATE_OS | None
    _timeout: float

    def __init__(
        self,
        impersonate: IMPERSONATE | None = "chrome_131",
        impersonate_os: IMPERSONATE_OS | None = "windows",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._impersonate_os = impersonate_os
        self._timeout = timeout

    async def get(self, url: str, **kwargs: object) -> object:
        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os=self._impersonate_os,
            timeout=self._timeout,
            http2_only=True,
        ) as client:
            return await client.get(url, **kwargs)

    async def get_many(self, urls: list[str]) -> list[object]:
        """Fetch multiple URLs concurrently."""
        import asyncio

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os=self._impersonate_os,
            timeout=self._timeout,
            http2_only=True,
        ) as client:
            tasks = [client.get(url) for url in urls]
            return await asyncio.gather(*tasks, return_exceptions=True)
