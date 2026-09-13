from __future__ import annotations

import logging
import random
import time

import discord
from discord.ext import commands

from services import db

log = logging.getLogger(__name__)

answers = [
    "whatever you're thinking, don't.",
    "you're seriously gonna send that?",
    "is typing you guys!",
    "it's a shame you wanna send that.",
    "you're really gonna talk like that?",
    "BORING!!",
    "glad you decided to join us.",
    "*reads as you're typing.*",
    "Preparing detonation.",
    "those are fighting words you're typing!!",
    ".......done typing yet?",
]

LEVEL_ROLE_IDS = [
    1153895475376816139,
    1153895480737136721,
    1153895485950664794,
    1153895491566846043,
    1153895496692269176,
    1153895501754814505,
    1153895506636980255,
    1154247465957085286,
    1153895512056004638,
]
DECORATIVE_ROLE_ID = 1153895470788260002


async def level_roles(user: discord.Member, guild: discord.Guild, level: int) -> str:
    new_roles: list[str] = []

    decorative_role = guild.get_role(DECORATIVE_ROLE_ID)
    if decorative_role and decorative_role not in user.roles:
        try:
            await user.add_roles(decorative_role, reason="SpryteAI level role")
        except discord.Forbidden:
            log.warning("Unable to add decorative level role in guild %s", guild.id)

    for role_id in LEVEL_ROLE_IDS:
        role = guild.get_role(role_id)
        if not role or role in user.roles:
            continue

        # Preserve the original level calculation while avoiding crashes for missing roles.
        threshold = max(1, (role.position - 1) * 5)
        if level >= threshold:
            try:
                await user.add_roles(role, reason=f"SpryteAI level {level}")
                new_roles.append(role.name)
            except discord.Forbidden:
                log.warning("Unable to add level role %s in guild %s", role.id, guild.id)

    return "\nYou also gained: " + ", ".join(new_roles) if new_roles else ""


async def add_experience(member: discord.Member, guild: discord.Guild) -> int | None:
    server_config = await db.get_server_config(guild)
    exp_mult = max(1, int(server_config["exp_mult"] or 1))
    exp_cooldown = max(0, int(server_config["exp_cooldown"] or 0))

    # Ensure the user exists, then let PostgreSQL perform the cooldown check and
    # XP write in one statement so concurrent messages cannot both award XP.
    await db.get_player_postgresData(member, guild)
    now = int(time.time())
    experience_gain = random.randint(15, 25) * exp_mult
    row = await db.fetchrow(
        """
        UPDATE users
        SET "Experience" = COALESCE("Experience", 0) + $1,
            "LastMessage" = $2
        WHERE "UserID" = $3
          AND "ServerID" = $4
          AND ($2 - COALESCE("LastMessage", 0)) >= $5
        RETURNING "Experience"
        """,
        experience_gain,
        now,
        member.id,
        guild.id,
        exp_cooldown,
    )
    if row:
        log.debug("Added %s experience to %s", experience_gain, member)
        return int(row["Experience"])
    return None


async def level_up(member: discord.Member, guild: discord.Guild, experience: int | None = None) -> None:
    data = await db.get_player_postgresData(member, guild)
    experience = int(experience if experience is not None else data["Experience"] or 0)
    current_level = max(1, int(data["ExpLevel"] or 1))
    updated_level = max(1, int(experience ** 0.25))

    if updated_level <= current_level:
        return

    role_text = await level_roles(member, guild, updated_level)
    await db.execute(
        'UPDATE users SET "ExpLevel" = $1 WHERE "ServerID" = $2 AND "UserID" = $3',
        updated_level,
        guild.id,
        member.id,
    )

    try:
        await member.send(f"Congratulations {member.mention}! You advanced to level {updated_level}!{role_text}")
    except (discord.Forbidden, discord.HTTPException):
        log.debug("Could not DM level-up notice to user %s", member.id)


class ExperienceListeners(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._typing_cooldowns: dict[tuple[int, int], float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return

        muted_role = discord.utils.get(message.guild.roles, name="Muted")
        if muted_role and muted_role in message.author.roles:
            return

        new_experience = await add_experience(message.author, message.guild)
        if new_experience is not None:
            await level_up(message.author, message.guild, new_experience)

    @commands.Cog.listener()
    async def on_typing(
        self,
        channel: discord.abc.Messageable,
        user: discord.Member | discord.User,
        when,
    ) -> None:
        if user.bot or not isinstance(channel, discord.TextChannel):
            return

        # Keep the playful typing response, but rate-limit it so it cannot flood a channel.
        key = (channel.id, user.id)
        now = time.monotonic()
        if now - self._typing_cooldowns.get(key, 0.0) < 30:
            return
        if random.randint(1, 4) != 1:
            return

        self._typing_cooldowns[key] = now
        await channel.send(f"{user.mention}, {random.choice(answers)}", delete_after=20)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExperienceListeners(bot))
    log.info("Cog loaded: ExperienceListeners")
