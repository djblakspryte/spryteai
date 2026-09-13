from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from contextvars import ContextVar
from typing import Iterable, Literal, Any

import discord
from discord import app_commands
from discord.ext import commands

from config import BRAND_NAME, config
from services import db

log = logging.getLogger(__name__)

_CURRENT_COMMUNITY_CONFIG: ContextVar[dict[str, Any] | None] = ContextVar("spryteai_community_config", default=None)


@dataclass(frozen=True)
class ChannelSpec:
    key: str
    name: str
    kind: str = "text"
    topic: str | None = None
    read_only: bool = False
    public: bool | None = None
    access_roles: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CategorySpec:
    key: str
    name: str
    public: bool = True
    access_roles: tuple[str, ...] = ()
    staff_only: bool = False
    channels: tuple[ChannelSpec, ...] = ()


def _id(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized or "item"


class SelfRoleSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        guild_id: int,
        group_key: str,
        group_label: str,
        role_entries: list[tuple[str, int, str | None, str]],
        row: int,
    ) -> None:
        self.group_key = group_key
        self.role_ids = {role_id for _, role_id, _, _ in role_entries if role_id}
        options = [
            discord.SelectOption(
                label=label[:100], value=str(role_id), emoji=emoji or None,
                description=description[:100] if description else None,
            )
            for label, role_id, emoji, description in role_entries if role_id
        ]
        super().__init__(
            custom_id=f"spryteai:selfroles:{guild_id}:{group_key}"[:100],
            placeholder=f"Choose {group_label.lower()}…"[:150], min_values=0,
            max_values=max(1, min(25, len(options))), options=options[:25], row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Self-roles are only available inside the server.", ephemeral=True)
            return
        selected = {int(value) for value in self.values}
        managed_roles = [interaction.guild.get_role(role_id) for role_id in self.role_ids]
        managed_roles = [role for role in managed_roles if role is not None and not role.managed]
        add_roles = [r for r in managed_roles if r.id in selected and r not in interaction.user.roles]
        remove_roles = [r for r in managed_roles if r.id not in selected and r in interaction.user.roles]
        try:
            if add_roles:
                await interaction.user.add_roles(*add_roles, reason=f"{BRAND_NAME} self-role selection")
            if remove_roles:
                await interaction.user.remove_roles(*remove_roles, reason=f"{BRAND_NAME} self-role selection")
        except discord.Forbidden:
            await interaction.response.send_message(
                f"I can't update those roles. Put the {BRAND_NAME} role above the self-assignable roles and give me Manage Roles.",
                ephemeral=True,
            )
            return
        names = [role.name for role in interaction.user.roles if role.id in selected]
        await interaction.response.send_message(
            f"Updated your {self.group_key} roles: **{', '.join(names) if names else 'none'}**.", ephemeral=True
        )


class ClearSelfRolesButton(discord.ui.Button):
    def __init__(self, *, guild_id: int, removable_ids: set[int]) -> None:
        super().__init__(
            label="Clear my self-roles", style=discord.ButtonStyle.secondary, emoji="🧹",
            custom_id=f"spryteai:selfroles:{guild_id}:clear"[:100], row=4,
        )
        self.removable_ids = removable_ids

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Self-roles are only available inside the server.", ephemeral=True)
            return
        removable = [r for r in interaction.user.roles if r.id in self.removable_ids and not r.managed]
        if removable:
            try:
                await interaction.user.remove_roles(*removable, reason=f"{BRAND_NAME} self-role clear")
            except discord.Forbidden:
                await interaction.response.send_message("I can't remove those roles. Check my role hierarchy.", ephemeral=True)
                return
        await interaction.response.send_message(f"Cleared your {BRAND_NAME} self-assignable roles.", ephemeral=True)


class CommunityRoleView(discord.ui.View):
    def __init__(self, community_cfg: dict[str, object], guild_id: int) -> None:
        super().__init__(timeout=None)
        role_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        definitions = community_cfg.get("role_definitions", {}) if isinstance(community_cfg.get("role_definitions"), dict) else {}
        group_cfg = community_cfg.get("self_role_groups", {}) if isinstance(community_cfg.get("self_role_groups"), dict) else {}
        grouped: dict[str, list[tuple[str, int, str | None, str]]] = {}
        removable_ids: set[int] = set()
        for key, raw in definitions.items():
            if not isinstance(raw, dict) or not raw.get("self_assignable", False):
                continue
            role_id = _id(role_ids.get(key))
            if not role_id:
                continue
            removable_ids.add(role_id)
            group = str(raw.get("group") or "interests")
            grouped.setdefault(group, []).append((
                str(raw.get("name") or key), role_id,
                str(raw.get("emoji")) if raw.get("emoji") else None,
                str(raw.get("description") or ""),
            ))
        for row, (group_key, entries) in enumerate(list(grouped.items())[:4]):
            raw_group = group_cfg.get(group_key, {}) if isinstance(group_cfg.get(group_key), dict) else {}
            label = str(raw_group.get("label") or group_key.replace("_", " ").title())
            self.add_item(SelfRoleSelect(
                guild_id=guild_id, group_key=group_key, group_label=label, role_entries=entries, row=row
            ))
        self.add_item(ClearSelfRolesButton(guild_id=guild_id, removable_ids=removable_ids))


class CommunityCommands(commands.GroupCog, group_name="community", group_description="Community setup and onboarding tools"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._persistent_view_guilds: set[int] = set()
        self._persistent_views: dict[int, CommunityRoleView] = {}
        self._view_bootstrap_task: asyncio.Task | None = None
        self._pending_invocation_delete: discord.abc.GuildChannel | None = None

    async def cog_load(self) -> None:
        self._view_bootstrap_task = asyncio.create_task(self._register_all_persistent_role_views(), name="community-role-views")

    async def cog_unload(self) -> None:
        if self._view_bootstrap_task and not self._view_bootstrap_task.done():
            self._view_bootstrap_task.cancel()
        for view in list(self._persistent_views.values()):
            try:
                self.bot.remove_view(view)
            except Exception:
                pass
        self._persistent_views.clear()
        self._persistent_view_guilds.clear()

    async def _activate_guild(self, guild: discord.Guild) -> tuple[int, dict[str, Any]]:
        cid = await db.community_id_for_guild(guild)
        full = await db.get_community_config_by_id(cid)
        _CURRENT_COMMUNITY_CONFIG.set(full)
        return cid, full

    @staticmethod
    def _full_cfg() -> dict[str, Any]:
        return _CURRENT_COMMUNITY_CONFIG.get() or config

    @staticmethod
    def _community_cfg() -> dict[str, object]:
        full = _CURRENT_COMMUNITY_CONFIG.get() or config
        value = full.get("community", {})
        return value if isinstance(value, dict) else {}

    @classmethod
    def _role_definitions(cls) -> dict[str, dict[str, object]]:
        raw = cls._community_cfg().get("role_definitions", {})
        if not isinstance(raw, dict):
            return {}
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}

    @classmethod
    def _layout(cls) -> list[CategorySpec]:
        raw_layout = cls._community_cfg().get("layout", [])
        if not isinstance(raw_layout, list):
            return []

        categories: list[CategorySpec] = []
        for raw_category in raw_layout:
            if not isinstance(raw_category, dict) or not raw_category.get("name"):
                continue
            category_name = str(raw_category["name"])
            category_key = str(raw_category.get("key") or _slug(category_name))
            raw_channels = raw_category.get("channels", [])
            channels: list[ChannelSpec] = []
            if isinstance(raw_channels, list):
                for raw_channel in raw_channels:
                    if not isinstance(raw_channel, dict) or not raw_channel.get("name"):
                        continue
                    channel_name = str(raw_channel["name"])
                    access = raw_channel.get("access_roles")
                    access_roles = tuple(str(item) for item in access) if isinstance(access, list) else None
                    public_value = raw_channel.get("public")
                    public = bool(public_value) if isinstance(public_value, bool) else None
                    channels.append(
                        ChannelSpec(
                            key=str(raw_channel.get("key") or _slug(channel_name)),
                            name=channel_name,
                            kind=str(raw_channel.get("type") or raw_channel.get("kind") or "text").lower(),
                            topic=str(raw_channel["topic"]) if raw_channel.get("topic") is not None else None,
                            read_only=bool(raw_channel.get("read_only", False)),
                            public=public,
                            access_roles=access_roles,
                        )
                    )
            access = raw_category.get("access_roles", [])
            categories.append(
                CategorySpec(
                    key=category_key,
                    name=category_name,
                    public=bool(raw_category.get("public", not bool(access) and not raw_category.get("staff_only", False))),
                    access_roles=tuple(str(item) for item in access) if isinstance(access, list) else (),
                    staff_only=bool(raw_category.get("staff_only", False)),
                    channels=tuple(channels),
                )
            )
        return categories

    @classmethod
    def _config_issues(cls, layout: list[CategorySpec] | None = None) -> list[str]:
        layout = layout if layout is not None else cls._layout()
        definitions = cls._role_definitions()
        issues: list[str] = []
        category_keys: set[str] = set()
        channel_keys: set[str] = set()
        channel_names: set[tuple[str, str]] = set()

        for category in layout:
            if category.key in category_keys:
                issues.append(f"duplicate category key `{category.key}`")
            category_keys.add(category.key)
            for role_key in category.access_roles:
                if role_key not in definitions:
                    issues.append(f"category `{category.name}` references unknown role key `{role_key}`")
            for channel in category.channels:
                if channel.key in channel_keys:
                    issues.append(f"duplicate channel key `{channel.key}`")
                channel_keys.add(channel.key)
                identity = (channel.name.casefold(), channel.kind)
                if identity in channel_names:
                    issues.append(f"duplicate {channel.kind} channel name `{channel.name}`")
                channel_names.add(identity)
                for role_key in channel.access_roles or ():
                    if role_key not in definitions:
                        issues.append(f"channel `{channel.name}` references unknown role key `{role_key}`")

        community = cls._community_cfg()
        for setting in ("roles_channel_key", "live_channel_key", "pokemon_spawn_channel_key"):
            value = str(community.get(setting) or "")
            if value and value not in channel_keys:
                issues.append(f"`community.{setting}` points to unknown channel key `{value}`")

        valid_permission_flags = set(discord.Permissions.VALID_FLAGS)
        for key, raw in definitions.items():
            aliases = raw.get("aliases", [])
            if aliases is not None and not isinstance(aliases, list):
                issues.append(f"role `{key}` has invalid `aliases`; expected a list")
            permissions = raw.get("permissions")
            if permissions is not None:
                if isinstance(permissions, list):
                    unknown = [str(flag) for flag in permissions if str(flag) not in valid_permission_flags]
                elif isinstance(permissions, dict):
                    unknown = [str(flag) for flag in permissions if str(flag) not in valid_permission_flags]
                else:
                    unknown = ["<invalid permissions value>"]
                if unknown:
                    issues.append(f"role `{key}` has unknown permission flag(s): {', '.join(unknown[:6])}")

        groups: dict[str, int] = {}
        for key, raw in definitions.items():
            if raw.get("self_assignable", False):
                group = str(raw.get("group") or "interests")
                groups[group] = groups.get(group, 0) + 1
        if len(groups) > 4:
            issues.append("more than 4 self-role groups are configured; Discord UI reserves one row for Clear")
        for group, count in groups.items():
            if count > 25:
                issues.append(f"self-role group `{group}` has {count} roles; Discord allows 25 options per select")
        return issues

    async def _register_all_persistent_role_views(self) -> None:
        await self.bot.wait_until_ready()
        for guild in list(self.bot.guilds):
            try:
                await self._register_persistent_role_view(guild)
            except Exception:
                log.exception("Unable to register self-role view for guild %s", guild.id)

    async def _register_persistent_role_view(self, guild: discord.Guild, *, force: bool = False) -> None:
        if guild.id in self._persistent_view_guilds and not force:
            return
        _, full = await self._activate_guild(guild)
        community_cfg = full.get("community", {}) if isinstance(full.get("community"), dict) else {}
        role_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        definitions = community_cfg.get("role_definitions", {}) if isinstance(community_cfg.get("role_definitions"), dict) else {}
        has_self_roles = any(
            isinstance(raw, dict) and raw.get("self_assignable", False) and _id(role_ids.get(key))
            for key, raw in definitions.items()
        )

        old_view = self._persistent_views.pop(guild.id, None)
        if old_view is not None:
            try:
                self.bot.remove_view(old_view)
            except Exception:
                log.debug("Unable to unregister old persistent role view for guild %s", guild.id, exc_info=True)
        self._persistent_view_guilds.discard(guild.id)

        if not has_self_roles:
            return
        view = CommunityRoleView(community_cfg, guild.id)
        self.bot.add_view(view)
        self._persistent_views[guild.id] = view
        self._persistent_view_guilds.add(guild.id)
        log.info("Registered persistent community self-role view for guild %s", guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await db.ensure_community_for_guild(guild.id, guild.name, guild.owner_id)
        await self._register_persistent_role_view(guild, force=True)

    async def _owner_only(self, interaction: discord.Interaction) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("You need Administrator permission to manage this community.", ephemeral=True)
        return False

    @staticmethod
    def _find_category(guild: discord.Guild, name: str) -> discord.CategoryChannel | None:
        target = name.casefold()
        return next((category for category in guild.categories if category.name.casefold() == target), None)

    @staticmethod
    def _find_channel(guild: discord.Guild, name: str, kind: str) -> discord.abc.GuildChannel | None:
        target = name.casefold()
        if kind == "voice":
            return next((channel for channel in guild.voice_channels if channel.name.casefold() == target), None)
        return next((channel for channel in guild.text_channels if channel.name.casefold() == target), None)

    @staticmethod
    def _find_role(guild: discord.Guild, name: str) -> discord.Role | None:
        target = name.casefold()
        return next((role for role in guild.roles if role.name.casefold() == target), None)

    def _staff_roles(self, guild: discord.Guild) -> list[discord.Role]:
        community_cfg = self._community_cfg()
        staff_cfg = community_cfg.get("staff_access", {}) if isinstance(community_cfg.get("staff_access"), dict) else {}
        full_cfg = self._full_cfg()
        configured_roles = full_cfg.get("roles", {}) if isinstance(full_cfg.get("roles"), dict) else {}
        result: dict[int, discord.Role] = {}

        top_level_keys = staff_cfg.get("top_level_role_keys", [])
        if isinstance(top_level_keys, list):
            for key in top_level_keys:
                role_id = _id(configured_roles.get(str(key)))
                if role_id and (role := guild.get_role(role_id)):
                    result[role.id] = role

        names = staff_cfg.get("role_names", [])
        if isinstance(names, list):
            for name in names:
                if role := self._find_role(guild, str(name)):
                    result[role.id] = role

        role_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        role_keys = staff_cfg.get("community_role_keys", [])
        if isinstance(role_keys, list):
            for key in role_keys:
                role_id = _id(role_ids.get(str(key)))
                if role_id and (role := guild.get_role(role_id)):
                    result[role.id] = role
        return list(result.values())

    @staticmethod
    def _dedupe_roles(roles: Iterable[discord.Role | None]) -> list[discord.Role]:
        result: dict[int, discord.Role] = {}
        for role in roles:
            if role is not None:
                result[role.id] = role
        return list(result.values())

    def _resolve_role_keys(self, guild: discord.Guild, keys: Iterable[str], role_ids: dict[str, int]) -> list[discord.Role]:
        roles: list[discord.Role | None] = []
        definitions = self._role_definitions()
        for key in keys:
            raw = definitions.get(str(key), {})
            if raw.get("builtin") == "premium_subscriber":
                roles.append(getattr(guild, "premium_subscriber_role", None))
                continue
            role_id = _id(role_ids.get(str(key)))
            roles.append(guild.get_role(role_id) if role_id else None)
        return self._dedupe_roles(roles)

    @staticmethod
    def _role_permissions(raw: dict[str, object]) -> discord.Permissions | None:
        configured = raw.get("permissions")
        if configured is None:
            return None
        permissions = discord.Permissions.none()
        if isinstance(configured, list):
            for flag in configured:
                name = str(flag)
                if name in discord.Permissions.VALID_FLAGS:
                    setattr(permissions, name, True)
        elif isinstance(configured, dict):
            for flag, enabled in configured.items():
                name = str(flag)
                if name in discord.Permissions.VALID_FLAGS:
                    setattr(permissions, name, bool(enabled))
        return permissions

    def _permission_overwrites(
        self,
        guild: discord.Guild,
        *,
        allowed_roles: list[discord.Role] | None,
        read_only: bool = False,
        public: bool = False,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

        if public:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False if read_only else True,
                add_reactions=False if read_only else True,
                connect=True,
                speak=True,
            )
        else:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                connect=False,
            )
            for role in allowed_roles or []:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False if read_only else True,
                    add_reactions=False if read_only else True,
                    connect=True,
                    speak=True,
                )

        for role in self._staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                add_reactions=True,
                connect=True,
                speak=True,
            )

        if guild.me is not None:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                add_reactions=True,
                embed_links=True,
                attach_files=True,
                connect=True,
                speak=True,
                manage_channels=True,
                manage_messages=True,
            )
        return overwrites

    async def _ensure_configured_roles(self, guild: discord.Guild) -> tuple[dict[str, int], int]:
        community_cfg = self._community_cfg()
        existing_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        role_ids: dict[str, int] = {str(k): _id(v) for k, v in existing_ids.items() if _id(v)}
        created_roles = 0

        for key, raw in self._role_definitions().items():
            if raw.get("builtin") == "premium_subscriber":
                role = getattr(guild, "premium_subscriber_role", None)
                if role is not None:
                    role_ids[key] = role.id
                continue

            existing = guild.get_role(_id(role_ids.get(key))) if _id(role_ids.get(key)) else None
            if existing is None and raw.get("name"):
                existing = self._find_role(guild, str(raw["name"]))
            if existing is None:
                aliases = raw.get("aliases", [])
                if isinstance(aliases, list):
                    for alias in aliases:
                        existing = self._find_role(guild, str(alias))
                        if existing is not None:
                            break

            desired_permissions = self._role_permissions(raw)
            if existing is not None:
                role_ids[key] = existing.id
                target_name = str(raw.get("name") or "")
                if not existing.managed:
                    edit_kwargs: dict[str, object] = {"reason": f"{BRAND_NAME} community role sync"}
                    if target_name and existing.name != target_name:
                        edit_kwargs["name"] = target_name
                    if desired_permissions is not None and existing.permissions != desired_permissions:
                        edit_kwargs["permissions"] = desired_permissions
                    if len(edit_kwargs) > 1:
                        try:
                            await existing.edit(**edit_kwargs)
                        except (discord.Forbidden, discord.HTTPException):
                            log.warning("Unable to sync role %s", existing.name, exc_info=True)
                continue

            if not raw.get("create", True) or not raw.get("name"):
                continue
            create_kwargs: dict[str, object] = {
                "name": str(raw["name"]),
                "reason": f"{BRAND_NAME} community setup",
            }
            if desired_permissions is not None:
                create_kwargs["permissions"] = desired_permissions
            role = await guild.create_role(**create_kwargs)
            role_ids[key] = role.id
            created_roles += 1
        return role_ids, created_roles

    async def _ensure_category(
        self,
        guild: discord.Guild,
        spec: CategorySpec,
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite],
        existing_id: int = 0,
    ) -> tuple[discord.CategoryChannel, bool]:
        existing = guild.get_channel(existing_id) if existing_id else None
        if not isinstance(existing, discord.CategoryChannel):
            existing = self._find_category(guild, spec.name)
        if existing:
            await existing.edit(name=spec.name, overwrites=overwrites, reason=f"{BRAND_NAME} community permission/name sync")
            return existing, False
        category = await guild.create_category(spec.name, overwrites=overwrites, reason=f"{BRAND_NAME} community setup")
        return category, True

    async def _ensure_channel(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        spec: ChannelSpec,
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite],
        existing_id: int = 0,
    ) -> tuple[discord.abc.GuildChannel, bool, bool]:
        existing = guild.get_channel(existing_id) if existing_id else None
        expected_type = discord.VoiceChannel if spec.kind == "voice" else discord.TextChannel
        if not isinstance(existing, expected_type):
            existing = self._find_channel(guild, spec.name, spec.kind)
        moved = False
        if existing:
            kwargs: dict[str, object] = {
                "name": spec.name,
                "overwrites": overwrites,
                "reason": f"{BRAND_NAME} community permission/name sync",
            }
            if existing.category_id != category.id:
                kwargs["category"] = category
                moved = True
            if isinstance(existing, discord.TextChannel) and spec.topic is not None:
                kwargs["topic"] = spec.topic
            await existing.edit(**kwargs)
            return existing, False, moved

        if spec.kind == "voice":
            channel = await guild.create_voice_channel(
                spec.name,
                category=category,
                overwrites=overwrites,
                reason=f"{BRAND_NAME} community setup",
            )
        else:
            channel = await guild.create_text_channel(
                spec.name,
                category=category,
                topic=spec.topic,
                overwrites=overwrites,
                reason=f"{BRAND_NAME} community setup",
            )
        return channel, True, False

    def _planned_keep_ids(self, guild: discord.Guild, layout: list[CategorySpec]) -> tuple[set[int], set[int]]:
        community_cfg = self._community_cfg()
        stored_categories = community_cfg.get("categories", {}) if isinstance(community_cfg.get("categories"), dict) else {}
        stored_channels = community_cfg.get("channels", {}) if isinstance(community_cfg.get("channels"), dict) else {}
        category_ids: set[int] = set()
        channel_ids: set[int] = set()
        for category_spec in layout:
            category = guild.get_channel(_id(stored_categories.get(category_spec.key)))
            if not isinstance(category, discord.CategoryChannel):
                category = self._find_category(guild, category_spec.name)
            if category is not None:
                category_ids.add(category.id)
            for channel_spec in category_spec.channels:
                channel = guild.get_channel(_id(stored_channels.get(channel_spec.key)))
                expected_type = discord.VoiceChannel if channel_spec.kind == "voice" else discord.TextChannel
                if not isinstance(channel, expected_type):
                    channel = self._find_channel(guild, channel_spec.name, channel_spec.kind)
                if channel is not None:
                    channel_ids.add(channel.id)
        return category_ids, channel_ids

    def _protected_role_ids(self, guild: discord.Guild, extra_role_ids: Iterable[int] = ()) -> set[int]:
        protected = {guild.default_role.id, *[int(role_id) for role_id in extra_role_ids if role_id]}
        community_cfg = self._community_cfg()

        for role in guild.roles:
            if role.managed:
                protected.add(role.id)
        if guild.me is not None:
            protected.update(role.id for role in guild.me.roles)

        full_cfg = self._full_cfg()
        configured_roles = full_cfg.get("roles", {}) if isinstance(full_cfg.get("roles"), dict) else {}
        preserve_cfg = community_cfg.get("preserve", {}) if isinstance(community_cfg.get("preserve"), dict) else {}
        top_level_keys = preserve_cfg.get("top_level_role_keys", [])
        if isinstance(top_level_keys, list):
            for key in top_level_keys:
                role_id = _id(configured_roles.get(str(key)))
                if role_id:
                    protected.add(role_id)

        names = preserve_cfg.get("role_names", [])
        if isinstance(names, list):
            for name in names:
                if role := self._find_role(guild, str(name)):
                    protected.add(role.id)

        runtime_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        for key, raw in self._role_definitions().items():
            if not raw.get("preserve", True):
                continue
            role_id = _id(runtime_ids.get(key))
            if role_id:
                protected.add(role_id)
            if raw.get("name") and (role := self._find_role(guild, str(raw["name"]))):
                protected.add(role.id)

        booster = getattr(guild, "premium_subscriber_role", None)
        if booster is not None:
            protected.add(booster.id)
        return protected

    def _destructive_preview(
        self, guild: discord.Guild, layout: list[CategorySpec]
    ) -> tuple[list[discord.abc.GuildChannel], list[discord.CategoryChannel], list[discord.Role]]:
        keep_categories, keep_channels = self._planned_keep_ids(guild, layout)
        obsolete_channels = [
            channel
            for channel in guild.channels
            if not isinstance(channel, discord.CategoryChannel) and channel.id not in keep_channels
        ]
        obsolete_categories = [category for category in guild.categories if category.id not in keep_categories]
        protected_roles = self._protected_role_ids(guild)
        target_role_names = {
            str(raw.get("name"))
            for raw in self._role_definitions().values()
            if raw.get("name")
        }
        obsolete_roles = [
            role
            for role in guild.roles
            if role.id not in protected_roles
            and role.name not in target_role_names
            and role != guild.default_role
            and not role.managed
        ]
        return obsolete_channels, obsolete_categories, obsolete_roles

    async def _prune_server(
        self,
        guild: discord.Guild,
        *,
        keep_channel_ids: set[int],
        keep_category_ids: set[int],
        keep_role_ids: set[int],
        invocation_channel_id: int | None,
    ) -> tuple[int, int, int, list[str]]:
        deleted_channels = deleted_categories = deleted_roles = 0
        failures: list[str] = []
        deferred_invocation: discord.abc.GuildChannel | None = None

        for channel in list(guild.channels):
            if isinstance(channel, discord.CategoryChannel) or channel.id in keep_channel_ids:
                continue
            if invocation_channel_id and channel.id == invocation_channel_id:
                deferred_invocation = channel
                continue
            try:
                await channel.delete(reason=f"{BRAND_NAME} destructive community restructure")
                deleted_channels += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"channel #{channel.name}: {type(exc).__name__}")

        for category in list(guild.categories):
            if category.id in keep_category_ids:
                continue
            try:
                await category.delete(reason=f"{BRAND_NAME} destructive community restructure")
                deleted_categories += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"category {category.name}: {type(exc).__name__}")

        protected_roles = self._protected_role_ids(guild, keep_role_ids)
        me = guild.me
        for role in reversed(guild.roles):
            if role.id in protected_roles or role == guild.default_role or role.managed:
                continue
            if me is not None and role >= me.top_role:
                failures.append(f"role @{role.name}: above/equal to {BRAND_NAME}")
                continue
            try:
                await role.delete(reason=f"{BRAND_NAME} destructive community restructure")
                deleted_roles += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"role @{role.name}: {type(exc).__name__}")

        self._pending_invocation_delete = deferred_invocation
        return deleted_channels, deleted_categories, deleted_roles, failures

    async def _persist_runtime_config(
        self,
        guild: discord.Guild,
        *,
        categories: dict[str, int],
        channels: dict[str, int],
        roles: dict[str, int],
        changed_by: int | None = None,
    ) -> None:
        cid, full = await self._activate_guild(guild)
        community = full.get("community", {}) if isinstance(full.get("community"), dict) else {}
        live_key = str(community.get("live_channel_key") or "")
        spawn_key = str(community.get("pokemon_spawn_channel_key") or "")
        patch = {
            "community": {"categories": categories, "channels": channels, "roles": roles},
            "streaming": {"live_channel_id": channels.get(live_key, 0)},
            "pokecord": {"spawn_channel_id": channels.get(spawn_key, 0)},
        }
        await db.patch_community_override(cid, patch, changed_by=changed_by)
        await self._activate_guild(guild)

    @staticmethod
    def _config_path_allowed(path: str) -> bool:
        normalized = path.strip().lower()
        allowed = (
            "community.",
            "streaming.",
            "pokecord.",
            "twitch.chat.",
            "twitch.discord.",
        )
        return normalized.startswith(allowed) and not any(
            blocked in normalized for blocked in ("secret", "token", "password", "redirect_uri", "client_id")
        )

    @staticmethod
    def _set_nested(target: dict[str, Any], path: str, value: Any) -> None:
        parts = [part for part in path.split(".") if part]
        cursor = target
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                child = {}
                cursor[part] = child
            cursor = child
        cursor[parts[-1]] = value

    @staticmethod
    def _delete_nested(target: dict[str, Any], path: str) -> bool:
        parts = [part for part in path.split(".") if part]
        if not parts:
            return False
        cursor: dict[str, Any] = target
        parents: list[tuple[dict[str, Any], str]] = []
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                return False
            parents.append((cursor, part))
            cursor = child
        if parts[-1] not in cursor:
            return False
        del cursor[parts[-1]]
        for parent, key in reversed(parents):
            child = parent.get(key)
            if isinstance(child, dict) and not child:
                del parent[key]
            else:
                break
        return True

    @staticmethod
    def _redact_config(value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, child in value.items():
                lowered = str(key).lower()
                if any(term in lowered for term in ("secret", "token", "password")):
                    result[str(key)] = "***REDACTED***"
                else:
                    result[str(key)] = CommunityCommands._redact_config(child)
            return result
        if isinstance(value, list):
            return [CommunityCommands._redact_config(item) for item in value]
        return value

    @app_commands.command(name="config-show", description="Show this community's database-backed configuration overrides.")
    async def config_show(self, interaction: discord.Interaction) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside your server.", ephemeral=True)
            return
        cid, _ = await self._activate_guild(interaction.guild)
        record = await db.get_community_record(cid)
        override = db.json_object(record["config"], field="communities.config") if record else {}
        features = db.json_object(record["features"], field="communities.features") if record else {}
        payload = {
            "community_id": cid,
            "features": features,
            "overrides": self._redact_config(override),
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
        if len(rendered) <= 1800:
            await interaction.response.send_message(f"```json\n{rendered}\n```", ephemeral=True)
            return
        file = discord.File(io.BytesIO(rendered.encode("utf-8")), filename=f"spryteai-community-{cid}.json")
        await interaction.response.send_message(
            f"Community `{cid}` has a larger override. I attached the redacted configuration.",
            file=file, ephemeral=True,
        )

    @app_commands.command(name="config-set", description="Set one database-backed configuration value for this community.")
    @app_commands.describe(path="Example: pokecord.spawn_min_seconds", value="JSON value, or plain text")
    async def config_set(self, interaction: discord.Interaction, path: str, value: str) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside your server.", ephemeral=True)
            return
        path = path.strip()
        if not path or not self._config_path_allowed(path):
            await interaction.response.send_message(
                "That path is not editable here. Allowed prefixes: `community.`, `streaming.`, `pokecord.`, "
                "`twitch.chat.`, and `twitch.discord.`. Credentials/tokens are never editable from Discord.",
                ephemeral=True,
            )
            return
        try:
            parsed: Any = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        cid, _ = await self._activate_guild(interaction.guild)
        record = await db.get_community_record(cid)
        override = db.json_object(record["config"], field="communities.config") if record else {}
        self._set_nested(override, path, parsed)
        await db.replace_community_override(cid, override, changed_by=interaction.user.id)
        await self._activate_guild(interaction.guild)
        if path.lower().startswith("community."):
            await self._register_persistent_role_view(interaction.guild, force=True)
        await interaction.response.send_message(
            f"Updated community `{cid}`: `{path}` = `{str(parsed)[:500]}`", ephemeral=True
        )

    @app_commands.command(name="config-reset", description="Remove one community override and fall back to the SpryteAI default.")
    @app_commands.describe(path="Configuration path to remove, such as pokecord.spawn_min_seconds")
    async def config_reset(self, interaction: discord.Interaction, path: str) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside your server.", ephemeral=True)
            return
        path = path.strip()
        if not path or not self._config_path_allowed(path):
            await interaction.response.send_message("That configuration path is not resettable here.", ephemeral=True)
            return
        cid, _ = await self._activate_guild(interaction.guild)
        record = await db.get_community_record(cid)
        override = db.json_object(record["config"], field="communities.config") if record else {}
        if not self._delete_nested(override, path):
            await interaction.response.send_message(f"`{path}` is not overridden for this community.", ephemeral=True)
            return
        await db.replace_community_override(cid, override, changed_by=interaction.user.id)
        await self._activate_guild(interaction.guild)
        if path.lower().startswith("community."):
            await self._register_persistent_role_view(interaction.guild, force=True)
        await interaction.response.send_message(
            f"Removed the `{path}` override for community `{cid}`. It now uses the deployment default.", ephemeral=True
        )

    @app_commands.command(name="feature", description="Enable or disable a SpryteAI feature for this community.")
    @app_commands.describe(feature="Feature to change", enabled="Whether this community can use the feature")
    async def feature_toggle(
        self,
        interaction: discord.Interaction,
        feature: Literal["pokecord", "twitch", "streaming"],
        enabled: bool,
    ) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside your server.", ephemeral=True)
            return
        cid, _ = await self._activate_guild(interaction.guild)
        await db.set_community_feature(cid, feature, enabled)
        await self._activate_guild(interaction.guild)

        # Apply long-running integrations immediately instead of waiting for a restart.
        if feature == "pokecord":
            for cog in self.bot.cogs.values():
                handler = getattr(cog, "set_community_enabled", None)
                if callable(handler):
                    try:
                        await handler(cid, enabled)
                    except Exception:
                        log.exception("Unable to apply Pokécord feature toggle for community %s", cid)
                    break
        elif feature == "twitch":
            twitch_cog = self.bot.get_cog("TwitchCommands")
            manager = getattr(twitch_cog, "manager", None) if twitch_cog is not None else None
            if manager is not None:
                try:
                    if enabled:
                        await manager.connect_eventsub(community_id=cid, restart=True)
                    else:
                        await manager.disconnect_community(cid)
                except Exception:
                    log.exception("Unable to apply Twitch feature toggle for community %s", cid)

        await interaction.response.send_message(
            f"**{feature}** is now **{'enabled' if enabled else 'disabled'}** for this community.", ephemeral=True
        )

    @app_commands.command(name="setup", description="Preview or apply the configured community server layout.")
    @app_commands.describe(
        apply="False previews the migration; True applies it.",
        destructive="Delete channels/categories/roles outside the configured layout when applying.",
    )
    async def setup_server(
        self,
        interaction: discord.Interaction,
        apply: bool = False,
        destructive: bool = True,
    ) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this command inside the server you want to configure.", ephemeral=True)
            return

        guild = interaction.guild
        await self._activate_guild(guild)
        layout = self._layout()
        definitions = self._role_definitions()
        if not layout:
            await interaction.response.send_message(
                "`community.layout` is empty or invalid. Add the server blueprint to the community defaults/override before running setup.",
                ephemeral=True,
            )
            return
        if not definitions:
            await interaction.response.send_message(
                "`community.role_definitions` is empty or invalid in this community configuration.",
                ephemeral=True,
            )
            return

        issues = self._config_issues(layout)
        if issues:
            await interaction.response.send_message(
                "**Community config has errors:**\n• " + "\n• ".join(issues[:12]),
                ephemeral=True,
            )
            return

        if not apply:
            categories = len(layout)
            text_channels = sum(1 for category in layout for spec in category.channels if spec.kind == "text")
            voice_channels = sum(1 for category in layout for spec in category.channels if spec.kind == "voice")
            self_role_names = [
                str(raw.get("name") or key)
                for key, raw in definitions.items()
                if raw.get("self_assignable", False)
            ]
            obsolete_channels, obsolete_categories, obsolete_roles = self._destructive_preview(guild, layout)
            deletion_preview = ""
            if destructive:
                channel_sample = ", ".join(f"#{c.name}" for c in obsolete_channels[:12]) or "none"
                category_sample = ", ".join(c.name for c in obsolete_categories[:8]) or "none"
                role_sample = ", ".join(f"@{r.name}" for r in obsolete_roles[:12]) or "none"
                deletion_preview = (
                    "\n\n**Destructive cleanup**\n"
                    f"• Channels to delete: **{len(obsolete_channels)}** ({channel_sample}{'…' if len(obsolete_channels) > 12 else ''})\n"
                    f"• Categories to delete: **{len(obsolete_categories)}** ({category_sample}{'…' if len(obsolete_categories) > 8 else ''})\n"
                    f"• Roles eligible for deletion: **{len(obsolete_roles)}** ({role_sample}{'…' if len(obsolete_roles) > 12 else ''})\n"
                    f"Managed/integration roles, @everyone, {BRAND_NAME}'s roles, and config-preserved roles are protected."
                )
            await interaction.response.send_message(
                "**Configured community restructure preview**\n"
                f"• {categories} target categories\n"
                f"• {text_channels} target text channels\n"
                f"• {voice_channels} target voice channels\n"
                f"• Self-roles: {', '.join(self_role_names) or 'none'}"
                f"{deletion_preview}\n\n"
                "Names, access roles, read-only behavior, and channel/category layout come from this community’s merged configuration. "
                + ("Everything else eligible is pruned. " if destructive else "Unrelated channels/roles are preserved. ")
                + "Run `/community setup apply:true destructive:" + ("true" if destructive else "false") + "` when you're ready.",
                ephemeral=True,
            )
            return

        me = guild.me
        if me is None or not me.guild_permissions.manage_channels or not me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                f"{BRAND_NAME} needs **Manage Channels** and **Manage Roles** before it can restructure the server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        community_cfg = self._community_cfg()
        existing_category_ids = community_cfg.get("categories", {}) if isinstance(community_cfg.get("categories"), dict) else {}
        existing_channel_ids = community_cfg.get("channels", {}) if isinstance(community_cfg.get("channels"), dict) else {}
        category_ids: dict[str, int] = {}
        channel_ids: dict[str, int] = {}
        role_ids, created_roles = await self._ensure_configured_roles(guild)
        created_categories = created_channels = moved_channels = 0
        keep_category_ids: set[int] = set()
        keep_channel_ids: set[int] = set()
        deleted_channels = deleted_categories = deleted_roles = 0
        prune_failures: list[str] = []

        for category_index, category_spec in enumerate(layout):
            if category_spec.staff_only:
                category_allowed = self._staff_roles(guild)
                category_public = False
            else:
                category_allowed = self._resolve_role_keys(guild, category_spec.access_roles, role_ids)
                category_public = category_spec.public and not category_spec.access_roles

            category_overwrites = self._permission_overwrites(
                guild,
                allowed_roles=category_allowed,
                public=category_public,
            )
            category, created = await self._ensure_category(
                guild,
                category_spec,
                category_overwrites,
                existing_id=_id(existing_category_ids.get(category_spec.key)),
            )
            created_categories += int(created)
            category_ids[category_spec.key] = category.id
            keep_category_ids.add(category.id)

            try:
                await category.edit(position=category_index, reason=f"{BRAND_NAME} community category ordering")
            except discord.HTTPException:
                log.warning("Unable to reorder category %s", category.name, exc_info=True)

            for channel_spec in category_spec.channels:
                if channel_spec.access_roles is not None:
                    effective_allowed = self._resolve_role_keys(guild, channel_spec.access_roles, role_ids)
                    channel_public = bool(channel_spec.public) if channel_spec.public is not None else False
                elif channel_spec.public is not None:
                    effective_allowed = [] if channel_spec.public else category_allowed
                    channel_public = channel_spec.public
                else:
                    effective_allowed = category_allowed
                    channel_public = category_public

                channel_overwrites = self._permission_overwrites(
                    guild,
                    allowed_roles=effective_allowed,
                    read_only=channel_spec.read_only,
                    public=channel_public,
                )
                channel, was_created, was_moved = await self._ensure_channel(
                    guild,
                    category,
                    channel_spec,
                    channel_overwrites,
                    existing_id=_id(existing_channel_ids.get(channel_spec.key)),
                )
                created_channels += int(was_created)
                moved_channels += int(was_moved)
                key = channel_spec.key
                if key in channel_ids:
                    key = f"{key}_{channel_spec.kind}"
                channel_ids[key] = channel.id
                keep_channel_ids.add(channel.id)

        await self._persist_runtime_config(
            guild, categories=category_ids, channels=channel_ids, roles=role_ids, changed_by=interaction.user.id
        )
        self._persistent_view_guilds.discard(guild.id)
        await self._register_persistent_role_view(guild, force=True)

        community_cfg = self._community_cfg()
        spawn_key = str(community_cfg.get("pokemon_spawn_channel_key") or "")
        spawn_id = channel_ids.get(spawn_key, 0)
        if spawn_id:
            for cog in self.bot.cogs.values():
                if hasattr(cog, "spawn_channel_id"):
                    try:
                        setattr(cog, "spawn_channel_id", spawn_id)
                    except Exception:
                        log.debug("Could not live-update Pokécord spawn channel", exc_info=True)

        if destructive:
            deleted_channels, deleted_categories, deleted_roles, prune_failures = await self._prune_server(
                guild,
                keep_channel_ids=keep_channel_ids,
                keep_category_ids=keep_category_ids,
                keep_role_ids=set(role_ids.values()),
                invocation_channel_id=interaction.channel_id,
            )

        roles_key = str(community_cfg.get("roles_channel_key") or "")
        live_key = str(community_cfg.get("live_channel_key") or "")
        roles_channel = guild.get_channel(channel_ids.get(roles_key, 0))
        live_channel = guild.get_channel(channel_ids.get(live_key, 0))
        spawn_channel = guild.get_channel(spawn_id)

        failure_text = ""
        if prune_failures:
            failure_text = "\n• Cleanup warnings: **" + str(len(prune_failures)) + "** (" + "; ".join(prune_failures[:5]) + ("…" if len(prune_failures) > 5 else "") + ")"

        await interaction.followup.send(
            "**Community restructure applied from config.**\n"
            f"• Categories created: **{created_categories}**\n"
            f"• Channels created: **{created_channels}**\n"
            f"• Existing channels moved: **{moved_channels}**\n"
            f"• Roles created: **{created_roles}**\n"
            "• Channel/category permissions: **synced to config policy**\n"
            f"• Channels deleted: **{deleted_channels}**\n"
            f"• Categories deleted: **{deleted_categories}**\n"
            f"• Roles deleted: **{deleted_roles}**"
            f"{failure_text}\n"
            f"• Role panel channel: {getattr(roles_channel, 'mention', 'not configured')}\n"
            f"• Live announcements: {getattr(live_channel, 'mention', 'not configured')}\n"
            f"• Pokémon spawns: {getattr(spawn_channel, 'mention', 'not configured')}\n\n"
            "Next, run `/community onboarding` to post the self-role panel.",
            ephemeral=True,
        )

        if destructive and self._pending_invocation_delete is not None:
            try:
                await self._pending_invocation_delete.delete(reason=f"{BRAND_NAME} destructive community restructure")
            except (discord.Forbidden, discord.HTTPException):
                log.warning("Unable to delete invocation channel %s", self._pending_invocation_delete.name, exc_info=True)
            finally:
                self._pending_invocation_delete = None

    @app_commands.command(name="onboarding", description="Post the persistent self-role onboarding panel.")
    async def onboarding(self, interaction: discord.Interaction) -> None:
        if not await self._owner_only(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside your server.", ephemeral=True)
            return

        await self._activate_guild(interaction.guild)
        community_cfg = self._community_cfg()
        role_ids = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        definitions = self._role_definitions()
        if not any(raw.get("self_assignable", False) and _id(role_ids.get(key)) for key, raw in definitions.items()):
            await interaction.response.send_message("Run `/community setup apply:true` first so I know which roles to manage.", ephemeral=True)
            return

        channel_key = str(community_cfg.get("roles_channel_key") or "")
        channel_id = _id(community_cfg.get("channels", {}).get(channel_key)) if isinstance(community_cfg.get("channels"), dict) else 0
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(f"I couldn't find the configured role-panel channel key `{channel_key}`.", ephemeral=True)
            return

        title = str(community_cfg.get("onboarding_title") or "Choose your community roles")
        description = str(
            community_cfg.get("onboarding_description")
            or "Use the menus below to choose your notification and interest roles. You can change these whenever you want."
        )
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())

        group_cfg = community_cfg.get("self_role_groups", {}) if isinstance(community_cfg.get("self_role_groups"), dict) else {}
        grouped: dict[str, list[str]] = {}
        for key, raw in definitions.items():
            if not raw.get("self_assignable", False) or not _id(role_ids.get(key)):
                continue
            group = str(raw.get("group") or "interests")
            grouped.setdefault(group, []).append(str(raw.get("name") or key))
        for group, names in list(grouped.items())[:4]:
            group_raw = group_cfg.get(group, {}) if isinstance(group_cfg.get(group), dict) else {}
            label = str(group_raw.get("label") or group.replace("_", " ").title())
            emoji = str(group_raw.get("emoji") or "")
            embed.add_field(name=f"{emoji} {label}".strip(), value=" • ".join(names), inline=False)
        embed.set_footer(text=str(community_cfg.get("onboarding_footer") or f"{BRAND_NAME} Community Onboarding"))

        await channel.send(embed=embed, view=CommunityRoleView(community_cfg, interaction.guild.id))
        self._persistent_view_guilds.discard(interaction.guild.id)
        await self._register_persistent_role_view(interaction.guild, force=True)
        await interaction.response.send_message(f"Posted the onboarding panel in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="status", description="Show the channels and roles this bot is using for community features.")
    async def status(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Run this inside the server.", ephemeral=True)
            return

        cid, full_cfg = await self._activate_guild(interaction.guild)
        community_cfg = self._community_cfg()
        channels = community_cfg.get("channels", {}) if isinstance(community_cfg.get("channels"), dict) else {}
        roles = community_cfg.get("roles", {}) if isinstance(community_cfg.get("roles"), dict) else {}
        features = full_cfg.get("features", {}) if isinstance(full_cfg.get("features"), dict) else {}

        def channel_text(key: str) -> str:
            obj = interaction.guild.get_channel(_id(channels.get(key)))
            return obj.mention if obj else "Not configured"

        def role_text(key: str) -> str:
            obj = interaction.guild.get_role(_id(roles.get(key)))
            return obj.mention if obj else "Not configured"

        embed = discord.Embed(title=f"{BRAND_NAME} Community Status", color=discord.Color.blurple())
        embed.description = f"Community ID: `{cid}`"
        embed.add_field(
            name="Features",
            value=" · ".join(
                f"{'✅' if bool(features.get(name, True)) else '❌'} {name.title()}"
                for name in ("pokecord", "twitch", "streaming")
            ),
            inline=False,
        )
        live_key = str(community_cfg.get("live_channel_key") or "")
        spawn_key = str(community_cfg.get("pokemon_spawn_channel_key") or "")
        roles_key = str(community_cfg.get("roles_channel_key") or "")
        embed.add_field(name="Live announcements", value=channel_text(live_key), inline=True)
        embed.add_field(name="Pokémon spawns", value=channel_text(spawn_key), inline=True)
        embed.add_field(name="Role panel", value=channel_text(roles_key), inline=True)

        definitions = self._role_definitions()
        status_keys = community_cfg.get("status_role_keys", [])
        if not isinstance(status_keys, list) or not status_keys:
            status_keys = [key for key, raw in definitions.items() if raw.get("self_assignable", False)][:6]
        for key in status_keys[:6]:
            raw = definitions.get(str(key), {})
            embed.add_field(name=str(raw.get("name") or key), value=role_text(str(key)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommunityCommands(bot))
    log.info("Cog loaded: CommunityCommands")
