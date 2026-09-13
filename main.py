from __future__ import annotations

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import BASE_DIR, BRAND_NAME, CREATOR_NAME, config, require_config
from services import db

BANNER = f"""
╔══════════════════════════════════════╗
║              {BRAND_NAME:^24}      ║
║        Built by {CREATOR_NAME:<19}║
╚══════════════════════════════════════╝
"""


def configure_logging() -> None:
    level_name = str(config.get("bot", {}).get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


configure_logging()
log = logging.getLogger(__name__)


async def get_prefix(bot: commands.Bot, message: discord.Message):
    default_prefix = str(config.get("bot", {}).get("prefix", "!"))
    if message.guild is None:
        return commands.when_mentioned_or(default_prefix)(bot, message)

    try:
        guild_config = await db.get_server_config(message.guild)
        prefix = guild_config["prefix"] or default_prefix
    except Exception:
        log.exception("Unable to retrieve prefix for guild %s; using default", message.guild.id)
        prefix = default_prefix

    return commands.when_mentioned_or(str(prefix))(bot, message)


def build_intents() -> discord.Intents:
    intent_config = config.get("bot", {}).get("intents", {})
    intents = discord.Intents.none()
    intents.guilds = bool(intent_config.get("guilds", True))
    intents.members = bool(intent_config.get("members", True))
    intents.messages = bool(intent_config.get("messages", True))
    intents.message_content = bool(intent_config.get("message_content", False))
    intents.reactions = bool(intent_config.get("reactions", True))
    intents.typing = bool(intent_config.get("typing", False))
    intents.moderation = bool(intent_config.get("bans", True))
    return intents


class SpryteAI(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=bool(config.get("bot", {}).get("case_insensitive", True)),
            intents=build_intents(),
        )
        self._extensions_loaded = False

    async def setup_hook(self) -> None:
        await db.connect()
        await self.load_extensions()

        if bool(config.get("bot", {}).get("sync_commands", True)):
            synced = await self.tree.sync()
            synced_names = ", ".join(command.name for command in synced)
            log.info(
                "Synced %s global application command(s): %s",
                len(synced),
                synced_names or "<none>",
            )

            pokemon = next((command for command in synced if command.name == "pokemon"), None)
            if pokemon is not None:
                options = getattr(pokemon, "options", None) or []
                child_names = [getattr(option, "name", "?") for option in options]
                log.info(
                    "Discord accepted /pokemon with %s child option(s): %s",
                    len(child_names),
                    ", ".join(child_names) or "<not exposed by returned model>",
                )

    async def load_extensions(self) -> None:
        if self._extensions_loaded:
            return

        cogs_dir = BASE_DIR / "cogs"
        for path in sorted(cogs_dir.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            relative = path.relative_to(BASE_DIR).with_suffix("")
            module = ".".join(relative.parts)
            try:
                await self.load_extension(module)
            except commands.ExtensionAlreadyLoaded:
                log.debug("Extension already loaded: %s", module)
            except Exception:
                log.exception("Failed to load extension: %s", module)

        self._extensions_loaded = True

    async def close(self) -> None:
        await db.close()
        await super().close()


bot = SpryteAI()


@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")
    log.info("%s", BANNER)
    status_text = str(config.get("bot", {}).get("status", BRAND_NAME))
    try:
        await bot.change_presence(activity=discord.Game(name=status_text))
    except discord.HTTPException:
        log.exception("Unable to update bot presence")


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    await db.add_guild_postgresql(guild)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    # Discord error 10062 means the interaction token is already invalid.
    # Trying to send another error response just creates a second traceback.
    original = getattr(error, "original", error)
    if interaction.extras.get("pokecord_interaction_expired") or (
        isinstance(original, discord.NotFound) and getattr(original, "code", None) == 10062
    ):
        log.warning(
            "Application interaction expired before acknowledgement: command=%s interaction=%s",
            interaction.command,
            interaction.id,
        )
        return

    log.error(
        "Application command error in %s: %s",
        interaction.command,
        error,
        exc_info=(type(error), error, error.__traceback__),
    )
    message = "That command failed unexpectedly. The error has been logged."
    if isinstance(error, app_commands.CheckFailure):
        message = "You do not have permission to use that command."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound as exc:
        if getattr(exc, "code", None) == 10062:
            log.warning(
                "Could not send application-command error response because interaction %s expired",
                interaction.id,
            )
            return
        log.exception("Unable to send application command error response")
    except discord.HTTPException:
        log.exception("Unable to send application command error response")


async def main() -> None:
    token = str(require_config(("bot", "token"), label="DISCORD_TOKEN"))
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
