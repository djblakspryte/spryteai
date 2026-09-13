from __future__ import annotations

import asyncio
import json
import logging
import random
import string
import time
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from config import BASE_DIR, BRAND_NAME, config
from services import db
from utils import helpers
from utils.pokeapi import PokeAPIClient, PokeAPIError

log = logging.getLogger(__name__)
c = commands  # Temporary alias retained to keep legacy decorators readable.

POKE_CONFIG = config.get("pokecord", {})
exp_secs = max(1, int(POKE_CONFIG.get("exp_cooldown", 30)))
DEFAULT_SPAWN_CHANNEL_ID = int(POKE_CONFIG.get("spawn_channel_id", 0) or 0)
DATA_DIR = BASE_DIR / "db" / "pokecordData"
IMAGE_DIR = DATA_DIR / "Images"
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

alolan_pokemon = [19, 20, 26, 27, 28, 37, 38, 50, 51, 52, 53, 74, 75, 76, 88, 89, 103, 105]
alolanIds = [10091, 10092, 10100, 10101, 10102, 10103, 10104, 10105, 10106, 10107, 10108, 10109, 10110, 10111,
             10112, 10113, 10114, 10115]

effectiveness = {
    "None": {"Normal": 1, "Fighting": 1, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 1, "Ghost": 1,
             "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 1,
             "Dark": 1, "Fairy": 1},
    "normal": {"Normal": 1, "Fighting": 2, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 1, "Ghost": 0,
               "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 1,
               "Dark": 1, "Fairy": 1},
    "fighting": {"Normal": 1, "Fighting": 1, "Flying": 2, "Poison": 1, "Ground": 1, "Rock": 0.5, "Bug": 0.5, "Ghost": 1,
                 "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 2, "Ice": 1, "Dragon": 1,
                 "Dark": 0.5, "Fairy": 2},
    "flying": {"Normal": 1, "Fighting": 0.5, "Flying": 1, "Poison": 1, "Ground": 0, "Rock": 2, "Bug": 0.5, "Ghost": 1,
               "Steel": 1, "Fire": 1, "Water": 1, "Grass": 0.5, "Electric": 2, "Psychic": 1, "Ice": 2, "Dragon": 1,
               "Dark": 1, "Fairy": 1},
    "poison": {"Normal": 1, "Fighting": 0.5, "Flying": 1, "Poison": 0.5, "Ground": 2, "Rock": 1, "Bug": 0.5, "Ghost": 1,
               "Steel": 1, "Fire": 1, "Water": 1, "Grass": 0.5, "Electric": 1, "Psychic": 2, "Ice": 1, "Dragon": 1,
               "Dark": 1, "Fairy": 0.5},
    "ground": {"Normal": 1, "Fighting": 1, "Flying": 1, "Poison": 0.5, "Ground": 1, "Rock": 0.5, "Bug": 1, "Ghost": 1,
               "Steel": 1, "Fire": 1, "Water": 2, "Grass": 2, "Electric": 0, "Psychic": 1, "Ice": 2, "Dragon": 1,
               "Dark": 1, "Fairy": 1},
    "rock": {"Normal": 0.5, "Fighting": 2, "Flying": 0.5, "Poison": 0.5, "Ground": 2, "Rock": 1, "Bug": 1, "Ghost": 1,
             "Steel": 2, "Fire": 0.5, "Water": 2, "Grass": 0.5, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 1,
             "Dark": 1, "Fairy": 1},
    "bug": {"Normal": 1, "Fighting": 0.5, "Flying": 2, "Poison": 1, "Ground": 0.5, "Rock": 2, "Bug": 1, "Ghost": 1,
            "Steel": 1, "Fire": 2, "Water": 1, "Grass": 0.5, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 1,
            "Dark": 1, "Fairy": 1},
    "ghost": {"Normal": 0, "Fighting": 0, "Flying": 1, "Poison": 0.5, "Ground": 1, "Rock": 1, "Bug": 0.5, "Ghost": 2,
              "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 1,
              "Dark": 2, "Fairy": 1},
    "steel": {"Normal": 0.5, "Fighting": 2, "Flying": 0.5, "Poison": 0, "Ground": 2, "Rock": 0.5, "Bug": 0.5,
              "Ghost": 1, "Steel": 0.5, "Fire": 2, "Water": 1, "Grass": 0.5, "Electric": 1, "Psychic": 0.5, "Ice": 0.5,
              "Dragon": 0.5, "Dark": 1, "Fairy": 0.5},
    "fire": {"Normal": 1, "Fighting": 1, "Flying": 1, "Poison": 1, "Ground": 2, "Rock": 2, "Bug": 0.5, "Ghost": 1,
             "Steel": 0.5, "Fire": 0.5, "Water": 2, "Grass": 0.5, "Electric": 1, "Psychic": 1, "Ice": 0.5, "Dragon": 1,
             "Dark": 1, "Fairy": 0.5},
    "water": {"Normal": 1, "Fighting": 1, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 1, "Ghost": 1,
              "Steel": 0.5, "Fire": 0.5, "Water": 0.5, "Grass": 2, "Electric": 2, "Psychic": 1, "Ice": 0.5, "Dragon": 1,
              "Dark": 1, "Fairy": 1},
    "grass": {"Normal": 1, "Fighting": 1, "Flying": 2, "Poison": 2, "Ground": 0.5, "Rock": 1, "Bug": 2, "Ghost": 1,
              "Steel": 1, "Fire": 2, "Water": 0.5, "Grass": 0.5, "Electric": 0.5, "Psychic": 1, "Ice": 2, "Dragon": 1,
              "Dark": 1, "Fairy": 1},
    "electric": {"Normal": 1, "Fighting": 1, "Flying": 0.5, "Poison": 1, "Ground": 2, "Rock": 1, "Bug": 1, "Ghost": 1,
                 "Steel": 0.5, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 0.5, "Psychic": 1, "Ice": 1, "Dragon": 1,
                 "Dark": 1, "Fairy": 1},
    "psychic": {"Normal": 1, "Fighting": 0.5, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 2, "Ghost": 2,
                "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 0.5, "Ice": 1, "Dragon": 1,
                "Dark": 2, "Fairy": 1},
    "ice": {"Normal": 1, "Fighting": 2, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 2, "Bug": 1, "Ghost": 1,
            "Steel": 2, "Fire": 2, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 1, "Ice": 0.5, "Dragon": 1,
            "Dark": 1, "Fairy": 1},
    "dragon": {"Normal": 1, "Fighting": 1, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 1, "Ghost": 1,
               "Steel": 1, "Fire": 0.5, "Water": 0.5, "Grass": 0.5, "Electric": 0.5, "Psychic": 1, "Ice": 2,
               "Dragon": 2, "Dark": 1, "Fairy": 2},
    "dark": {"Normal": 1, "Fighting": 2, "Flying": 1, "Poison": 1, "Ground": 1, "Rock": 1, "Bug": 2, "Ghost": 0.5,
             "Steel": 1, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 0, "Ice": 1, "Dragon": 1,
             "Dark": 0.5, "Fairy": 2},
    "fairy": {"Normal": 1, "Fighting": 0.5, "Flying": 1, "Poison": 2, "Ground": 1, "Rock": 1, "Bug": 0.5, "Ghost": 1,
              "Steel": 2, "Fire": 1, "Water": 1, "Grass": 1, "Electric": 1, "Psychic": 1, "Ice": 1, "Dragon": 0,
              "Dark": 0.5, "Fairy": 1}
}


def calcStat(base_stat: int, IV: int, level: int, EV: int, HP: bool = False):
    if HP:
        result = (((2 * base_stat + IV + ((EV ** (1 / 2)) / 4)) * level) / 100) + level + 10
    else:
        result = (((2 * base_stat + IV + ((EV ** (1 / 2)) / 4)) * level) / 100) + 5
    return result


MAX_POKEMON_LEVEL = 100


def calcExp(n):
    result = n ** 3
    return int(result)


def xp_progress(level: int, experience: int) -> dict[str, int | float | bool]:
    """Return cumulative XP progress for the Pokémon's current level."""
    level = max(1, min(MAX_POKEMON_LEVEL, int(level)))
    current_xp = max(0, int(experience))
    current_floor = calcExp(level)

    if level >= MAX_POKEMON_LEVEL:
        cap = calcExp(MAX_POKEMON_LEVEL)
        return {
            "current": min(current_xp, cap),
            "level_floor": cap,
            "next_level_total": cap,
            "into_level": 0,
            "level_span": 0,
            "remaining": 0,
            "percent": 100.0,
            "max_level": True,
        }

    next_total = calcExp(level + 1)
    into_level = max(0, current_xp - current_floor)
    level_span = max(1, next_total - current_floor)
    remaining = max(0, next_total - current_xp)
    percent = max(0.0, min(100.0, (into_level / level_span) * 100))
    return {
        "current": current_xp,
        "level_floor": current_floor,
        "next_level_total": next_total,
        "into_level": into_level,
        "level_span": level_span,
        "remaining": remaining,
        "percent": percent,
        "max_level": False,
    }


def xp_progress_bar(percent: float, segments: int = 10) -> str:
    filled = max(0, min(segments, round((float(percent) / 100) * segments)))
    return "█" * filled + "░" * (segments - filled)


def battleCredits(level):
    winner_credits = level * 100
    loser_credits = 0 - winner_credits
    return winner_credits, loser_credits


def setGender(name):
    female_only = ["nidoran-f", 'nidorina', 'nidoqueen', 'chansey', 'kangaskhan', 'jynx']
    male_only = ["nidoran-m", 'nidorino', 'nidoking', 'hitmonlee', 'hitmonchan', 'taurus']
    genderless = ["magnemite", "magneton", "voltorb", "electrode", "staryu", "starmie"]
    if name in male_only:
        return "male"
    elif name in female_only:
        return "female"
    elif name in genderless:
        return "genderless"
    else:
        gender = random.choice(('male', 'female'))
        return gender


def gender_from_species(species_data: dict) -> str:
    rate = int(species_data.get("gender_rate", -1))
    if rate < 0:
        return "genderless"
    if rate == 0:
        return "male"
    if rate >= 8:
        return "female"
    return "female" if random.randint(1, 8) <= rate else "male"


def _friendship_value(value, default: int = 70) -> int:
    try:
        raw = default if value is None else int(value)
    except (TypeError, ValueError):
        raw = default
    return max(0, min(255, raw))


NATURES = (
    "hardy", "lonely", "brave", "adamant", "naughty",
    "bold", "docile", "relaxed", "impish", "lax",
    "timid", "hasty", "serious", "jolly", "naive",
    "modest", "mild", "quiet", "bashful", "rash",
    "calm", "gentle", "sassy", "careful", "quirky",
)


DEFAULT_RARITY_WEIGHTS = {
    "common": 60.0,
    "uncommon": 25.0,
    "rare": 10.0,
    "epic": 4.0,
    "legendary": 0.8,
    "mythical": 0.2,
}
RARITY_LABELS = {
    "common": "Common",
    "uncommon": "Uncommon",
    "rare": "Rare",
    "epic": "Epic",
    "legendary": "Legendary",
    "mythical": "Mythical",
}


def pokemon_rarity(species_data: dict) -> str:
    """Classify a species independently from its configured spawn odds.

    Legendary/Mythical flags are authoritative. Normal species are grouped by
    PokéAPI capture rate, where a lower capture rate means a rarer species.
    """
    if species_data.get("is_mythical"):
        return "mythical"
    if species_data.get("is_legendary"):
        return "legendary"

    try:
        capture_rate = int(species_data.get("capture_rate", 255))
    except (TypeError, ValueError):
        capture_rate = 255

    if capture_rate <= 45:
        return "epic"
    if capture_rate <= 90:
        return "rare"
    if capture_rate <= 180:
        return "uncommon"
    return "common"


def spawn_rarity_weights(poke_config: dict | None = None) -> dict[str, float]:
    source = poke_config if isinstance(poke_config, dict) else POKE_CONFIG
    configured = source.get("rarity_weights") or {}
    result: dict[str, float] = {}
    for key, default in DEFAULT_RARITY_WEIGHTS.items():
        try:
            value = float(configured.get(key, default))
        except (TypeError, ValueError):
            value = default
        result[key] = max(0.0, value)
    if sum(result.values()) <= 0:
        return dict(DEFAULT_RARITY_WEIGHTS)
    return result


def roll_spawn_rarity(poke_config: dict | None = None) -> str:
    weights = spawn_rarity_weights(poke_config)
    names = list(weights)
    return random.choices(names, weights=[weights[name] for name in names], k=1)[0]


def shiny_roll_denominator(poke_config: dict | None = None) -> int:
    source = poke_config if isinstance(poke_config, dict) else POKE_CONFIG
    return max(1, int(source.get("shiny_roll", 512)))


# Gym leaders are intentionally modeled as scalable themed teams rather than
# exact per-version historical rosters. That keeps every generation playable
# against a user's current Pokémon while preserving each leader's identity.
GYM_REGION_CHOICES = [
    app_commands.Choice(name="Kanto · Gen I", value="kanto"),
    app_commands.Choice(name="Johto · Gen II", value="johto"),
    app_commands.Choice(name="Hoenn · Gen III", value="hoenn"),
    app_commands.Choice(name="Sinnoh · Gen IV", value="sinnoh"),
    app_commands.Choice(name="Unova · Gen V", value="unova"),
    app_commands.Choice(name="Kalos · Gen VI", value="kalos"),
    app_commands.Choice(name="Alola · Gen VII Grand Trials", value="alola"),
    app_commands.Choice(name="Galar · Gen VIII", value="galar"),
    app_commands.Choice(name="Paldea · Gen IX", value="paldea"),
]

GYM_REGION_META = {
    "kanto": {"name": "Kanto", "generation": 1},
    "johto": {"name": "Johto", "generation": 2},
    "hoenn": {"name": "Hoenn", "generation": 3},
    "sinnoh": {"name": "Sinnoh", "generation": 4},
    "unova": {"name": "Unova", "generation": 5},
    "kalos": {"name": "Kalos", "generation": 6},
    "alola": {"name": "Alola", "generation": 7},
    "galar": {"name": "Galar", "generation": 8},
    "paldea": {"name": "Paldea", "generation": 9},
}

GYM_LEADERS = {
    "kanto": (
        {"key": "brock", "name": "Brock", "type": "Rock", "badge": "Boulder Badge", "order": 1, "team": ("geodude", "onix")},
        {"key": "misty", "name": "Misty", "type": "Water", "badge": "Cascade Badge", "order": 2, "team": ("staryu", "starmie")},
        {"key": "lt-surge", "name": "Lt. Surge", "type": "Electric", "badge": "Thunder Badge", "order": 3, "team": ("voltorb", "pikachu", "raichu")},
        {"key": "erika", "name": "Erika", "type": "Grass", "badge": "Rainbow Badge", "order": 4, "team": ("victreebel", "tangela", "vileplume")},
        {"key": "koga", "name": "Koga", "type": "Poison", "badge": "Soul Badge", "order": 5, "team": ("koffing", "muk", "weezing")},
        {"key": "sabrina", "name": "Sabrina", "type": "Psychic", "badge": "Marsh Badge", "order": 6, "team": ("mr-mime", "kadabra", "alakazam")},
        {"key": "blaine", "name": "Blaine", "type": "Fire", "badge": "Volcano Badge", "order": 7, "team": ("ponyta", "rapidash", "arcanine")},
        {"key": "giovanni", "name": "Giovanni", "type": "Ground", "badge": "Earth Badge", "order": 8, "team": ("rhyhorn", "dugtrio", "nidoking", "rhydon")},
    ),
    "johto": (
        {"key": "falkner", "name": "Falkner", "type": "Flying", "badge": "Zephyr Badge", "order": 1, "team": ("pidgey", "pidgeotto")},
        {"key": "bugsy", "name": "Bugsy", "type": "Bug", "badge": "Hive Badge", "order": 2, "team": ("metapod", "kakuna", "scyther")},
        {"key": "whitney", "name": "Whitney", "type": "Normal", "badge": "Plain Badge", "order": 3, "team": ("clefairy", "miltank")},
        {"key": "morty", "name": "Morty", "type": "Ghost", "badge": "Fog Badge", "order": 4, "team": ("gastly", "haunter", "gengar")},
        {"key": "chuck", "name": "Chuck", "type": "Fighting", "badge": "Storm Badge", "order": 5, "team": ("primeape", "poliwrath")},
        {"key": "jasmine", "name": "Jasmine", "type": "Steel", "badge": "Mineral Badge", "order": 6, "team": ("magnemite", "steelix")},
        {"key": "pryce", "name": "Pryce", "type": "Ice", "badge": "Glacier Badge", "order": 7, "team": ("seel", "dewgong", "piloswine")},
        {"key": "clair", "name": "Clair", "type": "Dragon", "badge": "Rising Badge", "order": 8, "team": ("dragonair", "gyarados", "kingdra")},
    ),
    "hoenn": (
        {"key": "roxanne", "name": "Roxanne", "type": "Rock", "badge": "Stone Badge", "order": 1, "team": ("geodude", "nosepass")},
        {"key": "brawly", "name": "Brawly", "type": "Fighting", "badge": "Knuckle Badge", "order": 2, "team": ("machop", "meditite", "makuhita")},
        {"key": "wattson", "name": "Wattson", "type": "Electric", "badge": "Dynamo Badge", "order": 3, "team": ("voltorb", "electrike", "magneton", "manectric")},
        {"key": "flannery", "name": "Flannery", "type": "Fire", "badge": "Heat Badge", "order": 4, "team": ("numel", "slugma", "camerupt", "torkoal")},
        {"key": "norman", "name": "Norman", "type": "Normal", "badge": "Balance Badge", "order": 5, "team": ("spinda", "vigoroth", "slaking")},
        {"key": "winona", "name": "Winona", "type": "Flying", "badge": "Feather Badge", "order": 6, "team": ("swellow", "pelipper", "skarmory", "altaria")},
        {"key": "tate-liza", "name": "Tate & Liza", "type": "Psychic", "badge": "Mind Badge", "order": 7, "team": ("claydol", "xatu", "solrock", "lunatone")},
        {"key": "wallace", "name": "Wallace", "type": "Water", "badge": "Rain Badge", "order": 8, "team": ("luvdisc", "whiscash", "sealeo", "milotic")},
    ),
    "sinnoh": (
        {"key": "roark", "name": "Roark", "type": "Rock", "badge": "Coal Badge", "order": 1, "team": ("geodude", "onix", "cranidos")},
        {"key": "gardenia", "name": "Gardenia", "type": "Grass", "badge": "Forest Badge", "order": 2, "team": ("cherubi", "turtwig", "roserade")},
        {"key": "maylene", "name": "Maylene", "type": "Fighting", "badge": "Cobble Badge", "order": 3, "team": ("meditite", "machoke", "lucario")},
        {"key": "crasher-wake", "name": "Crasher Wake", "type": "Water", "badge": "Fen Badge", "order": 4, "team": ("gyarados", "quagsire", "floatzel")},
        {"key": "fantina", "name": "Fantina", "type": "Ghost", "badge": "Relic Badge", "order": 5, "team": ("drifblim", "gengar", "mismagius")},
        {"key": "byron", "name": "Byron", "type": "Steel", "badge": "Mine Badge", "order": 6, "team": ("magneton", "steelix", "bastiodon")},
        {"key": "candice", "name": "Candice", "type": "Ice", "badge": "Icicle Badge", "order": 7, "team": ("snover", "sneasel", "abomasnow", "froslass")},
        {"key": "volkner", "name": "Volkner", "type": "Electric", "badge": "Beacon Badge", "order": 8, "team": ("jolteon", "raichu", "luxray", "electivire")},
    ),
    "unova": (
        {"key": "cilan", "name": "Cilan", "type": "Grass", "badge": "Trio Badge", "order": 1, "team": ("lillipup", "pansage")},
        {"key": "chili", "name": "Chili", "type": "Fire", "badge": "Trio Badge", "order": 1, "team": ("lillipup", "pansear")},
        {"key": "cress", "name": "Cress", "type": "Water", "badge": "Trio Badge", "order": 1, "team": ("lillipup", "panpour")},
        {"key": "lenora", "name": "Lenora", "type": "Normal", "badge": "Basic Badge", "order": 2, "team": ("herdier", "watchog")},
        {"key": "burgh", "name": "Burgh", "type": "Bug", "badge": "Insect Badge", "order": 3, "team": ("whirlipede", "dwebble", "leavanny")},
        {"key": "elesa", "name": "Elesa", "type": "Electric", "badge": "Bolt Badge", "order": 4, "team": ("emolga", "zebstrika")},
        {"key": "clay", "name": "Clay", "type": "Ground", "badge": "Quake Badge", "order": 5, "team": ("krokorok", "palpitoad", "excadrill")},
        {"key": "skyla", "name": "Skyla", "type": "Flying", "badge": "Jet Badge", "order": 6, "team": ("swoobat", "unfezant", "swanna")},
        {"key": "brycen", "name": "Brycen", "type": "Ice", "badge": "Freeze Badge", "order": 7, "team": ("vanillish", "cryogonal", "beartic")},
        {"key": "drayden", "name": "Drayden", "type": "Dragon", "badge": "Legend Badge", "order": 8, "team": ("fraxure", "druddigon", "haxorus")},
        {"key": "iris", "name": "Iris", "type": "Dragon", "badge": "Legend Badge", "order": 8, "team": ("fraxure", "druddigon", "haxorus")},
        {"key": "cheren", "name": "Cheren", "type": "Normal", "badge": "Basic Badge", "order": 1, "team": ("patrat", "lillipup")},
        {"key": "roxie", "name": "Roxie", "type": "Poison", "badge": "Toxic Badge", "order": 2, "team": ("koffing", "whirlipede")},
        {"key": "marlon", "name": "Marlon", "type": "Water", "badge": "Wave Badge", "order": 8, "team": ("carracosta", "wailord", "jellicent")},
    ),
    "kalos": (
        {"key": "viola", "name": "Viola", "type": "Bug", "badge": "Bug Badge", "order": 1, "team": ("surskit", "vivillon")},
        {"key": "grant", "name": "Grant", "type": "Rock", "badge": "Cliff Badge", "order": 2, "team": ("amaura", "tyrunt")},
        {"key": "korrina", "name": "Korrina", "type": "Fighting", "badge": "Rumble Badge", "order": 3, "team": ("mienfoo", "machoke", "hawlucha")},
        {"key": "ramos", "name": "Ramos", "type": "Grass", "badge": "Plant Badge", "order": 4, "team": ("jumpluff", "weepinbell", "gogoat")},
        {"key": "clemont", "name": "Clemont", "type": "Electric", "badge": "Voltage Badge", "order": 5, "team": ("emolga", "magneton", "heliolisk")},
        {"key": "valerie", "name": "Valerie", "type": "Fairy", "badge": "Fairy Badge", "order": 6, "team": ("mawile", "mr-mime", "sylveon")},
        {"key": "olympia", "name": "Olympia", "type": "Psychic", "badge": "Psychic Badge", "order": 7, "team": ("sigilyph", "slowking", "meowstic-male")},
        {"key": "wulfric", "name": "Wulfric", "type": "Ice", "badge": "Iceberg Badge", "order": 8, "team": ("abomasnow", "cryogonal", "avalugg")},
    ),
    "alola": (
        {"key": "hala", "name": "Hala", "type": "Fighting", "badge": "Melemele Grand Trial", "order": 2, "team": ("machop", "makuhita", "crabrawler")},
        {"key": "olivia", "name": "Olivia", "type": "Rock", "badge": "Akala Grand Trial", "order": 4, "team": ("nosepass", "boldore", "lycanroc-midday")},
        {"key": "nanu", "name": "Nanu", "type": "Dark", "badge": "Ula'ula Grand Trial", "order": 6, "team": ("sableye", "krokorok", "krookodile")},
        {"key": "hapu", "name": "Hapu", "type": "Ground", "badge": "Poni Grand Trial", "order": 8, "team": ("golurk", "gastrodon", "mudsdale")},
    ),
    "galar": (
        {"key": "milo", "name": "Milo", "type": "Grass", "badge": "Grass Badge", "order": 1, "team": ("gossifleur", "eldegoss")},
        {"key": "nessa", "name": "Nessa", "type": "Water", "badge": "Water Badge", "order": 2, "team": ("goldeen", "arrokuda", "drednaw")},
        {"key": "kabu", "name": "Kabu", "type": "Fire", "badge": "Fire Badge", "order": 3, "team": ("ninetales", "arcanine", "centiskorch")},
        {"key": "bea", "name": "Bea", "type": "Fighting", "badge": "Fighting Badge", "order": 4, "team": ("hitmontop", "pangoro", "sirfetchd", "machamp")},
        {"key": "allister", "name": "Allister", "type": "Ghost", "badge": "Ghost Badge", "order": 4, "team": ("yamask", "mimikyu", "cursola", "gengar")},
        {"key": "opal", "name": "Opal", "type": "Fairy", "badge": "Fairy Badge", "order": 5, "team": ("mawile", "togekiss", "sylveon", "alcremie")},
        {"key": "gordie", "name": "Gordie", "type": "Rock", "badge": "Rock Badge", "order": 6, "team": ("barbaracle", "shuckle", "stonjourner", "coalossal")},
        {"key": "melony", "name": "Melony", "type": "Ice", "badge": "Ice Badge", "order": 6, "team": ("frosmoth", "beartic", "eiscue", "lapras")},
        {"key": "piers", "name": "Piers", "type": "Dark", "badge": "Dark Badge", "order": 7, "team": ("scrafty", "malamar", "skuntank", "obstagoon")},
        {"key": "raihan", "name": "Raihan", "type": "Dragon", "badge": "Dragon Badge", "order": 8, "team": ("flygon", "goodra", "turtonator", "duraludon")},
    ),
    "paldea": (
        {"key": "katy", "name": "Katy", "type": "Bug", "badge": "Bug Badge", "order": 1, "team": ("nymble", "tarountula", "lokix")},
        {"key": "brassius", "name": "Brassius", "type": "Grass", "badge": "Grass Badge", "order": 2, "team": ("petilil", "smoliv", "arboliva")},
        {"key": "iono", "name": "Iono", "type": "Electric", "badge": "Electric Badge", "order": 3, "team": ("wattrel", "bellibolt", "kilowattrel")},
        {"key": "kofu", "name": "Kofu", "type": "Water", "badge": "Water Badge", "order": 4, "team": ("veluza", "wugtrio", "dondozo")},
        {"key": "larry", "name": "Larry", "type": "Normal", "badge": "Normal Badge", "order": 5, "team": ("komala", "dudunsparce", "staraptor")},
        {"key": "ryme", "name": "Ryme", "type": "Ghost", "badge": "Ghost Badge", "order": 6, "team": ("banette", "mimikyu", "houndstone", "gengar")},
        {"key": "tulip", "name": "Tulip", "type": "Psychic", "badge": "Psychic Badge", "order": 7, "team": ("farigiraf", "gardevoir", "espathra", "gothitelle")},
        {"key": "grusha", "name": "Grusha", "type": "Ice", "badge": "Ice Badge", "order": 8, "team": ("frosmoth", "beartic", "cetitan", "glaceon")},
    ),
}

