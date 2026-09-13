# SpryteAI Multi-Community — 2026-09-12

- Added PostgreSQL `community_id` tenancy and Discord guild bindings.
- Added per-community JSONB config overrides, feature flags, and config history.
- Added platform-neutral community players and Discord/Twitch identity linking.
- Added per-community Twitch broadcaster OAuth/EventSub with one shared SpryteAI bot identity.
- Added Twitch Pokécord commands: `!catch`, `!pokemon`, `!list`, `!dex`.
- Added one independent wild Pokémon scheduler/capture lock per community.
- Scoped Pokémon ownership/selection/indexes by community.
- Added `/community config-show`, `config-set`, `config-reset`, and `feature`.
- `/community setup` now persists generated role/channel/category IDs to that community's database override.
- Persistent self-role component IDs are now guild-specific.
- Twitch spawn announcements can include official artwork links for chat viewers.

# SpryteAI modernization changes

## 2026-09 update

### Runtime and architecture
- Migrated active slash commands to cog-native `discord.app_commands`.
- Moved extension loading and command sync into `setup_hook()`.
- Removed active-cog imports from `main.py` and introduced `services.py` for shared services.
- Added clean database shutdown and rotating application logs.

### Database
- Replaced class-global lazy pool behavior with a single managed `asyncpg` pool.
- Added schema bootstrap for `botconfig`, `serverconfig`, and `users`.
- Added parameterized database helpers and transactional multi-step writes.
- Preserved legacy duplicate rows instead of destructively migrating them; rank/leaderboard reads deduplicate them logically.

### Credits
- Fixed sender transfers writing to `LastReceived`/`TimesReceived`.
- Fixed transfer-window counter reset behavior.
- Made sender/receiver balance updates part of one transaction with row locks.
- Made daily claims transactional.

### Experience
- Fixed cooldown arithmetic that previously wrapped at 60 seconds.
- Made the cooldown check and XP award one PostgreSQL update.
- Updated Pillow usage and removed shared temporary rank-card files.
- Avatar downloads now use Discord.py's asynchronous asset API.

### Commands and moderation
- Added missing responses/error handling to several general commands.
- Added division-by-zero handling to `/calc`.
- Restricted `/say` and `/repeat` and disabled mass mentions from their payloads.
- Hardened promote/demote/kick/ban/mute workflows around role hierarchy and permissions.
- Removed expensive Muted-role creation from the message listener.

### Security and deployment
- Removed credentials from distributed config/source/SQL data.
- Added `.env.example` and `.gitignore`.
- Replaced hard-coded startup directory with a portable script.
- Updated dependency pins in `requirements.txt`.
