"""Thin client for ESPN's public NFL core API."""

from __future__ import annotations

import platform
import socket
from types import TracebackType
from typing import Any, Iterator

import httpx

from espn.rate_limit import wait_before_espn_request


class ESPNClient:
    """Shared ESPN API settings (no HTTP session)."""

    base_url: str = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"

    def __init__(
        self,
        timeout: float = 30.0,
        host_name: str | None = None,
        host_hardware: str | None = None,
    ) -> None:
        self.host_name = host_name or socket.gethostname()
        self.host_hardware = host_hardware or platform.machine()
        self.name = f"{self.host_name}_{self.host_hardware}"
        self.timeout = timeout


class ESPNEndpoint(ESPNClient):
    """Call a single ESPN resource with optional query params and pagination."""

    def __init__(
        self,
        endpoint: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
        host_name: str | None = None,
        host_hardware: str | None = None,
    ) -> None:
        ESPNClient.__init__(
            self,
            timeout=timeout,
            host_name=host_name,
            host_hardware=host_hardware,
        )
        self.endpoint = endpoint
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": f"StatShift/{self.name}"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> ESPNEndpoint:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _endpoint_url(self) -> str:
        path = self.endpoint.lstrip("/")
        if path and not path.endswith("/"):
            path = f"{path}/"
        return f"{self.base_url}{path}"

    def get(
        self,
        url: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        wait_before_espn_request()
        response = self.client.get(url or self._endpoint_url(), params=params)
        response.raise_for_status()
        return response.json()

    def get_page(
        self,
        *,
        page: int = 1,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch one page. Pass filters via `params` (merged with page/limit)."""
        query = dict(params or {})
        query["page"] = page
        if limit is not None:
            query["limit"] = limit

        return self.get(params=query)

    def iter_pages(
        self,
        *,
        limit: int = 100,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield each paginated JSON response until pageCount is exhausted."""
        page = 1
        pages_fetched = 0

        while True:
            payload = self.get_page(page=page, limit=limit, params=params)
            yield payload

            pages_fetched += 1
            if max_pages is not None and pages_fetched >= max_pages:
                break

            page_count = payload.get("pageCount", 1)
            if page >= page_count:
                break
            page += 1

    def iter_items(
        self,
        *,
        limit: int = 100,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield each item from `items` across pages (usually `{$ref: ...}` links)."""
        for payload in self.iter_pages(
            limit=limit, params=params, max_pages=max_pages
        ):
            yield from payload.get("items", [])

    def resolve_ref(self, item: dict[str, Any]) -> dict[str, Any]:
        """Follow a hypermedia `$ref` link to load full resource JSON."""
        ref = item.get("$ref")
        if not ref:
            raise ValueError("Item has no $ref field")
        return self.get(ref)
