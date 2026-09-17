from __future__ import annotations

import json
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from collections.abc import Sequence
from typing import Any, AsyncIterator

import asyncpg

from config import config, require_config

log = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SCHEMA_LOCK_KEY = 0x5350525954454149  # "SPRYTEAI" as a stable advisory-lock key.
_CURRENT_COMMUNITY_ID: ContextVar[int | None] = ContextVar("spryteai_community_id", default=None)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


def _json_object(value: Any, *, field: str = "JSON object") -> dict[str, Any]:
    """Return a PostgreSQL JSON/JSONB value as a plain dict.

    asyncpg returns json/jsonb as text unless a custom codec is installed.  Some
    deployments may install a codec and return a mapping instead, so community
    configuration code must safely support both representations.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)

    parsed: Any = value
    if isinstance(parsed, (bytes, bytearray, memoryview)):
        parsed = bytes(parsed).decode("utf-8")

    # Handle normal JSON text and tolerate one level of accidental double
    # encoding from an older deployment.
    for _ in range(2):
        if not isinstance(parsed, str):
            break
        text = parsed.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            log.warning("Unable to decode %s from PostgreSQL; using an empty object", field)
            return {}

    if isinstance(parsed, dict):
        return dict(parsed)

    try:
        return dict(parsed)
    except (TypeError, ValueError):
        log.warning("Expected %s to be a JSON object, got %s; using an empty object", field, type(parsed).__name__)
        return {}


USER_COLUMNS = {
    "ServerID", "UserID", "UserName", "Experience", "ExpLevel", "Reputation",
    "LastMessage", "PokeLastMessage", "ServRank", "Warnings", "Infractions", "Credits", "Claimed",
    "LastClaimed", "TimesReceived", "LastReceived", "TimesTransferred",
    "LastTransferred", "Bot", "InviteCode", "Invites", "Joined", "UserNames",
    "NickNames", "steamID", "total_pokemon",
    "list_msg_id", "info_msg_id", "position",
}

# Keep boot-time DDL cheap and idempotent. Data repair, deduplication, constraints,
# and performance indexes live in versioned migrations and therefore run once.
SCHEMA_SQL = r'''
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS botconfig (
    blacklist BIGINT[],
    first_run BOOLEAN DEFAULT FALSE,
    creator BIGINT,
    description TEXT DEFAULT 'Powered by SpryteAI'
);

CREATE TABLE IF NOT EXISTS serverconfig (
    "ServerID" BIGINT PRIMARY KEY,
    prefix TEXT NOT NULL DEFAULT '!',
    first_run SMALLINT DEFAULT 0,
    "Min_Bet" BIGINT DEFAULT 5,
    "Mid_Bet" BIGINT DEFAULT 7,
    "Max_Bet" BIGINT DEFAULT 10,
    "ContributorRole" BIGINT DEFAULT 0,
    "ModRole" BIGINT DEFAULT 0,
    "AdminRole" BIGINT DEFAULT 0,
    welcome_chan_id BIGINT DEFAULT 0,
    leave_chan_id BIGINT DEFAULT 0,
    exp_mult SMALLINT DEFAULT 1,
    exp_cooldown INTEGER DEFAULT 60,
    slot_channels BIGINT[],
    "ServerName" TEXT,
    levelup_bool SMALLINT DEFAULT 1,
    embed_footer TEXT DEFAULT 'Powered by SpryteAI',
    "paymentBool" BOOLEAN DEFAULT TRUE,
    log_chan_id BIGINT,
    report_chan_id BIGINT,
    infrac_chan_id BIGINT,
    invitemsg_bool SMALLINT,
    owner BIGINT[]
);

CREATE TABLE IF NOT EXISTS users (
    "UserID" BIGINT NOT NULL,
    "ServerID" BIGINT NOT NULL,
    "UserName" TEXT,
    "Experience" BIGINT DEFAULT 0,
    "ExpLevel" BIGINT DEFAULT 1,
    "Reputation" BIGINT DEFAULT 0,
    "ServRank" BIGINT DEFAULT 999999,
    "Warnings" SMALLINT DEFAULT 0,
    "Infractions" SMALLINT DEFAULT 0,
    "Credits" BIGINT DEFAULT 0,
    "TimesReceived" SMALLINT DEFAULT 0,
    "TimesTransferred" SMALLINT DEFAULT 0,
    "InviteCode" TEXT,
    "LastMessage" BIGINT,
    "PokeLastMessage" BIGINT,
    "LastClaimed" BIGINT DEFAULT 158000,
    "LastReceived" BIGINT DEFAULT 158000,
    "LastTransferred" BIGINT DEFAULT 158000,
    "Bot" BOOLEAN,
    "Claimed" SMALLINT DEFAULT 0,
    "Invites" INTEGER DEFAULT 0,
    "Joined" BIGINT,
    "UserNames" TEXT[],
    "NickNames" TEXT[],
    "steamID" BIGINT,
    PRIMARY KEY ("ServerID", "UserID")
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS "PokeLastMessage" BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS "total_pokemon" INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS "pokedex" TEXT[][];
ALTER TABLE users ADD COLUMN IF NOT EXISTS "pokecord_items" TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS "list_msg_id" BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS "info_msg_id" BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS "position" INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS pokecord_poke_data (
    "index" INTEGER NOT NULL,
    "uid" INTEGER NOT NULL,
    "type" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "lvl" INTEGER NOT NULL DEFAULT 5,
    "exp" BIGINT NOT NULL DEFAULT 0,
    "color" TEXT,
    "height" INTEGER,
    "weight" INTEGER,
    "nature" TEXT,
    "gender" TEXT,
    "base_exp" INTEGER,
    "base_hp" INTEGER,
    "base_attack" INTEGER,
    "base_defense" INTEGER,
    "base_special_attack" INTEGER,
    "base_special_defense" INTEGER,
    "base_speed" INTEGER,
    "hp_iv" INTEGER,
    "attack_iv" INTEGER,
    "defense_iv" INTEGER,
    "special_attack_iv" INTEGER,
    "special_defense_iv" INTEGER,
    "speed_iv" INTEGER,
    "hp" INTEGER,
    "battle_hp" INTEGER,
    "status" TEXT,
    "status_turns" INTEGER NOT NULL DEFAULT 0,
    "friendship" INTEGER NOT NULL DEFAULT 70,
    "attack" INTEGER,
    "defense" INTEGER,
    "sp_attack" INTEGER,
    "sp_defense" INTEGER,
    "speed" INTEGER,
    "item" TEXT,
    "selected" BOOLEAN NOT NULL DEFAULT FALSE,
    "shiny" BOOLEAN NOT NULL DEFAULT FALSE,
    "lucky" BOOLEAN NOT NULL DEFAULT FALSE,
    "caughton" TEXT,
    "ownerid" BIGINT NOT NULL,
    "originalownerid" TEXT,
    "moves" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "name" TEXT NOT NULL,
    "traded" INTEGER NOT NULL DEFAULT 0,
    "form" TEXT,
    "ivpercentage" DOUBLE PRECISION DEFAULT 0,
    "starred" BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY ("ownerid", "uid")
);

ALTER TABLE pokecord_poke_data ADD COLUMN IF NOT EXISTS "status" TEXT;
ALTER TABLE pokecord_poke_data ADD COLUMN IF NOT EXISTS "status_turns" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE pokecord_poke_data ADD COLUMN IF NOT EXISTS "friendship" INTEGER NOT NULL DEFAULT 70;

CREATE TABLE IF NOT EXISTS pokecord_user_state (
    "ownerid" BIGINT PRIMARY KEY,
    "next_uid" INTEGER NOT NULL DEFAULT 1 CHECK ("next_uid" >= 1)
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

CREATE TABLE IF NOT EXISTS pokecord_gym_badges (
    "ServerID" BIGINT NOT NULL,
    "UserID" BIGINT NOT NULL,
    region TEXT NOT NULL,
    leader TEXT NOT NULL,
    badge TEXT NOT NULL,
    wins INTEGER NOT NULL DEFAULT 1,
    first_won_at BIGINT NOT NULL,
    last_won_at BIGINT NOT NULL,
    PRIMARY KEY ("ServerID", "UserID", region, leader)
);

CREATE SEQUENCE IF NOT EXISTS community_player_id_seq
    START WITH -1 INCREMENT BY -1 MINVALUE -9223372036854775808 MAXVALUE -1;

CREATE TABLE IF NOT EXISTS communities (
    community_id BIGINT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_discord_user_id BIGINT,
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    features JSONB NOT NULL DEFAULT '{"pokecord": true, "twitch": true, "streaming": true}'::JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS community_discord_guilds (
    guild_id BIGINT PRIMARY KEY,
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    guild_name TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_community_discord_guilds_community
    ON community_discord_guilds(community_id);

CREATE TABLE IF NOT EXISTS community_twitch_channels (
    community_id BIGINT PRIMARY KEY REFERENCES communities(community_id) ON DELETE CASCADE,
    broadcaster_user_id TEXT NOT NULL UNIQUE,
    broadcaster_login TEXT NOT NULL,
    broadcaster_display_name TEXT,
    oauth_account TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS community_players (
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL DEFAULT nextval('community_player_id_seq'),
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (community_id, player_id)
);

CREATE TABLE IF NOT EXISTS community_player_identities (
    community_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('discord', 'twitch')),
    platform_user_id TEXT NOT NULL,
    platform_login TEXT,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (community_id, platform, platform_user_id),
    UNIQUE (community_id, player_id, platform),
    FOREIGN KEY (community_id, player_id)
        REFERENCES community_players(community_id, player_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_community_player_identities_player
    ON community_player_identities(community_id, player_id);

CREATE TABLE IF NOT EXISTS community_link_codes (
    code TEXT PRIMARY KEY,
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_community_link_codes_expiry ON community_link_codes(expires_at);

CREATE TABLE IF NOT EXISTS community_overlay_tokens (
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    overlay_type TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,
    PRIMARY KEY (community_id, overlay_type)
);

CREATE TABLE IF NOT EXISTS community_config_history (
    history_id BIGSERIAL PRIMARY KEY,
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    config JSONB NOT NULL,
    changed_by BIGINT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
'''

OPTIMIZATION_MIGRATION_SQL = r'''
-- Preserve legacy duplicate rows before enforcing the intended users key.
CREATE TABLE IF NOT EXISTS users_duplicate_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_data JSONB NOT NULL
);

WITH ranked AS (
    SELECT ctid AS row_ctid, u.*,
           ROW_NUMBER() OVER (
               PARTITION BY "ServerID", "UserID"
               ORDER BY ctid DESC
           ) AS duplicate_rank
    FROM users AS u
), archived AS (
    INSERT INTO users_duplicate_archive (row_data)
    SELECT to_jsonb(r) - 'row_ctid' - 'duplicate_rank'
    FROM ranked AS r
    WHERE r.duplicate_rank > 1
    RETURNING 1
)
DELETE FROM users AS u
USING ranked AS r
WHERE u.ctid = r.row_ctid
  AND r.duplicate_rank > 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint AS c
        WHERE c.conrelid = 'users'::regclass
          AND c.contype IN ('p', 'u')
          AND (
              SELECT ARRAY_AGG(a.attname ORDER BY k.ordinality)
              FROM UNNEST(c.conkey) WITH ORDINALITY AS k(attnum, ordinality)
              JOIN pg_attribute AS a
                ON a.attrelid = c.conrelid AND a.attnum = k.attnum
          ) = ARRAY['ServerID', 'UserID']::NAME[]
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_server_user_key UNIQUE ("ServerID", "UserID");
    END IF;
END $$;

-- Seed a global per-trainer UID allocator from the collection itself. The
-- legacy counter lived in the per-guild users row, even though Pokémon are
-- globally keyed by ownerid; that could collide when one user caught in two guilds.
INSERT INTO pokecord_user_state ("ownerid", "next_uid")
SELECT "ownerid", COALESCE(MAX("uid"), 0) + 1
FROM pokecord_poke_data
GROUP BY "ownerid"
ON CONFLICT ("ownerid") DO UPDATE
SET "next_uid" = GREATEST(pokecord_user_state."next_uid", EXCLUDED."next_uid");

-- Legacy HP rows used NULL to mean full health. Materialize that once rather
-- than scanning the whole Pokémon table every process restart.
UPDATE pokecord_poke_data
SET "battle_hp" = "hp"
WHERE "battle_hp" IS NULL;

-- A trainer should have at most one selected Pokémon. Preserve the newest UID
-- if legacy data contains more than one, then enforce it at the index level.
WITH selected_ranked AS (
    SELECT ctid,
           ROW_NUMBER() OVER (PARTITION BY "ownerid" ORDER BY "uid" DESC) AS rn
    FROM pokecord_poke_data
    WHERE "selected" IS TRUE
)
UPDATE pokecord_poke_data AS p
SET "selected" = FALSE
FROM selected_ranked AS r
WHERE p.ctid = r.ctid
  AND r.rn > 1;

DROP INDEX IF EXISTS idx_pokecord_owner_selected;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pokecord_one_selected_per_owner
    ON pokecord_poke_data ("ownerid")
    WHERE "selected" IS TRUE;

CREATE INDEX IF NOT EXISTS idx_pokecord_owner_collection_order
    ON pokecord_poke_data ("ownerid", "selected" DESC, "starred" DESC, "uid" DESC);

CREATE INDEX IF NOT EXISTS idx_pokecord_owner_name
    ON pokecord_poke_data ("ownerid", "name");

CREATE INDEX IF NOT EXISTS idx_users_xp_leaderboard
    ON users ("ServerID", "ExpLevel" DESC, "Experience" DESC, "UserID")
    WHERE "Bot" IS NOT TRUE;

CREATE INDEX IF NOT EXISTS idx_users_credits_leaderboard
    ON users ("ServerID", "Credits" DESC, "UserID")
    WHERE "Bot" IS NOT TRUE;

DROP INDEX IF EXISTS idx_pokecord_gym_badges_user;
CREATE INDEX IF NOT EXISTS idx_pokecord_gym_badges_user_region_won
    ON pokecord_gym_badges ("ServerID", "UserID", region, first_won_at);

-- These two tables are update-heavy (XP, credits, battle state). Leaving a
-- little page room improves HOT-update opportunities and reduces page splits.
ALTER TABLE users SET (fillfactor = 90);
ALTER TABLE pokecord_poke_data SET (fillfactor = 90);

UPDATE botconfig
SET description = 'Powered by SpryteAI'
WHERE description IS NULL OR description = 'Powered by BlakSpryte';

UPDATE serverconfig
SET embed_footer = 'Powered by SpryteAI'
WHERE embed_footer IS NULL OR embed_footer = 'Powered by BlakSpryte';
'''

NORMALIZE_POKECORD_MIGRATION_SQL = r'''
-- Normalize legacy Pokédex arrays and serialized item bags. The old columns are
-- intentionally retained as rollback snapshots for one transition period, but
-- SpryteAI no longer reads or writes them after this migration.
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

-- Legacy Pokédex rows are TEXT[][] pairs: [dex id, species name]. Preserve
-- server-local completion semantics exactly as the old users row did.
WITH legacy_dex AS (
    SELECT
        u."ServerID",
        u."UserID",
        ((u."pokedex")[s.i][1])::INTEGER AS dex_id,
        COALESCE(NULLIF(TRIM((u."pokedex")[s.i][2]), ''), 'unknown') AS name
    FROM users AS u
    CROSS JOIN LATERAL generate_subscripts(u."pokedex", 1) AS s(i)
    WHERE u."pokedex" IS NOT NULL
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

-- Convert serialized JSON bags safely. Bad legacy JSON is ignored rather than
-- blocking bot startup; the untouched users.pokecord_items value remains as a
-- recovery snapshot if manual repair is ever needed.
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
        CASE
            WHEN COALESCE(e.value->>'total', '') ~ '^[0-9]+$' THEN (e.value->>'total')::INTEGER
            ELSE 0
        END AS quantity,
        CASE
            WHEN COALESCE(e.value->>'id', '') ~ '^[0-9]+$' THEN (e.value->>'id')::INTEGER
            ELSE NULL
        END AS item_api_id,
        CASE
            WHEN COALESCE(e.value->>'cost', '') ~ '^[0-9]+$' THEN (e.value->>'cost')::INTEGER
            ELSE NULL
        END AS purchase_cost,
        NULLIF(e.value->>'sprite', '') AS sprite_url
    FROM users AS u
    CROSS JOIN LATERAL (
        SELECT spryteai_try_jsonb(u."pokecord_items") AS bag
    ) AS parsed
    CROSS JOIN LATERAL jsonb_each(
        CASE WHEN jsonb_typeof(parsed.bag) = 'object' THEN parsed.bag ELSE '{}'::JSONB END
    ) AS e(key, value)
    WHERE jsonb_typeof(e.value) = 'object'
), grouped AS (
    SELECT
        "ServerID",
        "UserID",
        item_name,
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
'''

MULTI_COMMUNITY_MIGRATION_SQL = r'''
-- Twitch-only players use negative internal IDs so they can never collide with
-- positive Discord snowflakes reused as player IDs.
ALTER SEQUENCE community_player_id_seq
    INCREMENT BY -1 MINVALUE -9223372036854775808 MAXVALUE -1 RESTART WITH -1;

ALTER TABLE pokecord_poke_data ADD COLUMN IF NOT EXISTS community_id BIGINT;

UPDATE pokecord_poke_data
SET community_id = 0
WHERE community_id IS NULL;

ALTER TABLE pokecord_poke_data ALTER COLUMN community_id SET NOT NULL;
ALTER TABLE pokecord_poke_data
    ALTER COLUMN community_id SET DEFAULT NULLIF(current_setting('spryteai.community_id', true), '')::BIGINT;

DO $$
DECLARE
    pk_name TEXT;
BEGIN
    SELECT c.conname INTO pk_name
    FROM pg_constraint c
    WHERE c.conrelid = 'pokecord_poke_data'::regclass AND c.contype = 'p'
    LIMIT 1;
    IF pk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE pokecord_poke_data DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;

ALTER TABLE pokecord_poke_data
    ADD CONSTRAINT pokecord_poke_data_pkey PRIMARY KEY (community_id, "ownerid", "uid");

CREATE INDEX IF NOT EXISTS idx_pokecord_community_owner
    ON pokecord_poke_data(community_id, "ownerid", "uid");
CREATE INDEX IF NOT EXISTS idx_pokecord_community_selected
    ON pokecord_poke_data(community_id, "ownerid", "selected") WHERE "selected" = TRUE;
CREATE INDEX IF NOT EXISTS idx_pokecord_community_name
    ON pokecord_poke_data(community_id, "ownerid", LOWER("name"));

-- v1 enforced selected Pokémon globally by Discord owner id.  Once the same
-- person can play in several communities, selection must be isolated too.
DROP INDEX IF EXISTS uq_pokecord_one_selected_per_owner;
DROP INDEX IF EXISTS idx_pokecord_owner_collection_order;
DROP INDEX IF EXISTS idx_pokecord_owner_name;
CREATE UNIQUE INDEX IF NOT EXISTS uq_pokecord_one_selected_per_community_owner
    ON pokecord_poke_data(community_id, "ownerid")
    WHERE "selected" IS TRUE;
CREATE INDEX IF NOT EXISTS idx_pokecord_community_collection_order
    ON pokecord_poke_data(community_id, "ownerid", "selected" DESC, "starred" DESC, "uid" DESC);

CREATE OR REPLACE VIEW pokecord_poke_data_scoped AS
SELECT *
FROM pokecord_poke_data
WHERE community_id = NULLIF(current_setting('spryteai.community_id', true), '')::BIGINT
WITH LOCAL CHECK OPTION;

COMMENT ON VIEW pokecord_poke_data_scoped IS
    'Community-scoped Pokecord compatibility view. SpryteAI sets spryteai.community_id per request/task.';
'''

POKECORD_EVOLUTION_MIGRATION_SQL = r'''
ALTER TABLE pokecord_poke_data
    ADD COLUMN IF NOT EXISTS "friendship" INTEGER NOT NULL DEFAULT 70;

UPDATE pokecord_poke_data
SET "friendship" = LEAST(255, GREATEST(0, COALESCE("friendship", 70)));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'pokecord_poke_data'::regclass
          AND conname = 'ck_pokecord_friendship_range'
    ) THEN
        ALTER TABLE pokecord_poke_data
            ADD CONSTRAINT ck_pokecord_friendship_range
            CHECK ("friendship" BETWEEN 0 AND 255);
    END IF;
END $$;

-- Existing multi-community views were created before friendship existed.
-- CREATE OR REPLACE appends the new base-table column to the scoped view.
CREATE OR REPLACE VIEW pokecord_poke_data_scoped AS
SELECT *
FROM pokecord_poke_data
WHERE community_id = NULLIF(current_setting('spryteai.community_id', true), '')::BIGINT
WITH LOCAL CHECK OPTION;

COMMENT ON VIEW pokecord_poke_data_scoped IS
    'Community-scoped Pokecord compatibility view. SpryteAI sets spryteai.community_id per request/task.';
'''


OVERLAY_TOKENS_MIGRATION_SQL = r'''
CREATE TABLE IF NOT EXISTS community_overlay_tokens (
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    overlay_type TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,
    PRIMARY KEY (community_id, overlay_type)
);
'''


MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("2026-09-11-db-optimization-v1", OPTIMIZATION_MIGRATION_SQL),
    ("2026-09-11-pokecord-normalization-v2", NORMALIZE_POKECORD_MIGRATION_SQL),
    ("2026-09-12-multi-community-v3", MULTI_COMMUNITY_MIGRATION_SQL),
    ("2026-09-13-pokecord-evolution-v4", POKECORD_EVOLUTION_MIGRATION_SQL),
    ("2026-09-13-overlay-tokens-v5", OVERLAY_TOKENS_MIGRATION_SQL),
)


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._bot_config_cache: tuple[float, asyncpg.Record] | None = None
        self._server_config_cache: dict[int, tuple[float, asyncpg.Record]] = {}
        self._config_cache_ttl = max(
            0.0,
            float(config.get("database", {}).get("config_cache_ttl", 15)),
        )

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool has not been initialized")
        return self._pool

    @property
    def current_community_id(self) -> int | None:
        return _CURRENT_COMMUNITY_ID.get()

    def activate_community(self, community_id: int | None) -> None:
        _CURRENT_COMMUNITY_ID.set(int(community_id) if community_id is not None else None)

    @staticmethod
    def json_object(value: Any, *, field: str = "JSON object") -> dict[str, Any]:
        return _json_object(value, field=field)

    @asynccontextmanager
    async def tenant_connection(self, community_id: int | None = None) -> AsyncIterator[asyncpg.Connection]:
        cid = int(community_id) if community_id is not None else self.current_community_id
        async with self.pool.acquire() as connection:
            if cid is not None:
                await connection.execute(
                    "SELECT set_config('spryteai.community_id', $1, false)", str(cid)
                )
            try:
                yield connection
            finally:
                if cid is not None:
                    try:
                        await connection.execute("RESET spryteai.community_id")
                    except Exception:
                        log.exception("Unable to reset PostgreSQL community context")

    async def connect(self) -> None:
        if self._pool is not None:
            return

        db_config = config.get("database", {})
        host = require_config(("database", "host"), label="DATABASE_HOST")
        database = require_config(("database", "database"), label="DATABASE_NAME")
        user = require_config(("database", "user"), label="DATABASE_USER")
        password = require_config(("database", "password"), label="DATABASE_PASSWORD")

        min_size = max(1, int(db_config.get("pool_min_size", 1)))
        max_size = max(min_size, int(db_config.get("pool_size", 10)))
        command_timeout = max(1.0, float(db_config.get("command_timeout", 30)))
        max_queries = max(1_000, int(db_config.get("max_queries_per_connection", 50_000)))
        max_idle = max(30.0, float(db_config.get("max_inactive_connection_lifetime", 300)))
        statement_cache_size = max(0, int(db_config.get("statement_cache_size", 256)))

        pool_kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
            max_queries=max_queries,
            max_inactive_connection_lifetime=max_idle,
            statement_cache_size=statement_cache_size,
            server_settings={"application_name": "SpryteAI"},
        )

        try:
            self._pool = await asyncpg.create_pool(**pool_kwargs)
        except asyncpg.InvalidCatalogNameError:
            await self._create_or_migrate_database(host, database, user, password)
            self._pool = await asyncpg.create_pool(**pool_kwargs)

        await self.ensure_schema()
        log.info(
            "PostgreSQL pool initialized (min=%s max=%s timeout=%ss cache=%s)",
            min_size,
            max_size,
            command_timeout,
            statement_cache_size,
        )

    async def _create_or_migrate_database(self, host: str, database: str, user: str, password: str) -> None:
        if not _IDENTIFIER_RE.fullmatch(str(database)) or not _IDENTIFIER_RE.fullmatch(str(user)):
            raise RuntimeError("Database name and user must be simple PostgreSQL identifiers for auto-creation")

        legacy_database = str(config.get("database", {}).get("legacy_database", "") or "").strip()
        if legacy_database and not _IDENTIFIER_RE.fullmatch(legacy_database):
            raise RuntimeError("Legacy database name must be a simple PostgreSQL identifier")

        connection = await asyncpg.connect(
            host=host,
            user=user,
            password=password,
            database="postgres",
            server_settings={"application_name": "SpryteAI-database-bootstrap"},
        )
        try:
            target_exists = await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)", database
            )
            if target_exists:
                return

            legacy_exists = False
            if legacy_database and legacy_database != database:
                legacy_exists = await connection.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)", legacy_database
                )

            if legacy_exists:
                log.warning(
                    "Target database %s is missing; migrating existing database %s",
                    database,
                    legacy_database,
                )
                try:
                    await connection.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = $1 AND pid <> pg_backend_pid()",
                        legacy_database,
                    )
                    await connection.execute(f'ALTER DATABASE "{legacy_database}" RENAME TO "{database}"')
                    log.info("Renamed PostgreSQL database %s to %s", legacy_database, database)
                    return
                except asyncpg.PostgresError as exc:
                    raise RuntimeError(
                        f"Could not rename PostgreSQL database {legacy_database!r} to {database!r}. "
                        "Run db/migrate_database_to_spryteai.sql while connected to the postgres maintenance database, "
                        "then restart SpryteAI."
                    ) from exc

            log.warning("Database %s does not exist; attempting to create it", database)
            await connection.execute(f'CREATE DATABASE "{database}" WITH OWNER = "{user}"')
        finally:
            await connection.close()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self.invalidate_config_cache()
            log.info("PostgreSQL connection pool closed")

    async def ensure_schema(self) -> None:
        migration_applied = False
        async with self.pool.acquire() as connection:
            # Serialize schema work if more than one SpryteAI process starts at once.
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock($1)", _SCHEMA_LOCK_KEY)
                await connection.execute(SCHEMA_SQL)

                cooldown_type = await connection.fetchval(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'serverconfig'
                      AND column_name = 'exp_cooldown'
                    """
                )
                if cooldown_type == "smallint":
                    await connection.execute(
                        """
                        ALTER TABLE serverconfig
                        ALTER COLUMN exp_cooldown TYPE INTEGER
                        USING exp_cooldown::INTEGER
                        """
                    )

                await connection.execute(
                    """
                    INSERT INTO botconfig (blacklist, first_run, description)
                    SELECT ARRAY[]::BIGINT[], FALSE, 'Powered by SpryteAI'
                    WHERE NOT EXISTS (SELECT 1 FROM botconfig)
                    """
                )

                for version, sql in MIGRATIONS:
                    applied = await connection.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version = $1)",
                        version,
                    )
                    if applied:
                        continue
                    log.info("Applying database migration %s", version)
                    await connection.execute(sql)
                    await connection.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1)",
                        version,
                    )
                    migration_applied = True

            await self._bootstrap_communities(connection)

            # Refresh planner statistics only after a migration changed physical
            # structures/data. ANALYZE is inexpensive compared with VACUUM and
            # avoids forcing a full maintenance operation on every boot.
            if migration_applied:
                await connection.execute(
                    "ANALYZE users; ANALYZE pokecord_poke_data; ANALYZE pokecord_gym_badges; "
                    "ANALYZE pokecord_pokedex; ANALYZE pokecord_inventory;"
                )

        self.invalidate_config_cache()

    async def _bootstrap_communities(self, connection: asyncpg.Connection) -> None:
        rows = await connection.fetch('SELECT "ServerID", "ServerName" FROM serverconfig ORDER BY "ServerID"')
        configured_guild = int(config.get("guild_id") or 0)
        for row in rows:
            guild_id = int(row["ServerID"])
            name = str(row["ServerName"] or f"Discord {guild_id}")
            owner = None
            if configured_guild and guild_id == configured_guild:
                owners = await connection.fetchval('SELECT owner FROM serverconfig WHERE "ServerID"=$1', guild_id)
                if owners:
                    try:
                        owner = int(owners[0])
                    except (TypeError, ValueError, IndexError):
                        owner = None
            await connection.execute(
                """
                INSERT INTO communities (community_id, slug, name, owner_discord_user_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (community_id) DO UPDATE
                SET name = CASE WHEN communities.name LIKE 'Discord %' THEN EXCLUDED.name ELSE communities.name END,
                    updated_at = NOW()
                """,
                guild_id, f"discord-{guild_id}", name, owner,
            )
            await connection.execute(
                """
                INSERT INTO community_discord_guilds (guild_id, community_id, guild_name, is_primary)
                VALUES ($1, $1, $2, TRUE)
                ON CONFLICT (guild_id) DO NOTHING
                """,
                guild_id, name,
            )

        # Preserve the old single-community Pokémon collection by attaching it
        # to the original/oldest Discord community.
        default_community = configured_guild or (int(rows[0]["ServerID"]) if rows else 0)
        if default_community:
            await connection.execute(
                'UPDATE pokecord_poke_data SET community_id=$1 WHERE community_id=0',
                default_community,
            )

        # Seed Discord player identities from existing guild user rows. Discord
        # snowflakes are intentionally reused as the canonical player id so the
        # legacy Pokecord ownerid remains valid without renumbering Pokémon.
        await connection.execute(
            """
            INSERT INTO community_players (community_id, player_id, display_name)
            SELECT cg.community_id, u."UserID", MAX(u."UserName")
            FROM users u
            JOIN community_discord_guilds cg ON cg.guild_id = u."ServerID"
            GROUP BY cg.community_id, u."UserID"
            ON CONFLICT (community_id, player_id) DO NOTHING
            """
        )
        await connection.execute(
            """
            INSERT INTO community_player_identities
                (community_id, player_id, platform, platform_user_id, platform_login)
            SELECT cg.community_id, u."UserID", 'discord', u."UserID"::TEXT, MAX(u."UserName")
            FROM users u
            JOIN community_discord_guilds cg ON cg.guild_id = u."ServerID"
            GROUP BY cg.community_id, u."UserID"
            ON CONFLICT (community_id, platform, platform_user_id) DO NOTHING
            """
        )

    async def ensure_community_for_guild(
        self, guild_id: int, guild_name: str | None = None, owner_id: int | None = None
    ) -> int:
        guild_id = int(guild_id)
        row = await self.fetchrow(
            'SELECT community_id FROM community_discord_guilds WHERE guild_id=$1', guild_id
        )
        if row:
            return int(row["community_id"])
        name = str(guild_name or f"Discord {guild_id}")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO communities (community_id, slug, name, owner_discord_user_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (community_id) DO NOTHING
                    """, guild_id, f"discord-{guild_id}", name, owner_id,
                )
                await connection.execute(
                    """
                    INSERT INTO community_discord_guilds (guild_id, community_id, guild_name, is_primary)
                    VALUES ($1, $1, $2, TRUE)
                    ON CONFLICT (guild_id) DO UPDATE SET guild_name=EXCLUDED.guild_name
                    """, guild_id, name,
                )
        return guild_id

    async def community_id_for_guild(self, guild: Any) -> int:
        guild_id = int(getattr(guild, "id", guild))
        row = await self.fetchrow(
            'SELECT community_id FROM community_discord_guilds WHERE guild_id=$1', guild_id
        )
        if row:
            cid = int(row["community_id"])
        else:
            cid = await self.ensure_community_for_guild(
                guild_id, getattr(guild, "name", None), getattr(getattr(guild, "owner", None), "id", None)
            )
        self.activate_community(cid)
        return cid

    async def primary_guild_id_for_community(self, community_id: int) -> int | None:
        value = await self.fetchval(
            """
            SELECT guild_id FROM community_discord_guilds
            WHERE community_id=$1
            ORDER BY is_primary DESC, created_at, guild_id
            LIMIT 1
            """, int(community_id),
        )
        return int(value) if value is not None else None

    async def get_community_record(self, community_id: int) -> asyncpg.Record | None:
        return await self.fetchrow('SELECT * FROM communities WHERE community_id=$1', int(community_id))

    async def get_community_config_by_id(self, community_id: int) -> dict[str, Any]:
        row = await self.fetchrow('SELECT config, features FROM communities WHERE community_id=$1', int(community_id))
        override = _json_object(row["config"], field="communities.config") if row else {}
        merged = _deep_merge(config, override)
        merged["community_id"] = int(community_id)
        if row:
            merged["features"] = _json_object(row["features"], field="communities.features")
        return merged

    async def get_community_config_for_guild(self, guild: Any) -> dict[str, Any]:
        cid = await self.community_id_for_guild(guild)
        return await self.get_community_config_by_id(cid)

    async def replace_community_override(
        self, community_id: int, override: dict[str, Any], *, changed_by: int | None = None
    ) -> None:
        payload = json.dumps(override)
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                old = await connection.fetchval('SELECT config FROM communities WHERE community_id=$1 FOR UPDATE', int(community_id))
                await connection.execute(
                    'INSERT INTO community_config_history (community_id, config, changed_by) VALUES ($1,$2::JSONB,$3)',
                    int(community_id), json.dumps(_json_object(old, field="communities.config")), changed_by,
                )
                await connection.execute(
                    'UPDATE communities SET config=$2::JSONB, updated_at=NOW() WHERE community_id=$1',
                    int(community_id), payload,
                )

    async def patch_community_override(
        self, community_id: int, patch: dict[str, Any], *, changed_by: int | None = None
    ) -> dict[str, Any]:
        row = await self.fetchrow('SELECT config FROM communities WHERE community_id=$1', int(community_id))
        current = _json_object(row["config"], field="communities.config") if row else {}
        updated = _deep_merge(current, patch)
        await self.replace_community_override(community_id, updated, changed_by=changed_by)
        return updated

    async def set_community_feature(self, community_id: int, feature: str, enabled: bool) -> None:
        await self.execute(
            """
            UPDATE communities
            SET features = jsonb_set(COALESCE(features, '{}'::JSONB), ARRAY[$2::TEXT], to_jsonb($3::BOOLEAN), TRUE),
                updated_at=NOW()
            WHERE community_id=$1
            """, int(community_id), str(feature), bool(enabled),
        )

    async def community_feature_enabled(self, community_id: int, feature: str, default: bool = True) -> bool:
        value = await self.fetchval(
            'SELECT features ->> $2 FROM communities WHERE community_id=$1', int(community_id), str(feature)
        )
        if value is None:
            return default
        return str(value).lower() in {'true', '1', 'yes', 'on'}

    async def resolve_discord_player(
        self, guild: Any, user: Any, *, display_name: str | None = None
    ) -> tuple[int, int]:
        cid = await self.community_id_for_guild(guild)
        user_id = int(getattr(user, "id", user))
        name = str(
            display_name
            or getattr(user, "display_name", None)
            or getattr(user, "name", None)
            or user_id
        )

        await self.execute(
            """
            INSERT INTO community_players (
                community_id,
                player_id,
                display_name
            )
            VALUES ($1, $2, $3)
            ON CONFLICT (community_id, player_id) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                updated_at = NOW()
            """,
            cid,
            user_id,
            name,
        )

        await self.execute(
            """
            INSERT INTO community_player_identities (
                community_id,
                player_id,
                platform,
                platform_user_id,
                platform_login
            )
            VALUES ($1, $2, 'discord', $3, $4)
            ON CONFLICT (community_id, platform, platform_user_id) DO UPDATE
            SET player_id = EXCLUDED.player_id,
                platform_login = EXCLUDED.platform_login,
                linked_at = NOW()
            """,
            cid,
            user_id,
            str(user_id),
            name,
        )

        self.activate_community(cid)
        return cid, user_id

    async def resolve_twitch_player(
        self, community_id: int, twitch_user_id: str, twitch_login: str | None = None
    ) -> int:
        cid = int(community_id)
        twitch_user_id = str(twitch_user_id)
        row = await self.fetchrow(
            """
            SELECT player_id FROM community_player_identities
            WHERE community_id=$1 AND platform='twitch' AND platform_user_id=$2
            """, cid, twitch_user_id,
        )
        if row:
            self.activate_community(cid)
            return int(row["player_id"])
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                player_id = await connection.fetchval(
                    """
                    INSERT INTO community_players (community_id, display_name)
                    VALUES ($1,$2) RETURNING player_id
                    """, cid, twitch_login or twitch_user_id,
                )
                await connection.execute(
                    """
                    INSERT INTO community_player_identities
                        (community_id, player_id, platform, platform_user_id, platform_login)
                    VALUES ($1,$2,'twitch',$3,$4)
                    """, cid, int(player_id), twitch_user_id, twitch_login,
                )
        self.activate_community(cid)
        return int(player_id)

    async def get_overlay_token(self, community_id: int, overlay_type: str = "pokemon") -> str | None:
        value = await self.fetchval(
            """
            SELECT token
            FROM community_overlay_tokens
            WHERE community_id = $1 AND overlay_type = $2
            """,
            int(community_id),
            str(overlay_type),
        )
        return str(value) if value is not None else None

    async def get_or_create_overlay_token(
        self, community_id: int, overlay_type: str = "pokemon"
    ) -> str:
        cid = int(community_id)
        kind = str(overlay_type)
        existing = await self.get_overlay_token(cid, kind)
        if existing:
            return existing

        while True:
            token = secrets.token_urlsafe(32)
            try:
                value = await self.fetchval(
                    """
                    INSERT INTO community_overlay_tokens (community_id, overlay_type, token)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (community_id, overlay_type) DO NOTHING
                    RETURNING token
                    """,
                    cid,
                    kind,
                    token,
                )
                if value is not None:
                    return str(value)
                existing = await self.get_overlay_token(cid, kind)
                if existing:
                    return existing
            except asyncpg.UniqueViolationError:
                continue

    async def rotate_overlay_token(
        self, community_id: int, overlay_type: str = "pokemon"
    ) -> str:
        cid = int(community_id)
        kind = str(overlay_type)
        while True:
            token = secrets.token_urlsafe(32)
            try:
                await self.execute(
                    """
                    INSERT INTO community_overlay_tokens (community_id, overlay_type, token, rotated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (community_id, overlay_type) DO UPDATE
                    SET token = EXCLUDED.token,
                        rotated_at = NOW()
                    """,
                    cid,
                    kind,
                    token,
                )
                return token
            except asyncpg.UniqueViolationError:
                continue

    async def create_twitch_link_code(
        self, guild: Any, discord_user: Any, ttl_seconds: int = 600
    ) -> str:
        cid, _ = await self.resolve_discord_player(guild, discord_user)
        user_id = int(getattr(discord_user, "id", discord_user))

        await self.execute(
            """
            DELETE FROM community_link_codes
            WHERE expires_at < NOW()
               OR (community_id = $1 AND discord_user_id = $2)
            """,
            cid,
            user_id,
        )

        ttl = max(60, int(ttl_seconds))

        while True:
            code = secrets.token_hex(3).upper()
            try:
                await self.execute(
                    """
                    INSERT INTO community_link_codes (
                        code,
                        community_id,
                        discord_user_id,
                        expires_at
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        NOW() + ($4::INTEGER * INTERVAL '1 second')
                    )
                    """,
                    code,
                    cid,
                    user_id,
                    ttl,
                )
                return code
            except asyncpg.UniqueViolationError:
                continue

    async def consume_twitch_link_code(
        self, code: str, twitch_user_id: str, twitch_login: str, *, expected_community_id: int | None = None
    ) -> tuple[int, int] | None:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                if expected_community_id is None:
                    pending = await connection.fetchrow(
                        'DELETE FROM community_link_codes WHERE code=$1 AND expires_at>=NOW() RETURNING community_id, discord_user_id',
                        str(code).strip().upper(),
                    )
                else:
                    pending = await connection.fetchrow(
                        'DELETE FROM community_link_codes WHERE code=$1 AND community_id=$2 AND expires_at>=NOW() RETURNING community_id, discord_user_id',
                        str(code).strip().upper(), int(expected_community_id),
                    )
                if not pending:
                    return None
                cid = int(pending['community_id'])
                discord_id = int(pending['discord_user_id'])
                target_player = discord_id
                await connection.execute(
                    """
                    INSERT INTO community_players (community_id, player_id, display_name)
                    VALUES ($1,$2,$3) ON CONFLICT (community_id, player_id) DO NOTHING
                    """, cid, target_player, twitch_login,
                )
                source = await connection.fetchrow(
                    """
                    SELECT player_id FROM community_player_identities
                    WHERE community_id=$1 AND platform='twitch' AND platform_user_id=$2
                    FOR UPDATE
                    """, cid, str(twitch_user_id),
                )
                if source and int(source['player_id']) != target_player:
                    await self._merge_players(connection, cid, int(source['player_id']), target_player)
                await connection.execute(
                    """
                    INSERT INTO community_player_identities
                        (community_id, player_id, platform, platform_user_id, platform_login)
                    VALUES ($1,$2,'twitch',$3,$4)
                    ON CONFLICT (community_id, platform, platform_user_id) DO UPDATE
                    SET player_id=EXCLUDED.player_id, platform_login=EXCLUDED.platform_login, linked_at=NOW()
                    """, cid, target_player, str(twitch_user_id), twitch_login,
                )
        self.activate_community(cid)
        return cid, discord_id

    async def _merge_players(
        self, connection: asyncpg.Connection, community_id: int, source_player: int, target_player: int
    ) -> None:
        if source_player == target_player:
            return
        # Preserve every Pokémon. Conflicting UIDs are moved to the next free UID.
        rows = await connection.fetch(
            'SELECT uid FROM pokecord_poke_data WHERE community_id=$1 AND "ownerid"=$2 ORDER BY uid FOR UPDATE',
            community_id, source_player,
        )
        next_uid = int(await connection.fetchval(
            'SELECT COALESCE(MAX(uid),0)+1 FROM pokecord_poke_data WHERE community_id=$1 AND "ownerid"=$2',
            community_id, target_player,
        ))
        for row in rows:
            uid = int(row['uid'])
            conflict = await connection.fetchval(
                'SELECT 1 FROM pokecord_poke_data WHERE community_id=$1 AND "ownerid"=$2 AND uid=$3',
                community_id, target_player, uid,
            )
            new_uid = next_uid if conflict else uid
            if conflict:
                next_uid += 1
            await connection.execute(
                'UPDATE pokecord_poke_data SET "ownerid"=$3, uid=$4 WHERE community_id=$1 AND "ownerid"=$2 AND uid=$5',
                community_id, source_player, target_player, new_uid, uid,
            )
        # Pokédex: union entries, preserving earliest catch timestamp.
        await connection.execute(
            """
            INSERT INTO pokecord_pokedex ("ServerID","UserID",dex_id,name,first_caught_at)
            SELECT $1,$3,dex_id,name,first_caught_at FROM pokecord_pokedex WHERE "ServerID"=$1 AND "UserID"=$2
            ON CONFLICT ("ServerID","UserID",dex_id) DO UPDATE
            SET first_caught_at=LEAST(pokecord_pokedex.first_caught_at,EXCLUDED.first_caught_at), name=EXCLUDED.name
            """, community_id, source_player, target_player,
        )
        await connection.execute('DELETE FROM pokecord_pokedex WHERE "ServerID"=$1 AND "UserID"=$2', community_id, source_player)
        # Inventory: sum quantities.
        await connection.execute(
            """
            INSERT INTO pokecord_inventory ("ServerID","UserID",item_name,quantity,item_api_id,purchase_cost,sprite_url)
            SELECT $1,$3,item_name,quantity,item_api_id,purchase_cost,sprite_url
            FROM pokecord_inventory WHERE "ServerID"=$1 AND "UserID"=$2
            ON CONFLICT ("ServerID","UserID",item_name) DO UPDATE
            SET quantity=pokecord_inventory.quantity+EXCLUDED.quantity, updated_at=NOW()
            """, community_id, source_player, target_player,
        )
        await connection.execute('DELETE FROM pokecord_inventory WHERE "ServerID"=$1 AND "UserID"=$2', community_id, source_player)
        # Badges: keep highest win count and earliest first win.
        await connection.execute(
            """
            INSERT INTO pokecord_gym_badges ("ServerID","UserID",region,leader,badge,wins,first_won_at,last_won_at)
            SELECT $1,$3,region,leader,badge,wins,first_won_at,last_won_at
            FROM pokecord_gym_badges WHERE "ServerID"=$1 AND "UserID"=$2
            ON CONFLICT ("ServerID","UserID",region,leader) DO UPDATE
            SET wins=GREATEST(pokecord_gym_badges.wins,EXCLUDED.wins),
                first_won_at=LEAST(pokecord_gym_badges.first_won_at,EXCLUDED.first_won_at),
                last_won_at=GREATEST(pokecord_gym_badges.last_won_at,EXCLUDED.last_won_at)
            """, community_id, source_player, target_player,
        )
        await connection.execute('DELETE FROM pokecord_gym_badges WHERE "ServerID"=$1 AND "UserID"=$2', community_id, source_player)
        # Keep the global UID allocator ahead of all Pokémon now owned by the
        # target player.  It is intentionally conservative across communities:
        # gaps are harmless, duplicate UIDs are not.
        max_uid = int(await connection.fetchval(
            'SELECT COALESCE(MAX(uid),0) FROM pokecord_poke_data WHERE "ownerid"=$1',
            target_player,
        ) or 0)
        await connection.execute(
            '''
            INSERT INTO pokecord_user_state ("ownerid", "next_uid")
            VALUES ($1, $2)
            ON CONFLICT ("ownerid") DO UPDATE
            SET "next_uid" = GREATEST(pokecord_user_state."next_uid", EXCLUDED."next_uid")
            ''',
            target_player, max_uid + 1,
        )
        await connection.execute(
            'DELETE FROM community_players WHERE community_id=$1 AND player_id=$2', community_id, source_player
        )
        await connection.execute('DELETE FROM pokecord_user_state WHERE "ownerid"=$1', source_player)

    async def discord_id_for_twitch(self, community_id: int, twitch_user_id: str) -> int | None:
        value = await self.fetchval(
            """
            SELECT d.platform_user_id
            FROM community_player_identities t
            JOIN community_player_identities d
              ON d.community_id=t.community_id AND d.player_id=t.player_id AND d.platform='discord'
            WHERE t.community_id=$1 AND t.platform='twitch' AND t.platform_user_id=$2
            """, int(community_id), str(twitch_user_id),
        )
        return int(value) if value is not None else None

    async def unlink_twitch_for_discord(self, community_id: int, discord_user_id: int) -> bool:
        result = await self.execute(
            '''
            DELETE FROM community_player_identities t
            USING community_player_identities d
            WHERE t.community_id=$1
              AND d.community_id=t.community_id
              AND d.player_id=t.player_id
              AND d.platform='discord'
              AND d.platform_user_id=$2
              AND t.platform='twitch'
            ''',
            int(community_id), str(int(discord_user_id)),
        )
        try:
            return int(str(result).split()[-1]) > 0
        except (ValueError, IndexError):
            return False

    async def list_twitch_links(self, community_id: int) -> list[asyncpg.Record]:
        return await self.fetch(
            '''
            SELECT d.platform_user_id AS discord_user_id,
                   t.platform_user_id AS twitch_user_id,
                   t.platform_login AS twitch_login,
                   t.player_id
            FROM community_player_identities t
            JOIN community_player_identities d
              ON d.community_id=t.community_id
             AND d.player_id=t.player_id
             AND d.platform='discord'
            WHERE t.community_id=$1 AND t.platform='twitch'
            ORDER BY t.linked_at
            ''',
            int(community_id),
        )

    async def unbind_twitch_channel(self, community_id: int) -> None:
        await self.execute(
            'UPDATE community_twitch_channels SET enabled=FALSE, updated_at=NOW() WHERE community_id=$1',
            int(community_id),
        )

    async def bind_twitch_channel(
        self, community_id: int, broadcaster_user_id: str, broadcaster_login: str,
        broadcaster_display_name: str | None, oauth_account: str
    ) -> None:
        await self.execute(
            """
            INSERT INTO community_twitch_channels
                (community_id,broadcaster_user_id,broadcaster_login,broadcaster_display_name,oauth_account)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (community_id) DO UPDATE
            SET broadcaster_user_id=EXCLUDED.broadcaster_user_id,
                broadcaster_login=EXCLUDED.broadcaster_login,
                broadcaster_display_name=EXCLUDED.broadcaster_display_name,
                oauth_account=EXCLUDED.oauth_account, enabled=TRUE, updated_at=NOW()
            """, int(community_id), str(broadcaster_user_id), str(broadcaster_login), broadcaster_display_name, str(oauth_account),
        )

    async def twitch_channel_for_community(self, community_id: int) -> asyncpg.Record | None:
        return await self.fetchrow('SELECT * FROM community_twitch_channels WHERE community_id=$1 AND enabled=TRUE', int(community_id))

    async def community_for_twitch_broadcaster(self, broadcaster_user_id: str) -> int | None:
        value = await self.fetchval(
            'SELECT community_id FROM community_twitch_channels WHERE broadcaster_user_id=$1 AND enabled=TRUE',
            str(broadcaster_user_id),
        )
        return int(value) if value is not None else None

    async def list_twitch_communities(self) -> list[asyncpg.Record]:
        return await self.fetch(
            '''
            SELECT tc.*
            FROM community_twitch_channels tc
            JOIN communities c ON c.community_id=tc.community_id
            WHERE tc.enabled=TRUE
              AND c.enabled=TRUE
              AND COALESCE((c.features ->> 'twitch')::BOOLEAN, TRUE)=TRUE
            ORDER BY tc.community_id
            '''
        )

    def invalidate_config_cache(self, guild_id: int | None = None) -> None:
        self._bot_config_cache = None
        if guild_id is None:
            self._server_config_cache.clear()
        else:
            self._server_config_cache.pop(int(guild_id), None)

    def _invalidate_for_write(self, query: str) -> None:
        stripped = query.lstrip()
        if not re.match(r"(?is)^(UPDATE|INSERT|DELETE|TRUNCATE|ALTER)\b", stripped):
            return
        if re.search(r"(?i)\bserverconfig\b", query):
            self._server_config_cache.clear()
        if re.search(r"(?i)\bbotconfig\b", query):
            self._bot_config_cache = None

    async def execute(self, query: str, *args: Any) -> str:
        try:
            async with self.tenant_connection() as connection:
                result = await connection.execute(query, *args)
            self._invalidate_for_write(query)
            return result
        except Exception:
            log.exception("Database execute failed")
            raise

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        try:
            async with self.tenant_connection() as connection:
                row = await connection.fetchrow(query, *args)
            self._invalidate_for_write(query)
            return row
        except Exception:
            log.exception("Database fetchrow failed")
            raise

    async def fetchval(self, query: str, *args: Any, column: int = 0) -> Any:
        try:
            async with self.tenant_connection() as connection:
                value = await connection.fetchval(query, *args, column=column)
            self._invalidate_for_write(query)
            return value
        except Exception:
            log.exception("Database fetchval failed")
            raise

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        try:
            async with self.tenant_connection() as connection:
                rows = list(await connection.fetch(query, *args))
            self._invalidate_for_write(query)
            return rows
        except Exception:
            log.exception("Database fetch failed")
            raise

    async def _game_ids(self, guild_id: int, user_id: int) -> tuple[int, int]:
        row = await self.fetchrow(
            'SELECT community_id FROM community_discord_guilds WHERE guild_id=$1', int(guild_id)
        )
        community_id = int(row['community_id']) if row else await self.ensure_community_for_guild(int(guild_id))
        self.activate_community(community_id)
        return community_id, int(user_id)

    async def get_player_pokedex(self, community_id: int, player_id: int) -> list[asyncpg.Record]:
        self.activate_community(int(community_id))
        return await self.fetch(
            '''
            SELECT dex_id, name, first_caught_at
            FROM pokecord_pokedex
            WHERE "ServerID"=$1 AND "UserID"=$2
            ORDER BY dex_id
            ''',
            int(community_id), int(player_id),
        )

    async def record_player_pokedex(
        self, community_id: int, player_id: int, dex_id: int, name: str, *,
        caught_at: int = 0, connection: asyncpg.Connection | None = None
    ) -> None:
        self.activate_community(int(community_id))
        if connection is not None:
            await connection.execute(
                '''
                INSERT INTO pokecord_pokedex ("ServerID","UserID",dex_id,name,first_caught_at)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT ("ServerID","UserID",dex_id) DO UPDATE SET name=EXCLUDED.name
                ''',
                int(community_id), int(player_id), int(dex_id), str(name), int(caught_at),
            )
            return
        await self.execute(
            '''
            INSERT INTO pokecord_pokedex ("ServerID","UserID",dex_id,name,first_caught_at)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT ("ServerID","UserID",dex_id) DO UPDATE SET name=EXCLUDED.name
            ''',
            int(community_id), int(player_id), int(dex_id), str(name), int(caught_at),
        )

    async def get_pokedex_entries(self, guild_id: int, user_id: int) -> list[asyncpg.Record]:
        guild_id, user_id = await self._game_ids(guild_id, user_id)
        return await self.fetch(
            """
            SELECT dex_id, name, first_caught_at
            FROM pokecord_pokedex
            WHERE "ServerID" = $1 AND "UserID" = $2
            ORDER BY dex_id
            """,
            int(guild_id),
            int(user_id),
        )

    async def record_pokedex_entry(
        self,
        guild_id: int,
        user_id: int,
        dex_id: int,
        name: str,
        *,
        caught_at: int = 0,
        connection: asyncpg.Connection | None = None,
    ) -> None:
        community_id, player_id = await self._game_ids(guild_id, user_id)
        await self.record_player_pokedex(
            community_id, player_id, dex_id, name, caught_at=caught_at, connection=connection
        )

    async def get_inventory(
        self,
        guild_id: int,
        user_id: int,
        *,
        search: str = "",
        limit: int | None = None,
    ) -> list[asyncpg.Record]:
        guild_id, user_id = await self._game_ids(guild_id, user_id)
        needle = str(search or "").strip().lower().replace(" ", "-")
        safe_limit = 10_000 if limit is None else max(1, min(int(limit), 10_000))
        return await self.fetch(
            """
            SELECT item_name, quantity, item_api_id, purchase_cost, sprite_url
            FROM pokecord_inventory
            WHERE "ServerID" = $1
              AND "UserID" = $2
              AND quantity > 0
              AND ($3::TEXT = '' OR item_name LIKE '%' || $3::TEXT || '%')
            ORDER BY item_name
            LIMIT $4
            """,
            int(guild_id), int(user_id), needle, safe_limit,
        )

    async def get_inventory_item(
        self,
        guild_id: int,
        user_id: int,
        item_name: str,
        *,
        connection: asyncpg.Connection | None = None,
        for_update: bool = False,
    ) -> asyncpg.Record | None:
        guild_id, user_id = await self._game_ids(guild_id, user_id)
        executor = connection or self.pool
        lock = " FOR UPDATE" if for_update and connection is not None else ""
        return await executor.fetchrow(
            """
            SELECT item_name, quantity, item_api_id, purchase_cost, sprite_url
            FROM pokecord_inventory
            WHERE "ServerID" = $1 AND "UserID" = $2 AND item_name = $3 AND quantity > 0
            """ + lock,
            int(guild_id), int(user_id), str(item_name),
        )

    async def add_inventory_item(
        self,
        guild_id: int,
        user_id: int,
        item_name: str,
        *,
        quantity: int = 1,
        item_api_id: int | None = None,
        purchase_cost: int | None = None,
        sprite_url: str | None = None,
        connection: asyncpg.Connection | None = None,
    ) -> asyncpg.Record:
        guild_id, user_id = await self._game_ids(guild_id, user_id)
        executor = connection or self.pool
        row = await executor.fetchrow(
            """
            INSERT INTO pokecord_inventory (
                "ServerID", "UserID", item_name, quantity,
                item_api_id, purchase_cost, sprite_url
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT ("ServerID", "UserID", item_name) DO UPDATE
            SET quantity = pokecord_inventory.quantity + EXCLUDED.quantity,
                item_api_id = COALESCE(EXCLUDED.item_api_id, pokecord_inventory.item_api_id),
                purchase_cost = COALESCE(EXCLUDED.purchase_cost, pokecord_inventory.purchase_cost),
                sprite_url = COALESCE(EXCLUDED.sprite_url, pokecord_inventory.sprite_url),
                updated_at = NOW()
            RETURNING item_name, quantity, item_api_id, purchase_cost, sprite_url
            """,
            int(guild_id), int(user_id), str(item_name), max(0, int(quantity)),
            item_api_id, purchase_cost, sprite_url,
        )
        if row is None:
            raise RuntimeError("Unable to update Pokémon inventory")
        return row

    async def consume_inventory_item(
        self,
        guild_id: int,
        user_id: int,
        item_name: str,
        *,
        quantity: int = 1,
        connection: asyncpg.Connection | None = None,
    ) -> asyncpg.Record | None:
        guild_id, user_id = await self._game_ids(guild_id, user_id)
        executor = connection or self.pool
        return await executor.fetchrow(
            """
            UPDATE pokecord_inventory
            SET quantity = quantity - $4, updated_at = NOW()
            WHERE "ServerID" = $1
              AND "UserID" = $2
              AND item_name = $3
              AND quantity >= $4
            RETURNING item_name, quantity, item_api_id, purchase_cost, sprite_url
            """,
            int(guild_id), int(user_id), str(item_name), max(1, int(quantity)),
        )

    async def execute_many_in_transaction(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        async with self.tenant_connection() as connection:
            async with connection.transaction():
                for query, args in statements:
                    await connection.execute(query, *args)
                    self._invalidate_for_write(query)

    # Compatibility wrapper retained so the existing cogs need minimal changes.
    async def query_postgresDatabase(
        self,
        query: str,
        *args: Any,
        returnValue: bool = False,
        returnMultiple: bool = False,
    ) -> Any:
        if not returnValue:
            await self.execute(query, *args)
            return None
        if returnMultiple:
            return await self.fetch(query, *args)
        return await self.fetchrow(query, *args)

    async def get_bot_config(self) -> asyncpg.Record:
        now = time.monotonic()
        if self._bot_config_cache is not None:
            cached_at, row = self._bot_config_cache
            if now - cached_at <= self._config_cache_ttl:
                return row

        row = await self.fetchrow("SELECT * FROM botconfig LIMIT 1")
        if row is None:
            await self.ensure_schema()
            row = await self.fetchrow("SELECT * FROM botconfig LIMIT 1")
        if row is None:
            raise RuntimeError("Unable to initialize botconfig")
        self._bot_config_cache = (time.monotonic(), row)
        return row

    async def get_server_config(self, guild: Any) -> asyncpg.Record:
        guild_id = int(guild.id)
        now = time.monotonic()
        cached = self._server_config_cache.get(guild_id)
        if cached is not None:
            cached_at, row = cached
            if now - cached_at <= self._config_cache_ttl:
                return row

        row = await self.fetchrow('SELECT * FROM serverconfig WHERE "ServerID" = $1', guild_id)
        if row is None:
            await self.add_guild_postgresql(guild)
            row = await self.fetchrow('SELECT * FROM serverconfig WHERE "ServerID" = $1', guild_id)
        if row is None:
            raise RuntimeError(f"Unable to initialize server config for guild {guild_id}")
        self._server_config_cache[guild_id] = (time.monotonic(), row)
        return row

    async def add_guild_postgresql(self, guild: Any) -> None:
        default_prefix = str(config.get("bot", {}).get("prefix", "!"))
        await self.execute(
            """
            INSERT INTO serverconfig ("ServerID", "ServerName", prefix)
            VALUES ($1, $2, $3)
            ON CONFLICT ("ServerID") DO UPDATE SET "ServerName" = EXCLUDED."ServerName"
            """,
            guild.id,
            guild.name,
            default_prefix,
        )
        self.invalidate_config_cache(guild.id)
        await self.ensure_community_for_guild(
            guild.id, guild.name, getattr(getattr(guild, "owner", None), "id", None)
        )

    async def get_player_postgresData(self, member: Any, guild: Any, data: str | None = None) -> asyncpg.Record:
        if data is not None and data not in USER_COLUMNS:
            raise ValueError(f"Unsupported users column: {data}")

        if data is None:
            query = 'SELECT * FROM users WHERE "UserID" = $1 AND "ServerID" = $2'
        else:
            query = f'SELECT "{data}" FROM users WHERE "UserID" = $1 AND "ServerID" = $2'

        result = await self.fetchrow(query, member.id, guild.id)
        if result is None:
            await self.add_user_to_postgresDB(member, guild)
            result = await self.fetchrow(query, member.id, guild.id)

        if result is None:
            raise RuntimeError(f"Unable to initialize user {member.id} in guild {guild.id}")
        return result

    async def add_user_to_postgresDB(self, member: Any, guild: Any) -> asyncpg.Record:
        await self.resolve_discord_player(guild, member)
        now = int(time.time())
        nickname = member.nick if getattr(member, "nick", None) else member.name

        result = await self.fetchrow(
            """
            INSERT INTO users (
                "ServerID", "UserID", "UserName", "Experience", "ExpLevel", "Reputation",
                "LastMessage", "ServRank", "Warnings", "Infractions", "Credits", "Claimed",
                "LastClaimed", "TimesReceived", "LastReceived", "TimesTransferred",
                "LastTransferred", "Bot", "InviteCode", "NickNames", "UserNames"
            )
            VALUES ($1, $2, $3, 0, 1, 0, $4, 999999, 0, 0, 0, 0,
                    NULL, 0, NULL, 0, NULL, $5, NULL, $6, $7)
            ON CONFLICT ("ServerID", "UserID") DO NOTHING
            RETURNING *
            """,
            guild.id,
            member.id,
            member.name,
            now,
            bool(member.bot),
            [nickname],
            [member.name],
        )

        if result is None:
            result = await self.fetchrow(
                'SELECT * FROM users WHERE "ServerID" = $1 AND "UserID" = $2',
                guild.id,
                member.id,
            )
        if result is None:
            raise RuntimeError(f"Unable to add user {member.id} to guild {guild.id}")

        log.debug("Added/confirmed user %s (%s) in guild %s", member.name, member.id, guild.id)
        return result

    async def award_message_experience(
        self,
        member: Any,
        guild: Any,
        experience_gain: int,
        cooldown: int,
    ) -> asyncpg.Record | None:
        """Ensure a user exists and atomically award message XP in one round trip.

        For behavioral compatibility, a user's very first stored message creates
        the row but does not award XP; later eligible messages return both the
        new XP total and the previous/current level needed by the listener.
        """
        now = int(time.time())
        nickname = member.nick if getattr(member, "nick", None) else member.name
        return await self.fetchrow(
            """
            WITH inserted AS (
                INSERT INTO users (
                    "ServerID", "UserID", "UserName", "Experience", "ExpLevel",
                    "LastMessage", "Bot", "NickNames", "UserNames"
                )
                VALUES ($1, $2, $3, 0, 1, $4, $5, $6, $7)
                ON CONFLICT ("ServerID", "UserID") DO NOTHING
                RETURNING 1
            )
            UPDATE users
            SET "Experience" = COALESCE("Experience", 0) + $8,
                "LastMessage" = $4
            WHERE "ServerID" = $1
              AND "UserID" = $2
              AND NOT EXISTS (SELECT 1 FROM inserted)
              AND ($4 - COALESCE("LastMessage", 0)) >= $9
            RETURNING "Experience", "ExpLevel"
            """,
            guild.id,
            member.id,
            member.name,
            now,
            bool(member.bot),
            [nickname],
            [member.name],
            int(experience_gain),
            max(0, int(cooldown)),
        )

    async def remove_user_from_postgresDB(self, member: Any, guild: Any) -> None:
        status = await self.execute(
            'DELETE FROM users WHERE "ServerID" = $1 AND "UserID" = $2',
            guild.id,
            member.id,
        )
        log.info("Removed user %s (%s) from guild %s: %s", member.name, member.id, guild.id, status)
