# SpryteAI

SpryteAI is a multi-community Discord + Twitch bot with community automation, streaming integration, and a cross-platform Pokécord game.

## Multi-community support

One SpryteAI process can serve many independent communities. Every Discord guild receives an isolated `community_id`; its Twitch broadcaster, channels, roles, feature flags, configuration, Pokécord players, Pokémon, Pokédex, inventory, and badges are kept separate from every other community.

See [MULTI_COMMUNITY.md](MULTI_COMMUNITY.md) for the architecture and admin commands.

## First run / upgrade

1. Back up PostgreSQL:

```bash
pg_dump -Fc spryteai_data > spryteai_data_before_multicommunity.dump
```

2. Keep your existing `.env` credentials.
3. Copy this build over the project (or use the changed-files patch).
4. Start SpryteAI normally:

```bash
python main.py
```

Database migrations run automatically. The multi-community migration is:

```text
2026-09-12-multi-community-v3
```

## Community administration

```text
/community status
/community setup apply:false destructive:true
/community setup apply:true destructive:true
/community onboarding
/community config-show
/community config-set
/community config-reset
/community feature
```

`config/config.json` provides deployment defaults. `/community setup` and `/community config-*` store each guild's actual runtime configuration in PostgreSQL rather than rewriting shared JSON.

## Twitch

The host/deployment owner authorizes the shared Twitch bot account once:

```text
/twitch authorize account:bot
```

Each community Administrator authorizes their own broadcaster:

```text
/twitch authorize account:broadcaster
```

See [TWITCH_SETUP.md](TWITCH_SETUP.md).

## Twitch Pokécord

Bound Twitch communities can share the same live Pokécord game as Discord:

```text
!catch <pokemon>
!pokemon
!list
!dex
!link <code>
```

Discord users start linking with `/twitch link`. The same player then owns the same community-specific collection from both platforms.

## Database notes

- `DATABASE_OPTIMIZATION.md` — query/index/pool optimization
- `DATABASE_NORMALIZATION.md` — normalized Pokédex and inventory
- `MULTI_COMMUNITY.md` — tenant/community migration and configuration
- `db/SpryteAI.sql` — current full schema
- `db/migrate_multi_community.sql` — manual multi-community fallback
