from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands

from config import BRAND_NAME, config
from services import db
from utils import helpers

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InviteSnapshot:
    code: str
    uses: int
    inviter_id: int | None
    inviter_name: str
    channel_id: int | None
    max_uses: int
    is_vanity: bool = False


class Invites(commands.Cog):
    """Track invite usage, member attribution, and invite statistics."""

    ATTRIBUTION_TTL_SECONDS = 15.0

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._invite_cache: dict[int, dict[str, InviteSnapshot]] = {}
        self._pending_attribution: dict[int, deque[tuple[InviteSnapshot, float]]] = defaultdict(deque)
        self._guild_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._reaction_invite_requests: dict[int, int] = {}
        self._schema_lock = asyncio.Lock()
        self._schema_ready = False

    async def cog_load(self) -> None:
        if not self.bot.intents.members:
            log.warning(
                "Invite tracking requires the Server Members intent for member join/remove events."
            )
        try:
            await self._ensure_schema()
        except RuntimeError:
            # Some deployments load extensions before the DB pool has started.
            # on_ready() will retry after startup completes.
            log.debug("Invite attribution schema deferred until bot ready")

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_invite_attributions (
                    guild_id BIGINT NOT NULL,
                    member_id BIGINT NOT NULL,
                    invite_code TEXT,
                    inviter_id BIGINT,
                    inviter_name TEXT,
                    is_vanity BOOLEAN NOT NULL DEFAULT FALSE,
                    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (guild_id, member_id)
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_discord_invite_attributions_inviter
                ON discord_invite_attributions (guild_id, inviter_id)
                """
            )
            self._schema_ready = True

    async def _community_config(self, guild: discord.Guild) -> dict:
        try:
            community_id = await db.community_id_for_guild(guild)
            return await db.get_community_config_by_id(community_id)
        except Exception:
            log.exception("Unable to load community config for guild %s", guild.id)
            return config

    @staticmethod
    def _channel_id_from_config(cfg: dict, key: str) -> int:
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        channels = community.get("channels", {}) if isinstance(community.get("channels"), dict) else {}

        candidates = (
            channels.get(key),
            channels.get(f"{key}_log"),
            cfg.get(f"{key}_chan_id"),
            config.get(f"{key}_chan_id"),
        )
        for value in candidates:
            try:
                channel_id = int(value or 0)
            except (TypeError, ValueError):
                continue
            if channel_id:
                return channel_id
        return 0

    async def _log_channel(self, guild: discord.Guild, kind: str) -> discord.abc.Messageable | None:
        cfg = await self._community_config(guild)
        key = "welcome" if kind == "join" else "leave"
        channel_id = self._channel_id_from_config(cfg, key)
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
        if channel is not None and getattr(channel, "guild", guild).id == guild.id:
            return channel

        try:
            fetched = await self.bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        return fetched if getattr(fetched, "guild", guild).id == guild.id else None

    async def _embed_footer(self, guild: discord.Guild) -> str:
        cfg = await self._community_config(guild)
        bot_cfg = cfg.get("bot", {}) if isinstance(cfg.get("bot"), dict) else {}
        return str(
            cfg.get("embed_footer")
            or bot_cfg.get("embed_footer")
            or config.get("embed_footer")
            or f"Powered by {BRAND_NAME}"
        )

    @staticmethod
    def _snapshot_from_invite(invite: discord.Invite, *, vanity: bool = False) -> InviteSnapshot:
        inviter = None if vanity else invite.inviter
        channel = getattr(invite, "channel", None)
        return InviteSnapshot(
            code=str(invite.code),
            uses=max(0, int(invite.uses or 0)),
            inviter_id=int(inviter.id) if inviter is not None else None,
            inviter_name=(getattr(inviter, "display_name", None) or getattr(inviter, "name", None) or "Unknown")
            if inviter is not None
            else "VANITY",
            channel_id=int(channel.id) if channel is not None and getattr(channel, "id", None) is not None else None,
            max_uses=max(0, int(invite.max_uses or 0)),
            is_vanity=vanity,
        )

    async def _fetch_invite_snapshot(self, guild: discord.Guild) -> dict[str, InviteSnapshot] | None:
        me = guild.me
        if me is not None and not me.guild_permissions.manage_guild:
            log.warning(
                "Invite tracking unavailable for guild %s (%s): bot is missing Manage Server",
                guild.id,
                guild.name,
            )
            return None

        try:
            invites = await guild.invites()
        except discord.Forbidden:
            log.warning("Unable to read invites for guild %s: missing Manage Server", guild.id)
            return None
        except discord.HTTPException:
            log.exception("Unable to fetch invites for guild %s", guild.id)
            return None

        snapshot = {
            invite.code: self._snapshot_from_invite(invite)
            for invite in invites
        }

        try:
            vanity = await guild.vanity_invite()
        except (discord.Forbidden, discord.HTTPException):
            vanity = None

        if vanity is not None:
            snapshot[vanity.code] = self._snapshot_from_invite(vanity, vanity=True)

        return snapshot

    async def _prime_guild(self, guild: discord.Guild) -> bool:
        snapshot = await self._fetch_invite_snapshot(guild)
        if snapshot is None:
            return False
        self._invite_cache[guild.id] = snapshot
        self._pending_attribution[guild.id].clear()
        log.info("Invite cache primed for guild %s with %d invite(s)", guild.id, len(snapshot))
        return True

    def _queue_delta(self, guild_id: int, snapshot: InviteSnapshot, old_uses: int, delta: int) -> None:
        now = time.monotonic()
        # Preserve each observed use separately. This helps when several members
        # join through the same invite before Discord returns the next event.
        for offset in range(1, max(0, delta) + 1):
            self._pending_attribution[guild_id].append(
                (
                    InviteSnapshot(
                        code=snapshot.code,
                        uses=old_uses + offset,
                        inviter_id=snapshot.inviter_id,
                        inviter_name=snapshot.inviter_name,
                        channel_id=snapshot.channel_id,
                        max_uses=snapshot.max_uses,
                        is_vanity=snapshot.is_vanity,
                    ),
                    now,
                )
            )

    def _pop_pending(self, guild_id: int) -> InviteSnapshot | None:
        queue = self._pending_attribution[guild_id]
        now = time.monotonic()
        while queue and now - queue[0][1] > self.ATTRIBUTION_TTL_SECONDS:
            queue.popleft()
        return queue.popleft()[0] if queue else None

    async def _detect_used_invite(self, guild: discord.Guild) -> InviteSnapshot | None:
        async with self._guild_locks[guild.id]:
            fresh = await self._fetch_invite_snapshot(guild)
            if fresh is None:
                return self._pop_pending(guild.id)

            previous = self._invite_cache.get(guild.id)
            if previous is None:
                # Never treat a first snapshot as historical usage. This avoids
                # attributing an old invite's lifetime use count to a new member.
                self._invite_cache[guild.id] = fresh
                return None

            for code, current in fresh.items():
                old = previous.get(code)
                old_uses = old.uses if old is not None else 0
                if current.uses > old_uses:
                    self._queue_delta(guild.id, current, old_uses, current.uses - old_uses)

            # A max-use invite can disappear immediately after its final use.
            # Detect only the unambiguous "one use remaining" case to avoid
            # confusing manual deletions/expiry with a member join.
            for code, old in previous.items():
                if code in fresh or old.is_vanity or old.max_uses <= 0:
                    continue
                if old.uses + 1 == old.max_uses:
                    self._queue_delta(
                        guild.id,
                        InviteSnapshot(
                            code=old.code,
                            uses=old.max_uses,
                            inviter_id=old.inviter_id,
                            inviter_name=old.inviter_name,
                            channel_id=old.channel_id,
                            max_uses=old.max_uses,
                            is_vanity=False,
                        ),
                        old.uses,
                        1,
                    )

            self._invite_cache[guild.id] = fresh
            return self._pop_pending(guild.id)

    async def _save_attribution(self, member: discord.Member, invite: InviteSnapshot | None) -> None:
        await self._ensure_schema()
        # Ensure the normal user row exists before updating InviteCode.
        await db.get_player_postgresData(member, member.guild)

        invite_code = invite.code if invite is not None else None
        await db.execute(
            'UPDATE users SET "InviteCode"=$1 WHERE "ServerID"=$2 AND "UserID"=$3',
            invite_code,
            int(member.guild.id),
            int(member.id),
        )

        if invite is None:
            await db.execute(
                "DELETE FROM discord_invite_attributions WHERE guild_id=$1 AND member_id=$2",
                int(member.guild.id),
                int(member.id),
            )
            return

        await db.execute(
            """
            INSERT INTO discord_invite_attributions
                (guild_id, member_id, invite_code, inviter_id, inviter_name, is_vanity, joined_at)
            VALUES ($1,$2,$3,$4,$5,$6,NOW())
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET invite_code=EXCLUDED.invite_code,
                inviter_id=EXCLUDED.inviter_id,
                inviter_name=EXCLUDED.inviter_name,
                is_vanity=EXCLUDED.is_vanity,
                joined_at=NOW()
            """,
            int(member.guild.id),
            int(member.id),
            invite.code,
            invite.inviter_id,
            invite.inviter_name,
            bool(invite.is_vanity),
        )

    async def _load_attribution(self, guild_id: int, member_id: int):
        await self._ensure_schema()
        return await db.fetchrow(
            """
            SELECT invite_code, inviter_id, inviter_name, is_vanity
            FROM discord_invite_attributions
            WHERE guild_id=$1 AND member_id=$2
            """,
            int(guild_id),
            int(member_id),
        )

    async def _active_inviter_uses(self, guild: discord.Guild, inviter_id: int | None) -> int:
        if inviter_id is None:
            return 0
        snapshot = self._invite_cache.get(guild.id)
        if snapshot is None:
            fresh = await self._fetch_invite_snapshot(guild)
            if fresh is None:
                return 0
            snapshot = fresh
            self._invite_cache[guild.id] = fresh
        return sum(i.uses for i in snapshot.values() if i.inviter_id == inviter_id)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        try:
            await self._ensure_schema()
        except Exception:
            log.exception("Unable to initialize invite attribution schema")
            return

        for guild in self.bot.guilds:
            try:
                await self._prime_guild(guild)
            except Exception:
                log.exception("Unable to prime invite cache for guild %s", guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self._prime_guild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._invite_cache.pop(guild.id, None)
        self._pending_attribution.pop(guild.id, None)
        self._guild_locks.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        used = await self._detect_used_invite(member.guild)
        await self._save_attribution(member, used)

        channel = await self._log_channel(member.guild, "join")
        if channel is None:
            return

        if used is None:
            await channel.send(
                f"{member.mention} **joined**; I couldn't determine which invite was used.\n"
                f"Members: {member.guild.member_count or 'Unknown'}"
            )
            return

        inviter_name = "Vanity URL" if used.is_vanity else used.inviter_name
        await channel.send(
            f"{member.mention} **joined**; Invited by **{inviter_name}** "
            f"[{used.uses} invite use(s)]\nMembers: {member.guild.member_count or 'Unknown'}"
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        row = await self._load_attribution(member.guild.id, member.id)
        channel = await self._log_channel(member.guild, "leave")
        if channel is None:
            return

        if row is None:
            await channel.send(
                f"**{member.display_name}** left; I don't have an invite attribution for them.\n"
                f"Members: {member.guild.member_count or 'Unknown'}"
            )
            return

        is_vanity = bool(row["is_vanity"])
        inviter_id = int(row["inviter_id"]) if row["inviter_id"] is not None else None
        inviter_name = "Vanity URL" if is_vanity else str(row["inviter_name"] or "Unknown")
        total_uses = await self._active_inviter_uses(member.guild, inviter_id)
        usage_text = "" if is_vanity else f" [{total_uses} active invite use(s)]"
        await channel.send(
            f"**{member.display_name}** left; originally invited by **{inviter_name}**{usage_text}\n"
            f"Members: {member.guild.member_count or 'Unknown'}"
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if guild is None:
            return
        snapshot = self._snapshot_from_invite(invite)
        self._invite_cache.setdefault(guild.id, {})[invite.code] = snapshot
        log.info(
            "Invite created guild=%s code=%s inviter=%s",
            guild.id,
            invite.code,
            snapshot.inviter_id,
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if guild is None:
            return
        self._invite_cache.setdefault(guild.id, {}).pop(invite.code, None)
        log.info("Invite deleted guild=%s code=%s", guild.id, invite.code)

    @commands.hybrid_group(
        name="invites",
        fallback="stats",
        invoke_without_command=True,
        description="View and manage Discord invites.",
    )
    @commands.guild_only()
    async def invites(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        """Show invite statistics for yourself or another member."""
        member = member or ctx.author
        if not isinstance(member, discord.Member):
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        try:
            live_invites = await ctx.guild.invites()
        except discord.Forbidden:
            await ctx.send("I need **Manage Server** to read server invites.", ephemeral=True)
            return
        except discord.HTTPException:
            await ctx.send("Discord did not return the server's invites. Try again shortly.", ephemeral=True)
            return

        owned = [
            invite
            for invite in live_invites
            if invite.inviter is not None and invite.inviter.id == member.id
        ]
        total_uses = sum(int(invite.uses or 0) for invite in owned)

        colour = member.colour if member.colour.value else discord.Colour.blurple()
        embed = discord.Embed(color=colour, title=f"Invite Statistics — {member.display_name}")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=await self._embed_footer(ctx.guild))

        for invite in sorted(owned, key=lambda inv: int(inv.uses or 0), reverse=True)[:20]:
            channel_name = getattr(invite.channel, "name", None) or str(invite.channel)
            invite_type = getattr(getattr(invite, "type", None), "name", None)
            type_text = f" · {invite_type.replace('_', ' ').title()}" if invite_type else ""
            embed.add_field(
                name=f"#{channel_name} · {invite.code}{type_text}",
                value=f"Uses: **{int(invite.uses or 0):,}**",
                inline=False,
            )

        if not owned:
            embed.description = "No active invites created by this member were found."
            if member.id == ctx.author.id:
                embed.description += "\nReact with ➕ below to create one for this channel."
        else:
            embed.description = (
                f"Active invites: **{len(owned):,}**\n"
                f"Total active invite uses: **{total_uses:,}**"
            )
            if len(owned) > 20:
                embed.description += f"\nShowing the 20 most-used of {len(owned):,} active invites."

        msg = await ctx.send(embed=embed)
        if not owned and member.id == ctx.author.id and isinstance(msg, discord.Message):
            self._reaction_invite_requests[msg.id] = ctx.author.id
            try:
                await msg.add_reaction("➕")
            except discord.HTTPException:
                self._reaction_invite_requests.pop(msg.id, None)

    @invites.command(name="refresh", aliases=["init"])
    @helpers.is_creator()
    async def invite_refresh(self, ctx: commands.Context) -> None:
        """Owner: refresh the invite cache for this server."""
        ok = await self._prime_guild(ctx.guild)
        if ok:
            await ctx.send(f"✅ Invite cache refreshed with **{len(self._invite_cache.get(ctx.guild.id, {}))}** invite(s).")
        else:
            await ctx.send("❌ I couldn't refresh invites. Make sure I have **Manage Server**.", ephemeral=True)

    @invites.command(name="leaderboard", aliases=["lead"])
    async def leaderboard(self, ctx: commands.Context, number: int = 10) -> None:
        """Show the members whose active invites have the most uses."""
        number = max(1, min(int(number), 20))
        try:
            live_invites = await ctx.guild.invites()
        except discord.Forbidden:
            await ctx.send("I need **Manage Server** to read server invites.", ephemeral=True)
            return
        except discord.HTTPException:
            await ctx.send("Discord did not return the server's invites. Try again shortly.", ephemeral=True)
            return

        totals: dict[int, dict[str, object]] = {}
        for invite in live_invites:
            inviter = invite.inviter
            if inviter is None:
                continue
            entry = totals.setdefault(
                inviter.id,
                {
                    "name": getattr(inviter, "display_name", None) or inviter.name,
                    "uses": 0,
                    "count": 0,
                },
            )
            entry["uses"] = int(entry["uses"]) + int(invite.uses or 0)
            entry["count"] = int(entry["count"]) + 1

        ranked = sorted(
            totals.values(),
            key=lambda row: (int(row["uses"]), str(row["name"]).lower()),
            reverse=True,
        )[:number]

        embed = discord.Embed(
            title=f"Top {number} Invite Leaderboard",
            color=ctx.author.colour if isinstance(ctx.author, discord.Member) and ctx.author.colour.value else discord.Colour.blurple(),
        )
        embed.set_footer(text=await self._embed_footer(ctx.guild))

        if not ranked:
            embed.description = "No active member-created invites were found."
        else:
            for index, row in enumerate(ranked, start=1):
                embed.add_field(
                    name=f"#{index}. {row['name']}",
                    value=f"Uses: **{int(row['uses']):,}** · Active invites: **{int(row['count']):,}**",
                    inline=False,
                )

        await ctx.send(embed=embed)

    @invites.command(name="create")
    async def create_invite_command(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        max_age: int = 0,
        max_uses: int = 0,
        temporary: bool = False,
        unique: bool = True,
        guest: bool = False,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Create an invite using Discord's current invite API."""
        channel = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if channel is None:
            await ctx.send("Choose a text channel for the invite.", ephemeral=True)
            return

        if not channel.permissions_for(ctx.author).create_instant_invite:
            await ctx.send("You don't have permission to create invites in that channel.", ephemeral=True)
            return
        if ctx.guild.me is None or not channel.permissions_for(ctx.guild.me).create_instant_invite:
            await ctx.send("I don't have permission to create invites in that channel.", ephemeral=True)
            return

        max_age = max(0, int(max_age))
        max_uses = max(0, int(max_uses))
        audit_reason = reason or f"Invite requested by {ctx.author} ({ctx.author.id})"

        try:
            invite = await channel.create_invite(
                max_age=max_age,
                max_uses=max_uses,
                temporary=bool(temporary),
                unique=bool(unique),
                guest=bool(guest),
                reason=audit_reason,
            )
        except discord.Forbidden:
            await ctx.send("Discord denied the invite creation request due to permissions.", ephemeral=True)
            return
        except discord.HTTPException as exc:
            log.exception("Unable to create invite in channel %s", channel.id)
            await ctx.send(f"Discord rejected the invite request: `{exc}`", ephemeral=True)
            return

        self._invite_cache.setdefault(ctx.guild.id, {})[invite.code] = self._snapshot_from_invite(invite)
        await ctx.send(f"✅ Invite created: {invite.url}")

    async def _create_reaction_invite(self, payload: discord.RawReactionActionEvent) -> None:
        requester_id = self._reaction_invite_requests.get(payload.message_id)
        if requester_id is None or requester_id != payload.user_id:
            return
        if payload.guild_id is None or payload.emoji.name != "➕":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if member.bot or not channel.permissions_for(member).create_instant_invite:
            return
        if guild.me is None or not channel.permissions_for(guild.me).create_instant_invite:
            return

        try:
            invite = await channel.create_invite(
                unique=True,
                reason=f"Invite requested by reaction from {member} ({member.id})",
            )
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Unable to create reaction invite in channel %s", channel.id)
            return

        self._reaction_invite_requests.pop(payload.message_id, None)
        self._invite_cache.setdefault(guild.id, {})[invite.code] = self._snapshot_from_invite(invite)
        await channel.send(f"{member.mention} invite created: {invite.url}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if self.bot.user is not None and payload.user_id == self.bot.user.id:
            return
        await self._create_reaction_invite(payload)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        self._reaction_invite_requests.pop(payload.message_id, None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invites(bot))
