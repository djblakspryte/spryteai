from __future__ import annotations

import io
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from services import db
from utils import embeds

log = logging.getLogger(__name__)


def _short(value: str | None, limit: int = 1000) -> str:
    text = value or "No reason provided"
    return text if len(text) <= limit else text[: limit - 1] + "…"


class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _is_protected(self, guild: discord.Guild, user: discord.abc.User) -> bool:
        return user.id == guild.owner_id or await self.bot.is_owner(user)

    async def _log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        try:
            data = await db.get_server_config(guild)
        except Exception:
            log.exception("Unable to retrieve moderation log channel for guild %s", guild.id)
            return None
        channel_id = data["log_chan_id"]
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _log_action(
        self,
        guild: discord.Guild,
        *,
        action: str,
        moderator: discord.abc.User,
        user: discord.abc.User,
        reason: Optional[str] = None,
        role: discord.Role | None = None,
        attachment: discord.File | None = None,
    ) -> discord.TextChannel | None:
        channel = await self._log_channel(guild)
        if channel is None:
            return None

        embed = embeds.make_embed()
        embed.set_author(name=f"[{action.upper()}] {user}", icon_url=moderator.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=getattr(user, "mention", str(user)), inline=True)
        embed.add_field(name="Moderator", value=getattr(moderator, "mention", str(moderator)), inline=True)
        if role is not None:
            embed.add_field(name="Role", value=role.mention, inline=True)
        if reason is not None:
            embed.add_field(name="Reason", value=_short(reason), inline=False)

        try:
            if attachment:
                await channel.send(embed=embed, file=attachment)
            else:
                await channel.send(embed=embed)
        except discord.HTTPException:
            log.exception("Unable to write %s moderation log in guild %s", action, guild.id)
        return channel

    def _can_manage_role(self, ctx: discord.Interaction, role: discord.Role) -> tuple[bool, str | None]:
        if role.is_default() or role.managed:
            return False, "That role cannot be manually managed."
        if ctx.guild.owner_id != ctx.user.id and role >= ctx.user.top_role:
            return False, "You cannot manage a role equal to or above your highest role."
        bot_member = ctx.guild.me
        if bot_member is None or role >= bot_member.top_role:
            return False, "My bot role must be above the role you want me to manage."
        return True, None

    def _can_manage_member(self, ctx: discord.Interaction, user: discord.Member) -> tuple[bool, str | None]:
        if user.id == ctx.user.id:
            return False, "You cannot use this moderation action on yourself."
        if user.id == ctx.guild.owner_id:
            return False, "The server owner cannot be moderated."
        if ctx.guild.owner_id != ctx.user.id and user.top_role >= ctx.user.top_role:
            return False, "You cannot moderate a member with an equal or higher role."
        bot_member = ctx.guild.me
        if bot_member is None or user.top_role >= bot_member.top_role:
            return False, "My bot role must be above that member's highest role."
        return True, None

    @app_commands.command(name="whois", description="Shows information about a server member.")
    @app_commands.guild_only()
    async def whois(self, ctx: discord.Interaction, user: Optional[discord.Member] = None) -> None:
        user = user or ctx.user
        data = await db.get_player_postgresData(user, ctx.guild)
        usernames = "\n".join(data["UserNames"] or [user.name])
        nicknames = "\n".join(data["NickNames"] or [user.display_name])

        embed = embeds.make_embed()
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(name="Avatar", value=f"[Open avatar]({user.display_avatar.url})", inline=True)
        embed.add_field(name="Usernames", value=_short(usernames), inline=True)
        embed.add_field(name="Nicknames", value=_short(nicknames), inline=True)
        embed.add_field(
            name="Account Created",
            value=f"{discord.utils.format_dt(user.created_at, style='F')}\n{discord.utils.format_dt(user.created_at, style='R')}",
            inline=True,
        )
        if user.joined_at:
            embed.add_field(
                name="Joined Server",
                value=f"{discord.utils.format_dt(user.joined_at, style='F')}\n{discord.utils.format_dt(user.joined_at, style='R')}",
                inline=True,
            )

        invite_code = data["InviteCode"]
        if invite_code:
            inviter_text = f"Invite code: `{invite_code}`"
            try:
                invites = await ctx.guild.invites()
                invite = discord.utils.get(invites, code=invite_code)
                if invite and invite.inviter:
                    inviter_text = invite.inviter.mention
                else:
                    try:
                        vanity = await ctx.guild.vanity_invite()
                        if vanity.code == invite_code:
                            inviter_text = "Vanity invite"
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            except (discord.Forbidden, discord.HTTPException):
                pass
            embed.add_field(name="Invited By", value=inviter_text, inline=True)

        await ctx.response.send_message(embed=embed)

    @app_commands.command(name="inacmembercount", description="Estimates members eligible for a 7-day prune.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    async def inacmembercount(self, ctx: discord.Interaction) -> None:
        if not ctx.user.guild_permissions.kick_members:
            return await ctx.response.send_message("You need Kick Members permission.", ephemeral=True)
        count = await ctx.guild.estimate_pruned_members(days=7)
        message = (
            "No members are currently estimated to be eligible for a 7-day prune."
            if not count
            else f"Approximately {count:,} member(s) are eligible for a 7-day prune."
        )
        await ctx.response.send_message(message, ephemeral=True)

    @app_commands.command(name="delete", description="Deletes recent messages from this channel.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def delete(self, ctx: discord.Interaction, number: app_commands.Range[int, 1, 100]) -> None:
        if not ctx.user.guild_permissions.manage_messages:
            return await ctx.response.send_message("You need Manage Messages permission.", ephemeral=True)
        if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
            return await ctx.response.send_message("This command only works in text channels or threads.", ephemeral=True)

        await ctx.response.defer(ephemeral=True)
        messages = await ctx.channel.purge(limit=number)
        transcript = "\n".join(
            f"[{m.created_at.isoformat()}] {m.author} ({m.author.id}): {m.content or '[no text]'}"
            for m in reversed(messages)
        ) or "No messages deleted."
        transcript_file = discord.File(io.BytesIO(transcript.encode("utf-8")), filename="deleted_messages.txt")
        log_channel = await self._log_action(
            ctx.guild,
            action="message delete",
            moderator=ctx.user,
            user=ctx.user,
            reason=f"Deleted {len(messages)} message(s) in #{getattr(ctx.channel, 'name', 'channel')}",
            attachment=transcript_file,
        )
        suffix = f" Logged in {log_channel.mention}." if log_channel else ""
        await ctx.followup.send(f"Deleted {len(messages)} message(s).{suffix}", ephemeral=True)

    @app_commands.command(name="promote", description="Adds a role to a member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def promote(self, ctx: discord.Interaction, user: discord.Member, role: discord.Role) -> None:
        if not ctx.user.guild_permissions.manage_roles:
            return await ctx.response.send_message("You need Manage Roles permission.", ephemeral=True)
        allowed, error = self._can_manage_member(ctx, user)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)
        allowed, error = self._can_manage_role(ctx, role)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)
        if role in user.roles:
            return await ctx.response.send_message(f"{user.mention} already has {role.mention}.", ephemeral=True)

        try:
            await user.add_roles(role, reason=f"Promoted by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("Discord refused that role change. Check role hierarchy.", ephemeral=True)
        await self._log_action(ctx.guild, action="promotion", moderator=ctx.user, user=user, role=role)
        await ctx.response.send_message(f"Added {role.mention} to {user.mention}.", ephemeral=True)

    @app_commands.command(name="demote", description="Removes a role from a member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def demote(self, ctx: discord.Interaction, user: discord.Member, role: discord.Role) -> None:
        if not ctx.user.guild_permissions.manage_roles:
            return await ctx.response.send_message("You need Manage Roles permission.", ephemeral=True)
        allowed, error = self._can_manage_member(ctx, user)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)
        allowed, error = self._can_manage_role(ctx, role)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)
        if role not in user.roles:
            return await ctx.response.send_message(f"{user.mention} does not have {role.mention}.", ephemeral=True)

        try:
            await user.remove_roles(role, reason=f"Demoted by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("Discord refused that role change. Check role hierarchy.", ephemeral=True)
        await self._log_action(ctx.guild, action="demotion", moderator=ctx.user, user=user, role=role)
        await ctx.response.send_message(f"Removed {role.mention} from {user.mention}.", ephemeral=True)

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(self, ctx: discord.Interaction, user: discord.Member, reason: Optional[str] = None) -> None:
        if not ctx.user.guild_permissions.kick_members:
            return await ctx.response.send_message("You need Kick Members permission.", ephemeral=True)
        allowed, error = self._can_manage_member(ctx, user)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)

        try:
            await user.kick(reason=reason or f"Kicked by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("I cannot kick that member. Check my role hierarchy.", ephemeral=True)
        await self._log_action(ctx.guild, action="kick", moderator=ctx.user, user=user, reason=reason)
        await ctx.response.send_message(f"Kicked {user}.", ephemeral=True)

    async def _get_or_create_muted_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name="Muted")
        if role:
            return role
        return await guild.create_role(name="Muted", reason="SpryteAI mute functionality")

    @app_commands.command(name="mute", description="Applies SpryteAI's Muted role to a member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def mute(self, ctx: discord.Interaction, user: discord.Member, reason: Optional[str] = None) -> None:
        if not ctx.user.guild_permissions.manage_roles:
            return await ctx.response.send_message("You need Manage Roles permission.", ephemeral=True)
        allowed, error = self._can_manage_member(ctx, user)
        if not allowed:
            return await ctx.response.send_message(error, ephemeral=True)

        try:
            role = await self._get_or_create_muted_role(ctx.guild)
            if role not in user.roles:
                await user.add_roles(role, reason=reason or f"Muted by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("I cannot apply/create the Muted role. Check my permissions.", ephemeral=True)

        await self._log_action(ctx.guild, action="mute", moderator=ctx.user, user=user, reason=reason)
        await ctx.response.send_message(f"Muted {user.mention}.", ephemeral=True)

    @app_commands.command(name="unmute", description="Removes SpryteAI's Muted role from a member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def unmute(self, ctx: discord.Interaction, user: discord.Member, reason: Optional[str] = None) -> None:
        if not ctx.user.guild_permissions.manage_roles:
            return await ctx.response.send_message("You need Manage Roles permission.", ephemeral=True)
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if role is None or role not in user.roles:
            return await ctx.response.send_message(f"{user.mention} is not muted.", ephemeral=True)

        try:
            await user.remove_roles(role, reason=reason or f"Unmuted by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("I cannot remove the Muted role. Check my permissions.", ephemeral=True)

        await self._log_action(ctx.guild, action="unmute", moderator=ctx.user, user=user, reason=reason)
        await ctx.response.send_message(f"Unmuted {user.mention}.", ephemeral=True)

    @app_commands.command(name="ban", description="Bans a user from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, ctx: discord.Interaction, user: discord.User, reason: Optional[str] = None) -> None:
        if not ctx.user.guild_permissions.ban_members:
            return await ctx.response.send_message("You need Ban Members permission.", ephemeral=True)
        if await self._is_protected(ctx.guild, user) or user.id == ctx.user.id:
            return await ctx.response.send_message("That user cannot be banned by this command.", ephemeral=True)

        member = ctx.guild.get_member(user.id)
        if member:
            allowed, error = self._can_manage_member(ctx, member)
            if not allowed:
                return await ctx.response.send_message(error, ephemeral=True)

        try:
            await ctx.guild.ban(user, reason=reason or f"Banned by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("I cannot ban that user. Check my permissions and role hierarchy.", ephemeral=True)

        await self._log_action(ctx.guild, action="ban", moderator=ctx.user, user=user, reason=reason)
        await ctx.response.send_message(f"Banned {user}.", ephemeral=True)

    @app_commands.command(name="unban", description="Unbans a user from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban(self, ctx: discord.Interaction, user: discord.User, reason: Optional[str] = None) -> None:
        if not ctx.user.guild_permissions.ban_members:
            return await ctx.response.send_message("You need Ban Members permission.", ephemeral=True)

        try:
            await ctx.guild.fetch_ban(user)
        except discord.NotFound:
            return await ctx.response.send_message("That user is not currently banned.", ephemeral=True)

        try:
            await ctx.guild.unban(user, reason=reason or f"Unbanned by {ctx.user} ({ctx.user.id})")
        except discord.Forbidden:
            return await ctx.response.send_message("I cannot unban that user. Check my permissions.", ephemeral=True)

        await self._log_action(ctx.guild, action="unban", moderator=ctx.user, user=user, reason=reason)
        await ctx.response.send_message(f"Unbanned {user}.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCommands(bot))
    log.info("Cog loaded: AdminCommands")