GYM_LEADER_INDEX = {
    region: {leader["key"]: leader for leader in leaders}
    for region, leaders in GYM_LEADERS.items()
}


def setNature() -> str:
    # Natures are static game data; an API request for every catch is wasteful.
    return random.choice(NATURES)


def _walk_evolution_chain(node):
    yield node
    for child in node.get("evolves_to", []):
        yield from _walk_evolution_chain(child)


def _minimum_level_for_species(chain: dict, species_name: str) -> int:
    if chain.get("species", {}).get("name") == species_name:
        return 5
    for node in _walk_evolution_chain(chain):
        for child in node.get("evolves_to", []):
            if child.get("species", {}).get("name") != species_name:
                continue
            levels = [
                detail.get("min_level")
                for detail in child.get("evolution_details", [])
                if detail.get("min_level") is not None
            ]
            return max(5, min(levels)) if levels else 5
    return 5


async def select_damaging_moves(api: PokeAPIClient, pokemon_data: dict, limit: int = 4) -> list[dict]:
    candidates = [
        entry["move"]
        for entry in pokemon_data.get("moves", [])
        if any(
            detail.get("move_learn_method", {}).get("name") == "level-up"
            for detail in entry.get("version_group_details", [])
        )
    ]
    random.shuffle(candidates)

    selected: list[dict] = []
    # Fetch in small concurrent batches instead of requesting every move the
    # species has ever learned. Cached move metadata makes later catches cheap.
    for offset in range(0, len(candidates), 8):
        batch = candidates[offset:offset + 8]
        details = await asyncio.gather(
            *(api.get_json(move["url"]) for move in batch),
            return_exceptions=True,
        )
        for move, move_data in zip(batch, details):
            if isinstance(move_data, Exception):
                continue
            if move_data.get("damage_class", {}).get("name") != "status":
                selected.append(move)
                if len(selected) >= limit:
                    return selected

    if selected:
        return selected

    struggle = await api.move(165)
    return [{"name": struggle["name"], "url": f"{PokeAPIClient.BASE_URL}/move/165/"}]


async def build_pokemon_record(api: PokeAPIClient, uid: int, pokemon_data: dict, owner_id: int | str) -> dict:
    species_data = await api.get_json(pokemon_data["species"]["url"])
    evolution_chain = await api.get_json(species_data["evolution_chain"]["url"])
    moves = await select_damaging_moves(api, pokemon_data)

    level = _minimum_level_for_species(evolution_chain.get("chain", {}), pokemon_data["name"])
    stats = pokemon_data["stats"]

    hp_iv = randomGenerator(0, 16)
    attack_iv = randomGenerator(0, 16)
    defense_iv = randomGenerator(0, 16)
    special_attack_iv = randomGenerator(0, 16)
    special_defense_iv = randomGenerator(0, 16)
    speed_iv = randomGenerator(0, 16)

    base_hp = stats[0]["base_stat"]
    base_attack = stats[1]["base_stat"]
    base_defense = stats[2]["base_stat"]
    base_special_attack = stats[3]["base_stat"]
    base_special_defense = stats[4]["base_stat"]
    base_speed = stats[5]["base_stat"]

    return {
        "index": int(pokemon_data.get("dex_id", pokemon_data["id"])),
        "uid": uid,
        "type": [entry["type"]["name"] for entry in pokemon_data["types"]],
        "moves": moves,
        "lvl": level,
        "exp": calcExp(level),
        "color": species_data.get("color", {}).get("name", "black").upper(),
        "height": pokemon_data["height"],
        "weight": pokemon_data["weight"],
        "nature": setNature(),
        "gender": gender_from_species(species_data),
        "friendship": _friendship_value(species_data.get("base_happiness")),
        "base_exp": pokemon_data.get("base_experience") or 0,
        "base_hp": base_hp,
        "base_attack": base_attack,
        "base_defense": base_defense,
        "base_special_attack": base_special_attack,
        "base_special_defense": base_special_defense,
        "base_speed": base_speed,
        "hp_iv": hp_iv,
        "attack_iv": attack_iv,
        "defense_iv": defense_iv,
        "special_attack_iv": special_attack_iv,
        "special_defense_iv": special_defense_iv,
        "speed_iv": speed_iv,
        "hp": int(calcStat(base_hp, hp_iv, level, base_hp, True)),
        "attack": int(calcStat(base_attack, attack_iv, level, base_attack, False)),
        "defense": int(calcStat(base_defense, defense_iv, level, base_defense, False)),
        "sp_attack": int(calcStat(base_special_attack, special_attack_iv, level, base_special_attack, False)),
        "sp_defense": int(calcStat(base_special_defense, special_defense_iv, level, base_special_defense, False)),
        "speed": int(calcStat(base_speed, speed_iv, level, base_speed, False)),
        "item": None,
        "selected": False,
        "shiny": bool(pokemon_data.get("shiny", False)),
        "caughtBy": (datetime.now().strftime("%a, %b %d, %Y - %I:%M %p"), str(owner_id)),
        "form": pokemon_data.get("form"),
    }


def _render_png(raw: bytes, *, silhouette: bool = False) -> bytes:
    with Image.open(BytesIO(raw)) as source:
        image = source.convert("RGBA")
        if silhouette:
            alpha = image.getchannel("A")
            rendered = Image.new("RGBA", image.size, (0, 0, 0, 0))
            rendered.paste((0, 0, 0, 255), mask=alpha)
            image = rendered
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

def ivPercentage(pokeInfo):
    x = (pokeInfo['hp_iv'] + pokeInfo['attack_iv'] + pokeInfo['defense_iv'] + pokeInfo['special_attack_iv'] +
         pokeInfo['special_defense_iv'] + pokeInfo['speed_iv']) / 6
    if not x:
        return 0
    elif x < 0:
        return 0
    else:
        total = (x / 15) * 100
        return total


def critGen(baseSpeed):
    crit = baseSpeed / 2
    numRandom = randomGenerator(0, 255)
    if crit > numRandom:
        return True
    else:
        return False


def calcDMG(level, power, A, D, random, baseSpeed, trgts=1, weather=1, badge=1, crit=1, STAB=1, Type=1,
            Burn=1, other=1):
    if power is None: power = 0
    if critGen(baseSpeed):
        crit = 2
    Modifier = trgts * weather * badge * crit * random * STAB * Type * Burn * other
    damage = (((2 * level / 5 + 2) * power * (A / D) / 50) + 2) * Modifier
    return int(damage)


def gainedExp(b, L, lucky, a=1.5, e=1, f=1, p=1, s=1, t=1, v=1, battle=False):
    if battle:
        divider = 1
    else:
        divider = 10
    if lucky:
        result = int((a * t * b * e * L * p * f * v) / (7 * s) / divider) * 2
    else:
        result = int((a * t * b * e * L * p * f * v) / (7 * s) / divider)
    return result


def randomGenerator(num1: int, num2: int) -> int:
    """Return a uniformly random integer in the legacy half-open range [num1, num2).

    The old implementation sampled seven values first, which crashed for ranges
    smaller than seven elements (for example randomGenerator(0, 3)).
    """
    if num2 <= num1:
        raise ValueError("num2 must be greater than num1")
    return random.randrange(num1, num2)


class PokeBattle:
    _instances = set()

    def __init__(self, pokeMon, users, battleID):
        self.battleID = battleID
        self._instances.add(weakref.ref(self))

    @classmethod
    def getinstances(cls):
        dead = set()
        for ref in cls._instances:
            obj = ref()
            if obj is not None:
                yield obj
            else:
                dead.add(ref)
        cls._instances -= dead


STATUS_LABELS = {
    "burn": "🔥 Burned",
    "poison": "☠️ Poisoned",
    "paralysis": "⚡ Paralyzed",
    "sleep": "💤 Asleep",
    "freeze": "🧊 Frozen",
}


def _normalize_status(value: object) -> str | None:
    status = str(value or "").strip().lower()
    if status in {"bad-poison", "toxic"}:
        status = "poison"
    return status if status in STATUS_LABELS else None


def _status_label(value: object) -> str:
    status = _normalize_status(value)
    return STATUS_LABELS.get(status, "✅ Healthy")


