from __future__ import annotations

import asyncio
import copy
import logging
import time
from collections import OrderedDict
from typing import Any

import aiohttp

log = logging.getLogger(__name__)


class PokeAPIError(RuntimeError):
    """Raised when a PokéAPI resource cannot be retrieved."""


class PokeAPIClient:
    """Small async PokéAPI client with bounded TTL caches and request coalescing.

    PokéAPI data is largely immutable, so a long metadata TTL is intentional.
    Binary responses (artwork/sprites) use a shorter cache because they can be
    substantially larger than JSON payloads.
    """

    BASE_URL = "https://pokeapi.co/api/v2"

    def __init__(
        self,
        *,
        json_ttl: int = 6 * 60 * 60,
        bytes_ttl: int = 60 * 60,
        max_json_entries: int = 2_000,
        max_bytes_entries: int = 128,
        timeout: float = 20.0,
    ) -> None:
        self.json_ttl = max(60, int(json_ttl))
        self.bytes_ttl = max(60, int(bytes_ttl))
        self.max_json_entries = max(64, int(max_json_entries))
        self.max_bytes_entries = max(8, int(max_bytes_entries))
        self.timeout = float(timeout)

        self._session: aiohttp.ClientSession | None = None
        self._json_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._bytes_cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._inflight_json: dict[str, asyncio.Task[Any]] = {}
        self._inflight_bytes: dict[str, asyncio.Task[bytes]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._session is not None and not self._session.closed:
            return
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=8, sock_read=15)
        connector = aiohttp.TCPConnector(limit=24, limit_per_host=12, ttl_dns_cache=300)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "SpryteAI-Pokecord/2.0"},
            raise_for_status=False,
        )

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None and not session.closed:
            await session.close()

    async def __aenter__(self) -> "PokeAPIClient":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def _normalize_url(self, resource: str | int) -> str:
        value = str(resource).strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"{self.BASE_URL}/{value.lstrip('/')}"

    @staticmethod
    def _cache_get(cache: OrderedDict[str, tuple[float, Any]], key: str) -> Any | None:
        entry = cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return value

    @staticmethod
    def _cache_put(
        cache: OrderedDict[str, tuple[float, Any]],
        key: str,
        value: Any,
        ttl: int,
        max_entries: int,
    ) -> None:
        cache[key] = (time.monotonic() + ttl, value)
        cache.move_to_end(key)
        while len(cache) > max_entries:
            cache.popitem(last=False)

    async def _request_json(self, url: str) -> Any:
        await self.start()
        assert self._session is not None

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with self._session.get(url) as response:
                    if response.status == 404:
                        raise PokeAPIError(f"PokéAPI resource not found: {url}")
                    if response.status == 429 or 500 <= response.status < 600:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = min(float(retry_after), 5.0)
                            except ValueError:
                                delay = 0.5 * (2**attempt)
                        else:
                            delay = 0.5 * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    if response.status >= 400:
                        body = await response.text()
                        raise PokeAPIError(
                            f"PokéAPI returned HTTP {response.status} for {url}: {body[:160]}"
                        )
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, PokeAPIError) as exc:
                last_error = exc
                if isinstance(exc, PokeAPIError) and "not found" in str(exc).lower():
                    raise
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise PokeAPIError(f"Unable to retrieve PokéAPI resource: {url}") from last_error

    async def _request_bytes(self, url: str) -> bytes:
        await self.start()
        assert self._session is not None

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with self._session.get(url) as response:
                    if response.status == 404:
                        raise PokeAPIError(f"Image resource not found: {url}")
                    if response.status == 429 or 500 <= response.status < 600:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    if response.status >= 400:
                        raise PokeAPIError(f"Image request returned HTTP {response.status}: {url}")
                    return await response.read()
            except (aiohttp.ClientError, asyncio.TimeoutError, PokeAPIError) as exc:
                last_error = exc
                if isinstance(exc, PokeAPIError) and "not found" in str(exc).lower():
                    raise
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise PokeAPIError(f"Unable to retrieve image: {url}") from last_error

    async def get_json(self, resource: str | int, *, fresh: bool = False) -> Any:
        url = self._normalize_url(resource)
        if not fresh:
            cached = self._cache_get(self._json_cache, url)
            if cached is not None:
                # Callers mutate some PokéAPI payloads (uid/form/shiny), so never
                # expose the cached object directly.
                return copy.deepcopy(cached)

        async with self._lock:
            if not fresh:
                cached = self._cache_get(self._json_cache, url)
                if cached is not None:
                    return copy.deepcopy(cached)
            task = self._inflight_json.get(url)
            if task is None:
                task = asyncio.create_task(self._request_json(url))
                self._inflight_json[url] = task

        try:
            value = await task
        finally:
            async with self._lock:
                if self._inflight_json.get(url) is task:
                    self._inflight_json.pop(url, None)

        self._cache_put(self._json_cache, url, value, self.json_ttl, self.max_json_entries)
        return copy.deepcopy(value)

    async def get_bytes(self, url: str, *, fresh: bool = False) -> bytes:
        if not fresh:
            cached = self._cache_get(self._bytes_cache, url)
            if cached is not None:
                return cached

        async with self._lock:
            if not fresh:
                cached = self._cache_get(self._bytes_cache, url)
                if cached is not None:
                    return cached
            task = self._inflight_bytes.get(url)
            if task is None:
                task = asyncio.create_task(self._request_bytes(url))
                self._inflight_bytes[url] = task

        try:
            value = await task
        finally:
            async with self._lock:
                if self._inflight_bytes.get(url) is task:
                    self._inflight_bytes.pop(url, None)

        self._cache_put(self._bytes_cache, url, value, self.bytes_ttl, self.max_bytes_entries)
        return value

    async def pokemon(self, identifier: str | int) -> dict[str, Any]:
        return await self.get_json(f"pokemon/{identifier}/")

    async def species(self, identifier: str | int) -> dict[str, Any]:
        return await self.get_json(f"pokemon-species/{identifier}/")

    async def item(self, identifier: str | int) -> dict[str, Any]:
        return await self.get_json(f"item/{identifier}/")

    async def move(self, identifier: str | int) -> dict[str, Any]:
        return await self.get_json(f"move/{identifier}/")

    async def evolution_chain_for(self, pokemon_data: dict[str, Any]) -> dict[str, Any]:
        species_data = await self.get_json(pokemon_data["species"]["url"])
        return await self.get_json(species_data["evolution_chain"]["url"])

    @staticmethod
    def artwork_url(pokemon_data: dict[str, Any], *, shiny: bool = False) -> str | None:
        sprites = pokemon_data.get("sprites") or {}
        other = sprites.get("other") or {}
        official = other.get("official-artwork") or {}
        home = other.get("home") or {}
        showdown = other.get("showdown") or {}

        keys = ("front_shiny", "front_default") if shiny else ("front_default", "front_shiny")
        for source in (official, home, sprites, showdown):
            for key in keys:
                url = source.get(key) if isinstance(source, dict) else None
                if url:
                    return str(url)
        return None

    @property
    def cache_stats(self) -> dict[str, int]:
        return {
            "json": len(self._json_cache),
            "bytes": len(self._bytes_cache),
            "inflight_json": len(self._inflight_json),
            "inflight_bytes": len(self._inflight_bytes),
        }
