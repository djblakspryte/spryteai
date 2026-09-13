from __future__ import annotations

import logging
import random
import time
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from services import db
from utils import embeds, helpers

log = logging.getLogger(__name__)

MAX_BALANCE = 50_000


class BankCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="daily", description="Claim a random amount of credits every 24 hours.")
    @app_commands.guild_only()
    async def daily(self, ctx: discord.Interaction) -> None:
        await db.get_player_postgresData(ctx.user, ctx.guild)
        now = int(time.time())
        reward = random.randint(200, 500)

        response_message: str
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """
                    SELECT "Credits", "LastClaimed"
                    FROM users
                    WHERE "ServerID" = $1 AND "UserID" = $2
                    FOR UPDATE
                    """,
                    ctx.guild.id,
                    ctx.user.id,
                )
                if row is None:
                    raise RuntimeError("Unable to lock daily credit row")

                remaining, expired = helpers.timeDiff(row["LastClaimed"])
                if not expired:
                    response_message = (
                        f"{ctx.user.mention}, you already collected today. "
                        f"Try again in {helpers.display_time(remaining)}!"
                    )
                else:
                    current = int(row["Credits"] or 0)
                    if current + reward > MAX_BALANCE:
                        response_message = (
                            f"{ctx.user.mention}, your balance is too close to the "
                            f"{MAX_BALANCE:,}-credit cap."
                        )
                    else:
                        new_balance = current + reward
                        await connection.execute(
                            """
                            UPDATE users
                            SET "Credits" = $1, "Claimed" = 1, "LastClaimed" = $2
                            WHERE "ServerID" = $3 AND "UserID" = $4
                            """,
                            new_balance,
                            now,
                            ctx.guild.id,
                            ctx.user.id,
                        )
                        response_message = (
                            f"{ctx.user.mention}, you earned {reward:,} credits! "
                            f"Your balance is now {new_balance:,}."
                        )

        await ctx.response.send_message(response_message)

    @app_commands.command(name="credits", description="View credits or run a credit action.")
    @app_commands.guild_only()
    async def credits(
        self,
        ctx: discord.Interaction,
        func: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None,
    ) -> None:
        normalized = (func or "").strip().lower()

        if not normalized:
            target_user = user or ctx.user
            data = await db.get_player_postgresData(target_user, ctx.guild, "Credits")
            embed = embeds.make_embed()
            embed.set_author(
                name=f"SpryteAI Total Credits for: {target_user.name}",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.add_field(name="Credits", value=f"{int(data['Credits'] or 0):,}", inline=True)
            return await ctx.response.send_message(embed=embed)

        if normalized.startswith("transfer"):
            if user is None:
                return await ctx.response.send_message("Transfer error: specify a recipient.", ephemeral=True)
            amount = next((int(part) for part in normalized.split() if part.isdigit()), None)
            if amount is None:
                return await ctx.response.send_message("Transfer error: specify an amount, e.g. `transfer 250`.", ephemeral=True)
            message = await helpers.transfercredits(ctx, amount, ctx.user, user)
            return await ctx.response.send_message(message)

        if normalized.startswith("leaderboard"):
            row_num = next((int(part) for part in normalized.split() if part.isdigit()), 10)
            row_num = max(1, min(row_num, 25))
            result = await db.fetch(
                """
                WITH distinct_users AS (
                    SELECT DISTINCT ON ("UserID")
                        "UserID", "UserName", "Credits", "Bot"
                    FROM users
                    WHERE "ServerID" = $1 AND COALESCE("Bot", FALSE) = FALSE
                    ORDER BY "UserID", ctid DESC
                )
                SELECT "UserID", "UserName", "Credits",
                       ROW_NUMBER() OVER (ORDER BY "Credits" DESC, "UserID") AS row_number
                FROM distinct_users
                ORDER BY "Credits" DESC, "UserID"
                LIMIT $2
                """,
                ctx.guild.id,
                row_num,
            )
            embed = embeds.make_embed()
            embed.set_author(name=f"Top {row_num} Credits Leaderboard")
            if not result:
                embed.description = "No leaderboard data yet."
            for row in result:
                embed.add_field(
                    name=f"#{int(row['row_number'])}. {row['UserName']}",
                    value=f"{int(row['Credits'] or 0):,} credits",
                    inline=False,
                )
            return await ctx.response.send_message(embed=embed)

        if normalized.startswith("add"):
            if not await self.bot.is_owner(ctx.user):
                return await ctx.response.send_message("Only the bot owner can add credits.", ephemeral=True)
            amount = next((int(part) for part in normalized.split() if part.isdigit()), None)
            if amount is None:
                return await ctx.response.send_message("Add error: specify an amount.", ephemeral=True)

            if user is None:
                await db.execute(
                    'UPDATE users SET "Credits" = GREATEST(COALESCE("Credits", 0) + $1, 0) WHERE "ServerID" = $2',
                    amount,
                    ctx.guild.id,
                )
                return await ctx.response.send_message(
                    f"Added {amount:,} credits to every stored member in this server.", ephemeral=True
                )

            balance = await helpers.add_money(user, ctx.guild, amount)
            return await ctx.response.send_message(
                f"Added {amount:,} credits to {user.mention}; balance is now {balance:,}.", ephemeral=True
            )

        if normalized.startswith("reset"):
            if not await self.bot.is_owner(ctx.user):
                return await ctx.response.send_message("Only the bot owner can reset credits.", ephemeral=True)
            amount = next((int(part) for part in normalized.split() if part.isdigit()), None)
            if amount is None:
                return await ctx.response.send_message("Reset error: specify an amount.", ephemeral=True)

            amount = max(0, amount)
            if user is None:
                await db.execute(
                    'UPDATE users SET "Credits" = $1 WHERE "ServerID" = $2',
                    amount,
                    ctx.guild.id,
                )
                return await ctx.response.send_message(
                    f"Reset every stored member to {amount:,} credits.", ephemeral=True
                )

            await db.get_player_postgresData(user, ctx.guild)
            await db.execute(
                'UPDATE users SET "Credits" = $1 WHERE "ServerID" = $2 AND "UserID" = $3',
                amount,
                ctx.guild.id,
                user.id,
            )
            return await ctx.response.send_message(
                f"Reset {user.mention} to {amount:,} credits.", ephemeral=True
            )

        await ctx.response.send_message(
            "Unknown credit action. Try `transfer <amount>`, `leaderboard [count]`, `add <amount>`, or `reset <amount>`.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BankCommands(bot))
    log.info("Cog loaded: BankCommands")