class Battle:
    """Persistent current HP/status plus async move resolution."""

    def __init__(self, api: PokeAPIClient, health: int, battle_health: int | None, status: str | None = None, status_turns: int = 0):
        self.api = api
        self._health = max(1, int(health or 1))
        current = self._health if battle_health is None else int(battle_health)
        self._battle_health = min(self._health, max(0, current))
        self.status = _normalize_status(status)
        self.status_turns = max(0, int(status_turns or 0))
        self.held_item_consumed = False

    @property
    def health(self):
        return self._battle_health

    @health.setter
    def health(self, new_hp):
        self._battle_health = min(self._health, max(0, int(new_hp)))

    @property
    def max_health(self):
        return self._health

    async def before_turn(self) -> tuple[bool, str]:
        if self.health <= 0:
            return False, "It has fainted."
        if self.status == "sleep":
            if self.status_turns <= 0:
                self.status_turns = random.randint(1, 3)
            self.status_turns -= 1
            if self.status_turns <= 0:
                self.status = None
                return True, "💤 woke up!"
            return False, "💤 is fast asleep."
        if self.status == "freeze":
            if random.random() < 0.20:
                self.status = None
                return True, "🧊 thawed out!"
            return False, "🧊 is frozen solid."
        if self.status == "paralysis" and random.random() < 0.25:
            return False, "⚡ is fully paralyzed!"
        return True, ""

    def after_turn(self) -> str:
        if self.health <= 0:
            return ""
        if self.status == "burn":
            damage = max(1, self.max_health // 16)
            self.health -= damage
            return f"🔥 was hurt by its burn for **{damage}** HP."
        if self.status == "poison":
            damage = max(1, self.max_health // 8)
            self.health -= damage
            return f"☠️ was hurt by poison for **{damage}** HP."
        return ""

    def effective_speed(self, raw_speed: int) -> int:
        speed = max(1, int(raw_speed or 1))
        return max(1, speed // 2) if self.status == "paralysis" else speed

    async def attack(self, opponent, aPoke, dPoke, moveNum):
        move = json.loads(aPoke['moves'][moveNum - 1])
        moveData = await self.api.get_json(move['url'])
        moveType = moveData['type']['name']
        STAB = 1.5 if moveType in aPoke['type'] else 1
        Type = 1
        damage_class = moveData.get('damage_class', {}).get('name')
        damage = 0
        if damage_class != 'status':
            for defending_type in dPoke['type']:
                chart = effectiveness.get(defending_type.lower(), effectiveness.get(defending_type, {}))
                Type *= chart.get(moveType.capitalize(), 1)
            power = moveData.get('power') or 0
            if damage_class == 'special':
                attack_stat = aPoke['sp_attack']
                defense_stat = dPoke['sp_defense']
                burn = 1
            else:
                attack_stat = aPoke['attack']
                defense_stat = dPoke['defense']
                burn = 0.5 if self.status == "burn" else 1
            damage = calcDMG(aPoke['lvl'], power, attack_stat, max(1, defense_stat),
                             random.uniform(0.85, 1.0), aPoke['base_speed'], STAB=STAB, Type=Type, Burn=burn)
            log.debug("Move=%s STAB=x%s effectiveness=x%s", moveData['name'], STAB, Type)
            opponent.health -= damage

        applied_status = None
        meta = moveData.get("meta") or {}
        ailment = _normalize_status((meta.get("ailment") or {}).get("name"))
        if opponent.health > 0 and opponent.status is None and ailment:
            defender_types = {str(t).lower() for t in dPoke.get('type', [])}
            immune = (
                (ailment == 'burn' and 'fire' in defender_types)
                or (ailment == 'poison' and bool(defender_types & {'poison', 'steel'}))
                or (ailment == 'paralysis' and 'electric' in defender_types)
                or (ailment == 'freeze' and 'ice' in defender_types)
            )
            if immune:
                ailment = None

        if opponent.health > 0 and opponent.status is None and ailment:
            chance = meta.get("ailment_chance")
            if not isinstance(chance, (int, float)) or chance <= 0:
                chance = moveData.get("effect_chance")
            if not isinstance(chance, (int, float)) or chance <= 0:
                chance = 100 if damage_class == "status" else 0
            if random.uniform(0, 100) <= float(chance):
                opponent.status = ailment
                opponent.status_turns = random.randint(1, 3) if ailment == "sleep" else 0
                applied_status = ailment

        return {
            "move": moveData['name'],
            "damage": damage,
            "effectiveness": Type,
            "status": applied_status,
        }



# PokéAPI's evolution item category is our preferred source, but the bot keeps a
# canonical fallback catalog too.  This protects the shop from category-ID
# changes, incomplete API price data, and evolution items that live in other
# categories because they are held/trade items instead of direct-use items.
SHOP_DIRECT_EVOLUTION_ITEMS = (
    # Traditional stones
    "sun-stone",
    "moon-stone",
    "fire-stone",
    "thunder-stone",
    "water-stone",
    "leaf-stone",
    "shiny-stone",
    "dusk-stone",
    "dawn-stone",
    "ice-stone",
    # Gen VIII+
    "tart-apple",
    "sweet-apple",
    "cracked-pot",
    "chipped-pot",
    "galarica-cuff",
    "galarica-wreath",
    "black-augurite",
    "peat-block",
    "auspicious-armor",
    "malicious-armor",
    "syrupy-apple",
    "unremarkable-teacup",
    "masterpiece-teacup",
    "metal-alloy",
    # Legends: Arceus trade substitute (supported if PokéAPI exposes the trigger)
    "linking-cord",
)

SHOP_HELD_EVOLUTION_ITEMS = (
    "kings-rock",
    "metal-coat",
    "dragon-scale",
    "up-grade",
    "deep-sea-tooth",
    "deep-sea-scale",
    "protector",
    "electirizer",
    "magmarizer",
    "dubious-disc",
    "reaper-cloth",
    "prism-scale",
    "sachet",
    "whipped-dream",
    "razor-claw",
    "razor-fang",
    "oval-stone",
)

SHOP_MEDICINE_ITEMS = (
    "potion", "super-potion", "hyper-potion", "max-potion", "full-restore",
    "antidote", "burn-heal", "ice-heal", "awakening", "paralyze-heal", "full-heal",
    "revive", "max-revive",
)

SHOP_BERRY_ITEMS = (
    "oran-berry", "sitrus-berry",
    "pecha-berry", "rawst-berry", "cheri-berry", "chesto-berry", "aspear-berry", "lum-berry",
)

HEALING_ITEM_EFFECTS = {
    "potion": {"heal": 20},
    "super-potion": {"heal": 60},
    "hyper-potion": {"heal": 120},
    "max-potion": {"full_heal": True},
    "full-restore": {"full_heal": True, "cure": "any"},
    "antidote": {"cure": "poison"},
    "burn-heal": {"cure": "burn"},
    "ice-heal": {"cure": "freeze"},
    "awakening": {"cure": "sleep"},
    "paralyze-heal": {"cure": "paralysis"},
    "full-heal": {"cure": "any"},
    "revive": {"revive_fraction": 0.5},
    "max-revive": {"revive_fraction": 1.0},
    "oran-berry": {"heal": 10},
    "sitrus-berry": {"heal_fraction": 0.25},
    "pecha-berry": {"cure": "poison"},
    "rawst-berry": {"cure": "burn"},
    "cheri-berry": {"cure": "paralysis"},
    "chesto-berry": {"cure": "sleep"},
    "aspear-berry": {"cure": "freeze"},
    "lum-berry": {"cure": "any"},
}

# Bot-shop fallback prices.  PokéAPI's newest positive Poké Dollar purchase
# price always wins.  These values are only used when PokéAPI has no purchasable
# price for an otherwise valid evolution item, which is common for version-
# exclusive/reward items.  Keeping them here means the Discord game still has a
# usable economy instead of silently hiding the item.
SHOP_FALLBACK_PRICES = {
    # Common stones
    "sun-stone": 3000,
    "moon-stone": 3000,
    "fire-stone": 3000,
    "thunder-stone": 3000,
    "water-stone": 3000,
    "leaf-stone": 3000,
    "shiny-stone": 3000,
    "dusk-stone": 3000,
    "dawn-stone": 3000,
    "ice-stone": 3000,
    # Apples / pots / newer direct-use evolution items
    "tart-apple": 5000,
    "sweet-apple": 5000,
    "cracked-pot": 5000,
    "chipped-pot": 10000,
    "galarica-cuff": 5000,
    "galarica-wreath": 8000,
    "black-augurite": 8000,
    "peat-block": 8000,
    "auspicious-armor": 10000,
    "malicious-armor": 10000,
    "syrupy-apple": 8000,
    "unremarkable-teacup": 8000,
    "masterpiece-teacup": 12000,
    "metal-alloy": 10000,
    "linking-cord": 10000,
    # Held/trade evolution items
    "kings-rock": 10000,
    "metal-coat": 10000,
    "dragon-scale": 10000,
    "up-grade": 10000,
    "deep-sea-tooth": 10000,
    "deep-sea-scale": 10000,
    "protector": 10000,
    "electirizer": 10000,
    "magmarizer": 10000,
    "dubious-disc": 10000,
    "reaper-cloth": 10000,
    "prism-scale": 10000,
    "sachet": 10000,
    "whipped-dream": 10000,
    "razor-claw": 10000,
    "razor-fang": 10000,
    "oval-stone": 5000,
    # Medicine / recovery
    "potion": 200,
    "super-potion": 700,
    "hyper-potion": 1500,
    "max-potion": 2500,
    "full-restore": 3000,
    "antidote": 200,
    "burn-heal": 300,
    "ice-heal": 100,
    "awakening": 200,
    "paralyze-heal": 300,
    "full-heal": 400,
    "revive": 2000,
    "max-revive": 4000,
    # Berries
    "oran-berry": 200,
    "sitrus-berry": 600,
    "pecha-berry": 200,
    "rawst-berry": 200,
    "cheri-berry": 200,
    "chesto-berry": 200,
    "aspear-berry": 200,
    "lum-berry": 1200,
}


def _item_purchase_price(item: dict) -> int:
    """Return the newest available positive Poké Dollar purchase price.

    Prices are version-group specific in the current PokéAPI schema.  We pick
    the newest version group that actually has a positive purchase price.  If
    PokéAPI has no purchasable price for the item, use the Discord game's
    fallback economy price instead of removing the item from the store.
    """
    prices = item.get("prices") or []
    candidates = []

    for position, entry in enumerate(prices):
        if not isinstance(entry, dict):
            continue

        price = entry.get("purchase_price")
        currency = (entry.get("currency") or {}).get("name")
        if not isinstance(price, int) or price <= 0:
            continue
        if currency not in (None, "poke-dollar"):
            continue

        group_url = (entry.get("version_group") or {}).get("url", "")
        try:
            group_id = int(group_url.rstrip("/").rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            group_id = -1

        candidates.append((group_id, position, price))

    if candidates:
        return max(candidates, key=lambda value: (value[0], value[1]))[2]

    # Backward compatibility with older PokéAPI payloads that exposed `cost`.
    legacy = item.get("cost")
    if isinstance(legacy, (int, float)) and legacy > 0:
        return int(legacy)

    return int(SHOP_FALLBACK_PRICES.get(str(item.get("name", "")), 0))


def _canonical_item_name(value: object) -> str:
    """Normalize an item name for slash options and inventory keys."""
    return str(value or "").strip().lower().replace(" ", "-")


def _normalize_inventory(raw: object) -> dict[str, dict]:
    """Return bag data keyed by canonical item name.

    Older Pokécord builds keyed the JSON object by numeric PokéAPI item ID.
    The current store uses stable item names instead so the game does not
    depend on PokéAPI IDs or live item lookups merely to display/use a bag.
    This helper transparently migrates legacy rows in memory.
    """
    if not raw:
        return {}
    try:
        source = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    normalized: dict[str, dict] = {}
    for old_key, value in source.items():
        if not isinstance(value, dict):
            continue
        name = _canonical_item_name(value.get("name") or old_key)
        if not name:
            continue
        item = dict(value)
        item["name"] = name
        try:
            total = max(0, int(item.get("total", 0)))
        except (TypeError, ValueError):
            total = 0
        item["total"] = total
        if name in normalized:
            normalized[name]["total"] = int(normalized[name].get("total", 0)) + total
            # Keep richer metadata when the migrated row has it.
            for key in ("id", "cost", "sprite"):
                if normalized[name].get(key) in (None, "", 0) and item.get(key) not in (None, "", 0):
                    normalized[name][key] = item.get(key)
        else:
            normalized[name] = item
    return normalized


def _store_fallback_rows() -> list[list]:
    """Canonical shop rows that exist even when PokéAPI is unavailable."""
    names = dict.fromkeys((*SHOP_DIRECT_EVOLUTION_ITEMS, *SHOP_HELD_EVOLUTION_ITEMS, *SHOP_MEDICINE_ITEMS, *SHOP_BERRY_ITEMS))
    rows = []
    for name in names:
        cost = int(SHOP_FALLBACK_PRICES.get(name, 0))
        if cost > 0:
            rows.append([name, cost])
    return sorted(rows, key=lambda row: row[0])


class PokeItem:

    def __init__(self, value):
        # self.name = value['name']
        self.id = value['id']
        self.name = value['name']
        self.cost = _item_purchase_price(value)
        self.sprite = value['sprites']['default']
        self.total = 1

    @property
    def _name(self):
        return self.name

    @_name.setter
    def _name(self, ItemName):
        self.name = ItemName


# Legacy PokeObj/User wrappers were removed. Pokémon records are now built
# asynchronously by build_pokemon_record(), avoiding blocking network calls in
# object constructors.


def _pretty_move_name(raw_move) -> str:
    try:
        data = json.loads(raw_move) if isinstance(raw_move, str) else raw_move
        name = data.get("name", "Move")
    except (TypeError, ValueError, json.JSONDecodeError):
        name = str(raw_move)
    return " ".join(part.capitalize() for part in str(name).split("-"))


def _normalize_pokemon_guess(value: str) -> str:
    """Normalize human-friendly Pokémon guesses without revealing the answer.

    This intentionally ignores spaces, punctuation, apostrophes, and hyphens so
    guesses such as ``Mr Mime``, ``Mr. Mime`` and ``mr-mime`` compare equally.
    Gender symbols are normalized to PokéAPI's nidoran-f / nidoran-m naming.
    """
    text = str(value or "").strip().casefold().replace("♀", "f").replace("♂", "m")
    return "".join(ch for ch in text if ch.isalnum())


class PokemonCatchModal(discord.ui.Modal):
    """Private guessing modal opened from a wild Pokémon spawn."""

    def __init__(self, cog: "PokeCord"):
        super().__init__(title="Catch the wild Pokémon", timeout=90)
        self.cog = cog
        self.pokemon_name = discord.ui.TextInput(
            label="Pokémon name",
            placeholder="Who’s that Pokémon?",
            min_length=1,
            max_length=60,
            required=True,
        )
        self.add_item(self.pokemon_name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog._catch_from_modal(interaction, str(self.pokemon_name.value))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception("Pokecord catch modal failed", exc_info=error)
        message = "Something went wrong while submitting that guess. Try again."
        if interaction.response.is_done():
            try:
                await interaction.followup.send(message, ephemeral=True)
            except discord.HTTPException:
                pass
        else:
            await interaction.response.send_message(message, ephemeral=True)


class PokemonCatchView(discord.ui.View):
    """Public spawn controls. Guesses themselves remain private."""

    def __init__(self, cog: "PokeCord"):
        # Expiration is managed by the cog so the message can be updated with
        # the escaped Pokémon's identity before the next spawn is scheduled.
        super().__init__(timeout=None)
        self.cog = cog
        self.message: discord.Message | None = None

    @discord.ui.button(
        label="Catch Pokémon",
        emoji="🎯",
        style=discord.ButtonStyle.success,
        custom_id="pokecord:catch",
    )
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is not None:
            await self.cog._activate_guild(interaction.guild)
        if not self.cog.appeared or self.cog.caught:
            await interaction.response.send_message("That Pokémon has already been caught.", ephemeral=True)
            return
        await interaction.response.send_modal(PokemonCatchModal(self.cog))

    def mark_caught(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            self.catch_button.label = "Caught!"
            self.catch_button.emoji = "✅"
        except AttributeError:
            pass
        self.stop()

    def mark_replaced(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            self.catch_button.label = "Spawn ended"
            self.catch_button.emoji = "⌛"
        except AttributeError:
            pass
        self.stop()

    def mark_expired(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            self.catch_button.label = "Escaped!"
            self.catch_button.emoji = "💨"
        except AttributeError:
            pass
        self.stop()


class ConfirmationView(discord.ui.View):
    """Require one or more specific users to accept before continuing."""

    def __init__(self, users, summary: str, *, timeout: float = 90):
        super().__init__(timeout=timeout)
        self.users = {user.id: user for user in users}
        self.accepted_ids: set[int] = set()
        self.summary = summary
        self.decision: bool | None = None
        self.declined_by: int | None = None
        self.message = None

    def _disable_all(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

    def _status_text(self) -> str:
        lines = [self.summary, ""]
        for user_id, user in self.users.items():
            state = "✅ Accepted" if user_id in self.accepted_ids else "⏳ Waiting"
            lines.append(f"{user.mention}: {state}")
        if self.declined_by is not None:
            user = self.users.get(self.declined_by)
            lines.append(f"\n❌ Declined by {user.mention if user else 'a participant'}.")
        return "\n".join(lines)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.users:
            await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.accepted_ids.add(interaction.user.id)
        if self.accepted_ids == set(self.users):
            self.decision = True
            self._disable_all()
            self.stop()
        await interaction.response.edit_message(content=self._status_text(), view=self)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.decision = False
        self.declined_by = interaction.user.id
        self._disable_all()
        self.stop()
        await interaction.response.edit_message(content=self._status_text(), view=self)

    async def on_timeout(self):
        self.decision = False
        self._disable_all()
        if self.message is not None:
            try:
                await self.message.edit(content=self._status_text() + "\n\n⌛ Confirmation timed out.", view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class BattleMoveButton(discord.ui.Button):
    def __init__(self, move_index: int, move_name: str):
        super().__init__(
            label=f"{move_index}. {move_name}"[:80],
            style=discord.ButtonStyle.primary,
            row=0 if move_index <= 2 else 1,
        )
        self.move_index = move_index

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, BattleMoveView):
            return
        view.selected_move = self.move_index
        view._disable_all()
        view.stop()
        await interaction.response.edit_message(view=view)


class BattleMoveView(discord.ui.View):
    def __init__(self, player: discord.Member, moves, *, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.player = player
        self.selected_move: int | None = None
        self.forfeited = False
        self.message = None
        for index, raw_move in enumerate(list(moves)[:4], start=1):
            self.add_item(BattleMoveButton(index, _pretty_move_name(raw_move)))

    def _disable_all(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player.id:
            await interaction.response.send_message(f"It's {self.player.display_name}'s turn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Forfeit", style=discord.ButtonStyle.danger, emoji="🏳️", row=2)
    async def forfeit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.forfeited = True
        self._disable_all()
        self.stop()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        self.forfeited = True
        self._disable_all()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class PokedexView(discord.ui.View):
    PAGE_SIZE = 20

    def __init__(
        self,
        owner: discord.abc.User,
        pokedex_data,
        *,
        max_dex: int,
        page: int = 0,
        timeout: float = 600,
    ):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.max_dex = max(1, int(max_dex))
        self.page = max(0, int(page))
        self.message: discord.Message | None = None
        self.obtained = self._normalize_pokedex(pokedex_data)
        self.page = min(self.page, self.max_page)
        self._refresh_controls()

    @staticmethod
    def _normalize_pokedex(pokedex_data) -> dict[int, str]:
        obtained: dict[int, str] = {}
        for entry in pokedex_data or []:
            try:
                if hasattr(entry, "get"):
                    dex_id = int(entry.get("dex_id") or entry.get("index") or entry.get("id") or entry.get("dex"))
                    name = str(entry.get("name") or "Unknown")
                else:
                    dex_id = int(entry[0])
                    name = str(entry[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if dex_id > 0:
                obtained[dex_id] = name
        return obtained

    @property
    def max_page(self) -> int:
        return max(0, (self.max_dex - 1) // self.PAGE_SIZE)

    def _refresh_controls(self) -> None:
        self.page = min(max(0, self.page), self.max_page)
        at_start = self.page <= 0
        at_end = self.page >= self.max_page
        self.first_page.disabled = at_start
        self.previous_page.disabled = at_start
        self.next_page.disabled = at_end
        self.last_page.disabled = at_end
        self.page_indicator.label = f"{self.page + 1}/{self.max_page + 1}"

    def build_embed(self) -> discord.Embed:
        caught_count = len([dex_id for dex_id in self.obtained if 1 <= dex_id <= self.max_dex])
        completion = (caught_count / self.max_dex) * 100 if self.max_dex else 0.0
        start_dex = self.page * self.PAGE_SIZE + 1
        end_dex = min(self.max_dex, start_dex + self.PAGE_SIZE - 1)

        lines = []
        for dex_id in range(start_dex, end_dex + 1):
            if dex_id in self.obtained:
                name = self.obtained[dex_id].replace("-", " ").title()
                lines.append(f"✅ **#{dex_id:04d}** · {name}")
            else:
                lines.append(f"⬜ **#{dex_id:04d}** · ???")

        embed = discord.Embed(
            title=f"{self.owner.display_name}'s Pokédex",
            description="\n".join(lines) or "No Pokédex entries on this page.",
            color=0xEEE8AA,
        )
        embed.set_footer(
            text=(
                f"Obtained {caught_count}/{self.max_dex} Pokémon · {completion:.1f}% complete · "
                f"Page {self.page + 1}/{self.max_page + 1}"
            )
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("This Pokédex belongs to another trainer.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.max_page
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class PokemonListSortSelect(discord.ui.Select):
    def __init__(self, view: "PokemonListView"):
        self.list_view = view
        options = [
            discord.SelectOption(label="UID", value="uid", description="Catch order / Pokémon UID"),
            discord.SelectOption(label="Pokédex", value="dex", description="National Pokédex number"),
            discord.SelectOption(label="IV %", value="iv", description="Highest IV percentage first"),
            discord.SelectOption(label="Name", value="name", description="Alphabetical by Pokémon name"),
        ]
        for option in options:
            option.default = option.value == view.sorting
        super().__init__(placeholder="Sort collection…", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.list_view.sorting = self.values[0]
        self.list_view.page = 0
        self.list_view._sort_data()
        self.list_view._refresh_controls()
        self.list_view._refresh_sort_defaults()
        await interaction.response.edit_message(embed=self.list_view.build_embed(), view=self.list_view)


class PokemonListView(discord.ui.View):
    PAGE_SIZE = 10

    def __init__(self, owner: discord.abc.User, data: list[dict], *, sorting: str = "uid", page: int = 0, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.data = list(data)
        self.sorting = sorting if sorting in {"uid", "dex", "iv", "name"} else "uid"
        self.page = max(0, page)
        self.message: discord.Message | None = None
        self.add_item(PokemonListSortSelect(self))
        self._sort_data()
        self.page = min(self.page, self.max_page)
        self._refresh_controls()

    @property
    def max_page(self) -> int:
        return max(0, (len(self.data) - 1) // self.PAGE_SIZE)

    def _sort_data(self) -> None:
        if self.sorting == "dex":
            self.data.sort(key=lambda row: (int(row.get("index", 0)), int(row.get("uid", 0))))
        elif self.sorting == "iv":
            self.data.sort(key=lambda row: (float(ivPercentage(row)), int(row.get("uid", 0))), reverse=True)
        elif self.sorting == "name":
            self.data.sort(key=lambda row: (str(row.get("name", "")).lower(), int(row.get("uid", 0))))
        else:
            self.data.sort(key=lambda row: int(row.get("uid", 0)))

    def _refresh_sort_defaults(self) -> None:
        for child in self.children:
            if isinstance(child, PokemonListSortSelect):
                for option in child.options:
                    option.default = option.value == self.sorting

    def _refresh_controls(self) -> None:
        self.page = min(max(0, self.page), self.max_page)
        at_start = self.page <= 0
        at_end = self.page >= self.max_page
        self.first_page.disabled = at_start
        self.previous_page.disabled = at_start
        self.next_page.disabled = at_end
        self.last_page.disabled = at_end
        self.page_indicator.label = f"{self.page + 1}/{self.max_page + 1}"

    def build_embed(self) -> discord.Embed:
        title = f"{self.owner.display_name}'s Pokémon"
        embed = discord.Embed(title=title, color=0xEEE8AA)
        start = self.page * self.PAGE_SIZE
        rows = self.data[start:start + self.PAGE_SIZE]
        lines = []
        for item in rows:
            name = str(item.get("name", "Unknown")).replace("-", " ").title()
            form = item.get("form")
            if form:
                name += " (A)" if str(form).lower() == "alolan" else f" ({str(form).title()})"
            markers = []
            if item.get("selected"):
                markers.append("🟢")
            if item.get("starred"):
                markers.append("⭐")
            if item.get("shiny"):
                markers.append("✨")
            if item.get("lucky"):
                markers.append("🍀")
            marker_text = " ".join(markers)
            if marker_text:
                marker_text = f" {marker_text}"
            lines.append(
                f"**{name}** — UID `{item.get('uid')}` · Dex `#{item.get('index')}` · "
                f"Lv. `{item.get('lvl')}` · IV `{int(float(item.get('ivpercentage') or 0))}%`{marker_text}"
            )
        embed.description = "\n".join(lines) if lines else "No Pokémon on this page."
        sort_label = {"uid": "UID", "dex": "Pokédex", "iv": "IV %", "name": "Name"}[self.sorting]
        embed.set_footer(text=f"{len(self.data)} Pokémon · Page {self.page + 1}/{self.max_page + 1} · Sorted by {sort_label}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("This collection browser belongs to another trainer.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.max_page
        self._refresh_controls()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class _InteractionMessage:
    """Minimal message-like object for legacy game helpers used by slash commands."""

    def __init__(self, interaction: discord.Interaction):
        self.id = interaction.id
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.mentions: list[discord.Member | discord.User] = []
        self.content = ""


class _InteractionContext:
    """Compatibility surface for native slash commands while game internals are modernized incrementally."""

    def __init__(self, interaction: discord.Interaction, *, ephemeral: bool = True):
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.message = _InteractionMessage(interaction)
        self.ephemeral = ephemeral
        # After defer(), the first command result should replace the original
        # loading response rather than create a second webhook follow-up.
        self._original_filled = False

    async def send(self, content=None, **kwargs):
        # Keep personal Pokémon data private unless a command explicitly opts
        # into a public response. Individual callers may still override this.
        kwargs.setdefault("ephemeral", self.ephemeral)
        ephemeral = bool(kwargs.get("ephemeral"))

        if not self.interaction.response.is_done():
            await self.interaction.response.send_message(content=content, **kwargs)
            self._original_filled = True
            return await self.interaction.original_response()

        if not self.interaction.is_expired():
            # A deferred interaction already has an original response slot.
            # Fill that slot first instead of immediately using a webhook
            # follow-up. This reduces webhook traffic/rate-limit pressure and
            # is the normal Discord interaction response pattern.
            if not self._original_filled:
                edit_kwargs = dict(kwargs)
                edit_kwargs.pop("ephemeral", None)

                # edit_original_response() accepts attachments rather than the
                # Messageable.send() convenience `file`/`files` parameters.
                single_file = edit_kwargs.pop("file", None)
                many_files = edit_kwargs.pop("files", None)
                if single_file is not None:
                    edit_kwargs["attachments"] = [single_file]
                elif many_files is not None:
                    edit_kwargs["attachments"] = list(many_files)

                try:
                    message = await self.interaction.edit_original_response(
                        content=content, **edit_kwargs
                    )
                    self._original_filled = True
                    return message
                except discord.NotFound as exc:
                    if getattr(exc, "code", None) == 10062:
                        log.warning(
                            "Pokecord interaction %s expired before its original response could be edited",
                            self.interaction.id,
                        )
                    else:
                        log.warning(
                            "Pokecord original interaction response disappeared: %s", exc
                        )
                except discord.HTTPException as exc:
                    log.warning("Unable to edit Pokecord original interaction response: %s", exc)

            try:
                return await self.interaction.followup.send(
                    content=content, wait=True, **kwargs
                )
            except discord.NotFound as exc:
                if getattr(exc, "code", None) == 10062:
                    log.warning("Pokecord follow-up interaction %s expired", self.interaction.id)
                else:
                    log.warning("Pokecord follow-up failed: %s", exc)
            except discord.HTTPException as exc:
                log.warning("Pokecord follow-up failed: %s", exc)

        # Never leak an intended ephemeral response into the public channel if
        # the interaction token has expired or Discord rejects the follow-up.
        if ephemeral:
            log.warning("Dropped expired ephemeral Pokecord response for interaction %s", self.interaction.id)
            return None

        fallback = dict(kwargs)
        fallback.pop("ephemeral", None)
        return await self.channel.send(content=content, **fallback)


@dataclass
class _CommunitySpawnState:
    time_to_spawn: datetime | None = None
    pokestore: dict | None = None
    spawn_msg: int | None = None
    caught: bool = False
    spawn_task: asyncio.Task | None = None
    spawn_expiry_task: asyncio.Task | None = None
    spawn_view: PokemonCatchView | None = None
    capture_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Species IDs from the most recent successful spawns in this community.
    # This is intentionally per-community so one guild's spawn rotation never
    # affects another guild's available Pokémon.
    recent_species: list[int] = field(default_factory=list)


@app_commands.guild_only()
class PokeCord(commands.GroupCog, group_name="pokemon", group_description="Catch, train, trade, and manage Pokémon"):
    def __init__(self, bot):
        self.bot = bot
        self._spawn_states: dict[int, _CommunitySpawnState] = {}
        self._community_configs: dict[int, dict] = {}
        self._spawn_bootstrap_task: asyncio.Task | None = None
        self.randNums = []
        self._store_cache: tuple[float, list[list]] | None = None
        self._rarity_pools: dict[str, set[int]] = {name: set() for name in DEFAULT_RARITY_WEIGHTS}
        self.api = PokeAPIClient(
            json_ttl=int(POKE_CONFIG.get("api_cache_ttl", 21600)),
            bytes_ttl=int(POKE_CONFIG.get("image_cache_ttl", 3600)),
            max_json_entries=int(POKE_CONFIG.get("api_cache_entries", 2000)),
            max_bytes_entries=int(POKE_CONFIG.get("image_cache_entries", 128)),
        )

    def _state(self, community_id: int | None = None) -> _CommunitySpawnState:
        cid = int(community_id if community_id is not None else (db.current_community_id or 0))
        state = self._spawn_states.get(cid)
        if state is None:
            state = _CommunitySpawnState()
            self._spawn_states[cid] = state
        return state

    async def _activate_guild(self, guild: discord.Guild) -> tuple[int, dict]:
        cid = await db.community_id_for_guild(guild)
        cfg = await db.get_community_config_by_id(cid)
        self._community_configs[cid] = cfg
        return cid, cfg

    async def _activate_community(self, community_id: int) -> dict:
        cid = int(community_id)
        db.activate_community(cid)
        cfg = await db.get_community_config_by_id(cid)
        self._community_configs[cid] = cfg
        return cfg

    def _pokecord_cfg(self) -> dict:
        cid = int(db.current_community_id or 0)
        cfg = self._community_configs.get(cid, config)
        value = cfg.get("pokecord", {}) if isinstance(cfg, dict) else {}
        return value if isinstance(value, dict) else {}

    def _embed_footer(self) -> str:
        return str(self._pokecord_cfg().get("embed_footer") or f"Powered by {BRAND_NAME}")

    def _contributor_role_id(self) -> int:
        try:
            return int(self._pokecord_cfg().get("contributor_role_id") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def spawn_channel_id(self) -> int:
        cid = int(db.current_community_id or 0)
        cfg = self._community_configs.get(cid, config)
        community = cfg.get("community", {}) if isinstance(cfg.get("community"), dict) else {}
        channels = community.get("channels", {}) if isinstance(community.get("channels"), dict) else {}
        key = str(community.get("pokemon_spawn_channel_key") or "")
        try:
            channel_id = int(channels.get(key) or 0) if key else 0
        except (TypeError, ValueError):
            channel_id = 0
        if channel_id:
            return channel_id
        try:
            return int(self._pokecord_cfg().get("spawn_channel_id") or DEFAULT_SPAWN_CHANNEL_ID or 0)
        except (TypeError, ValueError):
            return DEFAULT_SPAWN_CHANNEL_ID

    @spawn_channel_id.setter
    def spawn_channel_id(self, value: int) -> None:
        cid = int(db.current_community_id or 0)
        cfg = self._community_configs.setdefault(cid, dict(config))
        pcfg = cfg.setdefault("pokecord", {})
        if isinstance(pcfg, dict):
            pcfg["spawn_channel_id"] = int(value or 0)

    def _spawn_channel_for_guild(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Return the configured spawn channel only when it belongs to *guild*.

        Community configs inherit application defaults for backwards compatibility.
        That means an unconfigured guild can otherwise see another guild's legacy
        global ``pokecord.spawn_channel_id``. Discord channel IDs are globally
        unique, so resolving through ``guild.get_channel`` safely rejects that
        inherited cross-guild ID without breaking the configured guild.
        """
        channel_id = self.spawn_channel_id
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _spawn_channel_for_community(self, community_id: int) -> discord.TextChannel | None:
        """Resolve a community's spawn channel without allowing cross-guild fallback."""
        guild_id = await db.primary_guild_id_for_community(int(community_id))
        if not guild_id:
            return None
        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            return None
        return self._spawn_channel_for_guild(guild)

    @property
    def time_to_spawn(self):
        return self._state().time_to_spawn

    @time_to_spawn.setter
    def time_to_spawn(self, value):
        self._state().time_to_spawn = value

    @property
    def pokestore(self):
        return self._state().pokestore

    @pokestore.setter
    def pokestore(self, value):
        self._state().pokestore = value

    @property
    def spawn_msg(self):
        return self._state().spawn_msg

    @spawn_msg.setter
    def spawn_msg(self, value):
        self._state().spawn_msg = value

    @property
    def caught(self):
        return self._state().caught

    @caught.setter
    def caught(self, value):
        self._state().caught = bool(value)

    @property
    def _spawn_task(self):
        return self._state().spawn_task

    @_spawn_task.setter
    def _spawn_task(self, value):
        self._state().spawn_task = value

    @property
    def _spawn_expiry_task(self):
        return self._state().spawn_expiry_task

    @_spawn_expiry_task.setter
    def _spawn_expiry_task(self, value):
        self._state().spawn_expiry_task = value

    @property
    def _spawn_view(self):
        return self._state().spawn_view

    @_spawn_view.setter
    def _spawn_view(self, value):
        self._state().spawn_view = value

    @property
    def _capture_lock(self):
        return self._state().capture_lock

    async def _bootstrap_community_spawns(self) -> None:
        await self.bot.wait_until_ready()
        for guild in list(self.bot.guilds):
            try:
                cid, _ = await self._activate_guild(guild)
                if not await db.community_feature_enabled(cid, "pokecord", True):
                    log.info("Pokécord scheduler skipped for guild %s: feature disabled", guild.id)
                    continue

                channel = self._spawn_channel_for_guild(guild)
                if channel is None:
                    log.info(
                        "Pokécord scheduler skipped for guild %s: no spawn channel configured for this guild",
                        guild.id,
                    )
                    continue

                self._schedule_spawn()
            except Exception:
                log.exception("Unable to start Pokécord scheduler for guild %s", guild.id)

    async def set_community_enabled(self, community_id: int, enabled: bool) -> None:
        """Apply a Pokécord feature toggle immediately for one community."""
        cid = int(community_id)
        await self._activate_community(cid)
        state = self._state(cid)
        if not enabled:
            if state.spawn_task is not None and not state.spawn_task.done():
                state.spawn_task.cancel()
            state.spawn_task = None
            self._cancel_spawn_expiry()
            if state.spawn_view is not None:
                await self._edit_spawn_view(replaced=True)
            state.pokestore = None
            state.spawn_msg = None
            state.time_to_spawn = None
            state.caught = False
            log.info("Pokécord disabled for community %s; scheduler stopped", cid)
            return

        channel = await self._spawn_channel_for_community(cid)
        if channel is None:
            log.info(
                "Pokécord enabled for community %s, but no valid spawn channel is configured; scheduler not started",
                cid,
            )
            return

        if state.pokestore is None and (state.spawn_task is None or state.spawn_task.done()):
            self._schedule_spawn()
        log.info("Pokécord enabled for community %s", cid)

    async def cog_load(self) -> None:
        await self.api.start()
        group = self.app_command
        child_count = len(group.commands) if group is not None else 0
        log.info("Pokecord API client started; native /pokemon group loaded with %s subcommands", child_count)

        # Each community gets an independent spawn state/scheduler.
        self._spawn_bootstrap_task = asyncio.create_task(
            self._bootstrap_community_spawns(), name="pokecord-community-spawn-bootstrap"
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Acknowledge every /pokemon command before its callback starts.

        Discord invalidates an interaction if its initial response misses the
        short acknowledgement window. GroupCog interaction checks run before
        the individual command callback, so this is the earliest common place
        to defer all Pokémon commands.
        """
        if interaction.guild is None or interaction.channel is None:
            return False

        community_id, _ = await self._activate_guild(interaction.guild)
        if not await db.community_feature_enabled(community_id, "pokecord", True):
            if not interaction.response.is_done():
                await interaction.response.send_message("Pokécord is disabled for this community.", ephemeral=True)
            return False
        interaction.extras["community_id"] = community_id

        command_name = getattr(interaction.command, "name", "")
        public_commands = {"catch", "release", "trade", "battle", "gym"}
        ephemeral = command_name not in public_commands
        interaction.extras["pokecord_ephemeral"] = ephemeral

        if interaction.response.is_done():
            return True

        age = max(0.0, (discord.utils.utcnow() - interaction.created_at).total_seconds())
        if age >= 2.0:
            log.warning(
                "Pokecord interaction %s reached interaction_check %.3fs after Discord created it",
                interaction.id, age,
            )

        try:
            await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        except discord.NotFound as exc:
            if getattr(exc, "code", None) == 10062:
                interaction.extras["pokecord_interaction_expired"] = True
                log.warning(
                    "Pokecord interaction %s expired during initial defer (age %.3fs); dropping command",
                    interaction.id, age,
                )
                return False
            raise
        return True

    async def _slash_context(
        self, interaction: discord.Interaction, *, ephemeral: bool = True
    ) -> _InteractionContext:
        if interaction.guild is None or interaction.channel is None:
            raise app_commands.NoPrivateMessage("Pokémon commands can only be used in a server.")

        # interaction_check() normally performs the defer before callbacks run.
        # Keep this guarded fallback for direct/manual invocation and future
        # refactors that may bypass the GroupCog check.
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(thinking=True, ephemeral=ephemeral)
            except discord.NotFound as exc:
                if getattr(exc, "code", None) == 10062:
                    interaction.extras["pokecord_interaction_expired"] = True
                    raise app_commands.CheckFailure(
                        "The Discord interaction expired before it could be acknowledged."
                    ) from exc
                raise

        effective_ephemeral = bool(
            interaction.extras.get("pokecord_ephemeral", ephemeral)
        )
        return _InteractionContext(interaction, ephemeral=effective_ephemeral)

    async def _require_owner(self, interaction: discord.Interaction, ctx: _InteractionContext) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        await ctx.send("This command is restricted to the bot owner.", ephemeral=True)
        return False

    async def _save_battle_state(self, owner_id: int, uid: int, battle: Battle) -> None:
        await db.execute(
            'UPDATE pokecord_poke_data_scoped SET "battle_hp"=$1, "status"=$2, "status_turns"=$3 WHERE "ownerid"=$4 AND "uid"=$5',
            int(battle.health), battle.status, int(battle.status_turns), int(owner_id), int(uid),
        )

    async def _persist_two_battle_states(self, first_owner: int, first_uid: int, first: Battle, second_owner: int, second_uid: int, second: Battle) -> None:
        await db.execute_many_in_transaction([
            (
                'UPDATE pokecord_poke_data_scoped SET "battle_hp"=$1, "status"=$2, "status_turns"=$3 WHERE "ownerid"=$4 AND "uid"=$5',
                (int(first.health), first.status, int(first.status_turns), int(first_owner), int(first_uid)),
            ),
            (
                'UPDATE pokecord_poke_data_scoped SET "battle_hp"=$1, "status"=$2, "status_turns"=$3 WHERE "ownerid"=$4 AND "uid"=$5',
                (int(second.health), second.status, int(second.status_turns), int(second_owner), int(second_uid)),
            ),
        ])

    async def _maybe_use_held_berry(self, owner_id: int, poke_data, battle: Battle) -> str:
        if battle.held_item_consumed or battle.health <= 0:
            return ""
        raw_item = poke_data.get('item')
        if not raw_item:
            return ""
        try:
            held = json.loads(raw_item) if isinstance(raw_item, str) else dict(raw_item)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""
        item_name = _canonical_item_name(held.get('name'))
        if item_name not in SHOP_BERRY_ITEMS:
            return ""

        triggered = False
        detail = ""
        if item_name == 'oran-berry' and battle.health <= battle.max_health // 2 and battle.health < battle.max_health:
            heal = min(10, battle.max_health - battle.health)
            battle.health += heal
            triggered = heal > 0
            detail = f"restored **{heal} HP**"
        elif item_name == 'sitrus-berry' and battle.health <= battle.max_health // 2 and battle.health < battle.max_health:
            heal = min(max(1, battle.max_health // 4), battle.max_health - battle.health)
            battle.health += heal
            triggered = heal > 0
            detail = f"restored **{heal} HP**"
        else:
            cure_map = {
                'pecha-berry': 'poison', 'rawst-berry': 'burn', 'cheri-berry': 'paralysis',
                'chesto-berry': 'sleep', 'aspear-berry': 'freeze',
            }
            cure = cure_map.get(item_name)
            if item_name == 'lum-berry' and battle.status:
                cure = battle.status
            if cure and battle.status == cure:
                old_status = battle.status
                battle.status = None
                battle.status_turns = 0
                triggered = True
                detail = f"cured {_status_label(old_status).lower()}"

        if not triggered:
            return ""

        battle.held_item_consumed = True
        await db.execute(
            'UPDATE pokecord_poke_data_scoped SET "item"=NULL WHERE "ownerid"=$1 AND "uid"=$2',
            int(owner_id), int(poke_data['uid']),
        )
        pretty = item_name.replace('-', ' ').title()
        return f"🍓 **{poke_data['name'].title()}** consumed its **{pretty}** and {detail}."

    @staticmethod
    def _battle_status_suffix(battle: Battle) -> str:
        return "" if battle.status is None else f" · {_status_label(battle.status)}"

    async def _use_recovery_item(self, ctx, poke_info, item_name: str) -> tuple[bool, bool, str]:
        effect = HEALING_ITEM_EFFECTS.get(item_name)
        if effect is None:
            return False, False, ""

        max_hp = max(1, int(poke_info['hp'] or 1))
        current_hp = min(max_hp, max(0, int(poke_info.get('battle_hp') if poke_info.get('battle_hp') is not None else max_hp)))
        status = _normalize_status(poke_info.get('status'))
        new_hp = current_hp
        new_status = status
        changed = False

        revive_fraction = effect.get('revive_fraction')
        if revive_fraction is not None:
            if current_hp > 0:
                return True, False, f"{poke_info['name'].title()} has not fainted, so **{item_name.replace('-', ' ').title()}** had no effect."
            new_hp = max(1, int(max_hp * float(revive_fraction)))
            changed = True
        elif current_hp <= 0:
            return True, False, f"{poke_info['name'].title()} has fainted. Use a **Revive** or **Max Revive** first."

        if effect.get('full_heal') and current_hp > 0 and new_hp < max_hp:
            new_hp = max_hp
            changed = True
        elif effect.get('heal') and current_hp > 0 and new_hp < max_hp:
            healed = min(max_hp - new_hp, int(effect['heal']))
            new_hp += healed
            changed = changed or healed > 0
        elif effect.get('heal_fraction') and current_hp > 0 and new_hp < max_hp:
            healed = min(max_hp - new_hp, max(1, int(max_hp * float(effect['heal_fraction']))))
            new_hp += healed
            changed = changed or healed > 0

        cure = effect.get('cure')
        if cure and status and (cure == 'any' or cure == status):
            new_status = None
            changed = True

        if not changed:
            if cure and not status:
                return True, False, f"{poke_info['name'].title()} is already healthy."
            return True, False, f"**{item_name.replace('-', ' ').title()}** would have no effect on {poke_info['name'].title()} right now."

        await db.execute(
            'UPDATE pokecord_poke_data_scoped SET "battle_hp"=$1, "status"=$2, "status_turns"=CASE WHEN $2::TEXT IS NULL THEN 0 ELSE "status_turns" END WHERE "ownerid"=$3 AND "uid"=$4',
            int(new_hp), new_status, int(ctx.author.id), int(poke_info['uid']),
        )
        hp_text = f"{new_hp}/{max_hp} HP"
        status_text = _status_label(new_status)
        return True, True, f"Used **{item_name.replace('-', ' ').title()}** on **{poke_info['name'].title()}** — {hp_text} · {status_text}."

    async def _pokemon_uid_choices(
        self,
        interaction: discord.Interaction,
        current: str | int | float,
        *,
        owner_id: int | None = None,
    ) -> list[app_commands.Choice[int]]:
        """Return up to 25 owned Pokémon as rich UID autocomplete choices."""
        owner_id = int(owner_id or interaction.user.id)
        needle = str(current or "").strip().lower()
        rows = await db.fetch(
            '''
            SELECT "uid", "name", "lvl", "ivpercentage", "selected", "starred", "shiny", "lucky"
            FROM pokecord_poke_data_scoped
            WHERE "ownerid" = $1
              AND (
                    $2::TEXT = ''
                    OR LOWER("name") LIKE '%' || $2::TEXT || '%'
                    OR "uid"::TEXT LIKE $2::TEXT || '%'
                  )
            ORDER BY "selected" DESC, "starred" DESC, "uid" DESC
            LIMIT 25
            ''',
            owner_id,
            needle,
        )
        choices: list[app_commands.Choice[int]] = []
        for row in rows:
            uid = int(row.get('uid', 0))
            name = str(row.get('name', 'Unknown')).replace('-', ' ').title()
            markers = ""
            if row.get('selected'):
                markers += " 🟢"
            if row.get('starred'):
                markers += " ⭐"
            if row.get('shiny'):
                markers += " ✨"
            if row.get('lucky'):
                markers += " 🍀"
            iv_percent = int(float(row.get('ivpercentage') or 0))
            label = f"{uid} · {name} · Lv. {row.get('lvl', '?')} · {iv_percent}% IV{markers}"
            choices.append(app_commands.Choice(name=label[:100], value=uid))
            if len(choices) >= 25:
                break
        return choices

    async def _bag_item_choices(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        rows = await db.get_inventory(
            interaction.guild.id,
            interaction.user.id,
            search=_canonical_item_name(current),
            limit=25,
        )
        choices: list[app_commands.Choice[str]] = []
        for row in rows:
            item_name = str(row['item_name'])
            pretty = item_name.replace('-', ' ').title()
            label = f"{pretty} · x{int(row['quantity'])}"
            choices.append(app_commands.Choice(name=label[:100], value=item_name))
        return choices

    async def _shop_item_choices(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        # The static catalog is immediately available. storeEmbed() may enrich
        # prices from PokéAPI, but autocomplete never depends on the API.
        if self._store_cache is None or time.monotonic() - self._store_cache[0] >= 21600:
            try:
                await asyncio.wait_for(self.storeEmbed(), timeout=2.25)
            except Exception as exc:
                log.debug("Shop autocomplete enrichment failed: %s", exc)
        rows = self._store_cache[1] if self._store_cache else _store_fallback_rows()
        needle = _canonical_item_name(current)
        choices: list[app_commands.Choice[str]] = []
        for name, cost in rows:
            pretty = str(name).replace('-', ' ').title()
            searchable = f"{name} {pretty.lower()}"
            if needle and needle not in searchable:
                continue
            choices.append(
                app_commands.Choice(
                    name=f"{pretty} · {int(cost):,} credits"[:100],
                    value=str(name),
                )
            )
            if len(choices) >= 25:
                break
        return choices

    async def _edit_spawn_view(
        self, *, caught: bool = False, replaced: bool = False, expired: bool = False
    ) -> None:
        view = self._spawn_view
        if view is None:
            return
        if caught:
            view.mark_caught()
        elif expired:
            view.mark_expired()
        elif replaced:
            view.mark_replaced()
        else:
            view.stop()

        message = view.message
        if message is None and self.spawn_msg:
            cid = int(db.current_community_id or 0)
            channel = await self._spawn_channel_for_community(cid) if cid else None
            if channel is not None and hasattr(channel, "fetch_message"):
                try:
                    message = await channel.fetch_message(self.spawn_msg)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message = None

        if message is not None:
            try:
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        self._spawn_view = None

    def _cancel_spawn_expiry(self) -> None:
        task = self._spawn_expiry_task
        self._spawn_expiry_task = None
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    def _schedule_spawn_expiry(self, message_id: int, view: PokemonCatchView) -> None:
        self._cancel_spawn_expiry()
        seconds = max(15, int(self._pokecord_cfg().get("spawn_expire_seconds", 180)))
        self._spawn_expiry_task = asyncio.create_task(
            self._expire_spawn_after(seconds, message_id, view),
            name="pokecord-spawn-expiry",
        )
        log.info("Wild Pokémon will expire in %s seconds", seconds)

    async def _expire_spawn_after(
        self, seconds: int, message_id: int, view: PokemonCatchView
    ) -> None:
        try:
            await asyncio.sleep(seconds)
            async with self._capture_lock:
                # Ignore stale timers after a catch, replacement, or newer spawn.
                if (
                    self.pokestore is None
                    or self.caught
                    or self.spawn_msg != message_id
                    or self._spawn_view is not view
                ):
                    return

                escaped = dict(self.pokestore)
                self.pokestore = None
                self.caught = False

                view.mark_expired()
                message = view.message
                if message is None:
                    cid = int(db.current_community_id or 0)
                    channel = await self._spawn_channel_for_community(cid) if cid else None
                    if channel is not None and hasattr(channel, "fetch_message"):
                        try:
                            message = await channel.fetch_message(message_id)
                        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                            message = None

                if message is not None:
                    pretty_name = str(escaped.get("name", "Unknown")).replace("-", " ").title()
                    embed = discord.Embed(
                        title="The wild Pokémon escaped!",
                        description=(
                            f"Nobody caught **{pretty_name}** before it fled. "
                            "Another wild Pokémon will appear soon."
                        ),
                        color=0x808080,
                    )
                    embed.set_image(url="attachment://poke_image.png")
                    embed.set_footer(text=self._embed_footer())
                    try:
                        await message.edit(embed=embed, view=view)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass

                self._spawn_view = None
                self.spawn_msg = None
                log.info(
                    "Wild Pokémon %s expired after %s seconds",
                    escaped.get("name", "unknown"),
                    seconds,
                )

                community_id = int(db.current_community_id or 0)
                if community_id:
                    self.bot.dispatch(
                        "pokecord_escape",
                        community_id,
                        {
                            "pokemon_name": str(escaped.get("name") or "Pokémon"),
                            "rarity": RARITY_LABELS.get(escaped.get("rarity", "common"), "Common"),
                            "shiny": bool(escaped.get("shiny", False)),
                        },
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Pokecord spawn expiration failed")
        finally:
            if self._spawn_expiry_task is asyncio.current_task():
                self._spawn_expiry_task = None

        if not self.bot.is_closed() and self.pokestore is None:
            self._schedule_spawn()

    async def _catch_from_modal(self, interaction: discord.Interaction, guess: str) -> None:
        """Handle a private button/modal guess while announcing successful catches publicly."""
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Pokémon can only be caught in a server.", ephemeral=True)
            return
        await self._activate_guild(interaction.guild)
        spawn_channel = self._spawn_channel_for_guild(interaction.guild)
        if spawn_channel is None:
            await interaction.response.send_message(
                "Pokécord does not have a spawn channel configured for this server.", ephemeral=True
            )
            return
        if interaction.channel.id != spawn_channel.id:
            await interaction.response.send_message(
                f"Use the catch button in {spawn_channel.mention}.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        message = _InteractionMessage(interaction)

        if helpers.check_role(interaction.user, self._contributor_role_id()):
            owned = await helpers.get_pokecord_postgresData(interaction.user, "*")
            if len(owned) >= 300:
                await interaction.edit_original_response(
                    content="Your Pokémon storage is full (300/300). Release a Pokémon before catching another."
                )
                return
        else:
            owned = await helpers.get_pokecord_postgresData(interaction.user, "*")
            if len(owned) >= 200:
                await interaction.edit_original_response(
                    content="Your Pokémon storage is full (200/200). Release a Pokémon before catching another."
                )
                return

        if not self.appeared:
            await interaction.edit_original_response(content="There isn't a wild Pokémon to catch right now.")
            return

        async with self._capture_lock:
            if not self.appeared or self.caught:
                await interaction.edit_original_response(content="Too late — that Pokémon has already been caught!")
                return
            caught = await self.check_capture(message, guess)

        if caught:
            await interaction.edit_original_response(content="✅ Gotcha! Your catch was saved.")
        else:
            await interaction.edit_original_response(content="❌ Nope — that's not the Pokémon. Try another guess!")

    async def cog_unload(self) -> None:
        if self._spawn_bootstrap_task and not self._spawn_bootstrap_task.done():
            self._spawn_bootstrap_task.cancel()
        for state in self._spawn_states.values():
            for task in (state.spawn_task, state.spawn_expiry_task):
                if task is not None and not task.done():
                    task.cancel()
        await self.api.close()

    async def _delete_invocation(self, ctx: commands.Context) -> None:
        # Interaction contexts contain a synthetic message. There is nothing
        # useful to delete, and trying to delete it can fail on slash commands.
        if ctx.interaction is not None:
            return
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    def __getstate__(self):
        return {
            "time": self.time_to_spawn,
            "store": self.pokestore,
            "msg": self.spawn_msg,
        }

    def __setstate__(self, dictState):
        self.time_to_spawn = dictState.get("time")
        self.pokestore = dictState.get("store")
        self.spawn_msg = dictState.get("msg")

    def getSeconds(self):
        return (self.time_to_spawn - datetime.now()).total_seconds()

    def setToSpawn(self):
        if self.time_to_spawn is None:
            return False
        else:
            return True

    @property
    def appeared(self):
        return self.pokestore is not None


    def _api_identifier_for_record(self, record: dict) -> int:
        index = int(record["index"])
        form = str(record.get("form") or "").lower()
        if form == "alolan" and index in alolan_pokemon:
            return alolanIds[alolan_pokemon.index(index)]
        return index

    async def _pokemon_for_record(self, record: dict) -> dict:
        return await self.api.pokemon(self._api_identifier_for_record(record))

    async def _artwork_bytes(self, pokemon: dict, *, shiny: bool = False) -> bytes:
        suffix = "shiny" if shiny else "normal"
        cache_file = IMAGE_DIR / f"artwork_{pokemon['id']}_{suffix}.png"
        if cache_file.exists():
            return await asyncio.to_thread(cache_file.read_bytes)

        url = self.api.artwork_url(pokemon, shiny=shiny)
        if not url:
            raise PokeAPIError(f"No artwork available for {pokemon.get('name', pokemon.get('id'))}")
        raw = await self.api.get_bytes(url)
        png = await asyncio.to_thread(_render_png, raw)
        await asyncio.to_thread(cache_file.write_bytes, png)
        return png

    async def _art_file(self, pokemon: dict, *, shiny: bool = False, filename: str = "pokemon.png") -> discord.File:
        data = await self._artwork_bytes(pokemon, shiny=shiny)
        return discord.File(BytesIO(data), filename=filename)

    async def _silhouette_file(self, pokemon: dict) -> discord.File:
        data = await self._artwork_bytes(pokemon, shiny=False)
        silhouette = await asyncio.to_thread(_render_png, data, silhouette=True)
        return discord.File(BytesIO(silhouette), filename="poke_image.png")

    @c.Cog.listener()
    async def on_command_completion(self, ctx):
        ...

    def sortNAME(self, e):
        return e['name']

    def sortUID(self, e):
        return e['uid']

    def sortDEX(self, e):
        return e['index']

    def sortIV(self, e):
        return e['iv']

    def sortItemID(self, e):
        return e[1]

    def sortPokeDEX(self, e):
        return int(e[0])

    @staticmethod
    def _find_evolution_node(chain: dict, species_name: str) -> dict | None:
        for node in _walk_evolution_chain(chain):
            if node.get("species", {}).get("name") == species_name:
                return node
        return None

    async def _pokemon_from_species_ref(self, species_ref: dict) -> dict:
        species = await self.api.get_json(species_ref["url"])
        varieties = species.get("varieties", [])
        variety = next((v for v in varieties if v.get("is_default")), varieties[0] if varieties else None)
        if variety is None:
            raise PokeAPIError(f"No Pokémon variety found for species {species_ref.get('name')}")
        return await self.api.get_json(variety["pokemon"]["url"])

    @staticmethod
    def _stored_move_names(orig_data: dict) -> set[str]:
        names: set[str] = set()
        for raw in orig_data.get("moves") or []:
            move = raw
            if isinstance(raw, str):
                try:
                    move = json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    move = {"name": raw}
            if isinstance(move, dict) and move.get("name"):
                names.add(str(move["name"]).strip().lower())
        return names

    @staticmethod
    def _level_up_move_names(pokemon: dict, level: int) -> set[str]:
        names: set[str] = set()
        for entry in pokemon.get("moves", []):
            move = entry.get("move") or {}
            move_name = str(move.get("name") or "").strip().lower()
            if not move_name:
                continue
            for detail in entry.get("version_group_details", []):
                if detail.get("move_learn_method", {}).get("name") != "level-up":
                    continue
                learned_at = int(detail.get("level_learned_at") or 0)
                if learned_at <= int(level):
                    names.add(move_name)
                    break
        return names

    async def _knows_move_for_evolution(
        self, pokemon: dict, orig_data: dict, move_name: str, level: int
    ) -> bool:
        required = str(move_name or "").strip().lower()
        if not required:
            return True
        if required in self._stored_move_names(orig_data):
            return True
        # The battle system deliberately stores damaging moves only. For
        # evolution requirements such as Mimic, count a level-up move as
        # "known" once this species can naturally learn it at the current level.
        return required in self._level_up_move_names(pokemon, level)

    async def _knows_move_type_for_evolution(
        self, pokemon: dict, orig_data: dict, move_type: str, level: int
    ) -> bool:
        required_type = str(move_type or "").strip().lower()
        if not required_type:
            return True

        candidate_names = self._stored_move_names(orig_data)
        candidate_names.update(self._level_up_move_names(pokemon, level))
        if not candidate_names:
            return False

        by_name = {
            str(entry.get("move", {}).get("name") or "").strip().lower(): entry.get("move", {}).get("url")
            for entry in pokemon.get("moves", [])
        }
        pending = []
        for name in sorted(candidate_names):
            url = by_name.get(name)
            if url:
                pending.append(self.api.get_json(url))
            else:
                pending.append(self.api.get_json(f"{PokeAPIClient.BASE_URL}/move/{name}/"))

        # Keep request fan-out bounded. PokeAPIClient caches these resources, so
        # subsequent evolution checks are normally local/cache hits.
        for offset in range(0, len(pending), 12):
            results = await asyncio.gather(*pending[offset:offset + 12], return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    continue
                if result.get("type", {}).get("name") == required_type:
                    return True
        return False

    def _evolution_time_of_day(self) -> str:
        cfg = self._pokecord_cfg()
        timezone_name = str(cfg.get("evolution_timezone") or "America/Chicago")
        try:
            now = datetime.now(ZoneInfo(timezone_name))
        except (ZoneInfoNotFoundError, ValueError):
            log.warning("Unknown Pokecord evolution timezone %r; using local server time", timezone_name)
            now = datetime.now()
        day_start = max(0, min(23, int(cfg.get("evolution_day_start_hour", 6))))
        night_start = max(day_start + 1, min(24, int(cfg.get("evolution_night_start_hour", 18))))
        return "day" if day_start <= now.hour < night_start else "night"

    async def _owner_has_species_for_evolution(self, owner_id: int | None, species_name: str) -> bool:
        if owner_id is None:
            return False
        return bool(await db.fetchval(
            'SELECT EXISTS(SELECT 1 FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND LOWER("name")=$2)',
            int(owner_id), str(species_name).lower(),
        ))

    async def _owner_has_type_for_evolution(self, owner_id: int | None, type_name: str) -> bool:
        if owner_id is None:
            return False
        return bool(await db.fetchval(
            'SELECT EXISTS(SELECT 1 FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND $2::TEXT = ANY("type"))',
            int(owner_id), str(type_name).lower(),
        ))

    @staticmethod
    def _evolution_stat_relation(orig_data: dict, level: int) -> int:
        attack = int(calcStat(
            int(orig_data.get("base_attack") or 1), int(orig_data.get("attack_iv") or 0),
            int(level), int(orig_data.get("base_attack") or 1), False,
        ))
        defense = int(calcStat(
            int(orig_data.get("base_defense") or 1), int(orig_data.get("defense_iv") or 0),
            int(level), int(orig_data.get("base_defense") or 1), False,
        ))
        return 1 if attack > defense else (-1 if attack < defense else 0)

    async def _evolution_detail_matches(
        self,
        pokemon: dict,
        orig_data: dict,
        detail: dict,
        *,
        trigger: str,
        level: int | None,
        item: str | None,
        friendship: int,
        owner_id: int | None,
        trade_species: str | None,
        allow_world_simplification: bool,
    ) -> tuple[bool, int]:
        actual_trigger = str(detail.get("trigger", {}).get("name") or "")
        if actual_trigger != trigger:
            return False, 0

        score = 1
        current_level = int(level if level is not None else orig_data.get("lvl") or 1)
        held_item = str(item or "").strip().lower() or None

        required_item = detail.get("item")
        if required_item is not None:
            if trigger != "use-item" or required_item.get("name") != held_item:
                return False, 0
            score += 120
        elif trigger == "use-item":
            # A use-item evolution must explicitly name the consumed item.
            return False, 0

        required_held = detail.get("held_item")
        if required_held is not None:
            if required_held.get("name") != held_item:
                return False, 0
            score += 80

        required_gender = detail.get("gender")
        if required_gender is not None:
            gender_map = {1: "female", 2: "male"}
            if gender_map.get(int(required_gender)) != str(orig_data.get("gender") or "").lower():
                return False, 0
            score += 70

        required_base_form = detail.get("base_form")
        if required_base_form is not None:
            if str(required_base_form.get("name") or "").lower() != str(pokemon.get("name") or "").lower():
                return False, 0
            score += 70

        minimum = detail.get("min_level")
        if minimum is not None:
            if current_level < int(minimum):
                return False, 0
            score += 20

        min_happiness = detail.get("min_happiness")
        if min_happiness is not None:
            if friendship < int(min_happiness):
                return False, 0
            score += 35

        # PokéCord has one persistent bond stat. Affection and beauty conditions
        # use that same 0-255 friendship value rather than silently randomizing.
        min_affection = detail.get("min_affection")
        if min_affection is not None:
            raw_affection = int(min_affection)
            affection_threshold = raw_affection if raw_affection > 10 else min(255, raw_affection * 80)
            if friendship < affection_threshold:
                return False, 0
            score += 35
        min_beauty = detail.get("min_beauty")
        if min_beauty is not None:
            if friendship < int(min_beauty):
                return False, 0
            score += 35

        required_move = detail.get("known_move")
        if required_move is not None:
            if not await self._knows_move_for_evolution(
                pokemon, orig_data, required_move.get("name"), current_level
            ):
                return False, 0
            score += 110

        # Newer PokéAPI data can describe a move-use requirement separately.
        # Because PokéCord does not persist move-use counters, learning the move
        # is the bot-friendly equivalent; min_move_count is handled below.
        used_move = detail.get("used_move")
        if used_move is not None:
            if not await self._knows_move_for_evolution(
                pokemon, orig_data, used_move.get("name"), current_level
            ):
                return False, 0
            score += 105

        required_move_type = detail.get("known_move_type")
        if required_move_type is not None:
            if not await self._knows_move_type_for_evolution(
                pokemon, orig_data, required_move_type.get("name"), current_level
            ):
                return False, 0
            score += 100

        relation = detail.get("relative_physical_stats")
        if relation is not None:
            if self._evolution_stat_relation(orig_data, current_level) != int(relation):
                return False, 0
            score += 90

        required_time = str(detail.get("time_of_day") or "").strip().lower()
        if required_time:
            if required_time != self._evolution_time_of_day():
                return False, 0
            score += 75

        required_trade_species = detail.get("trade_species")
        if required_trade_species is not None:
            if trigger != "trade" or str(required_trade_species.get("name") or "").lower() != str(trade_species or "").lower():
                return False, 0
            score += 115

        party_species = detail.get("party_species")
        if party_species is not None:
            if not await self._owner_has_species_for_evolution(owner_id, party_species.get("name")):
                return False, 0
            score += 65

        party_type = detail.get("party_type")
        if party_type is not None:
            if not await self._owner_has_type_for_evolution(owner_id, party_type.get("name")):
                return False, 0
            score += 65

        # Discord has no physical map/console orientation/weather context. For a
        # unique location/region evolution we substitute a configurable level
        # gate. If multiple sibling branches depend on different locations, we
        # refuse to guess which branch the trainer wanted.
        world_condition = bool(detail.get("location") or detail.get("region") or detail.get("near_special_rock"))
        if world_condition:
            if not allow_world_simplification:
                return False, 0
            special_level = max(1, int(self._pokecord_cfg().get("special_evolution_level", 30)))
            if current_level < special_level:
                return False, 0
            score += 45

        # Console-only mechanics are deliberately reduced to their accompanying
        # level/bond/move requirements instead of random chance.
        special_flags = (
            bool(detail.get("needs_overworld_rain")),
            bool(detail.get("needs_multiplayer")),
            bool(detail.get("turn_upside_down")),
            detail.get("min_move_count") is not None,
            detail.get("min_steps") is not None,
            detail.get("min_damage_taken") is not None,
        )
        if any(special_flags):
            special_level = max(1, int(self._pokecord_cfg().get("special_evolution_level", 30)))
            if minimum is None and current_level < special_level:
                return False, 0
            score += 15

        # A bare level-up evolution with no explicit numeric/conditional gate
        # used to receive a 25% random roll. Replace that with a deterministic
        # configurable level so evolutions can never occur merely by luck.
        explicit_gate = any((
            minimum is not None, min_happiness is not None, min_affection is not None,
            min_beauty is not None, required_move is not None, used_move is not None,
            required_move_type is not None, relation is not None, bool(required_time),
            required_gender is not None, required_held is not None, party_species is not None,
            party_type is not None, world_condition, any(special_flags),
        ))
        if trigger == "level-up" and not explicit_gate:
            fallback_level = max(1, int(self._pokecord_cfg().get("special_evolution_level", 30)))
            if current_level < fallback_level:
                return False, 0

        return True, score

    async def _find_evolution_target(
        self,
        orig_data: dict,
        *,
        trigger: str,
        level: int | None = None,
        item: str | None = None,
        friendship: int | None = None,
        owner_id: int | None = None,
        trade_species: str | None = None,
    ) -> dict | None:
        pokemon = await self._pokemon_for_record(orig_data)
        chain = await self.api.evolution_chain_for(pokemon)
        node = self._find_evolution_node(chain.get("chain", {}), str(orig_data["name"]).lower())
        if node is None:
            return None

        # If several sibling branches are distinguished only by world location,
        # there is no honest way to choose one in Discord without a location UI.
        world_branches = 0
        for child in node.get("evolves_to", []):
            if any(
                str(detail.get("trigger", {}).get("name") or "") == trigger
                and bool(detail.get("location") or detail.get("region") or detail.get("near_special_rock"))
                for detail in child.get("evolution_details", [])
            ):
                world_branches += 1
        allow_world_simplification = world_branches <= 1

        bond = _friendship_value(friendship if friendship is not None else orig_data.get("friendship"))
        matches: list[tuple[int, dict, dict]] = []
        for child in node.get("evolves_to", []):
            for detail in child.get("evolution_details", []):
                matched, score = await self._evolution_detail_matches(
                    pokemon, orig_data, detail,
                    trigger=trigger,
                    level=level,
                    item=item,
                    friendship=bond,
                    owner_id=owner_id,
                    trade_species=trade_species,
                    allow_world_simplification=allow_world_simplification,
                )
                if matched:
                    matches.append((score, child, detail))

        if not matches:
            return None

        best_score = max(score for score, _, _ in matches)
        _, child, detail = random.choice([entry for entry in matches if entry[0] == best_score])
        evolved_form = detail.get("evolved_form")
        if evolved_form and evolved_form.get("url"):
            target = await self.api.get_json(evolved_form["url"])
        else:
            target = await self._pokemon_from_species_ref(child["species"])
        log.debug(
            "Pokecord evolution matched %s -> %s via %s (score=%s friendship=%s)",
            orig_data.get("name"), target.get("name"), trigger, best_score, bond,
        )
        return target

    async def _update_evolved_pokemon(self, user, orig_data: dict, pokemon: dict) -> None:
        moves = await select_damaging_moves(self.api, pokemon)
        moves_list = [json.dumps(move) for move in moves]
        stats = pokemon["stats"]
        lvl = int(orig_data["lvl"])
        base_hp = stats[0]["base_stat"]
        base_attack = stats[1]["base_stat"]
        base_defense = stats[2]["base_stat"]
        base_sp_attack = stats[3]["base_stat"]
        base_sp_defense = stats[4]["base_stat"]
        base_speed = stats[5]["base_stat"]
        hp = int(calcStat(base_hp, orig_data["hp_iv"], lvl, base_hp, True))
        old_max_hp = max(1, int(orig_data['hp'] or 1))
        old_current_hp = min(old_max_hp, max(0, int(orig_data.get('battle_hp') if orig_data.get('battle_hp') is not None else old_max_hp)))
        missing_hp = old_max_hp - old_current_hp
        current_hp = 0 if old_current_hp <= 0 else max(1, min(hp, hp - missing_hp))
        attack = int(calcStat(base_attack, orig_data["attack_iv"], lvl, base_attack, False))
        defense = int(calcStat(base_defense, orig_data["defense_iv"], lvl, base_defense, False))
        sp_attack = int(calcStat(base_sp_attack, orig_data["special_attack_iv"], lvl, base_sp_attack, False))
        sp_defense = int(calcStat(base_sp_defense, orig_data["special_defense_iv"], lvl, base_sp_defense, False))
        speed = int(calcStat(base_speed, orig_data["speed_iv"], lvl, base_speed, False))

        await helpers.transaction_postgresDatabase(
            """UPDATE pokecord_poke_data_scoped SET
                   "index"=$1, "type"=$2, "base_hp"=$3, "base_exp"=$4,
                   "base_attack"=$5, "base_defense"=$6, "base_special_attack"=$7,
                   "base_special_defense"=$8, "base_speed"=$9, "name"=$10,
                   "height"=$11, "weight"=$12, "moves"=$13, "hp"=$14,
                   "battle_hp"=$15, "attack"=$16, "defense"=$17,
                   "sp_attack"=$18, "sp_defense"=$19, "speed"=$20
               WHERE "ownerid"=$21 AND "uid"=$22""",
            pokemon["id"],
            [entry["type"]["name"] for entry in pokemon["types"]],
            base_hp,
            pokemon.get("base_experience") or 0,
            base_attack,
            base_defense,
            base_sp_attack,
            base_sp_defense,
            base_speed,
            pokemon["name"],
            pokemon["height"],
            pokemon["weight"],
            moves_list,
            hp,
            current_hp,
            attack,
            defense,
            sp_attack,
            sp_defense,
            speed,
            user.id,
            orig_data["uid"],
        )

    async def itemEvolve(self, user, pokename, orig_data, _item):
        oldname = orig_data["name"]
        pokemon = await self._find_evolution_target(
            orig_data, trigger="use-item", item=_item, owner_id=int(user.id)
        )
        if pokemon is None:
            return oldname, pokename, False
        await self._update_evolved_pokemon(user, orig_data, pokemon)
        return oldname, pokemon["name"], True

    async def tradeEvolve(self, user, pokename, orig_data, _item, trade_species: str | None = None):
        oldname = orig_data["name"]
        pokemon = await self._find_evolution_target(
            orig_data, trigger="trade", item=_item, owner_id=int(user.id), trade_species=trade_species
        )
        if pokemon is None:
            return oldname, pokename, False
        await self._update_evolved_pokemon(user, orig_data, pokemon)
        return oldname, pokemon["name"], True

    async def evolve(self, pokename, orig_data, new_level, *, owner_id: int | None = None, friendship: int | None = None):
        held_item_name = None
        raw_held = orig_data.get("item")
        if raw_held:
            try:
                held_data = json.loads(raw_held) if isinstance(raw_held, str) else raw_held
                if isinstance(held_data, dict):
                    held_item_name = held_data.get("name")
            except (TypeError, ValueError, json.JSONDecodeError):
                held_item_name = None

        pokemon = await self._find_evolution_target(
            orig_data,
            trigger="level-up",
            level=new_level,
            item=held_item_name,
            friendship=friendship,
            owner_id=owner_id,
        )
        if pokemon is None:
            return False, pokename, None
        return True, pokemon["name"], pokemon

    async def addPokeList(self, ctx, value):
        """Persist a caught Pokémon and reserve its UID atomically.

        The legacy implementation selected ``total_pokemon`` first and updated
        it later, which allowed concurrent catches to reserve the same UID.
        Build the network/API-dependent record before opening a transaction,
        then increment the counter and insert the Pokémon in one DB transaction.
        """
        guild = ctx.guild
        _user = ctx.author
        owner_id = int(_user.id)
        guild_id = int(guild.id)

        # UID is assigned inside the transaction. No external API calls should
        # be held open while a PostgreSQL row lock is active.
        pokeData = await build_pokemon_record(self.api, 0, value, owner_id)
        movesList = [json.dumps(move) for move in pokeData['moves']]
        ivPer = ivPercentage(pokeData)

        sql = 'INSERT INTO pokecord_poke_data_scoped("index", "uid", "type", "lvl", "exp", "color", "height", "weight", "nature", ' \
              '"gender", "base_exp", "base_hp", "base_attack", "base_defense", "base_special_attack", "base_special_defense", ' \
              '"base_speed", "hp_iv", "attack_iv", "defense_iv", "special_attack_iv", "special_defense_iv", "speed_iv", "hp", "battle_hp", "attack", ' \
              '"defense", "sp_attack", "sp_defense", "speed", "item", "selected", "shiny", "lucky", "caughton", "ownerid", "originalownerid", "moves", ' \
              '"name", "traded", "form", "ivpercentage", "friendship") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, ' \
              '$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43)'

        async with db.tenant_connection() as connection:
            async with connection.transaction():
                uid_row = await connection.fetchrow(
                    '''
                    INSERT INTO pokecord_user_state ("ownerid", "next_uid")
                    VALUES ($1, 2)
                    ON CONFLICT ("ownerid") DO UPDATE
                    SET "next_uid" = pokecord_user_state."next_uid" + 1
                    RETURNING "next_uid" - 1 AS "uid"
                    ''',
                    owner_id,
                )
                pokeData['uid'] = int(uid_row['uid'])

                user_row = await connection.fetchrow(
                    '''
                    UPDATE users
                    SET "total_pokemon" = GREATEST(COALESCE("total_pokemon", 0), $1)
                    WHERE "UserID" = $2 AND "ServerID" = $3
                    RETURNING "UserID"
                    ''',
                    pokeData['uid'],
                    owner_id,
                    guild_id,
                )
                if user_row is None:
                    raise RuntimeError(f"Unable to update Pokémon state for user {owner_id}")

                await db.record_pokedex_entry(
                    guild_id,
                    owner_id,
                    int(value.get('dex_id') or value.get('id') or pokeData['index']),
                    str(value['name']),
                    caught_at=int(time.time()),
                    connection=connection,
                )

                caught_on = str(pokeData['caughtBy'][0])
                caught_owner_id = int(pokeData['caughtBy'][1])
                insert_args = (
                    pokeData['index'], pokeData['uid'], pokeData['type'], pokeData['lvl'],
                    pokeData['exp'], pokeData['color'], pokeData['height'], pokeData['weight'],
                    pokeData['nature'], pokeData['gender'], pokeData['base_exp'], pokeData['base_hp'],
                    pokeData['base_attack'], pokeData['base_defense'], pokeData['base_special_attack'],
                    pokeData['base_special_defense'], pokeData['base_speed'], pokeData['hp_iv'],
                    pokeData['attack_iv'], pokeData['defense_iv'], pokeData['special_attack_iv'],
                    pokeData['special_defense_iv'], pokeData['speed_iv'], pokeData['hp'], pokeData['hp'],
                    pokeData['attack'], pokeData['defense'], pokeData['sp_attack'], pokeData['sp_defense'],
                    pokeData['speed'], pokeData['item'], pokeData['selected'], pokeData['shiny'], False,
                    caught_on, caught_owner_id, str(caught_owner_id), movesList, value['name'], 0,
                    pokeData['form'], ivPer, pokeData['friendship'],
                )
                await connection.execute(sql, *insert_args)

        return pokeData

    async def _save_player_catch(self, community_id: int, player_id: int, value: dict) -> dict:
        """Persist a catch for a platform-neutral community player."""
        await self._activate_community(community_id)
        owner_id = int(player_id)
        pokeData = await build_pokemon_record(self.api, 0, value, owner_id)
        movesList = [json.dumps(move) for move in pokeData['moves']]
        ivPer = ivPercentage(pokeData)
        sql = 'INSERT INTO pokecord_poke_data_scoped("index", "uid", "type", "lvl", "exp", "color", "height", "weight", "nature", ' \
              '"gender", "base_exp", "base_hp", "base_attack", "base_defense", "base_special_attack", "base_special_defense", ' \
              '"base_speed", "hp_iv", "attack_iv", "defense_iv", "special_attack_iv", "special_defense_iv", "speed_iv", "hp", "battle_hp", "attack", ' \
              '"defense", "sp_attack", "sp_defense", "speed", "item", "selected", "shiny", "lucky", "caughton", "ownerid", "originalownerid", "moves", ' \
              '"name", "traded", "form", "ivpercentage", "friendship") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, ' \
              '$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43)'
        async with db.tenant_connection(community_id) as connection:
            async with connection.transaction():
                uid_row = await connection.fetchrow(
                    '''
                    INSERT INTO pokecord_user_state ("ownerid", "next_uid")
                    VALUES ($1, 2)
                    ON CONFLICT ("ownerid") DO UPDATE
                    SET "next_uid" = pokecord_user_state."next_uid" + 1
                    RETURNING "next_uid" - 1 AS "uid"
                    ''', owner_id,
                )
                pokeData['uid'] = int(uid_row['uid'])
                await db.record_player_pokedex(
                    community_id, owner_id,
                    int(value.get('dex_id') or value.get('id') or pokeData['index']),
                    str(value['name']), caught_at=int(time.time()), connection=connection,
                )
                caught_on = str(pokeData['caughtBy'][0])
                caught_owner_id = int(pokeData['caughtBy'][1])
                args = (
                    pokeData['index'], pokeData['uid'], pokeData['type'], pokeData['lvl'], pokeData['exp'],
                    pokeData['color'], pokeData['height'], pokeData['weight'], pokeData['nature'], pokeData['gender'],
                    pokeData['base_exp'], pokeData['base_hp'], pokeData['base_attack'], pokeData['base_defense'],
                    pokeData['base_special_attack'], pokeData['base_special_defense'], pokeData['base_speed'],
                    pokeData['hp_iv'], pokeData['attack_iv'], pokeData['defense_iv'], pokeData['special_attack_iv'],
                    pokeData['special_defense_iv'], pokeData['speed_iv'], pokeData['hp'], pokeData['hp'], pokeData['attack'],
                    pokeData['defense'], pokeData['sp_attack'], pokeData['sp_defense'], pokeData['speed'], pokeData['item'],
                    pokeData['selected'], pokeData['shiny'], False, caught_on, caught_owner_id, str(caught_owner_id),
                    movesList, value['name'], 0, pokeData['form'], ivPer, pokeData['friendship'],
                )
                await connection.execute(sql, *args)
        return pokeData

    async def twitch_catch(
        self, community_id: int, player_id: int, twitch_name: str, guess: str
    ) -> str:
        """Try to catch this community's active wild Pokémon from Twitch chat."""
        await self._activate_community(community_id)
        state = self._state(community_id)
        if state.pokestore is None:
            return "There isn't a wild Pokémon to catch right now."
        async with state.capture_lock:
            if state.pokestore is None or state.caught:
                return "Too late — that Pokémon has already been caught!"
            if _normalize_pokemon_guess(state.pokestore['name']) != _normalize_pokemon_guess(guess):
                return f"@{twitch_name} nope — that's not the Pokémon."
            state.caught = True
            caught = dict(state.pokestore)
            saved = await self._save_player_catch(community_id, player_id, caught)
            caught['uid'] = saved['uid']
            state.pokestore = None
            self._cancel_spawn_expiry()
            await self._edit_spawn_view(caught=True)
            state.spawn_msg = None
            self._schedule_spawn()

        pretty = str(caught.get('name') or 'Pokémon').replace('-', ' ').title()
        rarity = RARITY_LABELS.get(caught.get('rarity', 'common'), 'Common')
        shiny = " ✨SHINY" if caught.get('shiny') else ""
        # Tell Discord that Twitch won the shared spawn race, but only in the
        # Discord guild mapped to this community.
        channel = await self._spawn_channel_for_community(community_id)
        if channel is not None:
            try:
                await channel.send(
                    f"🎉 **{twitch_name}** caught **{pretty}** via Twitch! "
                    f"({rarity}{shiny}, UID {saved['uid']})"
                )
            except discord.HTTPException:
                log.exception("Unable to announce Twitch Pokémon catch in Discord")
        return f"🎉 @{twitch_name} caught {pretty}! {rarity}{shiny} · UID {saved['uid']}"

    async def twitch_summary(self, community_id: int, player_id: int, twitch_name: str) -> str:
        await self._activate_community(community_id)
        row = await db.fetchrow(
            '''
            SELECT "uid","name","lvl","ivpercentage","shiny","starred"
            FROM pokecord_poke_data_scoped
            WHERE "ownerid"=$1
            ORDER BY "selected" DESC, "starred" DESC, "uid" DESC
            LIMIT 1
            ''', int(player_id),
        )
        count = int(await db.fetchval(
            'SELECT COUNT(*) FROM pokecord_poke_data_scoped WHERE "ownerid"=$1', int(player_id)
        ) or 0)
        if row is None:
            return f"@{twitch_name} hasn't caught any Pokémon in this community yet."
        shiny = "✨ " if row['shiny'] else ""
        return (
            f"@{twitch_name}: {count} Pokémon · selected {shiny}{str(row['name']).title()} "
            f"Lv.{row['lvl']} · UID {row['uid']} · {float(row['ivpercentage'] or 0):.1f}% IV"
        )

    async def twitch_list(self, community_id: int, player_id: int, twitch_name: str) -> str:
        await self._activate_community(community_id)
        rows = await db.fetch(
            '''
            SELECT "uid","name","lvl","shiny" FROM pokecord_poke_data_scoped
            WHERE "ownerid"=$1 ORDER BY "uid" DESC LIMIT 6
            ''', int(player_id),
        )
        total = int(await db.fetchval(
            'SELECT COUNT(*) FROM pokecord_poke_data_scoped WHERE "ownerid"=$1', int(player_id)
        ) or 0)
        if not rows:
            return f"@{twitch_name} hasn't caught any Pokémon in this community yet."
        names = ", ".join(
            f"#{r['uid']} {'✨' if r['shiny'] else ''}{str(r['name']).title()} Lv.{r['lvl']}" for r in rows
        )
        return f"@{twitch_name}: {total} total · newest: {names}"

    async def twitch_dex(self, community_id: int, player_id: int, twitch_name: str) -> str:
        await self._activate_community(community_id)
        rows = await db.get_player_pokedex(community_id, player_id)
        max_dex = max(1, int(self._pokecord_cfg().get('max_pokemon_id', 1025)))
        caught = len({int(r['dex_id']) for r in rows})
        pct = min(100.0, caught / max_dex * 100)
        return f"@{twitch_name}'s Pokédex: {caught}/{max_dex} ({pct:.1f}%)"

    async def addExpLvlUp(self, user, poke_info, battle: bool = False):
        fresh = await db.fetchrow(
            'SELECT * FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND "uid"=$2',
            int(user.id), int(poke_info['uid']),
        )
        if fresh is not None:
            poke_info = fresh
        current_level = max(1, min(MAX_POKEMON_LEVEL, int(poke_info['lvl'])))
        current_xp = max(calcExp(current_level), int(poke_info['exp'] or 0))

        if current_level >= MAX_POKEMON_LEVEL:
            # Keep legacy rows sane if they already drifted above the level cap.
            capped_xp = calcExp(MAX_POKEMON_LEVEL)
            if int(poke_info['exp'] or 0) != capped_xp or int(poke_info['lvl']) != MAX_POKEMON_LEVEL:
                await helpers.transaction_postgresDatabase(
                    'UPDATE pokecord_poke_data_scoped SET "lvl"=$1, "exp"=$2 WHERE "ownerid"=$3 AND "uid"=$4',
                    MAX_POKEMON_LEVEL, capped_xp, user.id, poke_info['uid'],
                )
            return False, poke_info['name'].capitalize(), poke_info['name'], False, None, False

        new_xp = max(1, gainedExp(poke_info['base_exp'], current_level, poke_info['lucky'], battle))
        updated_xp = min(current_xp + new_xp, calcExp(MAX_POKEMON_LEVEL))

        # A large battle reward can cross more than one threshold. Do not lose
        # those earned levels just because the previous implementation checked
        # only current_level + 1.
        target_level = current_level
        while target_level < MAX_POKEMON_LEVEL and updated_xp >= calcExp(target_level + 1):
            target_level += 1

        level_up = target_level > current_level
        evolved = False
        new_name = poke_info['name']
        pokemon = None

        current_friendship = _friendship_value(poke_info.get('friendship'))
        levels_gained = max(0, target_level - current_level)
        friendship_gain = levels_gained * max(0, int(self._pokecord_cfg().get('friendship_gain_per_level', 5)))
        if battle:
            friendship_gain += max(0, int(self._pokecord_cfg().get('friendship_gain_per_battle', 1)))
        new_friendship = min(255, current_friendship + friendship_gain)

        if level_up:
            evolved, new_name, pokemon = await self.evolve(
                poke_info['name'], poke_info, target_level,
                owner_id=int(user.id), friendship=new_friendship,
            )

        source = pokemon or {
            'id': poke_info['index'],
            'name': poke_info['name'],
            'types': [{'type': {'name': t}} for t in poke_info['type']],
            'base_experience': poke_info['base_exp'],
            'stats': [
                {'base_stat': poke_info['base_hp']}, {'base_stat': poke_info['base_attack']},
                {'base_stat': poke_info['base_defense']}, {'base_stat': poke_info['base_special_attack']},
                {'base_stat': poke_info['base_special_defense']}, {'base_stat': poke_info['base_speed']},
            ],
            'height': poke_info['height'], 'weight': poke_info['weight'],
        }
        level = target_level if level_up else current_level
        bases = [entry['base_stat'] for entry in source['stats']]
        hp = int(calcStat(bases[0], poke_info['hp_iv'], level, bases[0], True))
        old_max_hp = max(1, int(poke_info['hp'] or 1))
        old_current_hp = min(old_max_hp, max(0, int(poke_info.get('battle_hp') if poke_info.get('battle_hp') is not None else old_max_hp)))
        missing_hp = old_max_hp - old_current_hp
        current_hp = 0 if old_current_hp <= 0 else max(1, min(hp, hp - missing_hp))
        attack = int(calcStat(bases[1], poke_info['attack_iv'], level, bases[1], False))
        defense = int(calcStat(bases[2], poke_info['defense_iv'], level, bases[2], False))
        sp_attack = int(calcStat(bases[3], poke_info['special_attack_iv'], level, bases[3], False))
        sp_defense = int(calcStat(bases[4], poke_info['special_defense_iv'], level, bases[4], False))
        speed = int(calcStat(bases[5], poke_info['speed_iv'], level, bases[5], False))
        moves = poke_info['moves']
        if evolved and pokemon is not None:
            moves = [json.dumps(m) for m in await select_damaging_moves(self.api, pokemon)]

        await helpers.transaction_postgresDatabase(
            """UPDATE pokecord_poke_data_scoped SET "index"=$1, "type"=$2, "lvl"=$3, "exp"=$4,
               "base_exp"=$5, "base_hp"=$6, "base_attack"=$7, "base_defense"=$8,
               "base_special_attack"=$9, "base_special_defense"=$10, "base_speed"=$11,
               "hp"=$12, "battle_hp"=$13, "attack"=$14, "defense"=$15,
               "sp_attack"=$16, "sp_defense"=$17, "speed"=$18, "height"=$19,
               "weight"=$20, "name"=$21, "moves"=$22, "friendship"=$23
               WHERE "ownerid"=$24 AND "uid"=$25""",
            source['id'], [x['type']['name'] for x in source['types']], level, updated_xp,
            source.get('base_experience') or 0, *bases, hp, current_hp, attack, defense, sp_attack,
            sp_defense, speed, source['height'], source['weight'], new_name, moves, new_friendship,
            user.id, poke_info['uid'],
        )
        log.debug("Added %s XP to %s (level %s)", new_xp, new_name, level)
        return True, poke_info['name'].capitalize(), new_name, level_up, level if level_up else None, evolved

    def _schedule_spawn(self, delay: float | None = None) -> None:
        # Never queue another wild Pokémon while one is already active.
        if self.pokestore is not None:
            return
        if self._spawn_task is not None and not self._spawn_task.done():
            return

        low = max(5, int(self._pokecord_cfg().get('spawn_min_seconds', 45)))
        high = max(low + 1, int(self._pokecord_cfg().get('spawn_max_seconds', 120)))
        delay = float(delay if delay is not None else random.randint(low, high))
        self.time_to_spawn = datetime.now() + timedelta(seconds=delay)
        self._spawn_task = asyncio.create_task(self._delayed_spawn(delay), name='pokecord-spawn')
        cid = int(db.current_community_id or 0)
        log.info(
            'Pokecord spawn scheduled in %.0f seconds for community %s, channel %s',
            delay,
            cid,
            self.spawn_channel_id,
        )

    async def _delayed_spawn(self, delay: float) -> None:
        retry = False
        try:
            await self.bot.wait_until_ready()
            await asyncio.sleep(max(0, delay))

            cid = int(db.current_community_id or 0)
            if not cid or await self._spawn_channel_for_community(cid) is None:
                log.info(
                    "Pokécord scheduler stopped for community %s: no valid spawn channel is configured",
                    cid,
                )
                self.time_to_spawn = None
                return

            # A manual spawn may have appeared while this timer was sleeping.
            if self.pokestore is not None:
                self.time_to_spawn = None
                return

            await self._spawn()
            retry = self.pokestore is None
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception('Pokecord delayed spawn failed')
            self.time_to_spawn = None
            retry = True
        finally:
            self._spawn_task = None

        # A temporary PokéAPI/Discord/channel failure must not kill spawning.
        if retry and not self.bot.is_closed() and self.pokestore is None:
            retry_delay = max(15, int(self._pokecord_cfg().get('spawn_retry_seconds', 30)))
            log.warning('Pokecord spawn failed; retrying in %s seconds', retry_delay)
            self._schedule_spawn(retry_delay)

    @c.Cog.listener()
    async def on_ready(self):
        # Community schedulers are started by _bootstrap_community_spawns().
        return

    @c.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            cid, _ = await self._activate_guild(guild)
            if not await db.community_feature_enabled(cid, "pokecord", True):
                return

            channel = self._spawn_channel_for_guild(guild)
            if channel is None:
                log.info(
                    "Pokécord scheduler not started for new guild %s: no spawn channel configured",
                    guild.id,
                )
                return

            self._schedule_spawn()
        except Exception:
            log.exception("Unable to start Pokécord scheduler for new guild %s", guild.id)

    @c.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        community_id, community_cfg = await self._activate_guild(message.guild)
        if not await db.community_feature_enabled(community_id, "pokecord", True):
            return
        if self._spawn_channel_for_guild(message.guild) is None:
            # The guild exists in the database, but Pokécord has not been
            # configured for it. Do not inherit another guild's global channel.
            return
        prefix = str(community_cfg.get("bot", {}).get("prefix", config.get("bot", {}).get("prefix", "!")))
        if message.content.startswith(f"{prefix}spawn"):
            return

        poke_info = await helpers.query_postgresDatabase(
            'SELECT * FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND "selected"=$2',
            message.author.id, True,
        )
        if poke_info:
            # Pokémon XP has its own cooldown timestamp. Sharing LastMessage
            # with the bot's normal server-XP listener caused the two systems to
            # race and intermittently suppress Pokémon XP awards.
            await helpers.get_player_postgresData(message.author, message.guild, 'PokeLastMessage')
            now = int(time.time())
            cooldown_cutoff = now - max(1, int(self._pokecord_cfg().get("exp_cooldown", exp_secs)))
            eligible = await helpers.query_postgresDatabase(
                """UPDATE users SET "PokeLastMessage"=$1
                   WHERE "ServerID"=$2 AND "UserID"=$3
                     AND COALESCE("PokeLastMessage", 0) <= $4
                   RETURNING "UserID"
                """,
                now, message.guild.id, message.author.id, cooldown_cutoff,
            )
            if eligible:
                _, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(message.author, poke_info)
                try:
                    if evolved:
                        await message.author.send(f"Congrats! Your {old_name} evolved into {pokename.capitalize()}!")
                    elif levelup:
                        await message.author.send(f"Congrats! Your {pokename.capitalize()} reached level {level}!")
                except discord.Forbidden:
                    pass

        if not self.setToSpawn():
            self._schedule_spawn()


    @app_commands.command(name="help", description="Show the Pokémon command guide")
    async def blak_cord_help(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        text = (
            "**Pokémon Commands**\n\n"
            "`Catch Pokémon` button — Open a private guess box on the wild spawn. `/pokemon catch` remains available as a fallback.\n"
            "Wild spawns use Common/Uncommon/Rare/Epic/Legendary/Mythical tiers; shiny is rolled independently per spawn.\n"
            "`/pokemon list [sorting]` — Browse your collection with paging buttons and a sort menu.\n"
            "`/pokemon info [uid]` — View one Pokémon (or your selected companion).\n"
            "`/pokemon select uid:<uid>` — Set your active companion.\n"
            "`/pokemon favorite uid:<uid>` / `/pokemon unfavorite uid:<uid>` — Manage favorites.\n"
            "`/pokemon dex [page]` — Browse your Pokédex with page controls.\n"
            "`/pokemon release uid:<uid> [confirm]` — Release a Pokémon for credits.\n"
            "`/pokemon shop` / `/pokemon buy <item>` — Browse or buy items.\n"
            "`/pokemon items` — View your bag.\n"
            "`/pokemon use`, `/pokemon give`, `/pokemon take` — Heal, cure, evolve, or manage held items.\n"
            "`/pokemon trade member:<user> your_uid:<uid> their_uid:<uid>` — Propose a trade; both trainers confirm with buttons.\n"
            "`/pokemon battle member:<user> your_uid:<uid> their_uid:<uid>` — Challenge a trainer and battle with move buttons.\n"
            "`/pokemon gym region:<region> leader:<leader> pokemon_uid:<uid>` — Battle a scalable Gym Leader from Gen I–IX.\n"
            "`/pokemon badges [region]` — View your Gym wins and earned badges.\n"
            "`/pokemon latest`, `/pokemon next`, `/pokemon previous` — Browse your collection."
        )
        await ctx.send(text)

    @app_commands.command(name="catch", description="Catch the Pokémon currently spawned")
    async def blak_catch(self, interaction: discord.Interaction, name: str):
        ctx = await self._slash_context(interaction, ephemeral=False)
        """Fallback slash command; the spawn message button is the primary catch UX."""
        if not self.spawn_channel_id or ctx.channel.id == self.spawn_channel_id:
            if len(ctx.message.mentions) >= 1:
                await ctx.send("Please do not use my resources for such menial tasks!")
            elif helpers.check_role(ctx.message.author, self._contributor_role_id()) and len(
                    await helpers.get_pokecord_postgresData(ctx.author, "*")) >= 300:
                await ctx.send(
                    f"{ctx.author.mention}, you have reached your Pokemon Storage Limit! Please release Pokemon to make more room!")
            elif not helpers.check_role(ctx.message.author, self._contributor_role_id()) and len(
                    await helpers.get_pokecord_postgresData(ctx.author, "*")) >= 200:
                await ctx.send(
                    f"{ctx.author.mention}, you have reached your Pokemon Storage Limit! Please release Pokemon to make more room or Subscribe to our Patreon for an extra 100 storage spots!")
            elif self.appeared and not self.caught:
                async with self._capture_lock:
                    if self.appeared and not self.caught:
                        await self.check_capture(ctx.message, name, responder=ctx)
                    else:
                        await ctx.send("The Pokémon has already been caught!")
            elif not self.appeared and self.caught:
                await ctx.send("The Pokemon has already been caught!")
            else:
                await ctx.send("There is no Pokemon currently spawned.")

    @app_commands.command(name="release", description="Release one of your Pokémon for credits")
    async def blak_release(self, interaction: discord.Interaction, uid: int, confirm: bool = False):
        ctx = await self._slash_context(interaction, ephemeral=False)
        """Release a Pokémon. Starred Pokémon require explicit confirmation."""
        poke_sql = 'SELECT name, starred from pokecord_poke_data_scoped WHERE "uid" = $1 and "ownerid" = $2'
        pokeinfo = await helpers.query_postgresDatabase(poke_sql, uid, ctx.author.id)
        if pokeinfo is None:
            await ctx.send(f"You do not own a Pokémon with UID `{uid}`.")
            return

        pokename = pokeinfo['name']
        if pokeinfo['starred'] and not confirm:
            await ctx.send(
                f"⭐ {pokename.capitalize()} is favorited. Run the command again with `confirm: True` to release it."
            )
            return

        users_sql = 'DELETE FROM pokecord_poke_data_scoped WHERE "uid" = $1 AND "ownerid" = $2'
        await helpers.transaction_postgresDatabase(users_sql, uid, ctx.author.id)
        await helpers.add_money(ctx.author, ctx.guild, 100)
        await ctx.send(f"{pokename.capitalize()} has been released. Farewell!\n100 credits added to your account!")

    @app_commands.command(name="trade", description="Trade Pokémon with another member")
    async def blak_trade(self, interaction: discord.Interaction, member: discord.Member, your_uid: int, their_uid: int):
        ctx = await self._slash_context(interaction, ephemeral=False)
        """Trade two Pokémon after both users confirm with buttons."""
        if member.bot:
            await ctx.send("Bots cannot trade Pokémon.")
            return
        if member == ctx.author:
            await ctx.send("You can't trade with yourself.")
            return

        poke_sql = 'SELECT * FROM pokecord_poke_data_scoped WHERE "uid" = $1 AND "ownerid" = $2'
        authorPokeData = await helpers.query_postgresDatabase(poke_sql, your_uid, ctx.author.id)
        tradePokeData = await helpers.query_postgresDatabase(poke_sql, their_uid, member.id)
        if authorPokeData is None:
            await ctx.send(f"You do not own a Pokémon with UID `{your_uid}`.")
            return
        if tradePokeData is None:
            await ctx.send(f"{member.mention} does not own a Pokémon with UID `{their_uid}`.")
            return
        if authorPokeData['traded'] >= 2 or tradePokeData['traded'] >= 2:
            await ctx.send("One of those Pokémon has already reached the trade limit.")
            return

        authorPokeName = authorPokeData['name']
        tradePokeName = tradePokeData['name']
        summary = (
            f"🔄 **Trade Proposal**\n"
            f"{ctx.author.mention}: **{authorPokeName.title()}** (UID `{your_uid}`)\n"
            f"{member.mention}: **{tradePokeName.title()}** (UID `{their_uid}`)\n\n"
            "Both trainers must accept."
        )
        view = ConfirmationView([ctx.author, member], summary, timeout=90)
        message = await ctx.send(content=view._status_text(), view=view)
        view.message = message
        await view.wait()
        if view.decision is not True:
            await ctx.send("Trade cancelled.")
            return

        authorItem = json.loads(authorPokeData['item'])['name'] if authorPokeData['item'] is not None else None
        tradeItem = json.loads(tradePokeData['item'])['name'] if tradePokeData['item'] is not None else None
        authoroldname, authorpokename, authorevolved = await self.tradeEvolve(
            ctx.author, authorPokeName, authorPokeData, authorItem, trade_species=tradePokeName
        )
        tradeoldname, tradepokename, tradeevolved = await self.tradeEvolve(
            member, tradePokeName, tradePokeData, tradeItem, trade_species=authorPokeName
        )
        if tradeevolved:
            tradePokeData = await helpers.query_postgresDatabase(poke_sql, their_uid, member.id)
            tradePokeName = tradepokename
        if authorevolved:
            authorPokeData = await helpers.query_postgresDatabase(poke_sql, your_uid, ctx.author.id)
            authorPokeName = authorpokename

        authorLuckyInt = randomGenerator(1, 5) if ctx.author.id == 290035422011326464 else randomGenerator(1, 20)
        tradeLuckyInt = randomGenerator(1, 5) if member.id == 290035422011326464 else randomGenerator(1, 20)
        if authorLuckyInt == 1 or tradeLuckyInt == 1:
            tradePokeLucky = authorPokeLucky = True
            hp_iv_trade = attack_iv_trade = defense_iv_trade = 12
            special_attack_iv_trade = special_defense_iv_trade = speed_iv_trade = 12
            hp_iv_author = attack_iv_author = defense_iv_author = 12
            special_attack_iv_author = special_defense_iv_author = speed_iv_author = 12
        else:
            authorPokeLucky = bool(authorPokeData['lucky'])
            hp_iv_author, attack_iv_author, defense_iv_author = authorPokeData['hp_iv'], authorPokeData['attack_iv'], authorPokeData['defense_iv']
            special_attack_iv_author, special_defense_iv_author, speed_iv_author = authorPokeData['special_attack_iv'], authorPokeData['special_defense_iv'], authorPokeData['speed_iv']
            tradePokeLucky = bool(tradePokeData['lucky'])
            hp_iv_trade, attack_iv_trade, defense_iv_trade = tradePokeData['hp_iv'], tradePokeData['attack_iv'], tradePokeData['defense_iv']
            special_attack_iv_trade, special_defense_iv_trade, speed_iv_trade = tradePokeData['special_attack_iv'], tradePokeData['special_defense_iv'], tradePokeData['speed_iv']

        insert_sql = 'INSERT INTO pokecord_poke_data_scoped("index", "uid", "type", "lvl", "exp", "color", "height", "weight", "nature", ' \
                     '"gender", "base_exp", "base_hp", "base_attack", "base_defense", "base_special_attack", "base_special_defense", ' \
                     '"base_speed", "hp_iv", "attack_iv", "defense_iv", "special_attack_iv", "special_defense_iv", "speed_iv", "hp", "attack", ' \
                     '"defense", "sp_attack", "sp_defense", "speed", "item", "selected", "shiny", "lucky", "caughton", "ownerid", "originalownerid", "moves", ' \
                     '"name", "traded", "form", "battle_hp", "status", "status_turns", "friendship") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, ' \
                     '$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44)'
        delete_sql = 'DELETE FROM pokecord_poke_data_scoped WHERE "uid" = $1 AND "ownerid" = $2'
        author_args = (
            authorPokeData['index'], tradePokeData['uid'], authorPokeData['type'], authorPokeData['lvl'], authorPokeData['exp'], authorPokeData['color'],
            authorPokeData['height'], authorPokeData['weight'], authorPokeData['nature'], authorPokeData['gender'], authorPokeData['base_exp'], authorPokeData['base_hp'],
            authorPokeData['base_attack'], authorPokeData['base_defense'], authorPokeData['base_special_attack'], authorPokeData['base_special_defense'], authorPokeData['base_speed'],
            hp_iv_author, attack_iv_author, defense_iv_author, special_attack_iv_author, special_defense_iv_author, speed_iv_author,
            authorPokeData['hp'], authorPokeData['attack'], authorPokeData['defense'], authorPokeData['sp_attack'], authorPokeData['sp_defense'], authorPokeData['speed'],
            authorPokeData['item'], authorPokeData['selected'], authorPokeData['shiny'], authorPokeLucky, authorPokeData['caughton'], int(member.id),
            authorPokeData['originalownerid'], authorPokeData['moves'], authorPokeData['name'], authorPokeData['traded'] + 1, authorPokeData['form'],
            int(authorPokeData.get('battle_hp') if authorPokeData.get('battle_hp') is not None else authorPokeData['hp']),
            authorPokeData.get('status'), int(authorPokeData.get('status_turns', 0) or 0),
            _friendship_value(authorPokeData.get('friendship')),
        )
        trade_args = (
            tradePokeData['index'], authorPokeData['uid'], tradePokeData['type'], tradePokeData['lvl'], tradePokeData['exp'], tradePokeData['color'],
            tradePokeData['height'], tradePokeData['weight'], tradePokeData['nature'], tradePokeData['gender'], tradePokeData['base_exp'], tradePokeData['base_hp'],
            tradePokeData['base_attack'], tradePokeData['base_defense'], tradePokeData['base_special_attack'], tradePokeData['base_special_defense'], tradePokeData['base_speed'],
            hp_iv_trade, attack_iv_trade, defense_iv_trade, special_attack_iv_trade, special_defense_iv_trade, speed_iv_trade,
            tradePokeData['hp'], tradePokeData['attack'], tradePokeData['defense'], tradePokeData['sp_attack'], tradePokeData['sp_defense'], tradePokeData['speed'],
            tradePokeData['item'], tradePokeData['selected'], tradePokeData['shiny'], tradePokeLucky, tradePokeData['caughton'], int(ctx.author.id),
            tradePokeData['originalownerid'], tradePokeData['moves'], tradePokeData['name'], tradePokeData['traded'] + 1, tradePokeData['form'],
            int(tradePokeData.get('battle_hp') if tradePokeData.get('battle_hp') is not None else tradePokeData['hp']),
            tradePokeData.get('status'), int(tradePokeData.get('status_turns', 0) or 0),
            _friendship_value(tradePokeData.get('friendship')),
        )
        await db.execute_many_in_transaction([
            (delete_sql, (your_uid, int(ctx.author.id))),
            (delete_sql, (their_uid, int(member.id))),
            (insert_sql, author_args),
            (insert_sql, trade_args),
        ])
        if tradeevolved:
            await ctx.send(f"Congratulations, {member.mention}! Your {tradeoldname} evolved into {tradePokeName.title()}!")
        if authorevolved:
            await ctx.send(f"Congratulations, {ctx.author.mention}! Your {authoroldname} evolved into {authorPokeName.title()}!")
        await ctx.send("✅ Trade completed!")

    async def _battle_turn(self, battle_message, player, attacker, defender, attacker_data, defender_data, author_poke, opponent_poke, author_data, opponent_data):
        embed = await self.battleEmbed(author_poke, opponent_poke, author_data, opponent_data)

        berry_note = await self._maybe_use_held_berry(player.id, attacker_data, attacker)
        can_move, status_note = await attacker.before_turn()
        if not can_move:
            residual = attacker.after_turn()
            name = attacker_data['name'].title()
            pieces = [piece for piece in (berry_note, f"**{name}** {status_note}", residual) if piece]
            return " ".join(pieces)

        view = BattleMoveView(player, attacker_data['moves'], timeout=60)
        view.message = battle_message
        await battle_message.edit(
            content=f"🎮 {player.mention}, choose a move for **{attacker_data['name'].title()}**.",
            embed=embed,
            view=view,
        )
        await view.wait()
        if view.forfeited or view.selected_move is None:
            return None

        result = await attacker.attack(defender, attacker_data, defender_data, view.selected_move)
        move_name = _pretty_move_name({"name": result['move']})
        effectiveness_note = ""
        if result['effectiveness'] > 1:
            effectiveness_note = " It's super effective!"
        elif result['effectiveness'] == 0:
            effectiveness_note = " It had no effect."
        elif result['effectiveness'] < 1:
            effectiveness_note = " It's not very effective."

        notes = []
        if berry_note:
            notes.append(berry_note)
        if status_note:
            notes.append(status_note)
        if result.get('status'):
            notes.append(f"{defender_data['name'].title()} is now {_status_label(result['status']).lower()}.")
        residual = attacker.after_turn() if defender.health > 0 else ""
        if residual:
            notes.append(residual)
        suffix = (" " + " ".join(notes)) if notes else ""
        return f"**{attacker_data['name'].title()}** used **{move_name}** for **{result['damage']}** damage.{effectiveness_note}{suffix}"

    @app_commands.command(name="battle", description="Challenge another member to a Pokémon battle")
    async def blak_battle(self, interaction: discord.Interaction, member: discord.Member, your_uid: int, their_uid: int):
        ctx = await self._slash_context(interaction, ephemeral=False)
        """Interactive button-driven Pokémon battle."""
        if member.bot:
            await ctx.send("Bots cannot battle Pokémon.")
            return
        if member == ctx.author:
            await ctx.send("You can't battle yourself.")
            return

        poke_sql = 'SELECT * FROM pokecord_poke_data_scoped WHERE "uid" = $1 AND "ownerid" = $2'
        authorPokeData = await helpers.query_postgresDatabase(poke_sql, your_uid, ctx.author.id)
        opponentPokeData = await helpers.query_postgresDatabase(poke_sql, their_uid, member.id)
        if authorPokeData is None:
            await ctx.send(f"You do not own a Pokémon with UID `{your_uid}`.")
            return
        if opponentPokeData is None:
            await ctx.send(f"{member.mention} does not own a Pokémon with UID `{their_uid}`.")
            return
        author_current_hp = int(authorPokeData.get('battle_hp') if authorPokeData.get('battle_hp') is not None else authorPokeData['hp'])
        opponent_current_hp = int(opponentPokeData.get('battle_hp') if opponentPokeData.get('battle_hp') is not None else opponentPokeData['hp'])
        if author_current_hp <= 0:
            await ctx.send(f"Your **{authorPokeData['name'].title()}** has fainted. Use a Revive before battling.")
            return
        if opponent_current_hp <= 0:
            await ctx.send(f"{member.mention}'s **{opponentPokeData['name'].title()}** has fainted and cannot battle.")
            return

        summary = (
            f"⚔️ **Battle Challenge**\n"
            f"{ctx.author.mention}: **{authorPokeData['name'].title()}** (UID `{your_uid}`)\n"
            f"{member.mention}: **{opponentPokeData['name'].title()}** (UID `{their_uid}`)\n\n"
            f"{member.mention}, accept the challenge?"
        )
        challenge = ConfirmationView([member], summary, timeout=60)
        challenge_message = await ctx.send(content=challenge._status_text(), view=challenge)
        challenge.message = challenge_message
        await challenge.wait()
        if challenge.decision is not True:
            await ctx.send("Battle challenge declined or timed out.")
            return

        authorPoke = Battle(
            self.api, authorPokeData['hp'], authorPokeData.get('battle_hp'),
            authorPokeData.get('status'), authorPokeData.get('status_turns', 0),
        )
        opponentPoke = Battle(
            self.api, opponentPokeData['hp'], opponentPokeData.get('battle_hp'),
            opponentPokeData.get('status'), opponentPokeData.get('status_turns', 0),
        )
        embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
        battle_message = await ctx.send(content="⚔️ Battle started!", embed=embed)

        winner = loser = None
        last_action = ""
        while authorPoke.health > 0 and opponentPoke.health > 0:
            if opponentPoke.effective_speed(opponentPokeData['speed']) > authorPoke.effective_speed(authorPokeData['speed']):
                turn_order = [
                    (member, opponentPoke, authorPoke, opponentPokeData, authorPokeData),
                    (ctx.author, authorPoke, opponentPoke, authorPokeData, opponentPokeData),
                ]
            else:
                turn_order = [
                    (ctx.author, authorPoke, opponentPoke, authorPokeData, opponentPokeData),
                    (member, opponentPoke, authorPoke, opponentPokeData, authorPokeData),
                ]
            for player, attacker, defender, attacker_data, defender_data in turn_order:
                if attacker.health <= 0 or defender.health <= 0:
                    break
                action = await self._battle_turn(
                    battle_message, player, attacker, defender, attacker_data, defender_data,
                    authorPoke, opponentPoke, authorPokeData, opponentPokeData,
                )
                if action is None:
                    loser = player
                    winner = member if player.id == ctx.author.id else ctx.author
                    last_action = f"🏳️ {player.mention} forfeited or ran out of time."
                    break
                last_action = action
                embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                await battle_message.edit(content=last_action, embed=embed, view=None)
                if defender.health <= 0:
                    winner = player
                    loser = member if player.id == ctx.author.id else ctx.author
                    break
                if attacker.health <= 0:
                    loser = player
                    winner = member if player.id == ctx.author.id else ctx.author
                    break
            if winner is not None:
                break

        await self._persist_two_battle_states(
            ctx.author.id, your_uid, authorPoke,
            member.id, their_uid, opponentPoke,
        )

        winner_data = authorPokeData if winner.id == ctx.author.id else opponentPokeData
        final_embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
        await battle_message.edit(content=f"{last_action}\n\n🏆 {winner.mention} won the battle!", embed=final_embed, view=None)
        completed, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(winner, winner_data, True)
        try:
            if evolved:
                await winner.send(f"Congrats! Your {old_name.capitalize()} evolved into {pokename.capitalize()}!")
            elif levelup:
                await winner.send(f"Congrats! Your {pokename.capitalize()} advanced to level {level}!")
        except discord.Forbidden:
            pass

        winner_credits, loser_credits = battleCredits(winner_data['lvl'])
        await helpers.add_money(winner, ctx.guild, winner_credits)
        await helpers.add_money(loser, ctx.guild, loser_credits)
        await ctx.send(f"💰 {winner.mention} won **{winner_credits} credits** from {loser.mention}.")

    async def _build_gym_pokemon(self, species: str, level: int, *, ace: bool = False) -> dict:
        pokemon = await self.api.pokemon(species)
        moves = await select_damaging_moves(self.api, pokemon)
        stats = [entry["base_stat"] for entry in pokemon["stats"]]
        iv = 15 if ace else 12
        level = max(5, min(MAX_POKEMON_LEVEL, int(level)))
        hp = int(calcStat(stats[0], iv, level, stats[0], True))
        return {
            "index": pokemon["id"],
            "uid": 0,
            "name": pokemon["name"],
            "form": None,
            "type": [entry["type"]["name"] for entry in pokemon["types"]],
            "lvl": level,
            "exp": calcExp(level),
            "base_exp": pokemon.get("base_experience") or 0,
            "base_hp": stats[0],
            "base_attack": stats[1],
            "base_defense": stats[2],
            "base_special_attack": stats[3],
            "base_special_defense": stats[4],
            "base_speed": stats[5],
            "hp": hp,
            "battle_hp": hp,
            "attack": int(calcStat(stats[1], iv, level, stats[1], False)),
            "defense": int(calcStat(stats[2], iv, level, stats[2], False)),
            "sp_attack": int(calcStat(stats[3], iv, level, stats[3], False)),
            "sp_defense": int(calcStat(stats[4], iv, level, stats[4], False)),
            "speed": int(calcStat(stats[5], iv, level, stats[5], False)),
            "moves": [json.dumps(move) for move in moves],
        }

    async def _gym_ai_move(self, attacker_data: dict, defender_data: dict) -> int:
        # Pick a reasonably smart damaging move, with a little unpredictability.
        raw_moves = list(attacker_data.get("moves", []))[:4]
        if not raw_moves:
            return 1
        if len(raw_moves) > 1 and random.random() < 0.15:
            return random.randint(1, len(raw_moves))

        async def detail_for(raw):
            move = json.loads(raw) if isinstance(raw, str) else raw
            return await self.api.get_json(move["url"])

        details = await asyncio.gather(*(detail_for(raw) for raw in raw_moves), return_exceptions=True)
        scored: list[tuple[float, int]] = []
        for index, detail in enumerate(details, start=1):
            if isinstance(detail, Exception):
                continue
            power = float(detail.get("power") or 1)
            move_type = detail.get("type", {}).get("name", "")
            stab = 1.5 if move_type in attacker_data.get("type", []) else 1.0
            type_multiplier = 1.0
            for defending_type in defender_data.get("type", []):
                chart = effectiveness.get(defending_type.lower(), effectiveness.get(defending_type, {}))
                type_multiplier *= chart.get(move_type.capitalize(), 1)
            scored.append((power * stab * type_multiplier, index))
        return max(scored)[1] if scored else 1

    async def _gym_battle_embed(
        self,
        player_battle: Battle,
        leader_battle: Battle,
        player_data: dict,
        leader_data: dict,
        leader: dict,
        region: str,
        defeated: int,
        total: int,
    ) -> discord.Embed:
        region_name = GYM_REGION_META[region]["name"]
        embed = discord.Embed(
            title=f"🏟️ {region_name} Gym — {leader['name']}",
            description=f"**{leader['type']}-type specialist** · {defeated}/{total} Pokémon defeated",
            color=0xE6B800,
        )
        player_moves = "\n".join(
            f"{index}. {_pretty_move_name(move)}"
            for index, move in enumerate(player_data.get("moves", [])[:4], start=1)
        ) or "No moves"
        embed.add_field(
            name=f"🎮 {player_data['name'].title()} · Lv. {player_data['lvl']}",
            value=f"**HP:** {player_battle.health}/{player_data['hp']}\n**Status:** {_status_label(player_battle.status)}\n\n{player_moves}",
            inline=True,
        )
        embed.add_field(
            name=f"🏅 {leader_data['name'].title()} · Lv. {leader_data['lvl']}",
            value=f"**HP:** {leader_battle.health}/{leader_data['hp']}\n**Status:** {_status_label(leader_battle.status)}\n**Type:** {' / '.join(t.title() for t in leader_data['type'])}",
            inline=True,
        )
        remaining = max(0, total - defeated - (1 if leader_battle.health <= 0 else 0))
        embed.add_field(
            name="Leader Team",
            value=f"{'✅' * defeated}{'🔴' if leader_battle.health > 0 else ''}{'⚪' * remaining}",
            inline=False,
        )
        embed.set_footer(text=self._embed_footer())
        return embed

    async def _gym_player_turn(
        self,
        battle_message: discord.Message,
        player: discord.Member,
        player_battle: Battle,
        leader_battle: Battle,
        player_data: dict,
        leader_data: dict,
        leader: dict,
        region: str,
        defeated: int,
        total: int,
    ) -> str | None:
        embed = await self._gym_battle_embed(
            player_battle, leader_battle, player_data, leader_data, leader, region, defeated, total
        )
        berry_note = await self._maybe_use_held_berry(player.id, player_data, player_battle)
        can_move, status_note = await player_battle.before_turn()
        if not can_move:
            residual = player_battle.after_turn()
            pieces = [piece for piece in (berry_note, f"**{player_data['name'].title()}** {status_note}", residual) if piece]
            return " ".join(pieces)

        view = BattleMoveView(player, player_data["moves"], timeout=60)
        view.message = battle_message
        await battle_message.edit(
            content=f"🎮 {player.mention}, choose a move for **{player_data['name'].title()}**.",
            embed=embed,
            view=view,
        )
        await view.wait()
        if view.forfeited or view.selected_move is None:
            return None
        result = await player_battle.attack(leader_battle, player_data, leader_data, view.selected_move)
        note = ""
        if result["effectiveness"] > 1:
            note = " It's super effective!"
        elif result["effectiveness"] == 0:
            note = " It had no effect."
        elif result["effectiveness"] < 1:
            note = " It's not very effective."
        extras = []
        if berry_note:
            extras.append(berry_note)
        if status_note:
            extras.append(status_note)
        if result.get('status'):
            extras.append(f"{leader_data['name'].title()} is now {_status_label(result['status']).lower()}.")
        residual = player_battle.after_turn() if leader_battle.health > 0 else ""
        if residual:
            extras.append(residual)
        suffix = (" " + " ".join(extras)) if extras else ""
        return f"**{player_data['name'].title()}** used **{_pretty_move_name({'name': result['move']})}** for **{result['damage']}** damage.{note}{suffix}"

    async def _record_gym_win(self, guild_id: int, user_id: int, region: str, leader: dict) -> bool:
        existing = await db.fetchrow(
            '''SELECT wins FROM pokecord_gym_badges
               WHERE "ServerID"=$1 AND "UserID"=$2 AND region=$3 AND leader=$4''',
            guild_id, user_id, region, leader["key"],
        )
        now = int(time.time())
        await db.execute(
            '''INSERT INTO pokecord_gym_badges
               ("ServerID", "UserID", region, leader, badge, wins, first_won_at, last_won_at)
               VALUES ($1, $2, $3, $4, $5, 1, $6, $6)
               ON CONFLICT ("ServerID", "UserID", region, leader)
               DO UPDATE SET wins = pokecord_gym_badges.wins + 1,
                             badge = EXCLUDED.badge,
                             last_won_at = EXCLUDED.last_won_at''',
            guild_id, user_id, region, leader["key"], leader["badge"], now,
        )
        return existing is None

    @app_commands.command(name="gym", description="Battle a Gym Leader from any generation")
    @app_commands.choices(region=GYM_REGION_CHOICES)
    async def gym_battle(self, interaction: discord.Interaction, region: str, leader: str, pokemon_uid: int):
        ctx = await self._slash_context(interaction, ephemeral=False)
        leader_data = GYM_LEADER_INDEX.get(region, {}).get(str(leader).lower())
        if leader_data is None:
            await ctx.send("Choose a valid Gym Leader from the autocomplete list.")
            return

        player_data = await helpers.query_postgresDatabase(
            'SELECT * FROM pokecord_poke_data_scoped WHERE "uid"=$1 AND "ownerid"=$2',
            pokemon_uid, ctx.author.id,
        )
        if player_data is None:
            await ctx.send(f"You do not own a Pokémon with UID `{pokemon_uid}`.")
            return
        player_current_hp = int(player_data.get('battle_hp') if player_data.get('battle_hp') is not None else player_data['hp'])
        if player_current_hp <= 0:
            await ctx.send(f"Your **{player_data['name'].title()}** has fainted. Use a Revive before challenging a Gym.")
            return

        player_level = max(5, min(MAX_POKEMON_LEVEL, int(player_data["lvl"])))
        difficulty_offset = max(-2, min(4, int(leader_data["order"]) - 4))
        ace_level = max(5, min(MAX_POKEMON_LEVEL, player_level + difficulty_offset))
        species_team = list(leader_data["team"])
        levels = [
            max(5, min(MAX_POKEMON_LEVEL, ace_level - (len(species_team) - 1 - index)))
            for index in range(len(species_team))
        ]

        try:
            built = await asyncio.gather(*(
                self._build_gym_pokemon(species, level, ace=(index == len(species_team) - 1))
                for index, (species, level) in enumerate(zip(species_team, levels))
            ))
        except (PokeAPIError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Unable to build Gym Leader team for %s: %s", leader_data["name"], exc)
            await ctx.send("The Gym Leader couldn't prepare their team right now. Try again shortly.")
            return

        region_name = GYM_REGION_META[region]["name"]
        intro = (
            f"🏟️ **{region_name} Gym Challenge**\n"
            f"{ctx.author.mention} vs **{leader_data['name']}**, {leader_data['type']}-type specialist\n"
            f"Your Pokémon: **{player_data['name'].title()}** · Lv. {player_level}\n"
            f"Leader team: **{len(built)} Pokémon** · Ace Lv. **{ace_level}**"
        )
        battle_message = await ctx.send(content=intro)
        player_battle = Battle(
            self.api, player_data["hp"], player_data.get("battle_hp"),
            player_data.get("status"), player_data.get("status_turns", 0),
        )
        defeated = 0
        last_action = ""

        for gym_index, gym_pokemon in enumerate(built):
            leader_battle = Battle(self.api, gym_pokemon["hp"], gym_pokemon["hp"])
            while player_battle.health > 0 and leader_battle.health > 0:
                player_first = player_battle.effective_speed(player_data["speed"]) >= leader_battle.effective_speed(gym_pokemon["speed"])
                turn_order = ("player", "leader") if player_first else ("leader", "player")

                for actor in turn_order:
                    if player_battle.health <= 0 or leader_battle.health <= 0:
                        break
                    if actor == "player":
                        action = await self._gym_player_turn(
                            battle_message, ctx.author, player_battle, leader_battle,
                            player_data, gym_pokemon, leader_data, region, defeated, len(built),
                        )
                        if action is None:
                            await self._save_battle_state(ctx.author.id, pokemon_uid, player_battle)
                            await battle_message.edit(
                                content=f"🏳️ {ctx.author.mention} forfeited the Gym challenge.",
                                view=None,
                            )
                            return
                        last_action = action
                    else:
                        can_move, status_note = await leader_battle.before_turn()
                        if not can_move:
                            residual = leader_battle.after_turn()
                            last_action = f"**{leader_data['name']}'s {gym_pokemon['name'].title()}** {status_note}"
                            if residual:
                                last_action += f" {residual}"
                        else:
                            move_index = await self._gym_ai_move(gym_pokemon, player_data)
                            result = await leader_battle.attack(player_battle, gym_pokemon, player_data, move_index)
                            note = ""
                            if result["effectiveness"] > 1:
                                note = " It's super effective!"
                            elif result["effectiveness"] == 0:
                                note = " It had no effect."
                            elif result["effectiveness"] < 1:
                                note = " It's not very effective."
                            extras = []
                            if status_note:
                                extras.append(status_note)
                            if result.get('status'):
                                extras.append(f"{player_data['name'].title()} is now {_status_label(result['status']).lower()}.")
                            residual = leader_battle.after_turn() if player_battle.health > 0 else ""
                            if residual:
                                extras.append(residual)
                            suffix = (" " + " ".join(extras)) if extras else ""
                            last_action = (
                                f"**{leader_data['name']}'s {gym_pokemon['name'].title()}** used "
                                f"**{_pretty_move_name({'name': result['move']})}** for **{result['damage']}** damage.{note}{suffix}"
                            )

                    embed = await self._gym_battle_embed(
                        player_battle, leader_battle, player_data, gym_pokemon,
                        leader_data, region, defeated, len(built),
                    )
                    await battle_message.edit(content=last_action, embed=embed, view=None)

            if player_battle.health <= 0:
                await self._save_battle_state(ctx.author.id, pokemon_uid, player_battle)
                final_embed = await self._gym_battle_embed(
                    player_battle, leader_battle, player_data, gym_pokemon,
                    leader_data, region, defeated, len(built),
                )
                await battle_message.edit(
                    content=f"💥 **{leader_data['name']}** defeated {ctx.author.mention}. Train up and challenge the Gym again!",
                    embed=final_embed,
                    view=None,
                )
                return

            defeated += 1
            if gym_index < len(built) - 1:
                next_pokemon = built[gym_index + 1]
                await battle_message.edit(
                    content=(
                        f"✅ **{gym_pokemon['name'].title()}** fainted! "
                        f"{leader_data['name']} sends out **{next_pokemon['name'].title()}**!"
                    ),
                    view=None,
                )
                await asyncio.sleep(1)

        await self._save_battle_state(ctx.author.id, pokemon_uid, player_battle)
        first_win = await self._record_gym_win(ctx.guild.id, ctx.author.id, region, leader_data)
        reward = (player_level * 100) + (int(leader_data["order"]) * 250) + (1000 if first_win else 0)
        await helpers.add_money(ctx.author, ctx.guild, reward)
        _, old_name, new_name, levelup, new_level, evolved = await self.addExpLvlUp(ctx.author, player_data, True)

        badge_text = f"🏅 **{leader_data['badge']} earned!**" if first_win else f"🏅 **{leader_data['badge']} defended again!**"
        progress = await db.fetchrow(
            'SELECT COUNT(*) AS total FROM pokecord_gym_badges WHERE "ServerID"=$1 AND "UserID"=$2 AND region=$3',
            ctx.guild.id, ctx.author.id, region,
        )
        count = int(progress["total"]) if progress else 0
        extras = ""
        if evolved:
            extras = f"\n✨ Your {old_name} evolved into **{new_name.title()}**!"
        elif levelup:
            extras = f"\n⬆️ **{new_name.title()}** reached level **{new_level}**!"
        final_embed = discord.Embed(
            title=f"🏆 {region_name} Gym Victory!",
            description=(
                f"{ctx.author.mention} defeated **{leader_data['name']}**!\n"
                f"{badge_text}\n"
                f"💰 **{reward:,} credits** awarded\n"
                f"📛 Region progress: **{count}/{len(GYM_LEADERS[region])}** leaders defeated"
                f"{extras}"
            ),
            color=0xFFD700,
        )
        final_embed.set_footer(text=self._embed_footer())
        await battle_message.edit(content=None, embed=final_embed, view=None)

    @app_commands.command(name="badges", description="View your Gym Leader victories and badges")
    @app_commands.choices(region=GYM_REGION_CHOICES)
    async def gym_badges(self, interaction: discord.Interaction, region: Optional[str] = None):
        ctx = await self._slash_context(interaction)
        if region:
            rows = await db.fetch(
                '''SELECT leader, badge, wins, first_won_at FROM pokecord_gym_badges
                   WHERE "ServerID"=$1 AND "UserID"=$2 AND region=$3 ORDER BY first_won_at''',
                ctx.guild.id, ctx.author.id, region,
            )
            meta = GYM_REGION_META[region]
            embed = discord.Embed(
                title=f"🏅 {ctx.author.display_name}'s {meta['name']} Badges",
                color=0xFFD700,
            )
            if not rows:
                embed.description = "No Gym victories in this region yet."
            else:
                lines = []
                for row in rows:
                    leader_info = GYM_LEADER_INDEX.get(region, {}).get(row["leader"], {"name": row["leader"].title()})
                    lines.append(f"✅ **{leader_info['name']}** — {row['badge']} · {row['wins']} win(s)")
                embed.description = "\n".join(lines)
            embed.set_footer(text=f"{len(rows)}/{len(GYM_LEADERS[region])} leaders defeated · {self._embed_footer()}")
            await ctx.send(embed=embed)
            return

        rows = await db.fetch(
            '''SELECT region, COUNT(*) AS total, SUM(wins) AS wins
               FROM pokecord_gym_badges
               WHERE "ServerID"=$1 AND "UserID"=$2
               GROUP BY region''',
            ctx.guild.id, ctx.author.id,
        )
        progress = {row["region"]: row for row in rows}
        embed = discord.Embed(title=f"🏅 {ctx.author.display_name}'s Gym Progress", color=0xFFD700)
        for region_key, meta in GYM_REGION_META.items():
            row = progress.get(region_key)
            count = int(row["total"]) if row else 0
            wins = int(row["wins"]) if row else 0
            suffix = " · Island Grand Trials" if region_key == "alola" else ""
            embed.add_field(
                name=f"Gen {meta['generation']} · {meta['name']}{suffix}",
                value=f"**{count}/{len(GYM_LEADERS[region_key])}** defeated · {wins} total win(s)",
                inline=False,
            )
        embed.set_footer(text=self._embed_footer())
        await ctx.send(embed=embed)

    async def battleEmbed(self, authorPoke, opponentPoke, authorData, opponentData):
        embed = discord.Embed(type="rich", title="__Pokémon Battle__", color=0xEEE8AA)

        def display_name(data):
            name = data['name'].title()
            form = data.get('form')
            if form:
                name += " (Alolan)" if form == 'alolan' else f" ({str(form).title()})"
            return name

        def move_list(data):
            return "\n".join(
                f"{index}. {_pretty_move_name(move)}"
                for index, move in enumerate(data['moves'][:4], start=1)
            )

        embed.add_field(
            name=display_name(authorData),
            value=f"**HP**: {authorPoke.health}/{authorData['hp']}\n**Status:** {_status_label(authorPoke.status)}\n\n{move_list(authorData)}",
            inline=True,
        )
        embed.add_field(
            name=display_name(opponentData),
            value=f"**HP**: {opponentPoke.health}/{opponentData['hp']}\n**Status:** {_status_label(opponentPoke.status)}\n\n{move_list(opponentData)}",
            inline=True,
        )
        embed.set_footer(text=self._embed_footer())
        return embed

    async def storeEmbed(self):
        now = time.monotonic()
        if self._store_cache and now - self._store_cache[0] < 21600:
            item_list = [row.copy() for row in self._store_cache[1]]
        else:
            # Start with a complete local catalog so the shop can NEVER become
            # empty because PokéAPI is unavailable or changes response shape.
            price_by_name = {name: cost for name, cost in _store_fallback_rows()}
            candidate_names = set(price_by_name)

            # PokéAPI is enrichment, not a dependency. It can contribute newly
            # categorized evolution items and newer official prices.
            try:
                evo_items = await self.api.get_json("item-category/evolution/")
                for resource in evo_items.get("items", []):
                    name = _canonical_item_name(resource.get("name"))
                    if name:
                        candidate_names.add(name)
            except Exception as exc:
                log.warning("Unable to load PokéAPI evolution category; using local catalog: %s", exc)

            async def enrich(name: str):
                try:
                    item = await self.api.item(name)
                    return name, item
                except Exception as exc:
                    return name, exc

            results = await asyncio.gather(*(enrich(name) for name in sorted(candidate_names)))
            enriched = 0
            failures = 0
            for name, result in results:
                if isinstance(result, Exception):
                    failures += 1
                    continue
                official_cost = _item_purchase_price(result)
                if official_cost > 0:
                    price_by_name[name] = official_cost
                    enriched += 1

            # Items discovered from the API are only added when they have an
            # official positive price. Local catalog items always remain.
            item_list = [
                [name, int(cost)]
                for name, cost in price_by_name.items()
                if int(cost) > 0
            ]
            item_list.sort(key=lambda row: row[0])
            self._store_cache = (now, [row.copy() for row in item_list])
            log.info(
                "Pokémon store catalog built: %d items (%d official prices, %d API failures)",
                len(item_list), enriched, failures,
            )

        embed = discord.Embed(type="rich", title="__Pokémon Store__", color=0xEEE8AA)
        price_map = {name: int(cost) for name, cost in item_list}

        def section(title: str, names) -> str:
            rows = [
                f"• **{name.replace('-', ' ').title()}** — {price_map[name]:,} credits"
                for name in names if name in price_map
            ]
            return f"**{title}**\n" + ("\n".join(rows) if rows else "None")

        evolution_names = [
            name for name, _ in item_list
            if name not in SHOP_MEDICINE_ITEMS and name not in SHOP_BERRY_ITEMS
        ]
        embed.description = (
            section("🧪 Medicine", SHOP_MEDICINE_ITEMS) + "\n\n"
            + section("🍓 Berries", SHOP_BERRY_ITEMS) + "\n\n"
            + section("✨ Evolution Items", evolution_names)
        )[:4000]
        embed.set_footer(text=f"Use /pokemon buy to purchase an item · {self._embed_footer()}")
        return embed

    @app_commands.command(name="shop", description="View the Pokémon item shop")
    async def blak_store(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        if self.spawn_channel_id and ctx.channel.id != self.spawn_channel_id:
            await ctx.send(f"Please use <#{self.spawn_channel_id}> for this command")
            return
        embed = await self.storeEmbed()
        await ctx.send(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the Pokémon shop")
    @app_commands.describe(item="Medicine, berry, or evolution item to purchase")
    async def buy(self, interaction: discord.Interaction, item: str):
        ctx = await self._slash_context(interaction)
        if self.spawn_channel_id and ctx.channel.id != self.spawn_channel_id:
            await ctx.send(f"Please use <#{self.spawn_channel_id}> for this command")
            return

        item_name = _canonical_item_name(item)
        catalog = {name: int(cost) for name, cost in (self._store_cache[1] if self._store_cache else _store_fallback_rows())}
        if item_name not in catalog:
            await ctx.send("That item is not available in the Pokémon shop.")
            return

        cost = catalog[item_name]
        api_id = None
        sprite = None
        try:
            api_item = await self.api.item(item_name)
            api_id = api_item.get('id')
            sprite = (api_item.get('sprites') or {}).get('default')
            latest_cost = _item_purchase_price(api_item)
            if latest_cost > 0:
                cost = latest_cost
        except Exception as exc:
            log.debug("PokéAPI item enrichment failed for %s: %s", item_name, exc)

        # Ensure the guild-local economy row exists, then debit credits and add
        # the item in the same transaction. Concurrent purchases cannot overspend.
        await db.get_player_postgresData(ctx.author, ctx.guild, 'Credits')
        async with db.tenant_connection() as conn:
            async with conn.transaction():
                balance = await conn.fetchval(
                    '''
                    UPDATE users
                    SET "Credits" = "Credits" - $1
                    WHERE "UserID" = $2 AND "ServerID" = $3
                      AND COALESCE("Credits", 0) >= $1
                    RETURNING "Credits"
                    ''',
                    int(cost), int(ctx.author.id), int(ctx.guild.id),
                )
                if balance is not None:
                    await db.add_inventory_item(
                        ctx.guild.id, ctx.author.id, item_name,
                        quantity=1, item_api_id=api_id, purchase_cost=cost,
                        sprite_url=sprite, connection=conn,
                    )

        if balance is None:
            await ctx.send("You don't have enough Credits for this purchase!")
            return

        await ctx.send(
            f"Successfully purchased **{item_name.replace('-', ' ').title()}** "
            f"for **{cost:,} credits**. Balance: **{int(balance):,}**."
        )

    @app_commands.command(name="items", description="View the items in your bag")
    async def blak_items(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        rows = await db.get_inventory(ctx.guild.id, ctx.author.id)
        if not rows:
            await ctx.send(f"{ctx.author.mention}, your bag is empty!")
            return

        embed = discord.Embed(
            type="rich",
            title=f"__{ctx.author.name}'s Item Bag__",
            color=0xEEE8AA,
        )
        lines = [
            f"__**{str(row['item_name']).replace('-', ' ').title()}**__ — **x{int(row['quantity'])}**"
            for row in rows
        ]
        embed.description = "\n".join(lines)[:4000]
        embed.set_footer(text=self._embed_footer())
        await ctx.send(embed=embed)

    @app_commands.command(name="use", description="Use a healing, status, berry, or evolution item on a Pokémon")
    @app_commands.describe(item="Item from your bag", pokemon_uid="Pokémon to use it on")
    async def item_use(self, interaction: discord.Interaction, item: str, pokemon_uid: int):
        ctx = await self._slash_context(interaction)
        item_name = _canonical_item_name(item)
        held = await db.get_inventory_item(ctx.guild.id, ctx.author.id, item_name)
        poke_info = await helpers.query_postgresDatabase(
            'SELECT * FROM pokecord_poke_data_scoped WHERE "ownerid" = $1 AND "uid" = $2',
            ctx.author.id, pokemon_uid,
        )
        if poke_info is None:
            await ctx.send("Pokémon UID does not match any Pokémon in your Box!")
            return
        if held is None:
            await ctx.send(f"You do not have **{item_name.replace('-', ' ').title()}** in your bag.")
            return

        handled, consume, message = await self._use_recovery_item(ctx, poke_info, item_name)
        if handled:
            if consume:
                consumed = await db.consume_inventory_item(ctx.guild.id, ctx.author.id, item_name)
                if consumed is None:
                    log.warning("Inventory race while consuming %s for user %s", item_name, ctx.author.id)
            await ctx.send(message)
            return

        oldname, pokename, evolved = await self.itemEvolve(
            ctx.author, poke_info['name'], poke_info, item_name,
        )
        if not evolved:
            await ctx.send("This item is not compatible with this Pokémon.")
            return

        consumed = await db.consume_inventory_item(ctx.guild.id, ctx.author.id, item_name)
        if consumed is None:
            log.warning("Inventory race while consuming evolution item %s for user %s", item_name, ctx.author.id)
        await ctx.send(f"Congratulations! You evolved your {oldname.capitalize()} into a {pokename.capitalize()}")

    @app_commands.command(name="give", description="Give an item to a Pokémon")
    @app_commands.describe(item="Item from your bag", pokemon_uid="Pokémon that should hold it")
    async def item_give(self, interaction: discord.Interaction, item: str, pokemon_uid: int):
        ctx = await self._slash_context(interaction)
        item_name = _canonical_item_name(item)
        if item_name in SHOP_MEDICINE_ITEMS:
            await ctx.send("Medicine can't be held. Use `/pokemon use` to give it to a Pokémon directly.")
            return

        error_message = None
        pokemon_name = None
        async with db.tenant_connection() as conn:
            async with conn.transaction():
                poke_info = await conn.fetchrow(
                    'SELECT "name", "item" FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND "uid"=$2 FOR UPDATE',
                    int(ctx.author.id), int(pokemon_uid),
                )
                if poke_info is None:
                    error_message = "Pokémon UID does not match any Pokémon in your Box!"
                elif poke_info['item']:
                    error_message = f"{poke_info['name'].title()} is already holding an item. Use `/pokemon take` first."
                else:
                    item_row = await db.get_inventory_item(
                        ctx.guild.id, ctx.author.id, item_name, connection=conn, for_update=True,
                    )
                    if item_row is None:
                        error_message = f"You do not have **{item_name.replace('-', ' ').title()}** in your bag."
                    else:
                        held_payload = {
                            'id': item_row['item_api_id'],
                            'name': item_name,
                            'cost': item_row['purchase_cost'],
                            'sprite': item_row['sprite_url'],
                            'total': 1,
                        }
                        consumed = await db.consume_inventory_item(
                            ctx.guild.id, ctx.author.id, item_name, connection=conn,
                        )
                        if consumed is None:
                            error_message = f"You do not have **{item_name.replace('-', ' ').title()}** in your bag."
                        else:
                            await conn.execute(
                                'UPDATE pokecord_poke_data_scoped SET "item"=$1 WHERE "ownerid"=$2 AND "uid"=$3',
                                json.dumps(held_payload), int(ctx.author.id), int(pokemon_uid),
                            )
                            pokemon_name = str(poke_info['name'])

        if error_message:
            await ctx.send(error_message)
            return
        await ctx.send(f"Gave {pokemon_name.title()} **{item_name.replace('-', ' ').title()}**.")

    @app_commands.command(name="take", description="Take the held item from a Pokémon")
    async def item_take(self, interaction: discord.Interaction, pokemon_uid: int):
        ctx = await self._slash_context(interaction)
        error_message = None
        pokemon_name = None
        item_name = None
        async with db.tenant_connection() as conn:
            async with conn.transaction():
                poke_info = await conn.fetchrow(
                    'SELECT "name", "item" FROM pokecord_poke_data_scoped WHERE "ownerid"=$1 AND "uid"=$2 FOR UPDATE',
                    int(ctx.author.id), int(pokemon_uid),
                )
                if poke_info is None:
                    error_message = "That Pokémon UID does not exist in your collection."
                elif not poke_info['item']:
                    error_message = f"{poke_info['name'].title()} is not holding an item."
                else:
                    try:
                        held = json.loads(poke_info['item']) if isinstance(poke_info['item'], str) else dict(poke_info['item'])
                    except (TypeError, ValueError, json.JSONDecodeError):
                        held = None
                    item_name = _canonical_item_name(held.get('name')) if held else ""
                    if not item_name:
                        error_message = "The held item data is invalid and could not be returned to your bag."
                    else:
                        raw_api_id = held.get('id')
                        raw_cost = held.get('cost')
                        try:
                            held_api_id = int(raw_api_id) if raw_api_id is not None else None
                        except (TypeError, ValueError):
                            held_api_id = None
                        try:
                            held_cost = int(raw_cost) if raw_cost is not None else None
                        except (TypeError, ValueError):
                            held_cost = None
                        await db.add_inventory_item(
                            ctx.guild.id, ctx.author.id, item_name, quantity=1,
                            item_api_id=held_api_id, purchase_cost=held_cost,
                            sprite_url=held.get('sprite'), connection=conn,
                        )
                        await conn.execute(
                            'UPDATE pokecord_poke_data_scoped SET "item"=NULL WHERE "ownerid"=$1 AND "uid"=$2',
                            int(ctx.author.id), int(pokemon_uid),
                        )
                        pokemon_name = str(poke_info['name'])

        if error_message:
            await ctx.send(error_message)
            return
        await ctx.send(
            f"Took **{item_name.replace('-', ' ').title()}** from {pokemon_name.title()} and returned it to your bag."
        )

    @app_commands.command(name="spawn", description="Owner: manually spawn a Pokémon by name or National Dex number")
    @app_commands.describe(
        pokemon="Pokémon name or National Dex number (for example: Pikachu or 25)",
        shiny="Whether the manually spawned Pokémon should be shiny",
    )
    async def cmd_spawn(
        self,
        interaction: discord.Interaction,
        pokemon: Optional[str] = None,
        shiny: bool = False,
    ):
        ctx = await self._slash_context(interaction)
        if not await self._require_owner(interaction, ctx):
            return
        await self._delete_invocation(ctx)

        # Prevent the automatic timer from creating a second spawn on top of
        # the owner's manual spawn.
        if self._spawn_task is not None and not self._spawn_task.done():
            self._spawn_task.cancel()
            self._spawn_task = None
        self._cancel_spawn_expiry()
        self.time_to_spawn = None

        await self._spawn(pokemon, True, shiny)
        await ctx.send("Manual Pokémon spawn requested.")

    async def _load_spawn_candidate(self, base_id: int) -> tuple[dict, dict]:
        identifier = base_id
        if base_id in alolan_pokemon and random.choice((False, True)):
            identifier = alolanIds[alolan_pokemon.index(base_id)]
        pokemon = await self.api.pokemon(identifier)
        species = await self.api.get_json(pokemon["species"]["url"])
        rarity = pokemon_rarity(species)
        self._rarity_pools.setdefault(rarity, set()).add(int(species.get("id", base_id)))
        return pokemon, species

    def _spawn_repeat_window(self) -> int:
        """Number of recent species to avoid repeating in one community."""
        try:
            return max(1, int(self._pokecord_cfg().get("spawn_repeat_window", 8)))
        except (TypeError, ValueError):
            return 8

    def _remember_spawn_species(self, species_id: int, community_id: int | None = None) -> None:
        state = self._state(community_id)
        species_id = int(species_id)
        state.recent_species.append(species_id)
        window = self._spawn_repeat_window()
        if len(state.recent_species) > window:
            del state.recent_species[:-window]

    def _eligible_cached_species(self, rarity: str, recent: set[int]) -> list[int]:
        pool = self._rarity_pools.get(rarity) or set()
        return [species_id for species_id in pool if int(species_id) not in recent]

    async def _choose_spawn_candidate(self, target_rarity: str, max_dex: int) -> tuple[dict, dict]:
        """Choose a varied species while preserving the configured rarity roll.

        The old selector reused a cached rarity member 85% of the time. When a
        tier had only one or two discovered species, that made repeats extremely
        common. We now avoid the community's recent spawn history whenever
        possible and keep discovering candidates until each rarity cache has a
        useful amount of variety.
        """
        state = self._state()
        recent = {int(species_id) for species_id in state.recent_species}
        pool = self._rarity_pools.setdefault(target_rarity, set())

        try:
            target_pool_size = max(4, int(self._pokecord_cfg().get("spawn_pool_target_size", 10)))
        except (TypeError, ValueError):
            target_pool_size = 10
        try:
            cache_reuse_chance = float(self._pokecord_cfg().get("spawn_cache_reuse_chance", 0.65))
        except (TypeError, ValueError):
            cache_reuse_chance = 0.65
        cache_reuse_chance = max(0.0, min(1.0, cache_reuse_chance))

        eligible = self._eligible_cached_species(target_rarity, recent)
        if eligible and len(pool) >= target_pool_size and random.random() < cache_reuse_chance:
            return await self._load_spawn_candidate(random.choice(eligible))

        attempts_by_tier = {
            "common": 20,
            "uncommon": 30,
            "rare": 45,
            "epic": 60,
            "legendary": 80,
            "mythical": 240,
        }
        attempts = attempts_by_tier.get(target_rarity, 40)
        for _ in range(attempts):
            base_id = random.randint(1, max_dex)
            try:
                pokemon, species = await self._load_spawn_candidate(base_id)
            except PokeAPIError:
                continue
            if pokemon_rarity(species) != target_rarity:
                continue
            species_id = int(species.get("id", base_id))
            if species_id in recent:
                continue
            return pokemon, species

        # Discovery may have broadened this tier even if the sampled candidate
        # itself was recently seen. Prefer any now-known non-recent member.
        eligible = self._eligible_cached_species(target_rarity, recent)
        if eligible:
            return await self._load_spawn_candidate(random.choice(eligible))

        # If the rolled tier cannot produce a fresh species, preserve variety by
        # falling down through adjacent tiers before allowing an immediate repeat.
        fallback_order = {
            "mythical": ("legendary", "epic", "rare", "uncommon", "common"),
            "legendary": ("epic", "rare", "uncommon", "common"),
            "epic": ("rare", "uncommon", "common"),
            "rare": ("uncommon", "common"),
            "uncommon": ("common",),
            "common": (),
        }
        for fallback in fallback_order.get(target_rarity, ()):
            fallback_eligible = self._eligible_cached_species(fallback, recent)
            if fallback_eligible:
                log.warning(
                    "Pokecord could not find a fresh %s; falling back to fresh %s",
                    target_rarity, fallback,
                )
                return await self._load_spawn_candidate(random.choice(fallback_eligible))

        # Last-resort discovery still honors the recent-spawn exclusion.
        for _ in range(24):
            base_id = random.randint(1, max_dex)
            try:
                pokemon, species = await self._load_spawn_candidate(base_id)
            except PokeAPIError:
                continue
            species_id = int(species.get("id", base_id))
            if species_id not in recent:
                return pokemon, species

        # Only repeat when every reasonable fresh-species path failed. This keeps
        # spawning alive during API outages or extremely restrictive configs.
        repeat_pool = self._rarity_pools.get(target_rarity) or set()
        if repeat_pool:
            repeated = random.choice(tuple(repeat_pool))
            log.warning(
                "Pokecord exhausted fresh candidates for %s; allowing repeat species %s",
                target_rarity, repeated,
            )
            return await self._load_spawn_candidate(repeated)

        raise PokeAPIError("Unable to find a spawn candidate")

    async def _spawn(self, message=None, command=False, shiny=False, manual=False):
        self.caught = False
        cid = int(db.current_community_id or 0)
        channel = await self._spawn_channel_for_community(cid) if cid else None
        if channel is None:
            log.warning(
                "Pokecord spawn skipped for community %s: channel %s is not configured in that community's guild",
                cid,
                self.spawn_channel_id,
            )
            self.time_to_spawn = None
            return

        max_dex = max(1, int(self._pokecord_cfg().get("max_pokemon_id", 1025)))

        if message is not None:
            raw_identifier = str(message).strip()
            if not raw_identifier:
                await channel.send("Give me a Pokémon name or National Dex number.")
                return

            # Numeric input keeps the existing Dex-number path, including the
            # chance for supported regional forms. Text input is normalized to
            # PokéAPI's identifier format (e.g. "Mr Mime" -> "mr-mime").
            try:
                base_id = int(raw_identifier)
            except ValueError:
                identifier = raw_identifier.lower().replace("_", "-").replace(" ", "-")
                while "--" in identifier:
                    identifier = identifier.replace("--", "-")
                try:
                    pokemon = await self.api.pokemon(identifier)
                    species = await self.api.get_json(pokemon["species"]["url"])
                    rarity = pokemon_rarity(species)
                    self._rarity_pools.setdefault(rarity, set()).add(int(species["id"]))
                except (KeyError, TypeError, ValueError, PokeAPIError) as exc:
                    log.warning("Unable to load manual Pokémon spawn %r: %s", raw_identifier, exc)
                    await channel.send(
                        f"I couldn't find a Pokémon named **{raw_identifier}**. "
                        "Try its National Dex number or PokéAPI-style name."
                    )
                    return
            else:
                if base_id < 1 or base_id > max_dex:
                    await channel.send(
                        f"National Dex number must be between **1** and **{max_dex}**."
                    )
                    return
                try:
                    pokemon, species = await self._load_spawn_candidate(base_id)
                except PokeAPIError as exc:
                    log.warning("Unable to load manual Pokémon spawn %s: %s", base_id, exc)
                    await channel.send("I couldn't load that Pokémon from PokéAPI.")
                    return

            target_rarity = pokemon_rarity(species)
        else:
            target_rarity = roll_spawn_rarity(self._pokecord_cfg())
            try:
                pokemon, species = await self._choose_spawn_candidate(target_rarity, max_dex)
            except PokeAPIError as exc:
                log.error("Unable to choose a %s spawn: %s", target_rarity, exc)
                self.time_to_spawn = None
                return

        actual_id = int(pokemon["id"])
        species_name = species.get("name", pokemon["name"])
        pokemon["dex_id"] = int(species.get("id", actual_id))
        pokemon["name"] = species_name
        pokemon["form"] = None
        if actual_id in alolanIds:
            pokemon["form"] = "alolan"
        else:
            api_name = str(pokemon.get("name", ""))
            raw_name = str((await self.api.pokemon(actual_id)).get("name", api_name))
            if raw_name.startswith(species_name + "-"):
                pokemon["form"] = raw_name[len(species_name) + 1:].upper()

        pokemon["rarity"] = pokemon_rarity(species)
        if message is not None:
            # Owner/manual spawns obey the explicit shiny option.
            pokemon["shiny"] = bool(shiny)
        else:
            # Shininess belongs to the wild spawn itself, not to the trainer
            # who happens to catch it. This roll is independent of rarity.
            pokemon["shiny"] = random.randint(1, shiny_roll_denominator(self._pokecord_cfg())) == 1
        self.pokestore = pokemon

        if manual:
            self.time_to_spawn = None
            return

        try:
            file = await self._silhouette_file(pokemon)
        except (PokeAPIError, OSError) as exc:
            log.exception("Unable to render Pokecord spawn artwork: %s", exc)
            self.pokestore = None
            self.time_to_spawn = None
            return

        # If an owner/manual spawn replaces an active one, disable the old
        # catch button so users cannot submit against a stale silhouette.
        if self._spawn_view is not None:
            self._cancel_spawn_expiry()
            await self._edit_spawn_view(replaced=True)

        embed = discord.Embed(
            title="A wild Pokémon appeared!",
            description=(
                "Think you know it? Press **Catch Pokémon** and enter your guess. "
                "Your guess stays private until someone gets it right."
            ),
            color=0xEEE8AA,
        )
        embed.set_image(url="attachment://poke_image.png")
        view = PokemonCatchView(self)
        sent_msg = await channel.send(embed=embed, file=file, view=view)
        self._remember_spawn_species(int(pokemon.get("dex_id") or species.get("id") or actual_id), cid)
        log.info(
            "Pokecord spawned %s (#%s) for community %s; recent rotation=%s",
            pokemon.get("name", "unknown"),
            pokemon.get("dex_id", actual_id),
            cid,
            self._state(cid).recent_species,
        )
        view.message = sent_msg
        self._spawn_view = view
        self.spawn_msg = sent_msg.id
        self.time_to_spawn = None
        self._schedule_spawn_expiry(sent_msg.id, view)
        community_id = int(db.current_community_id or 0)
        if community_id:
            # Twitch shares this exact spawn with Discord. Give Twitch viewers the
            # Discord-hosted silhouette attachment rather than unobscured official
            # artwork so neither platform gets the answer for free.
            # Resolve the Discord-hosted silhouette URL after the message has
            # actually been created. Normal attachments expose .url directly,
            # but keep embed/proxy fallbacks for Discord.py/API variations.
            silhouette_url = ""
            if sent_msg.attachments:
                silhouette_url = str(getattr(sent_msg.attachments[0], "url", "") or "").strip()

            if not silhouette_url and sent_msg.embeds:
                image = getattr(sent_msg.embeds[0], "image", None)
                candidate = str(getattr(image, "url", "") or "").strip() if image else ""
                # attachment:// is only meaningful inside Discord; Twitch needs
                # an externally fetchable CDN/proxy URL.
                if candidate and not candidate.startswith("attachment://"):
                    silhouette_url = candidate
                elif image:
                    proxy = str(getattr(image, "proxy_url", "") or "").strip()
                    if proxy and not proxy.startswith("attachment://"):
                        silhouette_url = proxy

            log.info(
                "Pokecord Twitch spawn dispatch community=%s message=%s attachments=%s silhouette_url=%s",
                community_id,
                sent_msg.id,
                len(sent_msg.attachments),
                silhouette_url or "<missing>",
            )

            self.bot.dispatch(
                "pokecord_spawn",
                community_id,
                {
                    "expires_in": max(15, int(self._pokecord_cfg().get("spawn_expire_seconds", 180))),
                    "silhouette_url": silhouette_url,
                    "discord_message_id": sent_msg.id,
                },
            )

    @app_commands.command(name="dex", description="Browse your Pokédex")
    @app_commands.describe(page="Optional starting page")
    async def pokeDEX(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 999] = 1):
        ctx = await self._slash_context(interaction)
        poke_list = await db.get_pokedex_entries(ctx.guild.id, ctx.author.id)
        max_dex = max(1, int(self._pokecord_cfg().get("max_pokemon_id", 1025)))

        view = PokedexView(
            ctx.author,
            poke_list,
            max_dex=max_dex,
            page=max(0, int(page) - 1),
        )
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message

    @app_commands.command(name="list", description="Browse the Pokémon in your collection")
    @app_commands.describe(sorting="Initial sort order; you can change this from the menu")
    async def pokelist(
        self,
        interaction: discord.Interaction,
        sorting: Literal["uid", "dex", "iv", "name"] = "uid",
    ):
        ctx = await self._slash_context(interaction)
        data = await db.fetch(
            '''
            SELECT "uid", "index", "name", "form", "lvl", "ivpercentage",
                   "selected", "starred", "shiny", "lucky"
            FROM pokecord_poke_data_scoped
            WHERE "ownerid" = $1
            ORDER BY "uid"
            ''',
            ctx.author.id,
        )
        if not data:
            await ctx.send(f"{ctx.author.mention}, you have not caught any Pokémon yet.")
            return

        view = PokemonListView(ctx.author, data, sorting=sorting, page=0)

        # Keep the channel tidy by replacing the user's previous collection browser.
        user_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, '*')
        try:
            old_message_id = int(user_data.get('list_msg_id') or 0)
            if old_message_id:
                old_message = await ctx.channel.fetch_message(old_message_id)
                await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, TypeError, ValueError):
            pass

        new_message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = new_message
        await helpers.transaction_postgresDatabase(
            'UPDATE users SET "list_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3',
            new_message.id, ctx.author.id, ctx.guild.id,
        )

    @app_commands.command(name="select", description="Set a Pokémon as your active companion")
    async def poke_select(self, interaction: discord.Interaction, uid: int):
        ctx = await self._slash_context(interaction)
        row = await db.fetchrow(
            '''
            WITH target AS (
                SELECT "name"
                FROM pokecord_poke_data_scoped
                WHERE "ownerid" = $1 AND "uid" = $2
            ), updated AS (
                UPDATE pokecord_poke_data_scoped
                SET "selected" = ("uid" = $2)
                WHERE "ownerid" = $1
                  AND EXISTS (SELECT 1 FROM target)
                  AND ("selected" IS TRUE OR "uid" = $2)
                RETURNING 1
            )
            SELECT "name" FROM target
            ''',
            ctx.author.id, uid,
        )
        if row is None:
            await ctx.send("That Pokémon UID does not exist in your collection.")
            return
        await ctx.send(f"{row['name'].capitalize()} set as companion!")

    @app_commands.command(name="favorite", description="Favorite a Pokémon")
    async def poke_star(self, interaction: discord.Interaction, uid: int):
        ctx = await self._slash_context(interaction)
        row = await db.fetchrow(
            'UPDATE pokecord_poke_data_scoped SET "starred" = TRUE '
            'WHERE "uid" = $1 AND "ownerid" = $2 RETURNING "name"',
            uid, ctx.author.id,
        )
        if row is None:
            await ctx.send("That Pokémon UID does not exist in your collection.")
            return
        await ctx.send(f"{row['name'].capitalize()} starred!")

    @app_commands.command(name="unfavorite", description="Remove a Pokémon from favorites")
    async def poke_unstar(self, interaction: discord.Interaction, uid: int):
        ctx = await self._slash_context(interaction)
        row = await db.fetchrow(
            'UPDATE pokecord_poke_data_scoped SET "starred" = FALSE '
            'WHERE "uid" = $1 AND "ownerid" = $2 RETURNING "name"',
            uid, ctx.author.id,
        )
        if row is None:
            await ctx.send("That Pokémon UID does not exist in your collection.")
            return
        await ctx.send(f"{row['name'].capitalize()} unstarred!")

    @app_commands.command(name="info", description="Show detailed information about a Pokémon")
    async def poke_info(self, interaction: discord.Interaction, uid: Optional[int] = None):
        ctx = await self._slash_context(interaction)
        """Shows info on specified pokemon
        Example: $rinfo *Optional: <uid>*"""
        # if ctx.channel.id == 716718691995222036:
        #    await ctx.send("Please use any other channel for this command!")
        #    return
        num = uid
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            if num is not None:
                count_sql = 'SELECT * FROM pokecord_poke_data_scoped where "ownerid" = $1 and "uid" = $2'
                poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, num)
            else:
                count_sql = 'SELECT * FROM pokecord_poke_data_scoped where "ownerid" = $1 and "selected" = $2'
                poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, True)
                if poke_info is None:
                    temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                    poke_info = temp[0]
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Pokémon collection"
                embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                str_desc = "End of List! Run Command Again"
                embed.description = str_desc[:2048 - len(str_title + str_footer)]
                embed.set_footer(text=str_footer)
            await self._delete_invocation(ctx)
            new_message = await ctx.send(embed=embed, file=file)
            users_sql = 'UPDATE users SET "info_msg_id" = $1, "position" = $2 WHERE "UserID" = $3 and "ServerID" = $4'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, int(poke_info['uid']),
                                                       ctx.author.id,
                                                       ctx.guild.id)
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.send(msg)

    async def embed_info(self, user, pokename, embedPokeList):
        guild = getattr(user, "guild", None)
        pokename = pokename.capitalize()
        str_title = "__{}'s Pokemon__".format(user.name)
        poke_count = int(await db.fetchval(
            'SELECT COUNT(DISTINCT "name") FROM pokecord_poke_data_scoped WHERE "ownerid" = $1',
            user.id,
        ) or 0)
        str_footer = f"Obtained {poke_count} unique species"
        if embedPokeList['form'] is not None:
            if embedPokeList['form'] == 'alolan':
                pokename += " (Alolan)"
            else:
                pokename += f" ({embedPokeList['form']})"
        if embedPokeList['starred']:
            pokename = "⭐" + pokename
        if embedPokeList['lucky']:
            pokename = "🍀" + pokename
        if embedPokeList['shiny']:
            pokename = "✨" + pokename
        pokename += f" **UID:** {embedPokeList['uid']} **IV%:** {int(ivPercentage(embedPokeList))}%"
        pokemon = await self._pokemon_for_record(embedPokeList)
        try:
            species_data = await self.api.get_json(pokemon["species"]["url"])
            rarity_label = RARITY_LABELS.get(pokemon_rarity(species_data), "Common")
        except (KeyError, PokeAPIError):
            rarity_label = "Unknown"
        file = await self._art_file(pokemon, shiny=bool(embedPokeList['shiny']), filename="pokemon.png")
        color = helpers.colors.get(embedPokeList['color'], 0x000000)
        embed = discord.Embed(type="rich", title=str_title, color=color)
        if "female" in embedPokeList['gender']:
            gender = "female"
        elif "male" in embedPokeList['gender']:
            gender = "male"
        else:
            gender = ""
        new_items = []
        types = ""
        for poke_type in embedPokeList['type']:
            emoji = discord.utils.get(guild.emojis, name=f"{poke_type}1") if guild else None
            types += f"{emoji or poke_type.title()} "
        for item in embedPokeList['moves']:
            word = json.loads(item)
            if len(str(word['name']).split('-')) > 1:
                new_words = str("{}").format(' '.join([word.capitalize() for word in str(word['name']).split('-')]))
                new_items.append(new_words)
            else:
                new_items.append(str(word['name']).capitalize())
        xp = xp_progress(embedPokeList['lvl'], embedPokeList['exp'])
        if xp['max_level']:
            xp_text = f"**XP:** {xp['current']:,} — **MAX LEVEL**\n{xp_progress_bar(100)} 100%"
        else:
            xp_text = (
                f"**XP:** {xp['current']:,} / {xp['next_level_total']:,}\n"
                f"**To Lv. {int(embedPokeList['lvl']) + 1}:** {xp['remaining']:,} XP\n"
                f"{xp_progress_bar(xp['percent'])} {xp['percent']:.1f}%"
            )

        current_hp = embedPokeList.get('battle_hp')
        if current_hp is None:
            current_hp = embedPokeList['hp']
        current_hp = min(int(embedPokeList['hp']), max(0, int(current_hp)))
        status_text = _status_label(embedPokeList.get('status'))
        friendship = _friendship_value(embedPokeList.get('friendship'))
        str_desc = "**Name:**  {} {}\n**Rarity:** {}\n**Type:** {}\n**Nature:**  {}\n**Friendship:** {}/255\n**LVL:**  {}\n{}\n**HP:**  {}/{} -  **IV:** {}\n**Status:** {}\n**ATK:**  {} -  " \
                   "**IV:** {}\n**DEF:**  {} -  **IV:** {}\n**SP_ATK:**  {} -  **IV:** {}\n**SP_DEF:**  {} -  **" \
                   "IV:** {}\n**SPD:**  {} -  **IV:** {}\n**Moves:**\n- {}\n**Caught On:**  {}".format(
            pokename, gender, rarity_label, types, str(embedPokeList['nature']).capitalize(), friendship, embedPokeList['lvl'], xp_text,
            current_hp, embedPokeList['hp'], embedPokeList['hp_iv'], status_text,
            embedPokeList['attack'], embedPokeList['attack_iv'], embedPokeList['defense'],
            embedPokeList['defense_iv'], embedPokeList['sp_attack'], embedPokeList['special_attack_iv'],
            embedPokeList['sp_defense'], embedPokeList['special_defense_iv'], embedPokeList['speed'],
            embedPokeList['speed_iv'],
            str("{}").format('\n- '.join([word for word in new_items])),
            embedPokeList['caughton'])
        embed.description = str_desc[:2048 - len(str_title + str_footer)]
        # embed.set_image(
        #    url=f"https:{url}"
        # f"https://assets.pokemon.com/assets/cms2/img/pokedex/full/{dex_id}.png"
        # self.pokestore['sprites']['front_default']
        # )
        embed.set_image(url="attachment://pokemon.png")
        embed.set_footer(text=str_footer)
        return embed, file

    @app_commands.command(name="next", description="Show the next Pokémon in your collection")
    async def poke_next(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        """Cycles forward in your list of Pokemon
        Example: $rinfo next"""
        # if ctx.channel.id == 716718691995222036:
        #    await ctx.send("Please use any other channel for this command!")
        #    return
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            old_position_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'position')
            old_position = old_position_data['position']
            position = old_position + 1
            if position >= len(data):
                position = 1
            count_sql = 'SELECT * FROM pokecord_poke_data_scoped where "ownerid" = $1 and "uid" = $2'
            poke_info = data[position]
            if poke_info is None:
                temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                # print(temp)
                poke_info = temp[0]
                # print(poke_info)
            users_sql = 'UPDATE users SET "position" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            # print(int(poke_info['uid']), position)
            await helpers.transaction_postgresDatabase(users_sql, int(poke_info['uid']),
                                                       ctx.author.id, ctx.guild.id)
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Pokémon collection"
                embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                str_desc = "End of List! Run Command Again"
                embed.description = str_desc[:2048 - len(str_title + str_footer)]
                embed.set_footer(text=str_footer)
            user_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'info_msg_id')
            if user_data['info_msg_id'] is not None:
                try:
                    msg_id = user_data['info_msg_id']
                    message = await ctx.channel.fetch_message(msg_id)
                    await message.delete()
                except TypeError:
                    pass
                except discord.errors.NotFound:
                    pass
            await self._delete_invocation(ctx)
            new_message = await ctx.send(embed=embed, file=file)
            users_sql = 'UPDATE users SET "info_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, ctx.author.id,
                                                       ctx.guild.id)
            # else:
            #    await ctx.send(embed=embed)
            #    users_sql = 'UPDATE users SET info_msg_id = $1 WHERE id = $2 and servID = $3'
            #    await helpers.transaction_postgresDatabase(users_sql, ctx.message.id, str(ctx.author.id),
            #                                               str(ctx.guild.id))
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.send(msg)

    @app_commands.command(name="previous", description="Show the previous Pokémon in your collection")
    async def poke_prev(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        """Cycles forward in your list of Pokemon
                Example: $rinfo prev"""
        # if ctx.channel.id == 716718691995222036:
        #    await ctx.send("Please use any other channel for this command!")
        #    return
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            old_position_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'position')
            old_position = old_position_data['position']
            position = old_position - 1
            if position < 0:
                position = len(data) - 1
            # count_sql = 'SELECT * FROM pokecord_poke_data_scoped where "ownerid" = $1 and "uid" = $2'
            poke_info = data[position]
            if poke_info is None:
                temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                # print(temp)
                poke_info = temp[0]
                # print(poke_info)
            users_sql = 'UPDATE users SET "position" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            # print(int(poke_info['uid']), position)
            await helpers.transaction_postgresDatabase(users_sql, int(poke_info['uid']),
                                                       ctx.author.id, ctx.guild.id)
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Pokémon collection"
                embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                str_desc = "End of List! Run Command Again"
                embed.description = str_desc[:2048 - len(str_title + str_footer)]
                embed.set_footer(text=str_footer)
            user_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'info_msg_id')
            if user_data['info_msg_id'] is not None:
                try:
                    msg_id = user_data['info_msg_id']
                    message = await ctx.channel.fetch_message(msg_id)
                    await message.delete()
                except TypeError:
                    pass
                except discord.errors.NotFound:
                    pass
            await self._delete_invocation(ctx)
            new_message = await ctx.send(embed=embed, file=file)
            users_sql = 'UPDATE users SET "info_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, ctx.author.id,
                                                       ctx.guild.id)
            # else:
            #    await ctx.send(embed=embed)
            #    users_sql = 'UPDATE users SET info_msg_id = $1 WHERE id = $2 and servID = $3'
            #    await helpers.transaction_postgresDatabase(users_sql, ctx.message.id, str(ctx.author.id),
            #                                               str(ctx.guild.id))
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.send(msg)

    @app_commands.command(name="latest", description="Show your most recently caught Pokémon")
    async def poke_latest(self, interaction: discord.Interaction):
        ctx = await self._slash_context(interaction)
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            data.sort(key=self.sortUID)
            poke_info = data[len(data) - 1]
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Pokémon collection"
                embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                str_desc = "End of List! Run Command Again"
                embed.description = str_desc[:2048 - len(str_title + str_footer)]
                embed.set_footer(text=str_footer)
            user_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'info_msg_id')
            if user_data['info_msg_id'] is not None:
                try:
                    msg_id = user_data['info_msg_id']
                    message = await ctx.channel.fetch_message(msg_id)
                    await message.delete()
                except TypeError:
                    pass
                except discord.errors.NotFound:
                    pass
            await self._delete_invocation(ctx)
            new_message = await ctx.send(embed=embed, file=file)
            users_sql = 'UPDATE users SET "info_msg_id" = $1, "position" = $2 WHERE "UserID" = $3 and "ServerID" = $4'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, int(poke_info['uid']), ctx.author.id,
                                                       ctx.guild.id)
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.send(msg)

    async def check_capture(self, message, pokemon, *, responder=None):
        send = responder.send if responder is not None else message.channel.send
        if self.pokestore is None:
            return False
        if _normalize_pokemon_guess(self.pokestore['name']) == _normalize_pokemon_guess(pokemon):
            self.caught = True
            embed = discord.Embed(type="rich", title="Gotcha!", color=0xEEE8AA)
            display_name = self.pokestore['name'].upper()
            if self.pokestore['shiny']:
                display_name = "✨ " + display_name
            rarity_label = RARITY_LABELS.get(self.pokestore.get("rarity", "common"), "Common")
            embed.description = (
                f"{display_name} was caught by {message.author.mention}\n"
                f"**Rarity:** {rarity_label}"
            )
            embed.set_image(url="attachment://caught.png")
            # Persist the Pokémon and normalized Pokédex entry together. A transient
            # Discord upload/TLS failure must not erase a valid catch.
            saved_pokemon = await self.addPokeList(message, self.pokestore)

            caught_pokemon = dict(self.pokestore)
            caught_pokemon['uid'] = saved_pokemon['uid']
            self.pokestore = None
            self._cancel_spawn_expiry()
            await self._edit_spawn_view(caught=True)
            self.spawn_msg = None

            # Mirror a Discord catch into Twitch chat. The event is scoped to the
            # active community, so catches in another guild cannot affect this one.
            community_id = int(db.current_community_id or 0)
            if community_id:
                self.bot.dispatch(
                    "pokecord_discord_catch",
                    community_id,
                    {
                        "pokemon_name": str(caught_pokemon.get("name") or "Pokémon"),
                        "rarity": rarity_label,
                        "shiny": bool(caught_pokemon.get("shiny", False)),
                        "discord_user_id": int(message.author.id),
                        "discord_name": str(
                            getattr(message.author, "display_name", None)
                            or getattr(message.author, "name", None)
                            or "A Discord trainer"
                        ),
                    },
                )

            # Start the next timer as soon as the catch has been committed.
            # A failed confirmation upload must never stop the spawn cycle.
            self._schedule_spawn()

            # Discord/aiohttp can occasionally surface transient TLS socket errors on uploads.
            # Retry once with a fresh File object, then fall back to a text/embed confirmation.
            sent = False
            for attempt in range(2):
                try:
                    file = await self._art_file(
                        caught_pokemon,
                        shiny=bool(caught_pokemon['shiny']),
                        filename="caught.png",
                    )
                    await send(embed=embed, file=file)
                    sent = True
                    break
                except (aiohttp.ClientError, OSError, discord.HTTPException) as exc:
                    log.warning(
                        "Catch confirmation upload failed (attempt %s/2) for user %s: %s",
                        attempt + 1,
                        message.author.id,
                        exc,
                    )
                    if attempt == 0:
                        await asyncio.sleep(1.0)

            if not sent:
                fallback = embed.copy()
                fallback.remove_image()
                try:
                    await send(embed=fallback)
                except (aiohttp.ClientError, OSError, discord.HTTPException):
                    log.exception(
                        "Catch was saved but Discord confirmation could not be sent for user %s",
                        message.author.id,
                    )
            return True
        return False

    async def convert_bw(self, poke, silhouette=True):
        if silhouette:
            return await self._silhouette_file(poke)
        return await self._art_file(poke, shiny=bool(poke.get("shiny", False)), filename="poke_image.png")

    async def wait_msg_delete(self, msg, after):
        await asyncio.sleep(after)
        await msg.delete()

    @app_commands.command(name="clean", description="Owner: clean Pokémon bot messages")
    async def cmd_clean(self, interaction: discord.Interaction, messages: int = 0):
        ctx = await self._slash_context(interaction)
        if not await self._require_owner(interaction, ctx):
            return
        if messages == 0:
            for msg in self.bot.cached_messages:
                await msg.delete()
        else:
            deleted = await ctx.channel.purge(limit=messages + 1)

    @app_commands.command(name="debug", description="Owner: show Pokémon runtime diagnostics")
    async def cmd_debug(self, interaction: discord.Interaction, *, message: str = "status"):
        ctx = await self._slash_context(interaction)
        if not await self._require_owner(interaction, ctx):
            return
        """Owner-only diagnostics. Arbitrary eval was intentionally removed."""
        if message.lower() not in {"status", "pokecord"}:
            await ctx.send("Unsafe eval debugging has been removed. Use `/pokemon debug message:status`.")
            return
        embed = discord.Embed(title="Pokecord Debug", color=0x7F0000)
        resolved_channel = self._spawn_channel_for_guild(interaction.guild) if interaction.guild else None
        embed.add_field(name="Spawn configured", value=str(resolved_channel is not None))
        embed.add_field(name="Spawn channel ID", value=str(self.spawn_channel_id or "not set"))
        embed.add_field(name="Channel resolved in this guild", value=str(resolved_channel is not None))
        embed.add_field(name="Pokemon spawned", value=str(self.appeared))
        embed.add_field(name="Caught", value=str(self.caught))
        embed.add_field(name="Spawn task", value=("running" if self._spawn_task and not self._spawn_task.done() else "idle"))
        embed.add_field(
            name="Expiry task",
            value=("running" if self._spawn_expiry_task and not self._spawn_expiry_task.done() else "idle"),
        )
        embed.add_field(name="Spawn expires after", value=f"{max(15, int(self._pokecord_cfg().get('spawn_expire_seconds', 180)))}s")
        weights = spawn_rarity_weights(self._pokecord_cfg())
        total_weight = sum(weights.values()) or 1.0
        rarity_summary = ", ".join(
            f"{RARITY_LABELS[name]} {(weight / total_weight) * 100:.2f}%"
            for name, weight in weights.items()
        )
        embed.add_field(name="Rarity weights", value=rarity_summary, inline=False)
        embed.add_field(name="Shiny odds", value=f"1 in {shiny_roll_denominator(self._pokecord_cfg()):,}")
        embed.add_field(name="Next spawn", value=str(self.time_to_spawn or "not scheduled"), inline=False)
        await ctx.send(embed=embed)



    # ---- Native slash-command autocomplete ---------------------------------
    # Discord treats the returned labels as suggestions while preserving the
    # integer UID/item IDs used by the existing game/database layer.

    @blak_release.autocomplete("uid")
    @blak_trade.autocomplete("your_uid")
    @blak_battle.autocomplete("your_uid")
    @gym_battle.autocomplete("pokemon_uid")
    @item_use.autocomplete("pokemon_uid")
    @item_give.autocomplete("pokemon_uid")
    @item_take.autocomplete("pokemon_uid")
    @poke_select.autocomplete("uid")
    @poke_star.autocomplete("uid")
    @poke_unstar.autocomplete("uid")
    @poke_info.autocomplete("uid")
    async def autocomplete_own_pokemon(
        self, interaction: discord.Interaction, current: int
    ) -> list[app_commands.Choice[int]]:
        return await self._pokemon_uid_choices(interaction, current)

    @blak_trade.autocomplete("their_uid")
    @blak_battle.autocomplete("their_uid")
    async def autocomplete_other_pokemon(
        self, interaction: discord.Interaction, current: int
    ) -> list[app_commands.Choice[int]]:
        member = getattr(interaction.namespace, 'member', None)
        owner_id = getattr(member, 'id', None)
        if owner_id is None:
            return []
        return await self._pokemon_uid_choices(interaction, current, owner_id=int(owner_id))

    @gym_battle.autocomplete("leader")
    async def autocomplete_gym_leader(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        region = str(getattr(interaction.namespace, "region", "") or "").lower()
        leaders = GYM_LEADERS.get(region, ())
        needle = str(current or "").strip().lower()
        choices = []
        for leader in leaders:
            label = f"{leader['name']} · {leader['type']} · {leader['badge']}"
            if needle and needle not in label.lower() and needle not in leader["key"]:
                continue
            choices.append(app_commands.Choice(name=label[:100], value=leader["key"]))
            if len(choices) >= 25:
                break
        return choices

    @buy.autocomplete("item")
    async def autocomplete_shop_item(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._shop_item_choices(interaction, current)

    @item_use.autocomplete("item")
    @item_give.autocomplete("item")
    async def autocomplete_bag_item(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._bag_item_choices(interaction, current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PokeCord(bot))
