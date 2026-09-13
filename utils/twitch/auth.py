from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode, urlsplit

from aiohttp import web

log = logging.getLogger(__name__)

BOT_SCOPES = [
    "user:read:chat",
    "user:write:chat",
    "user:bot",
]

BROADCASTER_SCOPES = [
    "channel:bot",
    "channel:manage:broadcast",
    "channel:read:subscriptions",
    "bits:read",
    "channel:manage:redemptions",
    "moderator:read:followers",
    "moderator:manage:announcements",
    "moderator:manage:shoutouts",
    "moderator:manage:banned_users",
    "channel:manage:polls",
    "clips:edit",
]


class TokenStore:
    """Small local encrypted-at-rest-by-OS-permissions token cache.

    The file is intentionally outside config.json and should be ignored by git.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()
        self._seed_from_env()

    def _load(self) -> None:
        try:
            if self.path.is_file():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            log.exception("Unable to read Twitch token store %s", self.path)
            self._data = {}

    def _seed_from_env(self) -> None:
        pairs = {
            "broadcaster": ("TWITCH_BROADCASTER_ACCESS_TOKEN", "TWITCH_BROADCASTER_REFRESH_TOKEN"),
            "bot": ("TWITCH_BOT_ACCESS_TOKEN", "TWITCH_BOT_REFRESH_TOKEN"),
        }
        changed = False
        for account, (access_name, refresh_name) in pairs.items():
            if self._data.get(account, {}).get("access_token"):
                continue
            access = os.getenv(access_name, "").strip()
            refresh = os.getenv(refresh_name, "").strip()
            if access:
                self._data[account] = {
                    "access_token": access,
                    "refresh_token": refresh,
                    "scope": [],
                    "token_type": "bearer",
                }
                changed = True
        if changed:
            self._save_sync()

    def _save_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get(self, account: str) -> dict[str, Any] | None:
        value = self._data.get(account)
        return dict(value) if isinstance(value, dict) else None

    async def put(self, account: str, token: dict[str, Any]) -> None:
        async with self._lock:
            current = dict(self._data.get(account) or {})
            current.update(token)
            self._data[account] = current
            await asyncio.to_thread(self._save_sync)

    async def clear(self, account: str) -> None:
        async with self._lock:
            self._data.pop(account, None)
            await asyncio.to_thread(self._save_sync)


class TwitchOAuthServer:
    def __init__(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        host: str,
        port: int,
        exchange_code: Callable[[str], Awaitable[dict[str, Any]]],
        validate_token: Callable[[str], Awaitable[dict[str, Any]]],
        on_authorized: Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]],
        brand_name: str = "SpryteAI",
    ) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.host = host
        self.port = port
        self.exchange_code = exchange_code
        self.validate_token = validate_token
        self.on_authorized = on_authorized
        self.brand_name = brand_name.strip() or "SpryteAI"
        self._states: dict[str, tuple[str, float]] = {}
        self._launches: dict[str, tuple[str, float]] = {}
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return
        app = web.Application()
        app.router.add_get("/twitch/authorize/{token}", self._authorize_redirect)
        app.router.add_get("/twitch/callback", self._callback)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        self._runner = runner
        log.info("Twitch OAuth callback listening on %s:%s", self.host, self.port)

    async def close(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    def authorization_url(self, account: str) -> str:
        """Return a short, one-time local launch URL safe for a Discord link button.

        The real Twitch authorization URL can exceed Discord's 512-character
        component URL limit once all broadcaster scopes are included.  The
        local launch endpoint redirects to that full URL while preserving the
        normal OAuth state validation used by the callback.
        """
        account_type = account.split(":", 1)[0]
        if account_type not in {"broadcaster", "bot"}:
            raise ValueError("account must be broadcaster[:community_id] or bot")

        now = time.monotonic()
        # Opportunistically remove expired entries whenever a new flow starts.
        self._states = {key: value for key, value in self._states.items() if value[1] >= now}
        self._launches = {key: value for key, value in self._launches.items() if value[1] >= now}

        expires_at = now + 900
        state = secrets.token_urlsafe(32)
        self._states[state] = (account, expires_at)
        scopes = BROADCASTER_SCOPES if account_type == "broadcaster" else BOT_SCOPES
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(scopes),
                "state": state,
                "force_verify": "true",
            }
        )
        twitch_url = f"https://id.twitch.tv/oauth2/authorize?{query}"

        launch_token = secrets.token_urlsafe(18)
        self._launches[launch_token] = (twitch_url, expires_at)
        parsed = urlsplit(self.redirect_uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("TWITCH_REDIRECT_URI must be an absolute http(s) URL")
        return f"{parsed.scheme}://{parsed.netloc}/twitch/authorize/{launch_token}"

    async def _authorize_redirect(self, request: web.Request) -> web.StreamResponse:
        token = request.match_info.get("token", "")
        entry = self._launches.pop(token, None)
        if not entry or entry[1] < time.monotonic():
            return web.Response(
                text=f"{self.brand_name} Twitch authorization link is invalid or expired. Run /twitch authorize again.",
                status=400,
            )
        raise web.HTTPFound(entry[0])

    async def _callback(self, request: web.Request) -> web.Response:
        state = request.query.get("state", "")
        entry = self._states.pop(state, None)
        if not entry or entry[1] < time.monotonic():
            return web.Response(text=f"{self.brand_name} Twitch authorization failed: invalid/expired state.", status=400)
        account = entry[0]
        if request.query.get("error"):
            return web.Response(
                text=f"{self.brand_name} Twitch authorization denied: {request.query.get('error_description') or request.query['error']}",
                status=400,
            )
        code = request.query.get("code")
        if not code:
            return web.Response(text=f"{self.brand_name} Twitch authorization failed: missing code.", status=400)
        try:
            token = await self.exchange_code(code)
            validation = await self.validate_token(str(token["access_token"]))
            await self.on_authorized(account, token, validation)
        except Exception as exc:
            log.exception("Twitch OAuth callback failed")
            return web.Response(text=f"{self.brand_name} Twitch authorization failed: {exc}", status=500)

        return web.Response(
            text=(
                f"{self.brand_name} successfully authorized the Twitch {account} account "
                f"{validation.get('login', '')}. You may close this tab."
            ),
            content_type="text/plain",
        )
