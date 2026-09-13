from __future__ import annotations

import logging

import discord
from discord.ext import commands

from services import db

log = logging.getLogger(__name__)


class AdminListeners(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await db.get_player_postgresData(member, member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await db.remove_user_from_postgresDB(member, member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.nick == before.nick or not after.nick:
            return

        data = await db.get_player_postgresData(before, before.guild)
        nicknames = list(data["NickNames"] or [])
        if after.nick not in nicknames:
            nicknames.append(after.nick)
            await db.execute(
                'UPDATE users SET "NickNames" = $1 WHERE "UserID" = $2 AND "ServerID" = $3',
                nicknames,
                after.id,
                after.guild.id,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return

        muted_role = discord.utils.get(message.guild.roles, name="Muted")
        if muted_role and muted_role in message.author.roles:
            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminListeners(bot))
    log.info("Cog loaded: AdminListeners")
