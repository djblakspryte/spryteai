from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Awaitable, Callable

import aiohttp

log = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]]


class EventSubWebSocket:
    def __init__(
        self,
        *,
        name: str,
        session: aiohttp.ClientSession,
        token_provider: Callable[[], Awaitable[str]],
        subscribe: Callable[[str, str, dict[str, str], str, str], Awaitable[None]],
        subscriptions_provider: Callable[[], Awaitable[list[tuple[str, str, dict[str, str]]]]],
        handler: EventHandler,
        keepalive_timeout: int = 30,
    ) -> None:
        self.name = name
        self.session = session
        self.token_provider = token_provider
        self.subscribe = subscribe
        self.subscriptions_provider = subscriptions_provider
        self.handler = handler
        self.keepalive_timeout = max(10, min(600, int(keepalive_timeout)))
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        self.connected = False
        self.session_id: str | None = None
        self.last_error: str | None = None
        self._recent_ids: deque[str] = deque(maxlen=512)
        self._recent_set: set[str] = set()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._closing = False
        self._task = asyncio.create_task(self._run(), name=f"twitch-eventsub-{self.name}")

    async def close(self) -> None:
        self._closing = True
        task = self._task
        self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.connected = False
        self.session_id = None

    async def restart(self) -> None:
        await self.close()
        self.start()

    def _remember(self, message_id: str) -> bool:
        if not message_id:
            return True
        if message_id in self._recent_set:
            return False
        if len(self._recent_ids) == self._recent_ids.maxlen:
            old = self._recent_ids.popleft()
            self._recent_set.discard(old)
        self._recent_ids.append(message_id)
        self._recent_set.add(message_id)
        return True

    async def _run(self) -> None:
        base_url = f"wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds={self.keepalive_timeout}"
        url = base_url
        transferred = False
        delay = 2
        while not self._closing:
            try:
                await self.token_provider()  # validate/refresh before connecting
                async with self.session.ws_connect(url, heartbeat=None, autoping=True) as ws:
                    self.connected = True
                    self.last_error = None
                    delay = 2
                    async for message in ws:
                        if message.type != aiohttp.WSMsgType.TEXT:
                            if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                                break
                            continue
                        payload = message.json()
                        metadata = payload.get("metadata") or {}
                        message_type = metadata.get("message_type")
                        message_id = str(metadata.get("message_id") or "")
                        if message_type == "session_welcome":
                            session = payload.get("payload", {}).get("session", {})
                            self.session_id = str(session.get("id") or "") or None
                            if self.session_id and not transferred:
                                await self._subscribe_all(self.session_id)
                            transferred = False
                            log.info("Twitch EventSub %s connected: %s", self.name, self.session_id)
                        elif message_type == "session_reconnect":
                            reconnect_url = payload.get("payload", {}).get("session", {}).get("reconnect_url")
                            if reconnect_url:
                                url = str(reconnect_url)
                                transferred = True
                                break
                        elif message_type == "notification":
                            if not self._remember(message_id):
                                continue
                            body = payload.get("payload") or {}
                            subscription = body.get("subscription") or {}
                            event = body.get("event") or {}
                            try:
                                await self.handler(str(subscription.get("type") or ""), event, subscription)
                            except Exception:
                                log.exception("Twitch EventSub handler failed for %s (%s)", subscription.get("type"), self.name)
                        elif message_type == "revocation":
                            body = payload.get("payload") or {}
                            subscription = body.get("subscription") or {}
                            log.warning(
                                "Twitch EventSub subscription revoked (%s): %s",
                                self.name,
                                subscription,
                            )
                    self.connected = False
                    self.session_id = None
                    if url != base_url and transferred:
                        continue
                    url = base_url
                    transferred = False
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.session_id = None
                self.last_error = str(exc)
                log.exception("Twitch EventSub %s connection failed", self.name)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                url = base_url
                transferred = False

    async def _subscribe_all(self, session_id: str) -> None:
        specs = await self.subscriptions_provider()
        token = await self.token_provider()
        for event_type, version, condition in specs:
            try:
                await self.subscribe(event_type, version, condition, session_id, token)
            except Exception:
                log.exception("Unable to create Twitch EventSub subscription %s (%s)", event_type, self.name)
