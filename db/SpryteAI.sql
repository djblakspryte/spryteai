-- SpryteAI PostgreSQL schema
-- Multi-community build. Safe for fresh installs; versioned migrations are also
-- applied automatically by database.py at startup.

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

CREATE TABLE IF NOT EXISTS community_config_history (
    history_id BIGSERIAL PRIMARY KEY,
    community_id BIGINT NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    config JSONB NOT NULL,
    changed_by BIGINT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

-- Seed one community per existing Discord guild. SpryteAI's automatic startup
-- path is preferred because it can honor config.guild_id when choosing the
-- legacy home community. This standalone SQL falls back to the lowest guild ID.
INSERT INTO communities (community_id, slug, name)
SELECT "ServerID", 'discord-' || "ServerID"::TEXT,
       COALESCE(NULLIF("ServerName", ''), 'Discord ' || "ServerID"::TEXT)
FROM serverconfig
ON CONFLICT (community_id) DO UPDATE
SET name = CASE WHEN communities.name LIKE 'Discord %' THEN EXCLUDED.name ELSE communities.name END,
    updated_at = NOW();

INSERT INTO community_discord_guilds (guild_id, community_id, guild_name, is_primary)
SELECT "ServerID", "ServerID", COALESCE("ServerName", 'Discord ' || "ServerID"::TEXT), TRUE
FROM serverconfig
ON CONFLICT (guild_id) DO UPDATE SET guild_name=EXCLUDED.guild_name;

UPDATE pokecord_poke_data
SET community_id = COALESCE((SELECT MIN("ServerID") FROM serverconfig), community_id)
WHERE community_id = 0;

INSERT INTO community_players (community_id, player_id, display_name)
SELECT cg.community_id, u."UserID", MAX(u."UserName")
FROM users u JOIN community_discord_guilds cg ON cg.guild_id=u."ServerID"
GROUP BY cg.community_id, u."UserID"
ON CONFLICT (community_id, player_id) DO NOTHING;

INSERT INTO community_player_identities
    (community_id, player_id, platform, platform_user_id, platform_login)
SELECT cg.community_id, u."UserID", 'discord', u."UserID"::TEXT, MAX(u."UserName")
FROM users u JOIN community_discord_guilds cg ON cg.guild_id=u."ServerID"
GROUP BY cg.community_id, u."UserID"
ON CONFLICT (community_id, platform, platform_user_id) DO NOTHING;

INSERT INTO schema_migrations(version) VALUES
('2026-09-11-db-optimization-v1'),
('2026-09-11-pokecord-normalization-v2'),
('2026-09-12-multi-community-v3')
ON CONFLICT (version) DO NOTHING;

ANALYZE users;
ANALYZE pokecord_poke_data;
ANALYZE pokecord_gym_badges;
ANALYZE pokecord_pokedex;
ANALYZE pokecord_inventory;
ANALYZE communities;

