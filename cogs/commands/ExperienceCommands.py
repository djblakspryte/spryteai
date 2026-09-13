from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from services import db
from utils import embeds

log = logging.getLogger(__name__)

ASSET_DIR = Path(__file__).resolve().parents[2] / "assets"


async def get_rank(member: discord.abc.User, guild: discord.Guild) -> int | None:
    sql = """
        WITH distinct_users AS (
            SELECT DISTINCT ON ("UserID")
                "UserID", "UserName", "Experience", "ExpLevel"
            FROM users
            WHERE "ServerID" = $1
            ORDER BY "UserID", ctid DESC
        ), ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                ORDER BY "ExpLevel" DESC, "Experience" DESC, "UserID"
            ) AS row_number
            FROM distinct_users
        )
        SELECT row_number FROM ranked WHERE "UserID" = $2
    """
    row = await db.fetchrow(sql, guild.id, member.id)
    return int(row["row_number"]) if row else None


def crop_center(image: Image.Image, crop_width: int, crop_height: int) -> Image.Image:
    img_width, img_height = image.size
    return image.crop(
        (
            (img_width - crop_width) // 2,
            (img_height - crop_height) // 2,
            (img_width + crop_width) // 2,
            (img_height + crop_height) // 2,
        )
    )


def crop_max_square(image: Image.Image) -> Image.Image:
    side = min(image.size)
    return crop_center(image, side, side)


def mask_circle_transparent(image: Image.Image, blur_radius: int, offset: int = 0) -> Image.Image:
    inset = blur_radius * 2 + offset
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((inset, inset, image.size[0] - inset, image.size[1] - inset), fill=255)
    if blur_radius:
        mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))
    result = image.copy()
    result.putalpha(mask)
    return result


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


class ExperienceCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="experience", description="Checks a user's current experience.")
    @app_commands.guild_only()
    async def experience(
        self,
        ctx: discord.Interaction,
        func: Optional[str] = None,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        target_user = user or ctx.user
        normalized = (func or "").strip().lower()

        if not normalized:
            data = await db.get_player_postgresData(target_user, ctx.guild, "Experience")
            embed = embeds.make_embed()
            embed.set_author(
                name=f"SpryteAI Experience Stat for: {target_user.name}",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.add_field(name="XP", value=f"{int(data['Experience'] or 0):,}", inline=True)
            return await ctx.response.send_message(embed=embed)

        if "level" in normalized:
            data = await db.get_player_postgresData(target_user, ctx.guild, "ExpLevel")
            embed = embeds.make_embed()
            embed.set_author(
                name=f"SpryteAI Level Stat for: {target_user.name}",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.add_field(name="Level", value=int(data["ExpLevel"] or 1), inline=True)
            return await ctx.response.send_message(embed=embed)

        if "leaderboard" in normalized:
            row_num = next((int(part) for part in normalized.split() if part.isdigit()), 10)
            row_num = max(1, min(row_num, 25))
            sql = """
                WITH distinct_users AS (
                    SELECT DISTINCT ON ("UserID")
                        "UserID", "UserName", "Experience", "ExpLevel"
                    FROM users
                    WHERE "ServerID" = $1 AND COALESCE("Bot", FALSE) = FALSE
                    ORDER BY "UserID", ctid DESC
                )
                SELECT "UserID", "UserName", "Experience", "ExpLevel",
                       ROW_NUMBER() OVER (
                           ORDER BY "ExpLevel" DESC, "Experience" DESC, "UserID"
                       ) AS row_number
                FROM distinct_users
                ORDER BY "ExpLevel" DESC, "Experience" DESC, "UserID"
                LIMIT $2
            """
            result = await db.fetch(sql, ctx.guild.id, row_num)
            embed = embeds.make_embed()
            embed.set_author(name=f"Top {row_num} Experience Leaderboard")
            if not result:
                embed.description = "No leaderboard data yet."
            for row in result:
                embed.add_field(
                    name=f"#{int(row['row_number'])}. {row['UserName']}",
                    value=f"Level {int(row['ExpLevel'] or 1)} • {int(row['Experience'] or 0):,} XP",
                    inline=False,
                )
            return await ctx.response.send_message(embed=embed)

        if "rank" in normalized:
            return await self.servrank(ctx, target_user)

        if "mult" in normalized:
            multiplier = next((int(part) for part in normalized.split() if part.isdigit()), None)
            if multiplier is None:
                server_data = await db.get_server_config(ctx.guild)
                return await ctx.response.send_message(f"Experience multiplier: x{server_data['exp_mult']}")
            if not ctx.user.guild_permissions.manage_guild:
                return await ctx.response.send_message(
                    "You need Manage Server permission to change the XP multiplier.", ephemeral=True
                )
            multiplier = max(1, min(multiplier, 100))
            await db.execute(
                'UPDATE serverconfig SET exp_mult = $1 WHERE "ServerID" = $2',
                multiplier,
                ctx.guild.id,
            )
            return await ctx.response.send_message(f"Experience multiplier set to x{multiplier}.", ephemeral=True)

        if "cool" in normalized:
            cooldown = next((int(part) for part in normalized.split() if part.isdigit()), None)
            if cooldown is None:
                server_data = await db.get_server_config(ctx.guild)
                return await ctx.response.send_message(f"Experience cooldown: {server_data['exp_cooldown']}s")
            if not ctx.user.guild_permissions.manage_guild:
                return await ctx.response.send_message(
                    "You need Manage Server permission to change the XP cooldown.", ephemeral=True
                )
            cooldown = max(0, min(cooldown, 86_400))
            await db.execute(
                'UPDATE serverconfig SET exp_cooldown = $1 WHERE "ServerID" = $2',
                cooldown,
                ctx.guild.id,
            )
            return await ctx.response.send_message(f"Experience cooldown set to {cooldown}s.", ephemeral=True)

        await ctx.response.send_message(
            "Unknown option. Try `level`, `leaderboard [count]`, `rank`, `mult [value]`, or `cool [seconds]`.",
            ephemeral=True,
        )

    @app_commands.command(name="stats", description="Shows a member's SpryteAI stats.")
    @app_commands.guild_only()
    async def stats(
        self,
        ctx: discord.Interaction,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        user = user or ctx.user
        data = await db.get_player_postgresData(user, ctx.guild)
        rank = await get_rank(user, ctx.guild)

        embed = embeds.make_embed()
        embed.set_author(
            name=f"SpryteAI Statistics for: {user.name}",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Level", value=int(data["ExpLevel"] or 1), inline=True)
        embed.add_field(name="Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
        embed.add_field(name="Rep", value=int(data["Reputation"] or 0), inline=True)
        embed.add_field(name="XP", value=f"{int(data['Experience'] or 0):,}", inline=True)
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name="rank", description="Generates a member's rank card.")
    @app_commands.guild_only()
    async def rank(
        self,
        ctx: discord.Interaction,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        await self.servrank(ctx, user or ctx.user)

    async def servrank(self, ctx: discord.Interaction, user: discord.abc.User) -> None:
        await ctx.response.defer()

        data = await db.get_player_postgresData(user, ctx.guild)
        cur_exp = int(data["Experience"] or 0)
        curr_level = max(1, int(data["ExpLevel"] or 1))
        rank = await get_rank(user, ctx.guild) or 0

        background = Image.open(ASSET_DIR / "rank_banner.png").convert("RGBA")
        avatar_bytes = await user.display_avatar.with_size(1024).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

        thumbx = int(background.size[1] / 6.75)
        thumby = int(background.size[1] / 4.75)
        thumb_size = (int(background.size[1] / 1.75), int(background.size[1] / 1.75))
        rect_size = [40, 40, background.size[0] - 40, background.size[1] - 40]

        next_level_exp = (curr_level + 1) ** 4
        current_level_exp = curr_level**4
        level_span = max(1, next_level_exp - current_level_exp)
        progress = max(0.0, min(1.0, (cur_exp - current_level_exp) / level_span))

        bar_left = thumb_size[0] + 100
        bar_top = thumb_size[1] + 20
        bar_right = rect_size[2] - 40
        bar_bottom = thumb_size[1] + 50
        fill_right = bar_left + max(12, int((bar_right - bar_left) * progress))

        txt = Image.new("RGBA", background.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt)
        normal_font = ImageFont.load_default(size=27 if len(user.name) > 10 else 37)
        small_font = ImageFont.load_default(size=24)
        big_font = ImageFont.load_default(size=65)

        name_position = (bar_left + 15, bar_top - (35 if len(user.name) > 10 else 45))
        draw.text(name_position, user.name, font=normal_font, fill="white")

        exp_str = f"{cur_exp:,}"
        next_exp_str = f"{next_level_exp:,}"
        draw.text((bar_right - 175, bar_bottom - 70), f" / {next_exp_str} XP", font=small_font, fill=(255, 255, 255, 128))
        draw.text((bar_right - 175 - text_size(draw, exp_str, small_font)[0], bar_bottom - 70), exp_str, font=small_font, fill="white")

        level_text = str(curr_level)
        rank_text = f"#{rank}" if rank else "—"
        level_w, _ = text_size(draw, level_text, big_font)
        level_label_w, _ = text_size(draw, "LEVEL", small_font)
        rank_w, _ = text_size(draw, rank_text, big_font)
        rank_label_w, _ = text_size(draw, "RANK", small_font)

        draw.text((rect_size[2] - 15 - level_w, 40), level_text, font=big_font, fill=(167, 12, 18, 255))
        draw.text((rect_size[2] - 18 - level_w - level_label_w, 78), "LEVEL", font=small_font, fill=(167, 12, 18, 255))
        draw.text((rect_size[2] - 75 - level_w - level_label_w - rank_w, 40), rank_text, font=big_font, fill="white")
        draw.text((rect_size[2] - 85 - level_w - level_label_w - rank_w - rank_label_w, 78), "RANK", font=small_font, fill="white")

        draw.rounded_rectangle((bar_left - 2, bar_top - 2, bar_right + 2, bar_bottom + 2), radius=15, fill=(255, 255, 255, 255))
        draw.rounded_rectangle((bar_left, bar_top, bar_right, bar_bottom), radius=15, fill=(56, 58, 61, 255))
        draw.rounded_rectangle((bar_left, bar_top, fill_right, bar_bottom), radius=15, fill=(167, 12, 18, 255))

        member = ctx.guild.get_member(user.id) if ctx.guild else None
        status = member.status if member else discord.Status.offline
        status_color = {
            discord.Status.online: (66, 167, 102, 255),
            discord.Status.idle: (243, 151, 0, 255),
            discord.Status.do_not_disturb: (227, 51, 52, 255),
        }.get(status, (97, 107, 124, 255))

        thumb_position = (thumbx, thumby)
        avatar = mask_circle_transparent(crop_max_square(avatar), 4).resize(thumb_size, Image.Resampling.LANCZOS)
        background.paste(avatar, thumb_position, avatar)
        output = Image.alpha_composite(background, txt)

        status_box = [
            thumb_position[0] + thumb_size[0] - 35,
            thumb_position[1] + thumb_size[1] - 35,
            thumb_position[0] + thumb_size[0],
            thumb_position[1] + thumb_size[1],
        ]
        final_draw = ImageDraw.Draw(output)
        final_draw.ellipse(status_box, fill=status_color, outline="white", width=4)

        buffer = io.BytesIO()
        output.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        await ctx.followup.send(file=discord.File(buffer, filename="rank_card.png"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExperienceCommands(bot))
    log.info("Cog loaded: ExperienceCommands")
