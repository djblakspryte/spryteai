# SpryteAI Pokécord Data Normalization

Migration: `2026-09-11-pokecord-normalization-v2`

This migration replaces the two remaining high-churn serialized values in `users` with relational tables.

## New tables

### `pokecord_pokedex`

One row per server, Discord user, and Pokédex number:

- `ServerID`
- `UserID`
- `dex_id`
- `name`
- `first_caught_at`

Primary key: `(ServerID, UserID, dex_id)`.

This preserves the existing behavior where Pokédex completion is tracked per Discord server.

### `pokecord_inventory`

One row per server, Discord user, and item:

- `ServerID`
- `UserID`
- `item_name`
- `quantity`
- `item_api_id`
- `purchase_cost`
- `sprite_url`
- `updated_at`

Primary key: `(ServerID, UserID, item_name)`.

The item bag is still server-local because credits/economy are server-local.

## Automatic migration

On startup SpryteAI checks `schema_migrations`. If v2 has not run, it:

1. Creates the normalized tables.
2. Copies every valid legacy `users.pokedex` entry into `pokecord_pokedex`.
3. Safely parses valid legacy `users.pokecord_items` JSON and aggregates duplicate/canonical item names into `pokecord_inventory`.
4. Ignores malformed legacy bag JSON instead of blocking startup.
5. Uses the tables’ composite primary-key indexes for user/Dex and user/item lookups without adding redundant write-heavy indexes.
6. Marks `2026-09-11-pokecord-normalization-v2` complete.

The legacy `users.pokedex` and `users.pokecord_items` columns are intentionally retained as read-only rollback snapshots for now. Runtime code no longer reads or writes them.

## Runtime improvements

- Catching a Pokémon writes the Pokémon and Pokédex entry in the same transaction.
- `/pokemon dex` reads indexed Pokédex rows instead of a multidimensional text array.
- Bag autocomplete searches PostgreSQL and returns at most 25 rows instead of deserializing the entire bag on every keystroke.
- `/pokemon items` reads normalized rows directly.
- `/pokemon buy` debits credits and adds inventory in one transaction, preventing concurrent overspending.
- `/pokemon give` and `/pokemon take` lock only the affected Pokémon/item rows and update inventory atomically.
- Inventory quantity changes are numeric SQL updates rather than read/JSON-modify/rewrite operations.

## Before first startup

Recommended backup:

```bash
pg_dump -Fc spryteai_data > spryteai_data_before_normalization.dump
```

Then restart SpryteAI normally. You should see:

```text
Applying database migration 2026-09-11-pokecord-normalization-v2
```

## Verification

After startup, these queries are useful:

```sql
SELECT version, applied_at
FROM schema_migrations
ORDER BY applied_at;

SELECT COUNT(*) AS dex_rows
FROM pokecord_pokedex;

SELECT COUNT(*) AS inventory_rows,
       COALESCE(SUM(quantity), 0) AS total_items
FROM pokecord_inventory
WHERE quantity > 0;
```

To compare a specific user's legacy/current bag during the transition:

```sql
SELECT "ServerID", "UserID", "pokecord_items"
FROM users
WHERE "UserID" = YOUR_DISCORD_ID;

SELECT *
FROM pokecord_inventory
WHERE "UserID" = YOUR_DISCORD_ID
ORDER BY "ServerID", item_name;
```

## Manual fallback

If the automatic migration cannot run, use:

```text
db/normalize_pokecord_data.sql
```

The manual script checks `schema_migrations`, so rerunning it after a successful v2 migration does not re-import stale legacy bag quantities.

## Later cleanup

Once the normalized tables have been used successfully for a while and a backup is available, a future migration can drop:

- `users.pokedex`
- `users.pokecord_items`

They are deliberately not dropped by v2 so rollback remains possible.
