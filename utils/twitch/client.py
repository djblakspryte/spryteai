from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .auth import TokenStore

log = logging.getLogger(__name__)


class TwitchAPIError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None) -> None:
        super().__init__(f"Twitch API {status}: {message}")
        self.status = status
        self.message = message
        self.payload = payload


class TwitchAPIClient:
    API = "https://api.twitch.tv/helix"
    ID = "https://id.twitch.tv/oauth2"

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tokens: TokenStore,
    ) -> None:
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tokens = tokens

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        async with self.session.post(f"{self.ID}/token", data=data) as response:
            payload = await self._json(response)
            if response.status != 200:
                raise TwitchAPIError(response.status, self._message(payload), payload)
            return payload

    async def refresh(self, account: str) -> dict[str, Any]:
        current = self.tokens.get(account) or {}
        refresh_token = str(current.get("refresh_token") or "")
        if not refresh_token:
            raise TwitchAPIError(401, f"No refresh token saved for Twitch {account}; authorize it again.")
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with self.session.post(f"{self.ID}/token", data=data) as response:
            payload = await self._json(response)
            if response.status != 200:
                raise TwitchAPIError(response.status, self._message(payload), payload)
            await self.tokens.put(account, payload)
            log.info("Refreshed Twitch %s OAuth token", account)
            return payload

    async def validate_token(self, access_token: str) -> dict[str, Any]:
        headers = {"Authorization": f"OAuth {access_token}"}
        async with self.session.get(f"{self.ID}/validate", headers=headers) as response:
            payload = await self._json(response)
            if response.status != 200:
                raise TwitchAPIError(response.status, self._message(payload), payload)
            return payload

    async def ensure_token(self, account: str) -> str:
        current = self.tokens.get(account) or {}
        access = str(current.get("access_token") or "")
        if not access:
            raise TwitchAPIError(401, f"Twitch {account} account has not been authorized.")
        try:
            validation = await self.validate_token(access)
        except TwitchAPIError as exc:
            if exc.status != 401:
                raise
            refreshed = await self.refresh(account)
            access = str(refreshed["access_token"])
            validation = await self.validate_token(access)
        await self.tokens.put(
            account,
            {
                "user_id": validation.get("user_id"),
                "login": validation.get("login"),
                "scopes": validation.get("scopes", validation.get("scope", [])),
                "expires_in": validation.get("expires_in"),
            },
        )
        return access

    async def request(
        self,
        account: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        retry_auth: bool = True,
    ) -> Any:
        access = await self.ensure_token(account)
        headers = {
            "Authorization": f"Bearer {access}",
            "Client-Id": self.client_id,
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        async with self.session.request(
            method,
            f"{self.API}{path}",
            params=params,
            json=json,
            headers=headers,
        ) as response:
            payload = await self._json(response)
            if response.status == 401 and retry_auth:
                await self.refresh(account)
                return await self.request(
                    account,
                    method,
                    path,
                    params=params,
                    json=json,
                    expected=expected,
                    retry_auth=False,
                )
            if response.status not in expected:
                raise TwitchAPIError(response.status, self._message(payload), payload)
            return payload

    async def create_eventsub(
        self,
        account: str,
        event_type: str,
        version: str,
        condition: dict[str, str],
        session_id: str,
    ) -> None:
        body = {
            "type": event_type,
            "version": version,
            "condition": condition,
            "transport": {"method": "websocket", "session_id": session_id},
        }
        await self.request(account, "POST", "/eventsub/subscriptions", json=body, expected=(202,))

    async def get_user(self, account: str, *, login: str | None = None, user_id: str | None = None) -> dict[str, Any] | None:
        params: dict[str, str] = {}
        if login:
            params["login"] = login.lstrip("@").strip()
        if user_id:
            params["id"] = str(user_id)
        payload = await self.request(account, "GET", "/users", params=params)
        data = payload.get("data") or []
        return data[0] if data else None

    async def get_channel(self, broadcaster_id: str, *, account: str = "broadcaster") -> dict[str, Any] | None:
        payload = await self.request(account, "GET", "/channels", params={"broadcaster_id": broadcaster_id})
        data = payload.get("data") or []
        return data[0] if data else None

    async def get_stream(self, broadcaster_id: str, *, account: str = "broadcaster") -> dict[str, Any] | None:
        payload = await self.request(account, "GET", "/streams", params={"user_id": broadcaster_id})
        data = payload.get("data") or []
        return data[0] if data else None

    async def get_game(self, name: str, *, account: str = "broadcaster") -> dict[str, Any] | None:
        payload = await self.request(account, "GET", "/games", params={"name": name})
        data = payload.get("data") or []
        return data[0] if data else None

    async def modify_channel(self, broadcaster_id: str, *, account: str = "broadcaster", **fields: Any) -> None:
        body = {key: value for key, value in fields.items() if value is not None}
        await self.request(
            account,
            "PATCH",
            "/channels",
            params={"broadcaster_id": broadcaster_id},
            json=body,
            expected=(204,),
        )

    async def send_chat(self, broadcaster_id: str, sender_id: str, message: str, *, reply_to: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "broadcaster_id": broadcaster_id,
            "sender_id": sender_id,
            "message": message[:500],
        }
        if reply_to:
            body["reply_parent_message_id"] = reply_to
        payload = await self.request("bot", "POST", "/chat/messages", json=body)
        data = payload.get("data") or []
        return data[0] if data else {}

    async def announce(self, broadcaster_id: str, message: str, color: str = "primary", *, account: str = "broadcaster") -> None:
        await self.request(
            account,
            "POST",
            "/chat/announcements",
            params={"broadcaster_id": broadcaster_id, "moderator_id": broadcaster_id},
            json={"message": message[:500], "color": color},
            expected=(204,),
        )

    async def shoutout(self, broadcaster_id: str, target_id: str, *, account: str = "broadcaster") -> None:
        await self.request(
            account,
            "POST",
            "/chat/shoutouts",
            params={
                "from_broadcaster_id": broadcaster_id,
                "to_broadcaster_id": target_id,
                "moderator_id": broadcaster_id,
            },
            expected=(204,),
        )

    async def create_clip(self, broadcaster_id: str, *, title: str | None = None, duration: float | None = None, account: str = "broadcaster") -> dict[str, Any]:
        params: dict[str, Any] = {"broadcaster_id": broadcaster_id}
        if title:
            params["title"] = title[:100]
        if duration is not None:
            params["duration"] = max(5.0, min(60.0, float(duration)))
        payload = await self.request(account, "POST", "/clips", params=params, expected=(202,))
        data = payload.get("data") or []
        return data[0] if data else {}

    async def create_poll(self, broadcaster_id: str, question: str, choices: list[str], duration: int, *, account: str = "broadcaster") -> dict[str, Any]:
        payload = await self.request(
            account,
            "POST",
            "/polls",
            json={
                "broadcaster_id": broadcaster_id,
                "title": question[:60],
                "choices": [{"title": choice[:25]} for choice in choices[:5]],
                "duration": max(15, min(1800, int(duration))),
            },
        )
        data = payload.get("data") or []
        return data[0] if data else {}

    async def ban_user(self, broadcaster_id: str, user_id: str, *, duration: int | None = None, reason: str | None = None, account: str = "broadcaster") -> None:
        data: dict[str, Any] = {"user_id": user_id}
        if duration is not None:
            data["duration"] = max(1, min(1_209_600, int(duration)))
        if reason:
            data["reason"] = reason[:500]
        await self.request(
            account,
            "POST",
            "/moderation/bans",
            params={"broadcaster_id": broadcaster_id, "moderator_id": broadcaster_id},
            json={"data": data},
        )

    async def unban_user(self, broadcaster_id: str, user_id: str, *, account: str = "broadcaster") -> None:
        await self.request(
            account,
            "DELETE",
            "/moderation/bans",
            params={"broadcaster_id": broadcaster_id, "moderator_id": broadcaster_id, "user_id": user_id},
            expected=(204,),
        )

    async def get_follow(self, broadcaster_id: str, user_id: str, *, account: str = "broadcaster") -> dict[str, Any] | None:
        payload = await self.request(
            account,
            "GET",
            "/channels/followers",
            params={"broadcaster_id": broadcaster_id, "user_id": user_id},
        )
        data = payload.get("data") or []
        return data[0] if data else None

    @staticmethod
    async def _json(response: aiohttp.ClientResponse) -> Any:
        if response.status == 204:
            return {}
        try:
            return await response.json(content_type=None)
        except Exception:
            return {"message": await response.text()}

    @staticmethod
    def _message(payload: Any) -> str:
        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("error") or payload)
        return str(payload)
