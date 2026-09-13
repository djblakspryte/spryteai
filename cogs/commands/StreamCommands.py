from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from config import BRAND_NAME
from services import db

log = logging.getLogger(__name__)

StreamKind = Literal["Gaming", "DJ Set", "Just Chatting", "Special"]
StreamPlatform = Literal["Twitch", "YouTube", "Facebook", "Other"]


def _id(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class StreamCommands(commands.GroupCog, group_name="stream", group_description="Stream announcement tools"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._auto_announced: set[tuple[int, int, str]] = set()

    async def _manage_check(self, interaction: discord.Interaction) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("You need Administrator permission to manage stream announcements.", ephemeral=True)
        return False

    @staticmethod
    def _live_channel(guild: discord.Guild, cfg: dict) -> discord.TextChannel | None:
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        channels = community.get("channels", {}) if isinstance(community.get("channels"), dict) else {}
        live_key = str(community.get("live_channel_key") or "")
        channel_id = _id(channels.get(live_key)) if live_key else 0
        streaming = cfg.get("streaming", {}) if isinstance(cfg.get("streaming"), dict) else {}
        if not channel_id:
            channel_id = _id(streaming.get("live_channel_id"))
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    @staticmethod
    def _alert_roles(guild: discord.Guild, kind: str, cfg: dict) -> list[discord.Role]:
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        role_cfg = community.get("roles", {}) if isinstance(community.get("roles"), dict) else {}
        streaming = cfg.get("streaming", {}) if isinstance(cfg.get("streaming"), dict) else {}
        mapping = streaming.get("alert_role_keys", {}) if isinstance(streaming.get("alert_role_keys"), dict) else {}
        kind_key = kind.casefold().replace(" ", "_")
        keys: list[str] = []
        for bucket in ("default", kind_key):
            values = mapping.get(bucket, [])
            if isinstance(values, list):
                keys.extend(str(value) for value in values)
        roles: list[discord.Role] = []
        for key in dict.fromkeys(keys):
            role = guild.get_role(_id(role_cfg.get(key)))
            if role and role not in roles:
                roles.append(role)
        return roles

    async def _post_announcement(
        self,
        guild: discord.Guild,
        *,
        streamer: discord.abc.User,
        title: str,
        url: str,
        kind: str,
        platform: str,
        description: str | None = None,
        automatic: bool = False,
        thumbnail_url: str | None = None,
        cfg: dict | None = None,
    ) -> discord.Message:
        cfg = cfg or await db.get_community_config_for_guild(guild)
        channel = self._live_channel(guild, cfg)
        if channel is None:
            raise RuntimeError("The live announcement channel is not configured. Run /community setup first.")
        roles = self._alert_roles(guild, kind, cfg)
        embed = discord.Embed(
            title=f"🔴 LIVE NOW — {title}", url=url,
            description=description or f"{streamer.mention} is live. Come hang out!",
            color=discord.Color.red(),
        )
        embed.add_field(name="Stream", value=kind, inline=True)
        embed.add_field(name="Platform", value=platform, inline=True)
        embed.set_footer(text=f"{'Automatically detected by' if automatic else ''} {BRAND_NAME}".strip())
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        elif getattr(streamer, "display_avatar", None) is not None:
            embed.set_thumbnail(url=streamer.display_avatar.url)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=url, emoji="▶️"))
        return await channel.send(
            content=" ".join(role.mention for role in roles) or None,
            embed=embed, view=view,
            allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
        )

    @app_commands.command(name="announce", description="Post a live stream announcement for this community.")
    async def announce(
        self, interaction: discord.Interaction, title: str, url: str,
        kind: StreamKind, platform: StreamPlatform, description: str | None = None,
    ) -> None:
        if not await self._manage_check(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this command inside your server.", ephemeral=True); return
        if not url.startswith(("https://", "http://")):
            await interaction.response.send_message("Please provide a full `https://` stream URL.", ephemeral=True); return
        cid = await db.community_id_for_guild(interaction.guild)
        if not await db.community_feature_enabled(cid, "streaming", True):
            await interaction.response.send_message("Streaming features are disabled for this community.", ephemeral=True); return
        cfg = await db.get_community_config_by_id(cid)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self._post_announcement(
                interaction.guild, streamer=interaction.user, title=title, url=url,
                kind=kind, platform=platform, description=description, cfg=cfg,
            )
        except (RuntimeError, discord.HTTPException) as exc:
            log.exception("Unable to post stream announcement")
            await interaction.followup.send(f"I couldn't post the stream announcement: {exc}", ephemeral=True); return
        await interaction.followup.send(f"Live announcement posted: {message.jump_url}", ephemeral=True)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.guild is None:
            return
        cid = await db.community_id_for_guild(after.guild)
        cfg = await db.get_community_config_by_id(cid)
        streaming = cfg.get("streaming", {}) if isinstance(cfg.get("streaming"), dict) else {}
        if not await db.community_feature_enabled(cid, "streaming", True) or not bool(streaming.get("auto_presence", False)):
            return
        # For a public bot, announce administrators/owners only instead of the deployment owner.
        if not after.guild_permissions.administrator and after.id != after.guild.owner_id:
            return
        before_stream = next((a for a in before.activities if isinstance(a, discord.Streaming)), None)
        after_stream = next((a for a in after.activities if isinstance(a, discord.Streaming)), None)
        if after_stream is None:
            if before_stream is not None:
                self._auto_announced = {x for x in self._auto_announced if not (x[0] == after.guild.id and x[1] == after.id)}
            return
        url = str(after_stream.url or "")
        key = (after.guild.id, after.id, url)
        if before_stream is not None or key in self._auto_announced or not url.startswith(("https://", "http://")):
            return
        text = f"{after_stream.name or ''} {getattr(after_stream, 'details', '') or ''}".casefold()
        kind = "DJ Set" if any(word in text for word in ("dj", "mix", "music", "set")) else "Gaming"
        platform = "Twitch" if "twitch" in url.casefold() else "YouTube" if "youtu" in url.casefold() else "Other"
        title = getattr(after_stream, "details", None) or after_stream.name or f"{after.display_name} is live"
        try:
            await self._post_announcement(after.guild, streamer=after, title=title, url=url, kind=kind, platform=platform, automatic=True, cfg=cfg)
            self._auto_announced.add(key)
        except Exception:
            log.exception("Automatic stream announcement failed for community %s", cid)

    @commands.Cog.listener()
    async def on_twitch_stream_online(self, event: dict) -> None:
        cid = _id(event.get("_community_id"))
        if not cid:
            return
        cfg = await db.get_community_config_by_id(cid)
        twitch_cfg = cfg.get("twitch", {}) if isinstance(cfg.get("twitch"), dict) else {}
        discord_cfg = twitch_cfg.get("discord", {}) if isinstance(twitch_cfg.get("discord"), dict) else {}
        if not await db.community_feature_enabled(cid, "streaming", True) or not bool(discord_cfg.get("announce_live", True)):
            return
        guild_id = await db.primary_guild_id_for_community(cid)
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if guild is None:
            log.warning("Twitch stream.online for community %s has no available Discord guild", cid); return
        channel_info = event.get("channel") or {}
        twitch_user = event.get("user") or {}
        login = str(event.get("broadcaster_user_login") or channel_info.get("broadcaster_login") or twitch_user.get("login") or "")
        display_name = str(event.get("broadcaster_user_name") or channel_info.get("broadcaster_name") or twitch_user.get("display_name") or login or "Streamer")
        title = str(channel_info.get("title") or f"{display_name} is live")
        game = str(channel_info.get("game_name") or "Live")
        url = f"https://www.twitch.tv/{login}" if login else str(twitch_cfg.get("channel_url") or "https://www.twitch.tv/")
        kind = "DJ Set" if any(word in f"{title} {game}".casefold() for word in ("dj", "music", "mix", "just dance")) else "Gaming"
        streamer = guild.owner or guild.me
        if streamer is None:
            return
        key = (guild.id, streamer.id, url)
        if key in self._auto_announced:
            return
        try:
            await self._post_announcement(
                guild, streamer=streamer, title=title, url=url, kind=kind, platform="Twitch",
                description=f"**{display_name}** is live on Twitch playing **{game}**. Come hang out!",
                automatic=True, thumbnail_url=str(twitch_user.get("profile_image_url") or "") or None, cfg=cfg,
            )
            self._auto_announced.add(key)
        except Exception:
            log.exception("Twitch EventSub stream announcement failed for community %s", cid)

    @commands.Cog.listener()
    async def on_twitch_stream_offline(self, event: dict) -> None:
        cid = _id(event.get("_community_id"))
        if not cid:
            return
        guild_id = await db.primary_guild_id_for_community(cid)
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if guild is None:
            return
        self._auto_announced = {x for x in self._auto_announced if x[0] != guild.id}
        cfg = await db.get_community_config_by_id(cid)
        twitch_cfg = cfg.get("twitch", {}) if isinstance(cfg.get("twitch"), dict) else {}
        discord_cfg = twitch_cfg.get("discord", {}) if isinstance(twitch_cfg.get("discord"), dict) else {}
        if not await db.community_feature_enabled(cid, "streaming", True) or not bool(discord_cfg.get("announce_offline", False)):
            return
        channel = self._live_channel(guild, cfg)
        if channel:
            name = str(event.get("broadcaster_user_name") or event.get("broadcaster_user_login") or "The streamer")
            try:
                await channel.send(f"⚫ **{name} is now offline.** Thanks for hanging out!")
            except discord.HTTPException:
                log.exception("Unable to post Twitch offline notice")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StreamCommands(bot))
    log.info("Cog loaded: StreamCommands")
