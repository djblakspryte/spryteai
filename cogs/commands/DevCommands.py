from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import BASE_DIR, config

log = logging.getLogger(__name__)


class DevCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _matching_extensions(self, cog_name: str) -> list[str]:
        needle = cog_name.strip().lower()
        matches: list[str] = []
        for path in sorted((BASE_DIR / "cogs").rglob("*.py")):
            if path.name.startswith("_"):
                continue
            module = ".".join(path.relative_to(BASE_DIR).with_suffix("").parts)
            if needle in module.lower():
                matches.append(module)
        return matches

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        return await self.bot.is_owner(interaction.user)

    async def manage_cog(self, ctx: discord.Interaction, cog_name: str, action: str) -> None:
        if not await self._is_owner(ctx):
            return await ctx.response.send_message("You do not have permission to use this command.", ephemeral=True)

        matches = self._matching_extensions(cog_name)
        if not matches:
            return await ctx.response.send_message(f"No cog found matching `{cog_name}`.", ephemeral=True)

        await ctx.response.defer(ephemeral=True)
        results: list[str] = []
        for module in matches:
            try:
                if action == "load":
                    await self.bot.load_extension(module)
                elif action == "unload":
                    await self.bot.unload_extension(module)
                elif action == "reload":
                    await self.bot.reload_extension(module)
                else:
                    raise ValueError(f"Unknown cog action: {action}")
                results.append(f"✅ {action.capitalize()}ed `{module}`")
            except commands.ExtensionError as exc:
                log.exception("Failed to %s extension %s", action, module)
                results.append(f"❌ `{module}`: {exc}")

        if bool(config.get("bot", {}).get("sync_on_cog_reload", False)):
            try:
                synced = await self.bot.tree.sync()
                results.append(f"🔄 Synced {len(synced)} global command(s)")
            except discord.HTTPException as exc:
                results.append(f"⚠️ Command sync failed: {exc}")

        await ctx.followup.send("\n".join(results), ephemeral=True)

    @app_commands.command(name="load", description="Loads a bot extension (owner only).")
    async def load(self, ctx: discord.Interaction, cog_name: str) -> None:
        await self.manage_cog(ctx, cog_name, "load")

    @app_commands.command(name="unload", description="Unloads a bot extension (owner only).")
    async def unload(self, ctx: discord.Interaction, cog_name: str) -> None:
        await self.manage_cog(ctx, cog_name, "unload")

    @app_commands.command(name="reload", description="Reloads a bot extension (owner only).")
    async def reload(self, ctx: discord.Interaction, cog_name: str) -> None:
        await self.manage_cog(ctx, cog_name, "reload")

    @app_commands.command(name="sync", description="Syncs global slash commands (owner only).")
    async def sync(self, ctx: discord.Interaction) -> None:
        if not await self._is_owner(ctx):
            return await ctx.response.send_message("You do not have permission to use this command.", ephemeral=True)

        await ctx.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        await ctx.followup.send(f"Synced {len(synced)} global command(s).", ephemeral=True)

    @app_commands.command(name="quit", description="Shuts down SpryteAI (owner only).")
    async def quit(self, ctx: discord.Interaction) -> None:
        if not await self._is_owner(ctx):
            return await ctx.response.send_message("You do not have permission to use this command.", ephemeral=True)

        await ctx.response.send_message("Shutting down... 👋", ephemeral=True)
        await self.bot.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DevCommands(bot))
    log.info("Cog loaded: DevCommands")
