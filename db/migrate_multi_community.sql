-- SpryteAI manual multi-community migration
-- Prefer restarting SpryteAI; database.py applies this automatically and can
-- honor config.guild_id when choosing the legacy Pokémon community.

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

INSERT INTO schema_migrations(version)
VALUES ('2026-09-12-multi-community-v3')
ON CONFLICT (version) DO NOTHING;

