from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import WSMsgType, web

log = logging.getLogger(__name__)


POKEMON_OVERLAY_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SpryteAI Pokémon Overlay</title>
<style>
  :root {
    color-scheme: dark;
    --panel-top: rgba(0, 153, 255, .97);
    --panel-bottom: rgba(0, 67, 181, .95);
    --border: rgba(255, 198, 40, .90);
    --shadow: rgba(0, 34, 94, .48);
    --image-bg-top: rgba(255,255,255,.30);
    --image-bg-bottom: rgba(255,255,255,.12);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  body { display: grid; place-items: center; }
  #overlay {
    width: min(96vw, 520px);
    height: min(94vh, 500px);
    min-height: 360px;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto auto;
    place-items: center;
    gap: 8px;
    padding: 18px 20px 16px;
    border: 3px solid var(--border);
    border-radius: 24px;
    background: linear-gradient(180deg, var(--panel-top), var(--panel-bottom));
    box-shadow: 0 18px 60px var(--shadow), inset 0 0 28px rgba(255,255,255,.08);
    opacity: 0;
    transform: translateY(22px) scale(.96);
    transition: opacity .28s ease, transform .28s ease;
    pointer-events: none;
  }
  #overlay.visible { opacity: 1; transform: translateY(0) scale(1); }
  #title { font-size: clamp(24px, 5.4vw, 38px); line-height: 1.05; font-weight: 900; text-align: center; letter-spacing: .02em; color: #fff; text-shadow: 0 3px 14px rgba(0,34,94,.65); }
  #pokemon-wrap {
    width: 100%;
    height: 100%;
    min-height: 230px;
    display: grid;
    place-items: center;
    padding: 8px;
    border-radius: 20px;
    background: radial-gradient(circle at 50% 35%, var(--image-bg-top), var(--image-bg-bottom));
    border: 2px solid rgba(255,255,255,.24);
    overflow: hidden;
  }
  #pokemon {
    width: 100%;
    height: 100%;
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transform: scale(1.12);
    filter: drop-shadow(0 14px 22px rgba(0, 24, 72, .46));
  }
  #hint { font-size: clamp(18px, 4vw, 27px); font-weight: 900; text-align: center; color: #fff; text-shadow: 0 2px 10px rgba(0,34,94,.55); }
  #timer { font-size: clamp(28px, 5.6vw, 40px); font-weight: 900; font-variant-numeric: tabular-nums; color: #ffd34d; text-shadow: 0 2px 10px rgba(0,34,94,.6); }
  #status { position: fixed; left: 8px; bottom: 6px; font-size: 11px; opacity: 0; }
  #overlay.result #pokemon { opacity: .42; transform: scale(.92); transition: opacity .2s ease, transform .2s ease; }
  #overlay.result #hint { font-size: clamp(21px, 4vw, 30px); }
</style>
</head>
<body>
  <main id="overlay" aria-live="polite">
    <div id="title">A WILD POKÉMON APPEARED!</div>
    <div id="pokemon-wrap"><img id="pokemon" alt="Wild Pokémon silhouette"></div>
    <div id="hint">Type !catch &lt;pokemon name&gt;</div>
    <div id="timer">--:--</div>
  </main>
  <div id="status">connecting</div>
