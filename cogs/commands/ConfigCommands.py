from __future__ import annotations

import io
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw

from services import db
from utils import embeds

log = logging.getLogger(__name__)


async def generate_thumbnail(target_role: discord.Role) -> discord.File:
    size = (100, 100)
    image = Image.new("RGBA", size, target_role.color.to_rgb())
    draw = ImageDraw.Draw(image)
    r, g, b = target_role.color.to_rgb()
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    draw.text((25, 42), "No Icon", fill="white" if brightness < 128 else "black")
    image_data = io.BytesIO()
    image.save(image_data, format="PNG")
    image_data.seek(0)
    return discord.File(image_data, filename="thumbnail.png")


async def handle_config(
    ctx: discord.Interaction,
    *,
    config_type: str,
    config_name: str,
    config_sql: str,
    config_value: Optional[str],
    server_config,
    bot: commands.Bot,
) -> tuple[str, discord.Embed | None, discord.File | None]:
    is_role = config_type == "role"
    is_channel = config_type == "channel"

    if config_value is not None:
        if not ctx.user.guild_permissions.manage_guild:
            return "You need Manage Server permission to change server configuration.", None, None
        if not config_value.isdigit():
            return f"Config error: {config_type} value must be a numeric Discord ID.", None, None

        config_id = int(config_value)
        item = ctx.guild.get_role(config_id) if is_role else ctx.guild.get_channel(config_id) if is_channel else None
        if item is None:
            return f"Config error: that {config_type} does not exist in this server.", None, None

        await db.execute(
            f'UPDATE serverconfig SET "{config_sql}" = $1 WHERE "ServerID" = $2',
            config_id,
            ctx.guild.id,
        )
        return f"{config_name} set to {item.mention}.", None, None

    configured_id = server_config[config_sql]
    item = ctx.guild.get_role(configured_id) if is_role else ctx.guild.get_channel(configured_id) if is_channel else None
    if item is None:
        return f"No valid {config_name} is currently configured.", None, None

    embed = embeds.make_embed()
    embed.set_author(
        name=f"SpryteAI - {config_name} for: {ctx.guild.name}",
        icon_url=bot.user.display_avatar.url if bot.user else None,
    )
    embed.add_field(name=config_type.capitalize(), value=item.mention, inline=True)

    thumbnail: discord.File | None = None
    if is_role:
        if isinstance(item.display_icon, discord.Asset):
            embed.set_thumbnail(url=item.display_icon.url)
        else:
            thumbnail = await generate_thumbnail(item)
            embed.set_thumbnail(url="attachment://thumbnail.png")
    elif ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    return "", embed, thumbnail


class ConfigCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="configtest", description="View or update SpryteAI configuration.")
    @app_commands.guild_only()
    async def config_command(self, ctx: discord.Interaction, func: str, value: Optional[str] = None) -> None:
        normalized = func.strip().lower()
        user_data = await db.get_player_postgresData(ctx.user, ctx.guild)
        server_config = await db.get_server_config(ctx.guild)

        if "steamid" in normalized:
            if value is not None:
                if not value.isdigit():
                    return await ctx.response.send_message("SteamID must be numeric.", ephemeral=True)
                if user_data["steamID"] not in (None, 0):
                    return await ctx.response.send_message(
                        "SteamID is already set. Contact an administrator to change it.", ephemeral=True
                    )
                steam_id = int(value)
                await db.execute(
                    'UPDATE users SET "steamID" = $1 WHERE "UserID" = $2 AND "ServerID" = $3',
                    steam_id,
                    ctx.user.id,
                    ctx.guild.id,
                )
                return await ctx.response.send_message(f"SteamID set to `{steam_id}`.", ephemeral=True)

            embed = embeds.make_embed()
            embed.set_author(
                name=f"SpryteAI - SteamID for: {ctx.user.name}",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
            )
            embed.set_thumbnail(url=ctx.user.display_avatar.url)
            embed.add_field(name="SteamID", value=user_data["steamID"] or "Not set", inline=True)
            return await ctx.response.send_message(embed=embed, ephemeral=True)

        mapping = {
            "contributor": ("role", "Contributor Role", "ContributorRole"),
            "moderator": ("role", "Moderator Role", "ModRole"),
            "admin": ("role", "Admin Role", "AdminRole"),
            "log": ("channel", "Log Channel", "log_chan_id"),
            "report": ("channel", "Report Channel", "report_chan_id"),
        }
        for keyword, (config_type, config_name, column) in mapping.items():
            if keyword in normalized:
                message, embed, thumbnail = await handle_config(
                    ctx,
                    config_type=config_type,
                    config_name=config_name,
                    config_sql=column,
                    config_value=value,
                    server_config=server_config,
                    bot=self.bot,
                )
                if embed and thumbnail:
                    return await ctx.response.send_message(embed=embed, file=thumbnail)
                if embed:
                    return await ctx.response.send_message(embed=embed)
                return await ctx.response.send_message(message, ephemeral=value is not None)

        if "prefix" in normalized:
            if value is not None:
                if not ctx.user.guild_permissions.manage_guild:
                    return await ctx.response.send_message(
                        "You need Manage Server permission to change the prefix.", ephemeral=True
                    )
                prefix = value.strip()
                if not 1 <= len(prefix) <= 5:
                    return await ctx.response.send_message("Prefix must be 1-5 characters.", ephemeral=True)
                await db.execute(
                    'UPDATE serverconfig SET prefix = $1 WHERE "ServerID" = $2',
                    prefix,
                    ctx.guild.id,
                )
                return await ctx.response.send_message(f"Prefix set to `{prefix}`.", ephemeral=True)

            embed = embeds.make_embed()
            embed.set_author(
                name=f"SpryteAI - Prefix for: {ctx.guild.name}",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
            )
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            embed.add_field(name="Prefix", value=f"`{server_config['prefix']}`", inline=True)
            return await ctx.response.send_message(embed=embed)

        await ctx.response.send_message(
            "Unknown config option. Try `steamid`, `contributor`, `moderator`, `admin`, `log`, `report`, or `prefix`.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCommands(bot))
    log.info("Cog loaded: ConfigCommands")
