# SpryteAI Database Optimization

This update optimizes the existing PostgreSQL database in place. It does **not** require recreating `spryteai_data`.

## What changed

### Hot-path query reduction

- Guild configuration is cached in memory for a short configurable TTL (`database.config_cache_ttl`, default 15 seconds). Any SpryteAI write to `serverconfig` or `botconfig` invalidates the cache immediately.
- Message XP now combines user creation, cooldown enforcement, XP mutation, and current-level return into a single PostgreSQL round trip.
- XP and credit leaderboards no longer use the legacy `DISTINCT ON (... ctid ...)` workaround once user uniqueness is enforced.
- Pokémon autocomplete now filters in PostgreSQL, selects only the fields needed by Discord, and returns at most 25 rows rather than loading every full Pokémon record on every keystroke.
- `/pokemon list` loads only collection-summary columns instead of moves, battle state, base stats, and other detail fields.
- `/pokemon favorite`, `/pokemon unfavorite`, and `/pokemon select` use fewer SQL round trips.
- Pokémon unique-species count uses `COUNT(DISTINCT name)` instead of materializing every grouped row in Python.

### Concurrency and integrity

- Existing duplicate `users` rows are archived to `users_duplicate_archive` before extras are removed.
- `(ServerID, UserID)` uniqueness is enforced for `users`, which removes the need for `ctid` reads during normal operation.
- At most one Pokémon may be selected per trainer, enforced with a partial unique index.
- Pokémon catch UIDs now come from global `pokecord_user_state`, fixing the old mismatch where the collection was global by Discord user but the UID counter was per guild.
- Catch UID allocation, user Pokédex/counter update, and Pokémon insert are transaction-safe.
- Schema changes are versioned in `schema_migrations` and protected with a PostgreSQL advisory lock so two SpryteAI processes cannot race startup migrations.

### Indexes

The migration adds indexes for the query patterns SpryteAI actually uses:

- XP leaderboard: `(ServerID, ExpLevel DESC, Experience DESC, UserID)` for non-bot users.
- Credits leaderboard: `(ServerID, Credits DESC, UserID)` for non-bot users.
- Pokémon collection order: `(ownerid, selected DESC, starred DESC, uid DESC)`.
- Pokémon owner/name lookups: `(ownerid, name)`.
- One-selected-Pokémon partial unique index.
- Gym badge progress/order: `(ServerID, UserID, region, first_won_at)`.

`users` and `pokecord_poke_data` use a fillfactor of 90 because both are update-heavy.

## Pool tuning

The following settings are now available under `database`:

```json
{
  "pool_min_size": 1,
  "pool_size": 10,
  "command_timeout": 30,
  "max_queries_per_connection": 50000,
  "max_inactive_connection_lifetime": 300,
  "statement_cache_size": 256,
  "config_cache_ttl": 15
}
```

The defaults are appropriate for a single SpryteAI process on a local PostgreSQL instance. Do not increase `pool_size` simply because the server has spare RAM; multiply it by the number of SpryteAI processes you run and keep the total comfortably below PostgreSQL's `max_connections`.

## Applying the optimization

Normally, just replace the changed files and restart SpryteAI. On startup it will apply `2026-09-11-db-optimization-v1` once and record it in `schema_migrations`.

For a manual migration, connect to `spryteai_data` and run:

```bash
psql -d spryteai_data -f db/optimize_database.sql
```

Before a production migration, a PostgreSQL backup is recommended:

```bash
pg_dump -Fc spryteai_data > spryteai_data_before_optimization.dump
```

The migration archives any legacy duplicate user rows before deduplication, but a normal database backup remains the safest rollback point.

## Optional maintenance

PostgreSQL autovacuum should normally handle maintenance. If this database has accumulated years of churn and you are doing a maintenance window, you can run:

```sql
VACUUM (ANALYZE) users;
VACUUM (ANALYZE) pokecord_poke_data;
VACUUM (ANALYZE) pokecord_gym_badges;
```

A routine `VACUUM FULL` is **not** recommended because it takes stronger locks and rewrites the table.

## Pokécord normalization v2

The follow-up migration `2026-09-11-pokecord-normalization-v2` moves Pokédex progress and item bags out of serialized `users` columns into `pokecord_pokedex` and `pokecord_inventory`. See `DATABASE_NORMALIZATION.md` for migration and verification details.
