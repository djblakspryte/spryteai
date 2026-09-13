from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp

from .auth import TokenStore, TwitchOAuthServer
from .client import TwitchAPIClient, TwitchAPIError
from .eventsub import EventSubWebSocket

log = logging.getLogger(__name__)

# community_id, event_type, event, subscription
ManagerEventHandler = Callable[[int, str, dict[str, Any], dict[str, Any]], Awaitable[None]]


class TwitchManager:
    """Own Twitch API/OAuth/EventSub state for every SpryteAI community.

    One Twitch bot identity is shared by the deployment.  Each community has its
    own broadcaster OAuth token stored under ``broadcaster:<community_id>`` and
    its own pair of EventSub sockets (broadcaster events + chat events).
    """

    def __init__(
        self,
        *,
        base_dir: Path,
        config: dict[str, Any],
        database: Any,
        event_handler: ManagerEventHandler,
    ) -> None:
        self.base_dir = base_dir
        self.config = config
        self.database = database
        self.event_handler = event_handler
        branding = config.get("branding", {}) if isinstance(config.get("branding"), dict) else {}
        self.brand_name = str(branding.get("name") or "SpryteAI").strip() or "SpryteAI"
        twitch = config.get("twitch", {}) if isinstance(config.get("twitch"), dict) else {}
        self.enabled = bool(twitch.get("enabled", True))
        self.client_id = str(twitch.get("client_id") or "").strip()
        self.client_secret = str(twitch.get("client_secret") or "").strip()
        self.redirect_uri = str(twitch.get("redirect_uri") or "http://localhost:8765/twitch/callback").strip()
        self.callback_host = str(twitch.get("oauth_callback_host") or "127.0.0.1")
        self.callback_port = int(twitch.get("oauth_callback_port") or 8765)
        eventsub = twitch.get("eventsub", {}) if isinstance(twitch.get("eventsub"), dict) else {}
        self.keepalive = int(eventsub.get("keepalive_timeout_seconds") or 30)
        self.eventsub_enabled = bool(eventsub.get("enabled", True))

        token_path = twitch.get("token_store") or "data/twitch_tokens.json"
        self.tokens = TokenStore(base_dir / str(token_path))
        self.session: aiohttp.ClientSession | None = None
        self.api: TwitchAPIClient | None = None
        self.oauth: TwitchOAuthServer | None = None
        self.bot_user: dict[str, Any] | None = None
        self.broadcasters: dict[int, dict[str, Any]] = {}
        self.broadcaster_sockets: dict[int, EventSubWebSocket] = {}
        self.bot_sockets: dict[int, EventSubWebSocket] = {}
        self._start_lock = asyncio.Lock()
        self._socket_lock = asyncio.Lock()

    @staticmethod
    def broadcaster_account(community_id: int) -> str:
        return f"broadcaster:{int(community_id)}"

    async def start(self) -> None:
        async with self._start_lock:
            if self.session is not None:
                return
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            if not self.client_id or not self.client_secret:
                log.warning("Twitch integration is installed but TWITCH_CLIENT_ID/TWITCH_CLIENT_SECRET are not configured")
                return
            self.api = TwitchAPIClient(
                session=self.session,
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                tokens=self.tokens,
            )
            self.oauth = TwitchOAuthServer(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                host=self.callback_host,
                port=self.callback_port,
                exchange_code=self.api.exchange_code,
                validate_token=self.api.validate_token,
                on_authorized=self._on_authorized,
                brand_name=self.brand_name,
            )
            try:
                await self.oauth.start()
            except OSError:
                log.exception("Could not start Twitch OAuth callback server")
            await self._load_identities()
            if self.enabled and self.eventsub_enabled:
                await self.connect_eventsub()

    async def close(self) -> None:
        sockets = [*self.broadcaster_sockets.values(), *self.bot_sockets.values()]
        for socket in sockets:
            await socket.close()
        self.broadcaster_sockets.clear()
        self.bot_sockets.clear()
        self.broadcasters.clear()
        if self.oauth:
            await self.oauth.close()
            self.oauth = None
        if self.session:
            await self.session.close()
            self.session = None
        self.api = None

    async def _validate_account(self, account: str) -> dict[str, Any] | None:
        if not self.api:
            return None
        try:
            token = await self.api.ensure_token(account)
            return await self.api.validate_token(token)
        except TwitchAPIError as exc:
            if exc.status != 401:
                log.warning("Unable to validate Twitch %s token: %s", account, exc)
            return None

    async def _load_identities(self) -> None:
        if not self.api:
            return
        self.bot_user = await self._validate_account("bot")
        self.broadcasters.clear()
        rows = await self.database.list_twitch_communities()
        for row in rows:
            cid = int(row["community_id"])
            account = str(row["oauth_account"] or self.broadcaster_account(cid))
            validation = await self._validate_account(account)
            if validation:
                self.broadcasters[cid] = validation

        # One-time compatibility: if a legacy single-broadcaster token exists,
        # attach it to the first community that has no broadcaster token yet.
        legacy = self.tokens.get("broadcaster")
        if legacy and not self.broadcasters:
            validation = await self._validate_account("broadcaster")
            communities = await self.database.fetch(
                """
                SELECT community_id
                FROM communities
                WHERE enabled=TRUE
                  AND COALESCE((features ->> 'twitch')::BOOLEAN, TRUE)=TRUE
                ORDER BY created_at, community_id
                LIMIT 1
                """
            )
            if validation and communities:
                cid = int(communities[0]["community_id"])
                account = self.broadcaster_account(cid)
                await self.tokens.put(account, dict(legacy))
                await self.database.bind_twitch_channel(
                    cid,
                    str(validation.get("user_id") or ""),
                    str(validation.get("login") or ""),
                    str(validation.get("login") or "") or None,
                    account,
                )
                self.broadcasters[cid] = validation
                log.info("Migrated legacy Twitch broadcaster token into community %s", cid)

    async def _on_authorized(self, account: str, token: dict[str, Any], validation: dict[str, Any]) -> None:
        await self.tokens.put(
            account,
            {
                **token,
                "user_id": validation.get("user_id"),
                "login": validation.get("login"),
                "scopes": validation.get("scopes", []),
            },
        )
        if account == "bot":
            self.bot_user = validation
            log.info("Authorized shared Twitch bot account: %s", validation.get("login"))
            if self.enabled and self.eventsub_enabled:
                await self.connect_eventsub(restart=True)
            return

        if not account.startswith("broadcaster:"):
            raise RuntimeError(f"Unexpected Twitch OAuth account key: {account}")
        try:
            community_id = int(account.split(":", 1)[1])
        except (ValueError, IndexError) as exc:
            raise RuntimeError(f"Invalid Twitch broadcaster account key: {account}") from exc

        await self.database.bind_twitch_channel(
            community_id,
            str(validation.get("user_id") or ""),
            str(validation.get("login") or ""),
            str(validation.get("login") or "") or None,
            account,
        )
        self.broadcasters[community_id] = validation
        log.info("Authorized Twitch broadcaster for community %s: %s", community_id, validation.get("login"))
        if self.enabled and self.eventsub_enabled:
            await self.connect_eventsub(community_id=community_id, restart=True)

    def authorization_url(self, account: str, *, community_id: int | None = None) -> str:
        if not self.oauth:
            raise RuntimeError("Twitch OAuth is unavailable. Configure TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET first.")
        if account == "broadcaster":
            if community_id is None:
                raise ValueError("A Discord community is required to authorize a broadcaster.")
            account = self.broadcaster_account(community_id)
        return self.oauth.authorization_url(account)

    async def connect_eventsub(self, *, community_id: int | None = None, restart: bool = False) -> None:
        if not self.api or not self.session:
            return
        async with self._socket_lock:
            if community_id is None:
                await self._load_identities()
                community_ids = sorted(self.broadcasters)
            else:
                cid = int(community_id)
                account = self.broadcaster_account(cid)
                validation = await self._validate_account(account)
                if validation:
                    self.broadcasters[cid] = validation
                community_ids = [cid]

            for cid in community_ids:
                if cid not in self.broadcasters:
                    continue
                await self._connect_community(cid, restart=restart)

    async def _connect_community(self, community_id: int, *, restart: bool = False) -> None:
        assert self.api is not None and self.session is not None
        cid = int(community_id)
        account = self.broadcaster_account(cid)

        async def handle(event_type: str, event: dict[str, Any], subscription: dict[str, Any]) -> None:
            await self.event_handler(cid, event_type, event, subscription)

        broadcaster_socket = self.broadcaster_sockets.get(cid)
        if broadcaster_socket is None:
            broadcaster_socket = EventSubWebSocket(
                name=f"broadcaster-{cid}",
                session=self.session,
                token_provider=lambda account=account: self.api.ensure_token(account),
                subscribe=lambda et, ver, cond, sid, _tok, account=account: self.api.create_eventsub(account, et, ver, cond, sid),
                subscriptions_provider=lambda cid=cid: self._broadcaster_subscriptions(cid),
                handler=handle,
                keepalive_timeout=self.keepalive,
            )
            self.broadcaster_sockets[cid] = broadcaster_socket
            broadcaster_socket.start()
        elif restart:
            await broadcaster_socket.restart()

        if self.bot_user:
            bot_socket = self.bot_sockets.get(cid)
            if bot_socket is None:
                bot_socket = EventSubWebSocket(
                    name=f"chat-bot-{cid}",
                    session=self.session,
                    token_provider=lambda: self.api.ensure_token("bot"),
                    subscribe=lambda et, ver, cond, sid, _tok: self.api.create_eventsub("bot", et, ver, cond, sid),
                    subscriptions_provider=lambda cid=cid: self._bot_subscriptions(cid),
                    handler=handle,
                    keepalive_timeout=self.keepalive,
                )
                self.bot_sockets[cid] = bot_socket
                bot_socket.start()
            elif restart:
                await bot_socket.restart()

    async def reconnect(self, community_id: int | None = None) -> None:
        await self.connect_eventsub(community_id=community_id, restart=True)

    async def disconnect_community(self, community_id: int) -> None:
        cid = int(community_id)
        for mapping in (self.broadcaster_sockets, self.bot_sockets):
            socket = mapping.pop(cid, None)
            if socket:
                await socket.close()
        self.broadcasters.pop(cid, None)

    async def _broadcaster_subscriptions(self, community_id: int) -> list[tuple[str, str, dict[str, str]]]:
        bid = self.broadcaster_id(community_id)
        if not bid:
            return []
        base = {"broadcaster_user_id": bid}
        return [
            ("stream.online", "1", dict(base)),
            ("stream.offline", "1", dict(base)),
            ("channel.update", "2", dict(base)),
            ("channel.follow", "2", {**base, "moderator_user_id": bid}),
            ("channel.subscribe", "1", dict(base)),
            ("channel.subscription.end", "1", dict(base)),
            ("channel.subscription.gift", "1", dict(base)),
            ("channel.subscription.message", "1", dict(base)),
            ("channel.cheer", "1", dict(base)),
            ("channel.raid", "1", {"to_broadcaster_user_id": bid}),
            ("channel.channel_points_custom_reward_redemption.add", "1", dict(base)),
        ]

    async def _bot_subscriptions(self, community_id: int) -> list[tuple[str, str, dict[str, str]]]:
        bid = self.broadcaster_id(community_id)
        uid = self.bot_id
        if not bid or not uid:
            return []
        condition = {"broadcaster_user_id": bid, "user_id": uid}
        return [
            ("channel.chat.message", "1", dict(condition)),
            ("channel.chat.notification", "1", dict(condition)),
        ]

    def broadcaster(self, community_id: int) -> dict[str, Any] | None:
        return self.broadcasters.get(int(community_id))

    def broadcaster_id(self, community_id: int) -> str:
        cid = int(community_id)
        account = self.broadcaster_account(cid)
        return str((self.broadcaster(cid) or {}).get("user_id") or (self.tokens.get(account) or {}).get("user_id") or "")

    def broadcaster_login(self, community_id: int) -> str:
        cid = int(community_id)
        account = self.broadcaster_account(cid)
        return str((self.broadcaster(cid) or {}).get("login") or (self.tokens.get(account) or {}).get("login") or "")

    @property
    def bot_id(self) -> str:
        return str((self.bot_user or {}).get("user_id") or (self.tokens.get("bot") or {}).get("user_id") or "")

    @property
    def bot_login(self) -> str:
        return str((self.bot_user or {}).get("login") or (self.tokens.get("bot") or {}).get("login") or "")

    def status(self, community_id: int) -> dict[str, Any]:
        cid = int(community_id)
        broadcaster_socket = self.broadcaster_sockets.get(cid)
        bot_socket = self.bot_sockets.get(cid)
        return {
            "enabled": self.enabled,
            "client_configured": bool(self.client_id and self.client_secret),
            "community_id": cid,
            "broadcaster_authorized": bool(self.broadcaster_id(cid)),
            "broadcaster_login": self.broadcaster_login(cid),
            "bot_authorized": bool(self.bot_id),
            "bot_login": self.bot_login,
            "broadcaster_eventsub": bool(broadcaster_socket and broadcaster_socket.connected),
            "bot_eventsub": bool(bot_socket and bot_socket.connected),
            "broadcaster_error": broadcaster_socket.last_error if broadcaster_socket else None,
            "bot_error": bot_socket.last_error if bot_socket else None,
        }

    def require_api(self) -> TwitchAPIClient:
        if not self.api:
            raise RuntimeError("Twitch API is not initialized. Configure Twitch credentials first.")
        return self.api
