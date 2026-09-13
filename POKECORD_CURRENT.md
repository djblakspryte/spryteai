# Pokecord current build

This full build includes the cumulative Pokecord modernization work:

- Native `/pokemon` slash-only command group (23 subcommands)
- Autocomplete for Pokémon UIDs and items
- Button-based collection paging/sorting
- Mostly ephemeral personal-management commands
- Interactive trade acceptance and battle move buttons
- Async/cached PokéAPI client and official artwork
- Offline-safe modern evolution-item shop with current-price enrichment
- Autonomous spawning with retry/channel-resolution diagnostics
- `Catch Pokémon` button + private name-entry modal
- Transactional catches/trades and PostgreSQL schema support

Configure `pokecord.spawn_channel_id` in `config/config.json` before relying on automatic spawns.
