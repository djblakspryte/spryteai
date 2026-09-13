# SpryteAI Full Rebrand

This build completes the rename to **SpryteAI**, including internal identifiers and the PostgreSQL database.

## Renamed internals

- Python bot class: `SpryteAI`
- Info command: `/spryteai`
- Persistent self-role IDs: `spryteai:selfroles:*`
- Webhook environment variable: `SPRYTEAI_WEBHOOK_URL`
- PokéAPI user-agent: `SpryteAI-Pokecord/2.0`
- Bot image: `assets/spryteai.png`
- SQL bootstrap: `db/SpryteAI.sql`
- Default PostgreSQL database: `spryteai_data`
- Project folder: `SpryteAI`

## Database migration

The config now targets `spryteai_data` and records `discord_data` as the legacy database. If `spryteai_data` does not exist but `discord_data` does, SpryteAI attempts to rename the existing database on startup so all tables and data are preserved.

If your `.env` currently contains `DATABASE_NAME=discord_data`, change it to:

```dotenv
DATABASE_NAME=spryteai_data
```

If automatic rename is blocked by PostgreSQL permissions, stop the bot and run `db/migrate_database_to_spryteai.sql` while connected to the `postgres` maintenance database.

## Discord persistent components

Because the self-role custom IDs are now fully renamed, any old onboarding panel will no longer respond after restart. Re-run `/community onboarding` once to post a fresh SpryteAI panel.

## Environment migration

If you used the old webhook environment variable, rename it in `.env` to `SPRYTEAI_WEBHOOK_URL`. Other generic variables such as `DISCORD_TOKEN`, `DATABASE_HOST`, and `DATABASE_USER` remain unchanged.
