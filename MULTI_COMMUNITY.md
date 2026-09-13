# SpryteAI Multi-Community Architecture

SpryteAI is now multi-tenant. One running bot process can serve many Discord/Twitch communities without sharing Pokémon, settings, role IDs, channel IDs, Twitch broadcaster authorizations, or account links between them.

## Tenant model

A `community_id` is SpryteAI's tenant boundary. By default, every Discord guild automatically receives a community whose ID is that guild ID. A Twitch broadcaster can then be attached to that community.

```text
SpryteAI deployment
├─ Community A
│  ├─ Discord guild A
│  ├─ Twitch broadcaster A
│  ├─ community config / feature flags
│  └─ Pokécord players, Pokémon, Pokédex, items, badges
└─ Community B
   ├─ Discord guild B
   ├─ Twitch broadcaster B
   ├─ community config / feature flags
   └─ isolated Pokécord game data
```

The Twitch bot identity is shared by the deployment. Broadcaster OAuth grants are stored separately as `broadcaster:<community_id>`.

## Player identity

SpryteAI uses a platform-neutral player inside each community.

- Discord identities reuse the positive Discord user snowflake as `player_id`, preserving existing Pokémon ownership.
- Twitch-only viewers receive a negative internal `player_id`, so they can never collide with a Discord snowflake.
- `/twitch link` creates a short community-bound code.
- `!link CODE` merges the Twitch player into the Discord player in that same community.
- The merge preserves Pokémon, Pokédex entries, inventory, Gym badges, and the UID allocator.

Link codes cannot be consumed from another community.

## Pokécord isolation

`pokecord_poke_data` now includes `community_id`. Runtime game queries use the `pokecord_poke_data_scoped` view, which is filtered by the PostgreSQL session setting `spryteai.community_id`.

Each community has an independent:

- wild spawn state and spawn scheduler
- catch lock
- Pokémon collection
- selected Pokémon
- Pokédex
- item inventory
- Gym badges
- rarity weights / shiny odds
- spawn channel and timing
- contributor storage role

A user can therefore select one Pokémon in Community A and a different Pokémon in Community B.

## Twitch Pokécord

Twitch viewers can use:

```text
!catch <pokemon name>
!pokemon
!list
!dex
!link <code>
```

A Discord wild spawn is also announced in the Twitch chat for the bound community. By default the Twitch message includes the official artwork URL because Twitch chat cannot display the Discord image attachment. This is controlled by:

```json
{
  "twitch": {
    "chat": {
      "pokecord_image_links": true
    }
  }
}
```

Discord and Twitch compete for the same active spawn. One capture lock/transaction determines the winner.

## Community configuration

`config/config.json` is now the deployment default/template. Community-specific overrides are stored in PostgreSQL `communities.config` as JSONB and deep-merged over the default at runtime.

Administrators can manage safe community settings from Discord:

```text
/community config-show
/community config-set path:<path> value:<JSON or text>
/community config-reset path:<path>
/community feature feature:<pokecord|twitch|streaming> enabled:<true|false>
```

Editable prefixes are intentionally limited to:

```text
community.*
streaming.*
pokecord.*
twitch.chat.*
twitch.discord.*
```

Secrets, tokens, passwords, Client IDs, and OAuth redirect settings cannot be changed through Discord.

Examples:

```text
/community config-set path:pokecord.spawn_min_seconds value:60
/community config-set path:pokecord.shiny_roll value:1024
/community config-set path:twitch.chat.prefix value:"?"
/community config-set path:twitch.chat.pokecord_image_links value:false
/community config-set path:streaming.auto_presence value:false
```

JSON objects and arrays are supported too, so a community can override its layout, role definitions, alert-role mapping, or rarity weights.

`/community setup apply:true` writes that guild's generated category/channel/role IDs back to its database override. It no longer overwrites a deployment-wide `config.json`.

Configuration changes are archived in `community_config_history` before replacement.

## Feature flags

Each community can independently enable or disable:

- `pokecord`
- `twitch`
- `streaming`

Disabling Pokécord immediately stops that community's spawn scheduler. Disabling Twitch disconnects that community's EventSub sockets without affecting other communities.

## Twitch authorization

The deployment owner authorizes the shared SpryteAI Twitch bot once:

```text
/twitch authorize account:bot
```

An Administrator in each Discord community authorizes that community's broadcaster:

```text
/twitch authorize account:broadcaster
```

SpryteAI stores the broadcaster token under `broadcaster:<community_id>` and creates separate EventSub connections for the community.

## Database migration

Automatic startup migration version:

```text
2026-09-12-multi-community-v3
```

The migration:

1. creates the community/player/binding/config tables;
2. adds `community_id` to Pokémon ownership;
3. changes the Pokémon primary key to `(community_id, ownerid, uid)`;
4. changes selected-Pokémon uniqueness to `(community_id, ownerid)`;
5. creates the tenant-scoped Pokémon view and indexes;
6. bootstraps existing Discord guilds as communities;
7. places legacy single-community Pokémon into the configured/default legacy community;
8. seeds Discord player identities without renumbering Pokémon.

The preferred migration method is simply restarting SpryteAI after making a backup. `db/migrate_multi_community.sql` is provided as a manual fallback.

## Backup before first run

```bash
pg_dump -Fc spryteai_data > spryteai_data_before_multicommunity.dump
```
