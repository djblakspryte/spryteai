from __future__ import annotations

import time
from typing import Any

from services import db

DAY_SECONDS = 86_400
TRANSFER_LIMIT = 1
TRANSFER_MAX_CREDITS = 1_000

intervals = (
    ("years", 31_536_000),
    ("weeks", 604_800),
    ("days", 86_400),
    ("hours", 3_600),
    ("minutes", 60),
    ("seconds", 1),
)


def timeDiff(timestamp_value: int | float | None) -> tuple[float, bool]:
    """Return seconds until 24h after timestamp and whether that window expired."""
    if not timestamp_value:
        return 0.0, True

    next_action = int(timestamp_value) + DAY_SECONDS
    remaining = next_action - time.time()
    if remaining <= 0:
        return 0.0, True
    return remaining, False


def display_time(seconds: int | float, granularity: int = 2) -> str:
    seconds = max(0, int(seconds))
    if seconds == 0:
        return "0 seconds"

    result: list[str] = []
    for name, count in intervals:
        value, seconds = divmod(seconds, count)
        if value:
            label = name[:-1] if value == 1 else name
            result.append(f"{value} {label}")
        if len(result) >= granularity:
            break
    return ", ".join(result)


async def add_money(member: Any, guild: Any, amount: int) -> int:
    await db.get_player_postgresData(member, guild)
    amount = int(amount)

    row = await db.fetchrow(
        """
        UPDATE users
        SET "Credits" = GREATEST(COALESCE("Credits", 0) + $1, 0)
        WHERE "ServerID" = $2 AND "UserID" = $3
        RETURNING "Credits"
        """,
        amount,
        guild.id,
        member.id,
    )
    if row is None:
        raise RuntimeError("Unable to update credits")
    return int(row["Credits"])


async def hasClaimedToday(guild: Any, user: Any) -> tuple[float, bool]:
    data = await db.get_player_postgresData(user, guild, data="LastClaimed")
    remaining, expired = timeDiff(data["LastClaimed"])
    return remaining, not expired


def _transfer_window(last_action: int | None, count: int | None) -> tuple[float, bool, int]:
    remaining, expired = timeDiff(last_action)
    normalized_count = 0 if expired else int(count or 0)
    return remaining, normalized_count >= TRANSFER_LIMIT, normalized_count


async def overTransferLimit(guild: Any, user: Any, sending: bool = True):
    row = await db.get_player_postgresData(user, guild)
    if sending:
        remaining, over_limit, count = _transfer_window(row["LastTransferred"], row["TimesTransferred"])
    else:
        remaining, over_limit, count = _transfer_window(row["LastReceived"], row["TimesReceived"])
    return remaining, over_limit, 0 if count == 0 else None


async def transfercredits(ctx: Any, credits: int, sender: Any, receiver: Any) -> str:
    credits = int(credits)
    if credits < 1:
        return "Please enter a value above 0!"
    if credits > TRANSFER_MAX_CREDITS:
        return f"{sender.mention}, the daily transfer limit is {TRANSFER_MAX_CREDITS:,} credits."
    if sender.id == receiver.id:
        return "You can't transfer credits to yourself."

    # Ensure both rows exist before acquiring row locks.
    await db.get_player_postgresData(sender, ctx.guild)
    await db.get_player_postgresData(receiver, ctx.guild)

    now = int(time.time())
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            rows = await connection.fetch(
                """
                SELECT "UserID", "Credits", "LastTransferred", "TimesTransferred",
                       "LastReceived", "TimesReceived"
                FROM users
                WHERE "ServerID" = $1 AND "UserID" = ANY($2::BIGINT[])
                FOR UPDATE
                """,
                ctx.guild.id,
                [sender.id, receiver.id],
            )
            by_user = {row["UserID"]: row for row in rows}
            sender_row = by_user.get(sender.id)
            receiver_row = by_user.get(receiver.id)
            if sender_row is None or receiver_row is None:
                raise RuntimeError("Unable to lock both credit accounts")

            sender_remaining, sender_over, sender_count = _transfer_window(
                sender_row["LastTransferred"], sender_row["TimesTransferred"]
            )
            receiver_remaining, receiver_over, receiver_count = _transfer_window(
                receiver_row["LastReceived"], receiver_row["TimesReceived"]
            )

            if sender_over:
                return (
                    f"{sender.mention}, you have reached the daily transfer limit. "
                    f"Try again in {display_time(sender_remaining)}."
                )
            if receiver_over:
                return (
                    f"{receiver.mention} has reached the daily receive limit. "
                    f"Try again in {display_time(receiver_remaining)}."
                )

            sender_credits = int(sender_row["Credits"] or 0)
            receiver_credits = int(receiver_row["Credits"] or 0)
            if sender_credits < credits:
                return f"{sender.mention}, you do not have enough credits for this transfer."

            sender_credits -= credits
            receiver_credits += credits

            await connection.execute(
                """
                UPDATE users
                SET "Credits" = $1, "LastTransferred" = $2, "TimesTransferred" = $3
                WHERE "ServerID" = $4 AND "UserID" = $5
                """,
                sender_credits,
                now,
                sender_count + 1,
                ctx.guild.id,
                sender.id,
            )
            await connection.execute(
                """
                UPDATE users
                SET "Credits" = $1, "LastReceived" = $2, "TimesReceived" = $3
                WHERE "ServerID" = $4 AND "UserID" = $5
                """,
                receiver_credits,
                now,
                receiver_count + 1,
                ctx.guild.id,
                receiver.id,
            )

    return (
        f"{sender.mention}, you sent {credits:,} credits to {receiver.mention}. "
        f"Your balance is now {sender_credits:,}; {receiver.mention} now has {receiver_credits:,}."
    )

