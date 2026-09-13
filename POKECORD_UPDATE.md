# Pokecord modernization patch

## What changed

- All PokéAPI and artwork traffic is asynchronous through one shared `aiohttp` session.
- PokéAPI JSON is held in a bounded TTL/LRU-style cache with request coalescing.
- Official PokéAPI artwork replaces Bulbapedia/archive HTML scraping.
- Artwork is normalized to PNG and cached on disk under `db/pokecordData/Images`.
- Spawn silhouettes are generated in memory, so concurrent commands do not share temp files.
- Spawn range is configurable and defaults to National Dex #1025.
- Legendary/mythical rarity uses species metadata instead of a hard-coded Gen I-III list.
- Spawn timers run as a background task instead of leaving an `on_message` listener asleep.
- Pokémon XP cooldown claiming is atomic in PostgreSQL.
- Level-up XP checks use the next-level threshold.
- Independent IV rolls now use the full legacy 0-15 range correctly (`randrange(0, 16)`).
- Speed uses the non-HP stat formula.
- Evolution lookup code is shared rather than duplicated for level/item/trade evolution.
- Store metadata is cached for six hours.
- Capture handling is serialized to prevent two users catching one spawn concurrently.

## Configuration

Merge these values into the `pokecord` object in your `config/config.json` as desired:

```json
{
  "max_pokemon_id": 1025,
  "legendary_roll": 300,
  "spawn_min_seconds": 45,
  "spawn_max_seconds": 120,
  "api_cache_ttl": 21600,
  "api_cache_entries": 2000,
  "image_cache_ttl": 3600,
  "image_cache_entries": 128
}
```

`legendary_roll: 300` means a randomly selected legendary/mythical candidate survives the rarity check about 1 in 300 times.
