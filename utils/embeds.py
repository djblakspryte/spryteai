from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Union

import discord
from discord.ext import commands

ContextLike = Union[commands.Context, discord.Interaction]


def make_embed(
    ctx: ContextLike | None = None,
    author: bool = False,
    title: str = "",
    description: str = "",
    title_url: str | None = None,
    thumbnail_url: str | None = None,
    image_url: str | None = None,
    fields: list[dict[str, Any]] | None = None,
    footer: str | None = None,
    color: int | discord.Colour | None = None,
    timestamp: int | float | datetime | None = None,
) -> discord.Embed:
    if not isinstance(color, (int, discord.Colour)):
        color = discord.Color.blurple()

    embed = discord.Embed(title=title, description=description, color=color)

    if ctx is not None and author:
        user = ctx.author if isinstance(ctx, commands.Context) else ctx.user
        embed.set_author(icon_url=str(user.display_avatar.url), name=user.display_name)

    if title_url:
        embed.url = title_url
    if thumbnail_url:
        embed.set_thumbnail(url=str(thumbnail_url))
    if image_url:
        embed.set_image(url=str(image_url))

    for field in fields or []:
        embed.add_field(
            name=field.get("name") or "\u200b",
            value=field.get("value") or "\u200b",
            inline=bool(field.get("inline", False)),
        )

    if footer:
        embed.set_footer(text=footer)

    if timestamp is not None:
        if isinstance(timestamp, (int, float)):
            embed.timestamp = datetime.fromtimestamp(timestamp, tz=UTC)
        elif timestamp.tzinfo is None:
            embed.timestamp = timestamp.replace(tzinfo=UTC)
        else:
            embed.timestamp = timestamp

    return embed


async def send_interaction_message(ctx: discord.Interaction, embed: discord.Embed) -> None:
    if ctx.response.is_done():
        await ctx.followup.send(embed=embed, ephemeral=True)
    else:
        await ctx.response.send_message(embed=embed, ephemeral=True)


async def success_message(ctx: ContextLike, description: str, title: str | None = None) -> None:
    embed = make_embed(title=title or "Success:", description=description, color=discord.Color.green())
    if isinstance(ctx, commands.Context):
        await ctx.send(embed=embed, delete_after=30)
    else:
        await send_interaction_message(ctx, embed)


async def error_message(ctx: ContextLike, description: str, title: str | None = None) -> None:
    embed = make_embed(title=title or "Error:", description=description, color=discord.Color.red())
    if isinstance(ctx, commands.Context):
        await ctx.send(embed=embed, delete_after=30)
    else:
        await send_interaction_message(ctx, embed)


async def warning_message(ctx: ContextLike, description: str, title: str | None = None) -> None:
    embed = make_embed(title=title or "Warning:", description=description, color=discord.Color.dark_gold())
    if isinstance(ctx, commands.Context):
        await ctx.send(embed=embed, delete_after=30)
    else:
        await send_interaction_message(ctx, embed)


def error_embed(
    ctx: ContextLike,
    description: str,
    title: str | None = None,
    author: bool = True,
) -> discord.Embed:
    return make_embed(
        ctx=ctx,
        title=title or "Error:",
        description=description,
        color=discord.Color.red(),
        author=author,
    )
