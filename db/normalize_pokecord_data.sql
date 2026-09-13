-- SpryteAI Pokécord normalization migration (manual fallback)
-- Guarded by schema_migrations; safe to rerun after taking a backup.
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pokecord_pokedex (
    "ServerID" BIGINT NOT NULL,
    "UserID" BIGINT NOT NULL,
    dex_id INTEGER NOT NULL CHECK (dex_id > 0),
    name TEXT NOT NULL,
    first_caught_at BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY ("ServerID", "UserID", dex_id)
);

CREATE TABLE IF NOT EXISTS pokecord_inventory (
    "ServerID" BIGINT NOT NULL,
    "UserID" BIGINT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    item_api_id INTEGER,
    purchase_cost INTEGER,
    sprite_url TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY ("ServerID", "UserID", item_name)
);

WITH legacy_dex AS (
    SELECT
        u."ServerID",
        u."UserID",
        ((u."pokedex")[s.i][1])::INTEGER AS dex_id,
        COALESCE(NULLIF(TRIM((u."pokedex")[s.i][2]), ''), 'unknown') AS name
    FROM users AS u
    CROSS JOIN LATERAL generate_subscripts(u."pokedex", 1) AS s(i)
    WHERE u."pokedex" IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM schema_migrations
          WHERE version = '2026-09-11-pokecord-normalization-v2'
      )
      AND (u."pokedex")[s.i][1] ~ '^[0-9]+$'
      AND ((u."pokedex")[s.i][1])::INTEGER > 0
), grouped_dex AS (
    SELECT "ServerID", "UserID", dex_id, MAX(name) AS name
    FROM legacy_dex
    GROUP BY "ServerID", "UserID", dex_id
)
INSERT INTO pokecord_pokedex ("ServerID", "UserID", dex_id, name, first_caught_at)
SELECT "ServerID", "UserID", dex_id, name, 0
FROM grouped_dex
ON CONFLICT ("ServerID", "UserID", dex_id) DO UPDATE
SET name = EXCLUDED.name;

CREATE OR REPLACE FUNCTION spryteai_try_jsonb(value TEXT)
RETURNS JSONB
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF value IS NULL OR BTRIM(value) = '' THEN
        RETURN NULL;
    END IF;
    RETURN value::JSONB;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

WITH raw_items AS (
    SELECT
        u."ServerID",
        u."UserID",
        LOWER(REPLACE(TRIM(COALESCE(NULLIF(e.value->>'name', ''), e.key)), ' ', '-')) AS item_name,
        CASE WHEN COALESCE(e.value->>'total', '') ~ '^[0-9]+$'
             THEN (e.value->>'total')::INTEGER ELSE 0 END AS quantity,
        CASE WHEN COALESCE(e.value->>'id', '') ~ '^[0-9]+$'
             THEN (e.value->>'id')::INTEGER ELSE NULL END AS item_api_id,
        CASE WHEN COALESCE(e.value->>'cost', '') ~ '^[0-9]+$'
             THEN (e.value->>'cost')::INTEGER ELSE NULL END AS purchase_cost,
        NULLIF(e.value->>'sprite', '') AS sprite_url
    FROM users AS u
    CROSS JOIN LATERAL (
        SELECT spryteai_try_jsonb(u."pokecord_items") AS bag
    ) AS parsed
    CROSS JOIN LATERAL jsonb_each(
        CASE WHEN jsonb_typeof(parsed.bag) = 'object' THEN parsed.bag ELSE '{}'::JSONB END
    ) AS e(key, value)
    WHERE jsonb_typeof(e.value) = 'object'
      AND NOT EXISTS (
          SELECT 1 FROM schema_migrations
          WHERE version = '2026-09-11-pokecord-normalization-v2'
      )
), grouped AS (
    SELECT
        "ServerID", "UserID", item_name,
        SUM(quantity)::INTEGER AS quantity,
        MAX(item_api_id) AS item_api_id,
        MAX(purchase_cost) AS purchase_cost,
        MAX(sprite_url) AS sprite_url
    FROM raw_items
    WHERE item_name <> '' AND quantity > 0
    GROUP BY "ServerID", "UserID", item_name
)
INSERT INTO pokecord_inventory (
    "ServerID", "UserID", item_name, quantity,
    item_api_id, purchase_cost, sprite_url
)
SELECT
    "ServerID", "UserID", item_name, quantity,
    item_api_id, purchase_cost, sprite_url
FROM grouped
ON CONFLICT ("ServerID", "UserID", item_name) DO UPDATE
SET quantity = GREATEST(pokecord_inventory.quantity, EXCLUDED.quantity),
    item_api_id = COALESCE(EXCLUDED.item_api_id, pokecord_inventory.item_api_id),
    purchase_cost = COALESCE(EXCLUDED.purchase_cost, pokecord_inventory.purchase_cost),
    sprite_url = COALESCE(EXCLUDED.sprite_url, pokecord_inventory.sprite_url),
    updated_at = NOW();

DROP FUNCTION IF EXISTS spryteai_try_jsonb(TEXT);

COMMENT ON COLUMN users."pokedex" IS
    'Legacy Pokédex snapshot; normalized source of truth is pokecord_pokedex.';
COMMENT ON COLUMN users."pokecord_items" IS
    'Legacy item-bag snapshot; normalized source of truth is pokecord_inventory.';

INSERT INTO schema_migrations (version)
VALUES ('2026-09-11-pokecord-normalization-v2')
ON CONFLICT (version) DO NOTHING;

COMMIT;

ANALYZE pokecord_pokedex;
ANALYZE pokecord_inventory;
