# BlakBot Config-Driven Community Setup

The community server blueprint is now controlled from `config/config.json`. Channel names, category names, access roles, read-only behavior, self-role definitions, stream alert roles, and the special channels used by Pokécord/stream announcements no longer live in the Python cogs.

## Files in this update

- `cogs/commands/CommunityCommands.py`
- `cogs/commands/StreamCommands.py`
- `config/config.example.json`

Do **not** replace your live `config/config.json` with the example. Copy/merge the `community` and `streaming.alert_role_keys` sections into your existing config.

## Runtime IDs vs definitions

BlakBot uses three runtime maps that it updates after `/community setup apply:true`:

```json
"community": {
  "categories": {},
  "channels": {},
  "roles": {}
}
```

Keep those objects in the config, but do not manually maintain their IDs unless you need to recover a setup. The actual desired server design belongs in `role_definitions` and `layout`.

## Role definitions

Example:

```json
"role_definitions": {
  "pokemon_trainer": {
    "name": "Pokémon Trainer",
    "emoji": "⚡",
    "description": "Access the Pokémon League.",
    "self_assignable": true,
    "group": "interests",
    "create": true,
    "preserve": true
  },
  "server_booster": {
    "name": "Server Booster",
    "create": false,
    "preserve": true,
    "builtin": "premium_subscriber"
  }
}
```

The dictionary key (`pokemon_trainer`) is the stable internal reference used by category/channel permissions. You can rename the actual Discord role by changing `name` without editing Python.

- `self_assignable`: include the role in `/community onboarding`.
- `group`: which onboarding selector contains it.
- `create`: create the role when missing.
- `preserve`: protect the role from destructive cleanup.
- `builtin: "premium_subscriber"`: use Discord's managed Server Booster role instead of creating one.

## Categories and channels

The entire structure is in `community.layout`:

```json
{
  "key": "pokemon_league",
  "name": "POKÉMON LEAGUE",
  "public": false,
  "access_roles": ["pokemon_trainer"],
  "channels": [
    {
      "key": "pokemon_spawns",
      "name": "pokemon-spawns",
      "type": "text",
      "topic": "Wild Pokémon appear here.",
      "read_only": true
    }
  ]
}
```

Supported category fields:

- `key`: stable config/runtime ID key.
- `name`: Discord category name.
- `public`: whether `@everyone` can view it.
- `access_roles`: role-definition keys that can view a restricted category.
- `staff_only`: restrict the category to the configured staff roles.
- `channels`: channel definitions.

Supported channel fields:

- `key`: stable channel key stored in `community.channels`.
- `name`: Discord channel name.
- `type`: `text` or `voice`.
- `topic`: text-channel topic.
- `read_only`: members can view but cannot send/react; staff and BlakBot retain write access.
- `public`: optional channel-level override of the category audience.
- `access_roles`: optional role-definition keys that override the category audience for that channel.

If a channel omits `public` and `access_roles`, it inherits the category audience.

## Staff access

Staff bypasses restricted/read-only areas according to config:

```json
"staff_access": {
  "top_level_role_keys": ["staff", "trial_mod", "chat_mod"],
  "role_names": ["Admin", "Administrator", "Moderator", "Staff"],
  "community_role_keys": []
}
```

`top_level_role_keys` refer to the existing top-level `roles` object in BlakBot's config. `role_names` lets you preserve/use existing Discord roles by name. `community_role_keys` can point at any configured `role_definitions` entry.

## Destructive-cleanup protection

Configure extra roles that should survive destructive setup:

```json
"preserve": {
  "top_level_role_keys": ["staff", "trial_mod", "chat_mod", "muted", "restricted", "vip", "nitro_booster"],
  "role_names": ["DJ BlakSpryte", "Admin", "Moderator", "Staff", "VIP", "Subscriber"]
}
```

Managed/integration roles, `@everyone`, BlakBot's own roles, Discord's Booster role, and `role_definitions` with `preserve: true` are also protected automatically.

## Special channel keys

These tell other BlakBot systems which configurable layout entry to use:

```json
"roles_channel_key": "roles",
"live_channel_key": "live_now",
"pokemon_spawn_channel_key": "pokemon_spawns"
```

You can rename the actual Discord channels freely. If you change the `key`, update these references too.

## Stream notification roles

Stream announcement pings are also config driven:

```json
"streaming": {
  "alert_role_keys": {
    "default": ["live_alerts"],
    "gaming": ["gaming_alerts"],
    "dj_set": ["dj_alerts"],
    "just_chatting": [],
    "special": []
  }
}
```

Each value references keys from `community.role_definitions` / `community.roles`. `default` is added to every stream announcement, then the matching stream kind is added.

## Applying changes

After editing `config/config.json`, restart/reload BlakBot so the in-memory config is refreshed, then preview:

```text
/community setup apply:false destructive:true
```

The command validates the config and refuses to run if it finds duplicate keys/names, unknown access-role references, invalid special channel references, or too many self-role UI options.

Apply:

```text
/community setup apply:true destructive:true
```

This creates/reuses roles, categories, and channels, synchronizes permission overwrites, persists the resulting IDs, and (when destructive is true) removes eligible objects outside the configured blueprint.

Then post/update onboarding:

```text
/community onboarding
```

Because the layout is config-driven, future server changes generally require only JSON edits followed by `/community setup`—not Python changes.
