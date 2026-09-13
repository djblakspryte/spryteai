SpryteAI multi-community JSONB decoding hotfix

Replace:
  database.py
  cogs/commands/CommunityCommands.py

Then restart SpryteAI.

Cause:
asyncpg returns PostgreSQL json/jsonb values as strings unless a custom codec is installed. The multi-community code was calling dict() directly on communities.config/features, producing ValueError.

Fix:
- Safely decode JSON/JSONB whether returned as str, bytes, or dict.
- Apply the decoder to community config/features reads.
- Apply it to community override history/update paths.
- Apply it to /community config-show, config-set, and config-reset.

No SQL migration or data reset is required.
