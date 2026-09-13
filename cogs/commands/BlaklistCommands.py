from __future__ import annotations

import logging
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from services import db

log = logging.getLogger(__name__)


class BlacklistCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def update_blacklist(self, user_id: int, *, remove: bool = False) -> str:
        data = await db.get_bot_config()
        blacklist = list(dict.fromkeys(data["blacklist"] or []))

        if remove:
            if user_id not in blacklist:
                return "User is not in the blacklist."
            blacklist.remove(user_id)
            status = "User removed from the blacklist."
        else:
            if user_id in blacklist:
                return "User is already blacklisted."
            blacklist.append(user_id)
            status = "User added to the blacklist."

        await db.execute('UPDATE botconfig SET blacklist = $1', blacklist)
        return status

    @app_commands.command(name="blacklist", description="Manage SpryteAI's global user blacklist (owner only).")
    async def blacklist(
        self,
        ctx: discord.Interaction,
        func: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None,
    ) -> None:
        if not await self.bot.is_owner(ctx.user):
            return await ctx.response.send_message("Only the bot owner can manage the blacklist.", ephemeral=True)

        action = (func or "list").strip().lower()
        if action in {"add", "del", "delete", "remove"} and user is None:
            return await ctx.response.send_message("Specify a user for that action.", ephemeral=True)

        if action == "add":
            if await self.bot.is_owner(user):
                return await ctx.response.send_message("The bot owner cannot be blacklisted.", ephemeral=True)
            return await ctx.response.send_message(await self.update_blacklist(user.id), ephemeral=True)

        if action in {"del", "delete", "remove"}:
            return await ctx.response.send_message(
                await self.update_blacklist(user.id, remove=True), ephemeral=True
            )

        if action not in {"list", "show", ""}:
            return await ctx.response.send_message("Use `add`, `remove`, or `list`.", ephemeral=True)

        data = await db.get_bot_config()
        blacklist = list(data["blacklist"] or [])
        if not blacklist:
            return await ctx.response.send_message("The blacklist is empty.", ephemeral=True)

        entries: list[str] = []
        for user_id in blacklist:
            known_user = self.bot.get_user(user_id)
            entries.append(known_user.mention if known_user else f"`{user_id}`")

        await ctx.response.send_message("Blacklist:\n" + "\n".join(entries), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlacklistCommands(bot))
    log.info("Cog loaded: BlacklistCommands")
