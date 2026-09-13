-- Run this while connected to the PostgreSQL maintenance database named "postgres",
-- not while connected to discord_data. Stop SpryteAI first so no sessions are using it.

SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'discord_data'
  AND pid <> pg_backend_pid();

ALTER DATABASE discord_data RENAME TO spryteai_data;