# --- Pokecord compatibility helpers ---------------------------------------
# These wrappers keep the legacy Pokecord cog isolated from main.py while
# routing all persistence through the shared Database service.

colors = {
    "BLACK": 0x000000,
    "BLUE": 0x3B4CCA,
    "BROWN": 0x8B4513,
    "GRAY": 0x808080,
    "GREEN": 0x3FA129,
    "PINK": 0xFF69B4,
    "PURPLE": 0xA33EA1,
    "RED": 0xE3350D,
    "WHITE": 0xFFFFFF,
    "YELLOW": 0xF7D02C,
}
black = (0, 0, 0, 255)
white = (255, 255, 255, 0)


def check_role(member: Any, role_id: int | str | None) -> bool:
    try:
        role_id = int(role_id or 0)
    except (TypeError, ValueError):
        return False
    if not role_id:
        return False
    return any(getattr(role, "id", None) == role_id for role in getattr(member, "roles", ()))


def pokeNumConverter(value: Any) -> str:
    """Return the three-digit National Dex image prefix used by legacy assets."""
    try:
        return f"{int(value):03d}"
    except (TypeError, ValueError):
        return str(value)


async def query_postgresDatabase(query: str, *args: Any, multiple: bool = False, **_: Any):
    if multiple:
        return await db.fetch(query, *args)
    return await db.fetchrow(query, *args)


async def transaction_postgresDatabase(query: str, *args: Any):
    return await db.execute(query, *args)


async def get_player_postgresData(member: Any, guild: Any, data: str | None = None):
    if data == "*":
        data = None
    return await db.get_player_postgresData(member, guild, data)


async def get_pokecord_postgresData(member: Any, data: str = "*"):
    guild = getattr(member, "guild", None)
    if guild is None:
        raise RuntimeError("Pokécord data requires a Discord guild/community context")
    await db.resolve_discord_player(guild, member)
    if data != "*":
        allowed = {
            "uid", "name", "selected", "starred", "shiny", "lucky", "index",
            "lvl", "exp", "ivpercentage", "item", "ownerid",
        }
        if data not in allowed:
            raise ValueError(f"Unsupported Pokecord column: {data}")
        return await db.fetch(
            f'SELECT "{data}" FROM pokecord_poke_data_scoped WHERE "ownerid" = $1 ORDER BY "uid"',
            member.id,
        )
    return await db.fetch(
        'SELECT * FROM pokecord_poke_data_scoped WHERE "ownerid" = $1 ORDER BY "uid"',
        member.id,
    )


async def enough_money(member: Any, guild: Any, amount: int) -> bool:
    row = await db.get_player_postgresData(member, guild, "Credits")
    return int(row["Credits"] or 0) >= int(amount)


async def withdraw_money(member: Any, guild: Any, amount: int) -> int:
    amount = max(0, int(amount))
    row = await db.fetchrow(
        '''
        UPDATE users
        SET "Credits" = GREATEST(COALESCE("Credits", 0) - $1, 0)
        WHERE "ServerID" = $2 AND "UserID" = $3
        RETURNING "Credits"
        ''',
        amount,
        guild.id,
        member.id,
    )
    if row is None:
        raise RuntimeError("Unable to withdraw credits")
    return int(row["Credits"])