<script>
(() => {
  const overlay = document.getElementById('overlay');
  const title = document.getElementById('title');
  const pokemon = document.getElementById('pokemon');
  const hint = document.getElementById('hint');
  const timer = document.getElementById('timer');
  const status = document.getElementById('status');
  const qs = new URLSearchParams(location.search);
  const token = qs.get('token') || '';
  const parts = location.pathname.split('/').filter(Boolean);
  const communityId = parts[parts.length - 1] || '';
  let expiresAt = 0;
  let countdownHandle = null;
  let resultHandle = null;
  let reconnectHandle = null;

  function setVisible(value) {
    overlay.classList.toggle('visible', !!value);
  }

  function stopCountdown() {
    if (countdownHandle) clearInterval(countdownHandle);
    countdownHandle = null;
  }

  function updateTimer() {
    if (!expiresAt) { timer.textContent = '--:--'; return; }
    const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    timer.textContent = `${m}:${String(s).padStart(2, '0')}`;
    if (remaining <= 0) stopCountdown();
  }

  function renderSpawn(data) {
    if (resultHandle) clearTimeout(resultHandle);
    resultHandle = null;
    overlay.classList.remove('result');
    title.textContent = 'A WILD POKÉMON APPEARED!';
    hint.textContent = data.catch_hint || 'Type !catch <pokemon name>';
    expiresAt = Number(data.expires_at_ms || 0);
    const imageId = String(data.image_id || '').trim();
    if (imageId) {
      pokemon.src = `/assets/pokemon/${encodeURIComponent(communityId)}/${encodeURIComponent(imageId)}.png?token=${encodeURIComponent(token)}`;
    } else {
      // Backwards-compatible fallback for an older server payload.
      const version = encodeURIComponent(String(data.image_version || Date.now()));
      pokemon.src = `/assets/pokemon/${encodeURIComponent(communityId)}.png?token=${encodeURIComponent(token)}&v=${version}`;
    }
    pokemon.style.display = '';
    setVisible(true);
    stopCountdown();
    updateTimer();
    countdownHandle = setInterval(updateTimer, 250);
  }

  function renderResult(data) {
    stopCountdown();
    expiresAt = 0;
    overlay.classList.add('result');
    title.textContent = data.outcome === 'escaped' ? 'THE WILD POKÉMON ESCAPED!' : 'GOTCHA!';
    if (data.outcome === 'escaped') {
      hint.textContent = data.pokemon_name ? `${data.pokemon_name} got away!` : 'The wild Pokémon got away!';
    } else {
      const who = data.trainer_name || 'A trainer';
      const mon = data.pokemon_name || 'the Pokémon';
      hint.textContent = `${who} caught ${mon}!`;
    }
    timer.textContent = '';
    setVisible(true);
    if (resultHandle) clearTimeout(resultHandle);
    resultHandle = setTimeout(() => {
      setVisible(false);
      overlay.classList.remove('result');
    }, Math.max(1000, Number(data.display_ms || 4000)));
  }

  function apply(data) {
    if (!data || typeof data !== 'object') return;
    if (data.type === 'spawn' && data.active) renderSpawn(data);
    else if (data.type === 'result') renderResult(data);
    else if (data.type === 'clear' || data.active === false) {
      stopCountdown();
      setVisible(false);
    }
  }

  function connect() {
    if (!token || !communityId) {
      status.textContent = 'invalid overlay URL';
      return;
    }
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${scheme}://${location.host}/ws/pokemon/${encodeURIComponent(communityId)}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    status.textContent = 'connecting';
    ws.onopen = () => { status.textContent = 'connected'; };
    ws.onmessage = (event) => {
      try { apply(JSON.parse(event.data)); } catch (_) {}
    };
    ws.onclose = () => {
      status.textContent = 'reconnecting';
      if (reconnectHandle) clearTimeout(reconnectHandle);
      reconnectHandle = setTimeout(connect, 2000);
    };
    ws.onerror = () => { try { ws.close(); } catch (_) {} };
  }

  connect();
})();
</script>
</body>
</html>
'''


@dataclass(slots=True)
class PokemonOverlayState:
    active: bool = False
    image_png: bytes | None = None
    image_version: int = 0
    image_id: str = ""
    expires_at_ms: int = 0
    catch_hint: str = "Type !catch <pokemon name>"
    last_payload: dict[str, Any] = field(default_factory=lambda: {"type": "clear", "active": False})
    clear_task: asyncio.Task[None] | None = None


class PokemonOverlayServer:
    """Small authenticated OBS Browser Source server for Pokécord spawns."""

    def __init__(self, *, database: Any, config: dict[str, Any]) -> None:
        self.database = database
        overlay_cfg = config.get("overlay", {}) if isinstance(config.get("overlay"), dict) else {}
        self.host = str(os.getenv("OVERLAY_HOST") or overlay_cfg.get("host") or "127.0.0.1")
        try:
            self.port = int(os.getenv("OVERLAY_PORT") or overlay_cfg.get("port") or 8080)
        except (TypeError, ValueError):
            self.port = 8080
        self.public_base_url = str(
            os.getenv("OVERLAY_PUBLIC_BASE_URL")
            or overlay_cfg.get("public_base_url")
            or "https://overlay.spryteai.cc"
        ).rstrip("/")
        try:
            self.result_display_ms = max(1000, int(overlay_cfg.get("result_display_ms", 4000)))
        except (TypeError, ValueError):
            self.result_display_ms = 4000

        self._states: dict[int, PokemonOverlayState] = {}
        self._images: dict[int, dict[str, bytes]] = {}
        self._clients: dict[int, set[web.WebSocketResponse]] = {}
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._started = False
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        return self._started

    def overlay_url(self, community_id: int, token: str) -> str:
        return f"{self.public_base_url}/pokemon/{int(community_id)}?token={token}"

    async def start(self) -> None:
        if self._started:
            return
        app = web.Application(client_max_size=2 * 1024 * 1024)
        app.add_routes(
            [
                web.get("/health", self._health),
                web.get("/pokemon/{community_id}", self._pokemon_page),
                web.get("/ws/pokemon/{community_id}", self._pokemon_ws),
                web.get("/assets/pokemon/{community_id}/{image_id}.png", self._pokemon_image_by_id),
                # Legacy current-image route retained for existing Browser Sources.
                web.get("/assets/pokemon/{community_id}.png", self._pokemon_image),
            ]
        )
        app.on_shutdown.append(self._on_shutdown)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        try:
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
        except Exception:
            await runner.cleanup()
            raise
        self._runner = runner
        self._site = site
        self._started = True
        log.info("Pokémon overlay server listening on http://%s:%s", self.host, self.port)

    async def close(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None
        self._site = None
        self._started = False
        self._clients.clear()

    async def _on_shutdown(self, app: web.Application) -> None:
        clients = [ws for group in self._clients.values() for ws in group]
        if clients:
            await asyncio.gather(
                *(ws.close(code=1001, message=b"SpryteAI shutting down") for ws in clients),
                return_exceptions=True,
            )

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "service": "spryteai-pokemon-overlay"})

    @staticmethod
    def _community_id(request: web.Request) -> int | None:
        try:
            value = int(request.match_info["community_id"])
            return value if value > 0 else None
        except (KeyError, TypeError, ValueError):
            return None

    async def _authorized(self, community_id: int, supplied: str) -> bool:
        supplied = str(supplied or "").strip()
        if not supplied:
            return False
        expected = await self.database.get_overlay_token(community_id, "pokemon")
        return bool(expected and secrets.compare_digest(str(expected), supplied))

    async def _require_auth(self, request: web.Request) -> int:
        community_id = self._community_id(request)
        if community_id is None:
            raise web.HTTPNotFound()
        if not await self._authorized(community_id, request.query.get("token", "")):
            raise web.HTTPForbidden(text="Invalid or expired SpryteAI overlay token")
        return community_id

    async def _pokemon_page(self, request: web.Request) -> web.Response:
        await self._require_auth(request)
        return web.Response(
            text=POKEMON_OVERLAY_HTML,
            content_type="text/html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    async def _pokemon_image(self, request: web.Request) -> web.Response:
        community_id = await self._require_auth(request)
        state = self._states.get(community_id)
        if state is None or not state.image_png:
            raise web.HTTPNotFound(text="No active Pokémon silhouette")
        return web.Response(
            body=state.image_png,
            content_type="image/png",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    async def _pokemon_image_by_id(self, request: web.Request) -> web.Response:
        community_id = await self._require_auth(request)
        image_id = str(request.match_info.get("image_id") or "").strip().lower()
        # SHA-256 IDs are hex; rejecting anything else also prevents path tricks.
        if len(image_id) != 64 or any(ch not in "0123456789abcdef" for ch in image_id):
            raise web.HTTPNotFound(text="Unknown Pokémon silhouette")
        image_png = self._images.get(community_id, {}).get(image_id)
        if not image_png:
            raise web.HTTPNotFound(text="Unknown Pokémon silhouette")
        return web.Response(
            body=image_png,
            content_type="image/png",
            headers={
                # The URL is content-addressed: a given hash always represents
                # exactly one PNG, so it is safe to cache indefinitely.
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{image_id}"',
            },
        )

    async def _pokemon_ws(self, request: web.Request) -> web.StreamResponse:
        community_id = await self._require_auth(request)
        ws = web.WebSocketResponse(heartbeat=25.0, autoping=True)
        await ws.prepare(request)
        self._clients.setdefault(community_id, set()).add(ws)
        state = self._states.get(community_id)
        try:
            await ws.send_json(state.last_payload if state is not None else {"type": "clear", "active": False})
            async for msg in ws:
                if msg.type == WSMsgType.TEXT and msg.data == "ping":
                    await ws.send_str("pong")
                elif msg.type == WSMsgType.ERROR:
                    log.debug("Overlay WebSocket error for community %s: %s", community_id, ws.exception())
                    break
        finally:
            group = self._clients.get(community_id)
            if group is not None:
                group.discard(ws)
                if not group:
                    self._clients.pop(community_id, None)
        return ws

    async def _broadcast(self, community_id: int, payload: dict[str, Any]) -> None:
        clients = list(self._clients.get(int(community_id), set()))
        if not clients:
            return
        results = await asyncio.gather(*(ws.send_json(payload) for ws in clients), return_exceptions=True)
        for ws, result in zip(clients, results):
            if isinstance(result, Exception) or ws.closed:
                self._clients.get(int(community_id), set()).discard(ws)

    async def show_spawn(self, community_id: int, info: dict[str, Any]) -> None:
        community_id = int(community_id)
        image_png = info.get("silhouette_png")
        if isinstance(image_png, bytearray):
            image_png = bytes(image_png)
        if not isinstance(image_png, bytes) or not image_png:
            log.warning("Overlay spawn for community %s has no silhouette PNG; keeping overlay hidden", community_id)
            return
        try:
            seconds = max(1, int(info.get("expires_in") or 180))
        except (TypeError, ValueError):
            seconds = 180
        now_ms = int(time.time() * 1000)
        state = self._states.setdefault(community_id, PokemonOverlayState())
        if state.clear_task is not None and not state.clear_task.done():
            state.clear_task.cancel()
        state.clear_task = None
        state.active = True
        state.image_png = image_png
        state.image_version += 1
        # Content-address the silhouette so the WebSocket event and subsequent
        # HTTP fetch can never drift to a newer community image. Discord and OBS
        # now refer to the exact same rendered PNG bytes.
        image_id = hashlib.sha256(image_png).hexdigest()
        state.image_id = image_id
        images = self._images.setdefault(community_id, {})
        images[image_id] = image_png
        # Keep only a small recent immutable image cache per community.
        while len(images) > 8:
            oldest = next(iter(images))
            if oldest == image_id and len(images) > 1:
                oldest = next(key for key in images if key != image_id)
            images.pop(oldest, None)
        state.expires_at_ms = now_ms + (seconds * 1000)
        state.catch_hint = str(info.get("catch_hint") or "Type !catch <pokemon name>")
        payload = {
            "type": "spawn",
            "active": True,
            "expires_at_ms": state.expires_at_ms,
            "image_version": state.image_version,
            "image_id": state.image_id,
            "catch_hint": state.catch_hint,
        }
        state.last_payload = payload
        await self._broadcast(community_id, payload)
        log.info("Pokémon overlay activated for community %s (%ss, image=%s)", community_id, seconds, state.image_id[:12])

    async def show_result(
        self,
        community_id: int,
        *,
        outcome: str,
        pokemon_name: str | None = None,
        trainer_name: str | None = None,
    ) -> None:
        community_id = int(community_id)
        state = self._states.setdefault(community_id, PokemonOverlayState())
        state.active = False
        payload = {
            "type": "result",
            "active": False,
            "outcome": "escaped" if outcome == "escaped" else "caught",
            "pokemon_name": str(pokemon_name or "").replace("-", " ").title(),
            "trainer_name": str(trainer_name or ""),
            "display_ms": self.result_display_ms,
        }
        state.last_payload = payload
        await self._broadcast(community_id, payload)
        if state.clear_task is not None and not state.clear_task.done():
            state.clear_task.cancel()
        state.clear_task = asyncio.create_task(
            self._clear_result_after(community_id, payload, self.result_display_ms / 1000),
            name=f"pokemon-overlay-clear-{community_id}",
        )
        log.info("Pokémon overlay result for community %s: %s", community_id, payload["outcome"])

    async def _clear_result_after(
        self, community_id: int, payload: dict[str, Any], delay: float
    ) -> None:
        try:
            await asyncio.sleep(max(1.0, delay))
            state = self._states.get(int(community_id))
            if state is None or state.last_payload is not payload:
                return
            state.image_png = None
            state.active = False
            state.last_payload = {"type": "clear", "active": False}
            await self._broadcast(int(community_id), state.last_payload)
        except asyncio.CancelledError:
            raise
        finally:
            state = self._states.get(int(community_id))
            if state is not None and state.clear_task is asyncio.current_task():
                state.clear_task = None

    async def clear(self, community_id: int) -> None:
        community_id = int(community_id)
        state = self._states.setdefault(community_id, PokemonOverlayState())
        if state.clear_task is not None and not state.clear_task.done():
            state.clear_task.cancel()
        state.clear_task = None
        state.active = False
        state.image_png = None
        state.last_payload = {"type": "clear", "active": False}
        await self._broadcast(community_id, state.last_payload)
