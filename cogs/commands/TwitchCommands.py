from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Literal

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config import BASE_DIR, BRAND_NAME, config
from services import db
from utils.twitch import TwitchAPIError, TwitchManager

log = logging.getLogger(__name__)

TwitchAccount = Literal["broadcaster", "bot"]
AnnouncementColor = Literal["primary", "blue", "green", "orange", "purple"]


def _id(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _truncate(text: str, limit: int = 1000) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


class TwitchCommands(commands.GroupCog, group_name="twitch", group_description="Manage Twitch integration"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = TwitchManager(base_dir=BASE_DIR, config=config, database=db, event_handler=self._handle_event)
        self._startup_task: asyncio.Task[None] | None = None
        self._last_live_event: dict[int, dict] = {}
        self._chat_send_lock = asyncio.Lock()
        self._chat_send_times: deque[float] = deque()
        self._chat_channel_last_sent: dict[int, float] = {}

    async def cog_load(self) -> None:
        self._startup_task = asyncio.create_task(self.manager.start(), name="twitch-manager-start")

    async def cog_unload(self) -> None:
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
        await self.manager.close()

    async def _ensure_started(self) -> None:
        if self._startup_task:
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass
            finally:
                self._startup_task = None
        if self.manager.session is None:
            await self.manager.start()

    async def _community_context(self, interaction: discord.Interaction) -> tuple[int, dict] | None:
        if interaction.guild is None:
            if not interaction.response.is_done():
                await interaction.response.send_message("Run this command inside the Discord community you want to manage.", ephemeral=True)
            return None
        cid = await db.community_id_for_guild(interaction.guild)
        cfg = await db.get_community_config_by_id(cid)
        return cid, cfg

    async def _manage_check(self, interaction: discord.Interaction) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("You need Administrator permission to manage this community's Twitch integration.", ephemeral=True)
        return False

    def _guild_for_community(self, community_id: int) -> discord.Guild | None:
        # Fast path: communities currently default to their primary guild ID.
        guild = self.bot.get_guild(int(community_id))
        return guild

    async def _resolve_guild(self, community_id: int) -> discord.Guild | None:
        guild = self._guild_for_community(community_id)
        if guild:
            return guild
        guild_id = await db.primary_guild_id_for_community(community_id)
        return self.bot.get_guild(guild_id) if guild_id else None

    @staticmethod
    def _community_channel(guild: discord.Guild, cfg: dict, key: str) -> discord.TextChannel | None:
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        channels = community.get("channels", {}) if isinstance(community.get("channels"), dict) else {}
        channel = guild.get_channel(_id(channels.get(key)))
        return channel if isinstance(channel, discord.TextChannel) else None

    @staticmethod
    def _subscriber_role(guild: discord.Guild, cfg: dict) -> discord.Role | None:
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        roles = community.get("roles", {}) if isinstance(community.get("roles"), dict) else {}
        role = guild.get_role(_id(roles.get("subscriber")))
        if role:
            return role
        definitions = community.get("role_definitions", {}) if isinstance(community.get("role_definitions"), dict) else {}
        subscriber = definitions.get("subscriber", {}) if isinstance(definitions.get("subscriber"), dict) else {}
        expected = str(subscriber.get("name") or "Subscriber").casefold()
        return next((item for item in guild.roles if item.name.casefold() == expected), None)

    async def _post_event_embed(
        self, community_id: int, title: str, description: str, *, color: discord.Color | None = None
    ) -> None:
        cfg = await db.get_community_config_by_id(community_id)
        twitch_cfg = cfg.get("twitch", {}) if isinstance(cfg.get("twitch"), dict) else {}
        discord_cfg = twitch_cfg.get("discord", {}) if isinstance(twitch_cfg.get("discord"), dict) else {}
        guild = await self._resolve_guild(community_id)
        if not guild:
            return
        key = str(discord_cfg.get("event_channel_key") or "stream_chat")
        channel = self._community_channel(guild, cfg, key)
        if not channel:
            return
        embed = discord.Embed(title=title, description=description, color=color or discord.Color.purple())
        embed.set_footer(text=f"Twitch • {BRAND_NAME}")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            log.exception("Unable to post Twitch event to Discord community %s", community_id)

    async def _sync_subscriber_role(
        self, community_id: int, twitch_user_id: str, subscribed: bool | None = None
    ) -> bool:
        discord_id = await db.discord_id_for_twitch(community_id, twitch_user_id)
        if not discord_id:
            return False
        guild = await self._resolve_guild(community_id)
        if not guild:
            return False
        cfg = await db.get_community_config_by_id(community_id)
        role = self._subscriber_role(guild, cfg)
        member = guild.get_member(discord_id)
        if not role or not member:
            return False
        if subscribed is None:
            bid = self.manager.broadcaster_id(community_id)
            account = self.manager.broadcaster_account(community_id)
            if not bid:
                return False
            payload = await self.manager.require_api().request(
                account, "GET", "/subscriptions", params={"broadcaster_id": bid, "user_id": twitch_user_id}
            )
            subscribed = bool(payload.get("data"))
        try:
            if subscribed and role not in member.roles:
                await member.add_roles(role, reason=f"Twitch subscription synced by {BRAND_NAME}")
            elif not subscribed and role in member.roles:
                await member.remove_roles(role, reason="Twitch subscription ended")
            return True
        except discord.HTTPException:
            log.exception("Unable to sync Twitch subscriber role for Discord user %s", discord_id)
            return False

    async def _wait_for_chat_slot(self, community_id: int) -> None:
        """Respect Twitch's per-channel and shared bot-account chat limits.

        Twitch applies a 1 message/second per-channel limit to regular chatbot
        accounts and a 20 messages/30 seconds shared limit across the bot user.
        All bot-originated Twitch chat messages pass through _send_chat(), so a
        single serializer here prevents independent EventSub/Pokecord handlers
        from racing each other into HTTP 429 responses.
        """
        cid = int(community_id)
        loop = asyncio.get_running_loop()

        while True:
            now = loop.time()
            while self._chat_send_times and now - self._chat_send_times[0] >= 30.0:
                self._chat_send_times.popleft()

            last = self._chat_channel_last_sent.get(cid)
            channel_wait = 0.0 if last is None else max(0.0, 1.05 - (now - last))

            global_wait = 0.0
            if len(self._chat_send_times) >= 20:
                global_wait = max(0.0, 30.05 - (now - self._chat_send_times[0]))

            wait_for = max(channel_wait, global_wait)
            if wait_for <= 0:
                self._chat_channel_last_sent[cid] = now
                self._chat_send_times.append(now)
                return

            await asyncio.sleep(wait_for)

    async def _send_chat(self, community_id: int, message: str, *, reply_to: str | None = None) -> None:
        bid = self.manager.broadcaster_id(community_id)
        if not bid or not self.manager.bot_id:
            return

        # Twitch's Send Chat Message endpoint accepts at most 500 characters.
        message = _truncate(str(message), 500)

        async with self._chat_send_lock:
            await self._wait_for_chat_slot(community_id)
            try:
                await self.manager.require_api().send_chat(
                    bid, self.manager.bot_id, message, reply_to=reply_to
                )
                return
            except TwitchAPIError as exc:
                if getattr(exc, "status", None) != 429:
                    log.exception("Unable to send Twitch chat message for community %s", community_id)
                    return

                # The local limiter should prevent normal chat-rate violations,
                # but Twitch can still return 429 if another process/session is
                # using the same bot account. Back off once instead of dropping
                # a gameplay event immediately.
                log.warning(
                    "Twitch chat rate limited for community %s; retrying once after backoff",
                    community_id,
                )
                await asyncio.sleep(2.0)
                await self._wait_for_chat_slot(community_id)
                try:
                    await self.manager.require_api().send_chat(
                        bid, self.manager.bot_id, message, reply_to=reply_to
                    )
                except Exception:
                    log.exception(
                        "Unable to send Twitch chat message for community %s after rate-limit retry",
                        community_id,
                    )
            except Exception:
                log.exception("Unable to send Twitch chat message for community %s", community_id)

    async def _handle_event(self, community_id: int, event_type: str, event: dict, subscription: dict) -> None:
        db.activate_community(community_id)
        log.debug("Twitch EventSub community=%s event=%s: %s", community_id, event_type, event)
        cfg = await db.get_community_config_by_id(community_id)
        if not bool((cfg.get("features") or {}).get("twitch", True)):
            return
        twitch_cfg = cfg.get("twitch", {}) if isinstance(cfg.get("twitch"), dict) else {}
        discord_cfg = twitch_cfg.get("discord", {}) if isinstance(twitch_cfg.get("discord"), dict) else {}
        chat_cfg = twitch_cfg.get("chat", {}) if isinstance(twitch_cfg.get("chat"), dict) else {}
        bid = self.manager.broadcaster_id(community_id)
        account = self.manager.broadcaster_account(community_id)

        if event_type == "stream.online":
            self._last_live_event[community_id] = event
            info = dict(event)
            info["_community_id"] = community_id
            try:
                channel = await self.manager.require_api().get_channel(bid, account=account)
                if channel:
                    info["channel"] = channel
                user = await self.manager.require_api().get_user(account, user_id=bid)
                if user:
                    info["user"] = user
            except Exception:
                log.exception("Unable to enrich Twitch stream.online for community %s", community_id)
            self.bot.dispatch("twitch_stream_online", info)
            return

        if event_type == "stream.offline":
            self._last_live_event.pop(community_id, None)
            payload = dict(event)
            payload["_community_id"] = community_id
            self.bot.dispatch("twitch_stream_offline", payload)
            return

        if event_type == "channel.chat.message":
            await self._handle_chat_message(community_id, event, chat_cfg)
            return

        if event_type == "channel.follow":
            name = event.get("user_name") or event.get("user_login") or "Someone"
            if bool(chat_cfg.get("thank_follows", True)):
                await self._send_chat(community_id, f"Thanks for the follow, {name}! 💜")
            if bool(discord_cfg.get("announce_follows", False)):
                await self._post_event_embed(community_id, "💜 New Twitch Follower", f"**{name}** just followed the channel.")
            return

        if event_type == "channel.subscribe":
            name = event.get("user_name") or "A viewer"
            await self._sync_subscriber_role(community_id, str(event.get("user_id") or ""), True)
            if bool(chat_cfg.get("thank_subs", True)):
                await self._send_chat(community_id, f"Thank you for subscribing, {name}! ⭐")
            if bool(discord_cfg.get("announce_subs", True)):
                await self._post_event_embed(community_id, "⭐ New Twitch Subscriber", f"**{name}** subscribed!", color=discord.Color.gold())
            return

        if event_type == "channel.subscription.end":
            await self._sync_subscriber_role(community_id, str(event.get("user_id") or ""), False)
            return

        if event_type == "channel.subscription.gift":
            name = "Anonymous" if event.get("is_anonymous") else (event.get("user_name") or "Someone")
            total = int(event.get("total") or 1)
            if bool(chat_cfg.get("thank_subs", True)):
                await self._send_chat(community_id, f"{name} just gifted {total} sub{'s' if total != 1 else ''}! Thank you! 🎁")
            if bool(discord_cfg.get("announce_subs", True)):
                await self._post_event_embed(community_id, "🎁 Gift Subs!", f"**{name}** gifted **{total}** subscription{'s' if total != 1 else ''}.", color=discord.Color.gold())
            return

        if event_type == "channel.subscription.message":
            name = event.get("user_name") or "A subscriber"
            months = event.get("cumulative_months") or event.get("duration_months") or "?"
            if bool(chat_cfg.get("thank_subs", True)):
                await self._send_chat(community_id, f"Welcome back, {name}! {months} months strong! 💜")
            return

        if event_type == "channel.cheer":
            name = "Anonymous" if event.get("is_anonymous") else (event.get("user_name") or "Someone")
            bits = int(event.get("bits") or 0)
            if bool(chat_cfg.get("thank_cheers", True)):
                await self._send_chat(community_id, f"Thank you {name} for the {bits} Bits! ✨")
            if bool(discord_cfg.get("announce_cheers", True)):
                await self._post_event_embed(community_id, "✨ Twitch Cheer", f"**{name}** cheered **{bits} Bits**.", color=discord.Color.purple())
            return

        if event_type == "channel.raid":
            name = event.get("from_broadcaster_user_name") or "A streamer"
            viewers = int(event.get("viewers") or event.get("viewer_count") or 0)
            if bool(chat_cfg.get("welcome_raids", True)):
                discord_url = str(chat_cfg.get("discord_url") or "").strip()
                suffix = f" Join the Discord: {discord_url}" if discord_url else ""
                await self._send_chat(community_id, f"Welcome raiders from {name}! 🔥 Thanks for bringing {viewers} viewers.{suffix}")
            if bool(discord_cfg.get("announce_raids", True)):
                await self._post_event_embed(community_id, "🔥 RAID INCOMING", f"**{name}** raided with **{viewers}** viewers!", color=discord.Color.red())
            return

        if event_type == "channel.channel_points_custom_reward_redemption.add" and bool(discord_cfg.get("announce_redemptions", False)):
            name = event.get("user_name") or "A viewer"
            reward = (event.get("reward") or {}).get("title") or "Channel Point reward"
            user_input = event.get("user_input") or ""
            text = f"**{name}** redeemed **{reward}**."
            if user_input:
                text += f"\n> {_truncate(user_input, 500)}"
            await self._post_event_embed(community_id, "🎟️ Channel Points", text, color=discord.Color.green())

    async def _handle_chat_message(self, community_id: int, event: dict, chat_cfg: dict) -> None:
        if not bool(chat_cfg.get("enabled", True)):
            return
        chatter_id = str(event.get("chatter_user_id") or "")
        if chatter_id and chatter_id == self.manager.bot_id:
            return
        message = str((event.get("message") or {}).get("text") or "").strip()
        prefix = str(chat_cfg.get("prefix") or "!")
        if not message.startswith(prefix):
            return
        parts = message[len(prefix):].strip().split()
        if not parts:
            return
        command, args = parts[0].casefold(), parts[1:]
        name = str(event.get("chatter_user_name") or event.get("chatter_user_login") or "viewer")
        login = str(event.get("chatter_user_login") or name)
        message_id = str(event.get("message_id") or "") or None
        badges = event.get("badges") or []
        badge_names = {str(item.get("set_id") or "").casefold() for item in badges if isinstance(item, dict)}
        bid = self.manager.broadcaster_id(community_id)
        account = self.manager.broadcaster_account(community_id)
        privileged = chatter_id == bid or bool({"broadcaster", "moderator"} & badge_names)
        static = chat_cfg.get("responses", {}) if isinstance(chat_cfg.get("responses"), dict) else {}

        async def say(text: str) -> None:
            await self._send_chat(community_id, text, reply_to=message_id)

        if command == "commands":
            await say("Commands: !catch !pokemon !list !dex !discord !socials !uptime !followage !lurk !link")
        elif command == "discord":
            await say(str(static.get("discord") or chat_cfg.get("discord_url") or "Discord link is not configured yet."))
        elif command == "socials":
            await say(str(static.get("socials") or f"Follow this community across its configured socials — powered by {BRAND_NAME}."))
        elif command == "lurk":
            await say(f"Thanks for lurking, {name}! 💜")
        elif command == "uptime":
            await self._chat_uptime(community_id, message_id)
        elif command == "followage":
            await self._chat_followage(community_id, chatter_id, name, message_id)
        elif command == "link" and args:
            linked = await db.consume_twitch_link_code(args[0], chatter_id, login, expected_community_id=community_id)
            if linked:
                try:
                    await self._sync_subscriber_role(community_id, chatter_id, None)
                except Exception:
                    log.exception("Initial subscriber-role sync failed after account link")
                await say(f"{name}, your Twitch and Discord accounts are now linked. ✅")
            else:
                await say(f"{name}, that link code is invalid, expired, or belongs to another community.")
        elif command in {"catch", "pokemon", "list", "dex"}:
            if not await db.community_feature_enabled(community_id, "pokecord", True):
                await say("Pokécord is disabled in this community.")
                return
            poke = self.bot.get_cog("PokeCord")
            if poke is None:
                await say("Pokécord is temporarily unavailable.")
                return
            player_id = await db.resolve_twitch_player(community_id, chatter_id, login)
            if command == "catch":
                if not args:
                    await say(f"@{name} use {prefix}catch <pokemon name>")
                else:
                    await say(await poke.twitch_catch(community_id, player_id, name, " ".join(args)))
            elif command == "pokemon":
                await say(await poke.twitch_summary(community_id, player_id, name))
            elif command == "list":
                await say(await poke.twitch_list(community_id, player_id, name))
            else:
                await say(await poke.twitch_dex(community_id, player_id, name))
        elif privileged and command == "title" and args:
            title = " ".join(args)
            await self.manager.require_api().modify_channel(bid, account=account, title=title)
            await self._send_chat(community_id, f"Stream title updated: {title}")
        elif privileged and command == "game" and args:
            game_name = " ".join(args)
            game = await self.manager.require_api().get_game(game_name, account=account)
            if game:
                await self.manager.require_api().modify_channel(bid, account=account, game_id=game["id"])
                await self._send_chat(community_id, f"Category updated to {game['name']}.")
        elif privileged and command == "so" and args:
            user = await self.manager.require_api().get_user(account, login=args[0])
            if user:
                await self.manager.require_api().shoutout(bid, str(user["id"]), account=account)
                await self._send_chat(community_id, f"Go show @{user['login']} some love! 💜")
        elif privileged and command == "clip":
            clip = await self.manager.require_api().create_clip(bid, account=account)
            if clip.get("edit_url"):
                await self._send_chat(community_id, f"Clip created: {clip['edit_url']}")

    async def _chat_uptime(self, community_id: int, reply_to: str | None) -> None:
        bid = self.manager.broadcaster_id(community_id)
        account = self.manager.broadcaster_account(community_id)
        stream = await self.manager.require_api().get_stream(bid, account=account)
        if not stream:
            await self._send_chat(community_id, "The stream is currently offline.", reply_to=reply_to)
            return
        started = datetime.fromisoformat(str(stream["started_at"]).replace("Z", "+00:00"))
        seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
        hours, rem = divmod(seconds, 3600)
        minutes, _ = divmod(rem, 60)
        await self._send_chat(community_id, f"Stream uptime: {hours}h {minutes}m", reply_to=reply_to)

    async def _chat_followage(self, community_id: int, user_id: str, name: str, reply_to: str | None) -> None:
        bid = self.manager.broadcaster_id(community_id)
        account = self.manager.broadcaster_account(community_id)
        follow = await self.manager.require_api().get_follow(bid, user_id, account=account)
        if not follow:
            await self._send_chat(community_id, f"{name} isn't following yet — today's a great day to start! 💜", reply_to=reply_to)
            return
        followed = datetime.fromisoformat(str(follow["followed_at"]).replace("Z", "+00:00"))
        days = max(0, (datetime.now(timezone.utc) - followed).days)
        await self._send_chat(community_id, f"{name} has been following for {days:,} day{'s' if days != 1 else ''}! 💜", reply_to=reply_to)

    async def _shorten_url(self, url: str) -> str:
        """Shorten a long Twitch-facing URL with TinyURL's modern API.

        TinyURL allows link creation through its Free plan. The official API
        requires a bearer token, but avoids the preview/interstitial used by
        TinyURL's deprecated unauthenticated endpoint. If shortening is not
        configured or fails, return the original Discord URL so Pokécord
        spawning is never interrupted.
        """
        original = str(url or "").strip()
        if not original:
            return ""

        twitch_cfg = config.get("twitch", {}) if isinstance(config, dict) else {}
        token = str(
            os.getenv("TINYURL_TOKEN")
            or (twitch_cfg.get("tinyurl_token") if isinstance(twitch_cfg, dict) else "")
            or ""
        ).strip()

        if not token:
            log.warning(
                "TINYURL_TOKEN is not configured; using the original Pokecord silhouette URL"
            )
            return original

        session = self.manager.session
        if session is None or session.closed:
            return original

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.post(
                "https://api.tinyurl.com/create",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "url": original,
                    "domain": "tinyurl.com",
                },
                timeout=timeout,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    body = (await response.text()).strip()
                    log.warning(
                        "Unable to shorten Pokecord silhouette URL with TinyURL "
                        "(HTTP %s, non-JSON response): %s",
                        response.status,
                        body[:200],
                    )
                    return original

                data = payload.get("data") if isinstance(payload, dict) else None
                short_url = str(data.get("tiny_url") or "").strip() if isinstance(data, dict) else ""
                if 200 <= response.status < 300 and short_url.startswith(("https://", "http://")):
                    log.info("Shortened Pokecord silhouette URL with TinyURL: %s", short_url)
                    return short_url

                error = payload.get("errors") if isinstance(payload, dict) else payload
                if isinstance(payload, dict) and not error:
                    error = payload.get("message") or payload
                log.warning(
                    "Unable to shorten Pokecord silhouette URL with TinyURL (HTTP %s): %s",
                    response.status,
                    str(error)[:300],
                )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            log.exception("Unable to shorten Pokecord silhouette URL with TinyURL")

        return original

    @commands.Cog.listener()
    async def on_pokecord_spawn(self, community_id: int, info: dict) -> None:
        await self._ensure_started()
        if not (self.manager.broadcaster_id(community_id) and self.manager.bot_id):
            return

        seconds = int(info.get("expires_in") or 0)
        suffix = f" You have about {seconds}s." if seconds else ""
        silhouette_url = str(info.get("silhouette_url") or "").strip()

        # Send the spawn instruction and silhouette in one Twitch message.
        # Sending them as two immediate messages can trip Twitch's per-channel
        # chat rate limit and cause the URL message to receive HTTP 429.
        spawn_message = f"🌿 A wild Pokémon appeared! Use !catch <pokemon name>.{suffix}"

        if silhouette_url:
            short_url = await self._shorten_url(silhouette_url)
            log.info(
                "Including Pokecord silhouette URL in Twitch spawn message for community %s: %s",
                community_id,
                short_url,
            )
            spawn_message += f"\n🖼️ Silhouette: {short_url}"
        else:
            log.warning(
                "Pokecord spawn for community %s did not include a usable silhouette URL",
                community_id,
            )

        await self._send_chat(community_id, spawn_message)

    @commands.Cog.listener()
    async def on_pokecord_discord_catch(self, community_id: int, info: dict) -> None:
        """Tell Twitch when a Discord trainer wins the shared spawn."""
        await self._ensure_started()
        if not (self.manager.broadcaster_id(community_id) and self.manager.bot_id):
            return

        name = str(info.get("discord_name") or "A Discord trainer")
        pokemon = str(info.get("pokemon_name") or "Pokémon").replace("-", " ").title()
        rarity = str(info.get("rarity") or "Common")
        shiny = " ✨SHINY" if bool(info.get("shiny")) else ""
        await self._send_chat(
            community_id,
            f"🎉 {name} caught {pokemon} in Discord! {rarity}{shiny}. Another wild Pokémon will appear soon.",
        )

    @commands.Cog.listener()
    async def on_pokecord_escape(self, community_id: int, info: dict) -> None:
        """Tell Twitch when nobody catches the shared spawn before it expires."""
        await self._ensure_started()
        if not (self.manager.broadcaster_id(community_id) and self.manager.bot_id):
            return

        pokemon = str(info.get("pokemon_name") or "Pokémon").replace("-", " ").title()
        rarity = str(info.get("rarity") or "Common")
        shiny = " ✨SHINY" if bool(info.get("shiny")) else ""
        await self._send_chat(
            community_id,
            f"💨 The wild {pokemon} escaped! {rarity}{shiny}. Another wild Pokémon will appear soon.",
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)
        message = f"Twitch rejected that request: {original.message}" if isinstance(original, TwitchAPIError) else f"Twitch command failed: {original}"
        if not isinstance(original, TwitchAPIError):
            log.exception("Twitch application command failed", exc_info=(type(original), original, original.__traceback__))
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message[:1900], ephemeral=True)
            else:
                await interaction.response.send_message(message[:1900], ephemeral=True)
        except discord.HTTPException:
            pass

    async def _require_broadcaster(self, interaction: discord.Interaction) -> tuple[int, dict, str, str] | None:
        ctx = await self._community_context(interaction)
        if ctx is None:
            return None
        cid, cfg = ctx
        bid = self.manager.broadcaster_id(cid)
        if not bid:
            await interaction.response.send_message("This community has not authorized a Twitch broadcaster yet. Use `/twitch authorize broadcaster`.", ephemeral=True)
            return None
        return cid, cfg, bid, self.manager.broadcaster_account(cid)

    @app_commands.command(name="authorize", description="Authorize this community's Twitch broadcaster or the shared bot account.")
    async def authorize(self, interaction: discord.Interaction, account: TwitchAccount) -> None:
        await self._ensure_started()
        if account == "bot":
            if not await self.bot.is_owner(interaction.user):
                await interaction.response.send_message(f"Only the deployment owner can authorize the shared {BRAND_NAME} Twitch bot account.", ephemeral=True)
                return
            url = self.manager.authorization_url("bot")
            note = f"Sign into the separate {BRAND_NAME} Twitch bot account."
        else:
            if not await self._manage_check(interaction):
                return
            ctx = await self._community_context(interaction)
            if ctx is None:
                return
            cid, _ = ctx
            url = self.manager.authorization_url("broadcaster", community_id=cid)
            note = "Sign into the Twitch broadcaster account for this Discord community."
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=f"Authorize Twitch {account.title()}", url=url, style=discord.ButtonStyle.link, emoji="🟣"))
        await interaction.response.send_message(
            f"{note}\nThe link expires in about 15 minutes. Open it on the computer running {BRAND_NAME} because the OAuth callback uses localhost.",
            view=view, ephemeral=True,
        )

    @app_commands.command(name="status", description="Show this community's Twitch and EventSub status.")
    async def status(self, interaction: discord.Interaction) -> None:
        ctx = await self._community_context(interaction)
        if ctx is None:
            return
        cid, _ = ctx
        await self._ensure_started()
        state = self.manager.status(cid)
        embed = discord.Embed(title=f"{BRAND_NAME} Twitch Status", color=discord.Color.purple())
        embed.add_field(name="Community", value=f"`{cid}`", inline=True)
        embed.add_field(name="Broadcaster", value=(f"✅ {state['broadcaster_login']}" if state["broadcaster_authorized"] else "❌ Not authorized"), inline=True)
        embed.add_field(name="Bot", value=(f"✅ {state['bot_login']}" if state["bot_authorized"] else "❌ Not authorized"), inline=True)
        embed.add_field(name="Broadcaster EventSub", value="🟢 Connected" if state["broadcaster_eventsub"] else "🔴 Disconnected", inline=True)
        embed.add_field(name="Chat EventSub", value="🟢 Connected" if state["bot_eventsub"] else "🔴 Disconnected", inline=True)
        errors = [str(state[k]) for k in ("broadcaster_error", "bot_error") if state.get(k)]
        if errors:
            embed.add_field(name="Last error", value=_truncate("\n".join(errors), 1000), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reconnect", description="Reconnect this community's Twitch EventSub sockets.")
    async def reconnect(self, interaction: discord.Interaction) -> None:
        if not await self._manage_check(interaction):
            return
        ctx = await self._community_context(interaction)
        if ctx is None:
            return
        cid, _ = ctx
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self._ensure_started()
        await self.manager.reconnect(cid)
        await interaction.followup.send("Twitch EventSub reconnect requested for this community.", ephemeral=True)

    @app_commands.command(name="say", description="Send a message as SpryteAI in this community's Twitch chat.")
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._community_context(interaction)
        if ctx is None: return
        cid, _ = ctx
        await interaction.response.defer(ephemeral=True)
        await self._ensure_started(); await self._send_chat(cid, message)
        await interaction.followup.send("Sent to Twitch chat.", ephemeral=True)

    @app_commands.command(name="title", description="Change this community's Twitch stream title.")
    async def title(self, interaction: discord.Interaction, title: str) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        cid, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True); await self._ensure_started()
        await self.manager.require_api().modify_channel(bid, account=account, title=title[:140])
        await interaction.followup.send(f"Twitch title updated to **{title[:140]}**.", ephemeral=True)

    @app_commands.command(name="game", description="Change this community's Twitch category/game.")
    async def game(self, interaction: discord.Interaction, name: str) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        cid, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        game = await self.manager.require_api().get_game(name, account=account)
        if not game:
            await interaction.followup.send(f"I couldn't find a Twitch category named `{name}`.", ephemeral=True); return
        await self.manager.require_api().modify_channel(bid, account=account, game_id=game["id"])
        await interaction.followup.send(f"Twitch category updated to **{game['name']}**.", ephemeral=True)

    @app_commands.command(name="announcement", description="Send a highlighted Twitch chat announcement.")
    async def announcement(self, interaction: discord.Interaction, message: str, color: AnnouncementColor = "primary") -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True); await self._ensure_started()
        await self.manager.require_api().announce(bid, message, color, account=account)
        await interaction.followup.send("Twitch announcement sent.", ephemeral=True)

    @app_commands.command(name="shoutout", description="Send an official Twitch shoutout.")
    async def shoutout(self, interaction: discord.Interaction, username: str) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        target = await self.manager.require_api().get_user(account, login=username)
        if not target:
            await interaction.followup.send(f"I couldn't find Twitch user `{username}`.", ephemeral=True); return
        await self.manager.require_api().shoutout(bid, str(target["id"]), account=account)
        await interaction.followup.send(f"Shoutout sent to **{target['display_name']}**.", ephemeral=True)

    @app_commands.command(name="clip", description="Create a Twitch clip from this community's live stream.")
    async def clip(self, interaction: discord.Interaction, title: str | None = None, duration: float = 30.0) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        result = await self.manager.require_api().create_clip(bid, title=title, duration=duration, account=account)
        await interaction.followup.send(str(result.get("edit_url") or result.get("url") or "Clip request accepted."), ephemeral=True)

    @app_commands.command(name="poll", description="Create a Twitch poll. Separate choices with | characters.")
    async def poll(self, interaction: discord.Interaction, question: str, choices: str, duration: int = 60) -> None:
        if not await self._manage_check(interaction): return
        options = [item.strip() for item in choices.split("|") if item.strip()]
        if not 2 <= len(options) <= 5:
            await interaction.response.send_message("Provide 2–5 choices separated with `|`.", ephemeral=True); return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        result = await self.manager.require_api().create_poll(bid, question, options, duration, account=account)
        await interaction.followup.send(f"Poll started: **{result.get('title', question)}**", ephemeral=True)

    async def _resolve_twitch_user(self, account: str, username: str) -> dict | None:
        return await self.manager.require_api().get_user(account, login=username)

    @app_commands.command(name="timeout", description="Timeout a Twitch chatter.")
    async def timeout_user(self, interaction: discord.Interaction, username: str, seconds: int = 300, reason: str | None = None) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        target = await self._resolve_twitch_user(account, username)
        if not target: await interaction.followup.send("Twitch user not found.", ephemeral=True); return
        await self.manager.require_api().ban_user(bid, str(target["id"]), duration=seconds, reason=reason, account=account)
        await interaction.followup.send(f"Timed out **{target['display_name']}** for {seconds} seconds.", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a Twitch chatter.")
    async def ban(self, interaction: discord.Interaction, username: str, reason: str | None = None) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        target = await self._resolve_twitch_user(account, username)
        if not target: await interaction.followup.send("Twitch user not found.", ephemeral=True); return
        await self.manager.require_api().ban_user(bid, str(target["id"]), reason=reason, account=account)
        await interaction.followup.send(f"Banned **{target['display_name']}**.", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a Twitch chatter.")
    async def unban(self, interaction: discord.Interaction, username: str) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._require_broadcaster(interaction)
        if ctx is None: return
        _, _, bid, account = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        target = await self._resolve_twitch_user(account, username)
        if not target: await interaction.followup.send("Twitch user not found.", ephemeral=True); return
        await self.manager.require_api().unban_user(bid, str(target["id"]), account=account)
        await interaction.followup.send(f"Unbanned **{target['display_name']}**.", ephemeral=True)

    @app_commands.command(name="link", description="Link your Discord account to your Twitch account in this community.")
    async def link(self, interaction: discord.Interaction) -> None:
        ctx = await self._community_context(interaction)
        if ctx is None: return
        cid, cfg = ctx
        await self._ensure_started()
        if not self.manager.broadcaster_id(cid) or not self.manager.bot_id:
            await interaction.response.send_message("Twitch linking isn't ready until this community's broadcaster and the shared Twitch bot are authorized.", ephemeral=True); return
        code = await db.create_twitch_link_code(interaction.guild, interaction.user)
        twitch_cfg = cfg.get("twitch", {}) if isinstance(cfg.get("twitch"), dict) else {}
        prefix = str((twitch_cfg.get("chat", {}) or {}).get("prefix") or "!")
        login = self.manager.broadcaster_login(cid) or "this community's Twitch channel"
        await interaction.response.send_message(
            f"In **{login}** Twitch chat, type `{prefix}link {code}` within 10 minutes.\nYour Twitch catches and Discord Pokémon will then use the same SpryteAI player.",
            ephemeral=True,
        )

    @app_commands.command(name="unlink", description="Unlink your Discord account from Twitch in this community.")
    async def unlink(self, interaction: discord.Interaction) -> None:
        ctx = await self._community_context(interaction)
        if ctx is None: return
        cid, _ = ctx
        removed = await db.unlink_twitch_for_discord(cid, interaction.user.id)
        await interaction.response.send_message("Twitch account unlinked." if removed else "You didn't have a linked Twitch account in this community.", ephemeral=True)

    @app_commands.command(name="syncroles", description="Resync Subscriber roles for linked Twitch accounts in this community.")
    async def syncroles(self, interaction: discord.Interaction) -> None:
        if not await self._manage_check(interaction): return
        ctx = await self._community_context(interaction)
        if ctx is None: return
        cid, _ = ctx
        await interaction.response.defer(ephemeral=True, thinking=True); await self._ensure_started()
        links = await db.list_twitch_links(cid)
        checked = changed = 0
        for link in links:
            checked += 1
            try:
                if await self._sync_subscriber_role(cid, str(link["twitch_user_id"]), None): changed += 1
            except Exception:
                log.exception("Twitch role sync failed for link %s", dict(link))
        await interaction.followup.send(f"Checked {checked} linked account(s); {changed} role sync(s) completed.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TwitchCommands(bot))
    log.info("Cog loaded: TwitchCommands")
