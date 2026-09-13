from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Literal, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from config import config
from services import db
from utils import embeds

log = logging.getLogger(__name__)


class GeneralCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="hello", description="Greets you.")
    async def hello(self, ctx: discord.Interaction) -> None:
        await ctx.response.send_message(f"Hello, {ctx.user.mention}, I see you!")

    @app_commands.command(name="namaste", description="A compact response for the haters.")
    async def namaste(self, ctx: discord.Interaction) -> None:
        await ctx.response.send_message("╭∩╮（︶︿︶）╭∩╮")

    @app_commands.command(name="blunt", description="Rolls a virtual blunt with someone.")
    async def blunt(
        self,
        ctx: discord.Interaction,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        user = user or ctx.user
        await ctx.response.send_message(f"*Rolls a fat one with {user.mention}*")

    @app_commands.command(name="membercount", description="Shows the server member count.")
    @app_commands.guild_only()
    async def membercount(self, ctx: discord.Interaction) -> None:
        await ctx.response.send_message(f"{ctx.guild.member_count:,} members")

    @app_commands.command(name="calc", description="Simple calculator.")
    async def calc(
        self,
        ctx: discord.Interaction,
        func: Literal["add", "sub", "mul", "div"],
        num1: float,
        num2: float,
    ) -> None:
        operations = {
            "add": lambda: num1 + num2,
            "sub": lambda: num1 - num2,
            "mul": lambda: num1 * num2,
            "div": lambda: num1 / num2,
        }
        if func == "div" and num2 == 0:
            return await ctx.response.send_message("Cannot divide by zero.", ephemeral=True)
        result = operations[func]()
        await ctx.response.send_message(f"{result:g}")

    @app_commands.command(name="say", description="Makes the bot say a message.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def say(self, ctx: discord.Interaction, message: str) -> None:
        if not ctx.user.guild_permissions.manage_messages:
            return await ctx.response.send_message("You need Manage Messages permission.", ephemeral=True)
        await ctx.channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        await ctx.response.send_message("Message sent.", ephemeral=True)

    @app_commands.command(name="repeat", description="Repeats a message up to five times.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def repeat(self, ctx: discord.Interaction, times: app_commands.Range[int, 1, 5], content: str) -> None:
        if not ctx.user.guild_permissions.manage_messages:
            return await ctx.response.send_message("You need Manage Messages permission.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        for _ in range(times):
            await ctx.channel.send(content, allowed_mentions=discord.AllowedMentions.none())
        await ctx.followup.send(f"Repeated the message {times} time(s).", ephemeral=True)

    @app_commands.command(name="joined", description="Shows when a member joined this server.")
    @app_commands.guild_only()
    async def joined(self, ctx: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        member = member or ctx.user
        if member.joined_at is None:
            return await ctx.response.send_message("Join date is unavailable.", ephemeral=True)
        await ctx.response.send_message(
            f"{member.mention} joined {discord.utils.format_dt(member.joined_at, style='F')} "
            f"({discord.utils.format_dt(member.joined_at, style='R')})."
        )

    @app_commands.command(name="time", description="Shows the current UTC time.")
    async def time(self, ctx: discord.Interaction) -> None:
        now = discord.utils.utcnow()
        await ctx.response.send_message(discord.utils.format_dt(now, style="F"))

    @app_commands.command(name="cool", description="Lets SpryteAI judge whether something is cool.")
    async def cool(self, ctx: discord.Interaction, item: str) -> None:
        answer = random.choice(("No", "Yes"))
        await ctx.response.send_message(f"{answer}, {item} is {'not ' if answer == 'No' else ''}cool.")

    @app_commands.command(name="hoe", description="A playful random yes/no command.")
    async def hoe(self, ctx: discord.Interaction, member: discord.User) -> None:
        if await self.bot.is_owner(member):
            answer = "No"
        else:
            answer = random.choice(("No", "Yes"))
        await ctx.response.send_message(f"{answer}, {member.mention} is {'not ' if answer == 'No' else ''}a hoe")

    @app_commands.command(name="pfp", description="Gets a user's profile picture.")
    async def pfp(
        self,
        ctx: discord.Interaction,
        user: Optional[Union[discord.Member, discord.User]] = None,
        profile: bool = False,
    ) -> None:
        user = user or ctx.user
        if profile and isinstance(user, discord.Member):
            user = self.bot.get_user(user.id) or user
        embed = embeds.make_embed()
        embed.set_author(icon_url=user.display_avatar.url, name=str(user))
        embed.set_image(url=user.display_avatar.url)
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Gets the latency between you and the bot.")
    async def ping(self, ctx: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        if latency <= 50:
            color = 0x44FF44
        elif latency <= 100:
            color = 0xFFD000
        elif latency <= 200:
            color = 0xFF6600
        else:
            color = 0x990000
        embed = embeds.make_embed(color=color, description=f"🏓 Pong! **{latency} ms**")
        if self.bot.user:
            embed.set_author(icon_url=self.bot.user.display_avatar.url, name="PING")
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name="mutual", description="Shows servers shared by you and another user that SpryteAI can see.")
    async def mutual(
        self,
        ctx: discord.Interaction,
        user: Union[discord.Member, discord.User],
    ) -> None:
        guilds = [
            guild.name
            for guild in self.bot.guilds
            if guild.get_member(ctx.user.id) is not None and guild.get_member(user.id) is not None
        ]
        await ctx.response.send_message("\n".join(guilds) if guilds else "No mutual servers found.", ephemeral=True)

    @app_commands.command(name="spryteai", description="Displays SpryteAI information.")
    @app_commands.guild_only()
    async def spryteai(self, ctx: discord.Interaction) -> None:
        app_info = await self.bot.application_info()
        cogs = "\n".join(sorted(self.bot.cogs.keys())) or "None"
        bot_member = ctx.guild.me
        roles = "\n".join(role.name for role in reversed(bot_member.roles[1:])) if bot_member else "Unknown"

        embed = embeds.make_embed()
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_author(icon_url=self.bot.user.display_avatar.url, name=f"{self.bot.user.name} Info")

        community_id = await db.community_id_for_guild(ctx.guild)
        community_record = await db.get_community_record(community_id)
        community_cfg = await db.get_community_config_by_id(community_id)
        owner_name = getattr(app_info.owner, "name", str(app_info.owner))
        default_prefix = community_cfg.get("bot", {}).get("prefix", "!")
        community_name = str(community_record["name"] if community_record else ctx.guild.name)

        embed.add_field(name="Community", value=f"{community_name} (`{community_id}`)", inline=True)
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Prefix", value=f"`{default_prefix}` or `/`", inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.1f} ms", inline=True)
        embed.add_field(name="Guild Count", value=f"{len(self.bot.guilds):,}", inline=True)
        embed.add_field(name="User Cache", value=f"{len(self.bot.users):,}", inline=True)
        embed.add_field(name="Cogs", value=cogs[:1024], inline=False)
        embed.add_field(name="Roles", value=roles[:1024] or "None", inline=False)
        embed.add_field(name="Description", value=app_info.description or "Powered by SpryteAI", inline=False)

        file = discord.File(str(Path(__file__).resolve().parents[2] / "assets" / "spryteai.png"), filename="image.png")
        embed.set_image(url="attachment://image.png")
        await ctx.response.send_message(file=file, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCommands(bot))
    log.info("Cog loaded: GeneralCommands")
