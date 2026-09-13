from main import *

from datetimetest import datetime, timedelta

import requests
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from pathlib import Path
from bs4 import BeautifulSoup
import uuid

# Trainer -> [Items, box, ]

'''try:
    with open("./db/pokecordData/Data/rcUserData.json") as dta:
        pokecordData = json.load(dta)
        print("blakCord Data File Loaded")
except Exception:
    pokecordData = {}
    print("blakCord Data File Not Created, Using Temporary Storage.")'''

with open("./config/config.json") as cfg:
    config = json.load(cfg)
    print("Loaded blakCord Config")

exp_secs = config.get("exp_secs")
contributorrole = config.get("ContributorRole")
embed_footer = config.get("embed_footer")

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


def calcExp(n):
    result = n ** 3
    return int(result)


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


def setNature():
    num = randomGenerator(1, 25)
    nature_json = requests.get(f"https://pokeapi.co/api/v2/nature/{num}").json()
    return nature_json['name']


def setColor(name):
    info = requests.get("https://pokeapi.co/api/v2/pokemon-color/").json()

    for i in range(info['count']):
        i += 1
        color_json = requests.get(f"https://pokeapi.co/api/v2/pokemon-color/{i}").json()
        for item in color_json["pokemon_species"]:
            if name == item['name']:
                return color_json['name'].upper()


def setLevel(pokeName, data):
    species_info = requests.get((data['species']['url'])).json()
    lvl_items = requests.get(species_info['evolution_chain']['url']).json()
    level = 0
    Found = False
    for item, value in lvl_items['chain'].items():
        # print(item, type(value))
        if item == "species":
            if value['name'] == pokeName:
                level = 5
                Found = True
                break
        elif item == "evolves_to":
            if len(value) >= 1:
                for i in range(len(value)):
                    if value[i]['species']['name'] == pokeName:
                        level = value[i]['evolution_details'][0]['min_level']
                        Found = True
                        break
                    elif len(value[i]['evolves_to']) >= 1:
                        for i in range(len(value[i]['evolves_to'])):
                            if value[i]['evolves_to'][0]['species']['name'] == pokeName:
                                level = value[i]['evolves_to'][0]['evolution_details'][0]['min_level']
                                Found = True
                                break
                    elif Found:
                        break
        elif Found:
            break
    if level == 0 or level is None:
        level = 5
    return int(level)


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
        print(True)
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


def randomGenerator(num1, num2):
    # anum = random.randint(num1, num2)
    # bnum = random.randint(num1, num2)
    # cnum = random.randint(num1, num2)
    # dnum = random.randint(num1, num2)
    # enum = random.randint(num1, num2)
    # fnum = random.randint(num1, num2)
    # gnum = random.randint(num1, num2)
    randomlist = random.sample(range(num1, num2), 7)
    # print(anum, bnum, cnum, dnum, enum, fnum)
    # choice_list = [anum, bnum, cnum, dnum, enum, fnum, gnum]
    znum = random.randint(0, len(randomlist) - 1)
    rnum = randomlist[znum]
    return rnum


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


class Battle:
    """Blueprint for a new pokemon"""

    def __init__(self, health, battle_health):
        self._health = health
        self._battle_health = battle_health

    @property
    def health(self):
        """The health of the Pokemon which is between 0 and 100"""
        return self._battle_health

    @health.setter
    def health(self, new_hp):
        """Set the new heath value"""
        # here the health limits are enforced
        self._battle_health = min(self._health, max(0, new_hp))

    async def attack(self, ctx, opponent, aPoke, dPoke, moveNum):
        """Attack another Pokemon with the chosen attack (1 or 2)

        This function also returns the raw amount of random damage dealt. The
        amount of damage dealt depends on the attack type.
        """
        move = json.loads(aPoke['moves'][moveNum - 1])
        moveData = requests.get(move['url']).json()
        # print(moveData['name'])
        moveType = moveData['type']['name']
        STAB = 1
        Type = 1
        if moveType in aPoke['type']:
            STAB = 1.5
        if moveData['damage_class']['name'] != 'status':
            for type in dPoke['type']:
                for k, v in effectiveness.items():
                    if k in type:
                        # print(k)
                        for a, b in v.items():
                            if moveType == a.lower():
                                Type = Type * b
                                # print(Type)
            damage = calcDMG(aPoke['lvl'], moveData['power'], aPoke['attack'], dPoke['defense'],
                             random.uniform(0.85, 1.0), aPoke['base_speed'], STAB=STAB, Type=Type)
            await ctx.send(f"Damage to {dPoke['name']}: {damage}")
            print(f"Move: {moveData['name']} STAB: x{STAB}, TE: x{Type}")
            opponent.health -= damage
        else:
            damage = False
        return damage


class PokeItem:

    def __init__(self, value):
        # self.name = value['name']
        self.id = value['id']
        self.name = value['name']
        self.cost = int(value['cost'])
        self.sprite = value['sprites']['default']
        self.total = 1

    @property
    def _name(self):
        return self.name

    @_name.setter
    def _name(self, ItemName):
        self.name = ItemName


class PokeObj:
    def __init__(self, uid, pokeObj, psn):
        self.index = pokeObj['id']
        self.uid = pokeObj.get('uid', 1)
        self.type = [type['type']['name'] for type in pokeObj['types']]
        pokeMoves = []
        for move in pokeObj['moves']:
            # print(move)
            moveData = None
            # print(move['version_group_details'])
            if move['version_group_details'][0]['move_learn_method']['name'] == "level-up":
                moveData = requests.get(move['move']['url']).json()
                if "stat" not in moveData['damage_class']['name']:
                    # print(moveData['damage_class']['name'], True, move['move']['name'])
                    pokeMoves.append(move)
        if len(pokeMoves) < 1:
            url = "https://pokeapi.co/api/v2/move/165"
            moveData = requests.get(url).json()
            move = {}
            move['name'] = moveData['name']
            move['url'] = "https://pokeapi.co/api/v2/move/165"
            self.moves = [move]
        elif len(pokeMoves) < 4:
            self.moves = [item['move'] for item in random.sample(pokeMoves, len(pokeMoves))]
        else:
            self.moves = [item['move'] for item in random.sample(pokeMoves, 4)]
        self.lvl = setLevel(pokeObj['name'], pokeObj)
        self.exp = calcExp(self.lvl)
        self.color = setColor(pokeObj['name'])
        self.height = pokeObj['height']
        self.weight = pokeObj['weight']
        self.nature = setNature()
        self.gender = setGender(pokeObj['name'])
        self.base_exp = pokeObj['base_experience']
        self.base_hp = pokeObj['stats'][0]['base_stat']
        self.base_attack = pokeObj['stats'][1]['base_stat']
        self.base_defense = pokeObj['stats'][2]['base_stat']
        self.base_special_attack = pokeObj['stats'][3]['base_stat']
        self.base_special_defense = pokeObj['stats'][4]['base_stat']
        self.base_speed = pokeObj['stats'][5]['base_stat']
        self.hp_iv = randomGenerator(0, 15)
        self.attack_iv = randomGenerator(0, 15)
        self.defense_iv = randomGenerator(0, 15)
        self.special_attack_iv = randomGenerator(0, 15)
        self.special_defense_iv = self.special_attack_iv
        self.speed_iv = randomGenerator(0, 15)
        self.hp = int(calcStat(self.base_hp, self.hp_iv, self.lvl, self.base_hp, True))
        self.attack = int(calcStat(self.base_attack, self.attack_iv, self.lvl, self.base_attack, False))
        self.defense = int(calcStat(self.base_defense, self.defense_iv, self.lvl, self.base_defense, False))
        self.sp_attack = int(calcStat(self.base_special_attack, self.special_attack_iv, self.lvl,
                                      self.base_special_attack, False))
        self.sp_defense = int(calcStat(self.base_special_defense, self.special_defense_iv, self.lvl,
                                       self.base_special_defense, False))
        self.speed = int(calcStat(self.base_speed, self.speed_iv, self.lvl, self.base_speed, True))
        self.item = None
        self.selected = False
        self.shiny = pokeObj['shiny']
        self.caughtBy = (datetime.now().strftime("%a, %b %d, %Y - %I:%M %p"), psn)
        self.form = pokeObj.get('form', None)

    @property
    def _name(self):
        return self.name

    @_name.setter
    def _name(self, PokeName):
        self.name = PokeName

    @property
    def _index(self):
        return self.index

    @_index.setter
    def _index(self, index):
        self.index = index

    @property
    def _moves(self):
        return self.moves

    @_moves.setter
    def _moves(self, moves):
        self.moves = moves

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)


class User:
    def __init__(self, user, poke, reload: bool = False):
        self.user = user
        self.position = 0
        self.msg = 0
        self.total_pokemon = 1
        if reload is False:
            self.pokeList = {poke['name']: [PokeObj(self.uid, poke, str(self.user)).__dict__]}
            self.key = poke['name']
        else:
            self.pokeList = poke
            keys_view = poke.keys()
            key_iterator = iter(keys_view)
            first_key = next(key_iterator)
            self.key = first_key
        self.items = []
        self.checkUser(str(self.user), self.position, self.key, self.msg, self.total_pokemon, self.items, self.pokeList)

    def removePokemon(self, name):
        if name in self.pokeList.keys():
            poke = self.pokeList[name].pop()
            if len(self.pokeList[name]) == 0:
                del self.pokeList[name]
            return poke
        else:
            return None

    def hasPokemon(self, name):
        if name in self.pokeList.keys():
            return True
        else:
            return False

    def listInventory(self):
        pass


class PokeCord(c.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.time_to_spawn = None
        self.pokestore = None
        self.imgr_results = None
        self.imgr_result = None
        self.spawn_msg = None
        self.caught = False
        self.randNums = []

    def __getstate__(self):
        return ({
            'time': self.time_to_spawn,
            'store': self.pokestore,
            'imgr': self.imgr_results,
            'msg': self.spawn_msg
        })
        pass

    def __setstate__(self, dictState):
        self.time_to_spawn = dictState['time']
        self.pokestore = dictState['store']
        self.imgr_results = dictState['imgr']
        self.spawn_msg = dictState['msg']
        pass

    @property
    def time_to_spawn(self):
        return self._time_to_spawn

    @time_to_spawn.setter
    def time_to_spawn(self, value):
        self._time_to_spawn = value

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

    async def check_return(self, ctx, channel, check, timeout: int = 60):
        try:
            msg = await self.bot.wait_for('message', timeout=float(int(timeout)), check=check)
            value = msg.content.replace(" ", "").lower()
            return value
        except asyncio.TimeoutError:
            await self.check_error(ctx, channel)
            return None

    async def check_error(self, ctx, channel):
        await channel.send("OOF! Sorry! Please rerun the command to restart the process")

    async def itemEvolve(self, user, pokename, orig_data, _item):
        evolved = False
        pokemon_json = None
        oldname = orig_data['name']
        info = requests.get(f"https://pokeapi.co/api/v2/pokemon/{orig_data['id']}/").json()
        species_info = requests.get((info['species']['url'])).json()
        results = requests.get(species_info['evolution_chain']['url']).json()
        for a, chain in enumerate(results['chain'].items()):
            if chain[0] == 'species':
                if pokename == chain[1]['name']:
                    for b, evo in enumerate(results['chain']['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "use-item":
                            if evo['evolution_details'][0]['item'] is not None:
                                if evo['evolution_details'][0]['item']['name'] == _item:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
        if evolved is False:
            for a, result in enumerate(results['chain']['evolves_to']):
                if pokename == result['species']['name']:
                    for b, evo in enumerate(result['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "use-item":
                            if evo['evolution_details'][0]['item'] is not None:
                                if evo['evolution_details'][0]['item']['name'] == _item:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
        if evolved:
            if len(pokemon_json['moves']) < 4:
                moves = [item['move'] for item in random.sample(pokemon_json['moves'], len(pokemon_json['moves']))]
            else:
                moves = [item['move'] for item in random.sample(pokemon_json['moves'], 4)]
            movesList = []
            for move in moves:
                mdata = json.dumps(move)
                movesList.append(mdata)
            index = pokemon_json['id']
            base_hp = pokemon_json['stats'][0]['base_stat']
            base_exp = pokemon_json['base_experience']
            base_attack = pokemon_json['stats'][1]['base_stat']
            base_defense = pokemon_json['stats'][2]['base_stat']
            base_special_attack = pokemon_json['stats'][3]['base_stat']
            base_special_defense = pokemon_json['stats'][4]['base_stat']
            base_speed = pokemon_json['stats'][5]['base_stat']
            height = pokemon_json['height']
            weight = pokemon_json['weight']
            sql = 'UPDATE discord_data.pokecord_poke_data SET "index" =$1, "base_hp" = $2, "base_exp" = $3, "base_attack" = $4, "base_defense" = $5, "base_special_attack" = $6, "base_special_defense" = $7, "base_speed" = $8, "name" = $9, "height" = $10, "weight" = $11 WHERE "ownerid" = $12 and "uid" = $13'
            values = (
                index, base_hp, base_exp, base_attack, base_defense, base_special_attack, base_special_defense,
                base_speed, pokename, height, weight, user.id, orig_data['uid'])
            await helpers.transaction_postgresDatabase(sql, *values)
        return oldname, pokename, evolved

    async def tradeEvolve(self, user, pokename, orig_data, _item):
        evolved = False
        pokemon_json = None
        oldname = orig_data['name']
        info = requests.get(f"https://pokeapi.co/api/v2/pokemon/{orig_data['index']}/").json()
        species_info = requests.get((info['species']['url'])).json()
        results = requests.get(species_info['evolution_chain']['url']).json()
        for a, chain in enumerate(results['chain'].items()):
            if chain[0] == 'species':
                if pokename == chain[1]['name']:
                    for b, evo in enumerate(results['chain']['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "trade":
                            if evo['evolution_details'][0]['held_item'] is not None:
                                if evo['evolution_details'][0]['held_item']['name'] == _item:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
                            elif evo['evolution_details'][0]['held_item'] is None:
                                evolved = True
                                pokename = evo['species']['name']
                                pokemon_json = requests.get(
                                    requests.get(evo['species']['url']).json()['varieties'][0]['pokemon']['url']).json()
                                break
        if evolved is False:
            for a, result in enumerate(results['chain']['evolves_to']):
                if pokename == result['species']['name']:
                    for b, evo in enumerate(result['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "trade":
                            if evo['evolution_details'][0]['held_item'] is not None:
                                if evo['evolution_details'][0]['held_item']['name'] == _item:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
                            elif evo['evolution_details'][0]['held_item'] is None:
                                evolved = True
                                pokename = evo['species']['name']
                                pokemon_json = requests.get(
                                    requests.get(evo['species']['url']).json()['varieties'][0]['pokemon']['url']).json()
                                break
        if evolved:
            if len(pokemon_json['moves']) < 4:
                moves = [item['move'] for item in random.sample(pokemon_json['moves'], len(pokemon_json['moves']))]
            else:
                moves = [item['move'] for item in random.sample(pokemon_json['moves'], 4)]
            movesList = []
            for move in moves:
                mdata = json.dumps(move)
                movesList.append(mdata)
            index = pokemon_json['id']
            base_hp = pokemon_json['stats'][0]['base_stat']
            base_exp = pokemon_json['base_experience']
            base_attack = pokemon_json['stats'][1]['base_stat']
            base_defense = pokemon_json['stats'][2]['base_stat']
            base_special_attack = pokemon_json['stats'][3]['base_stat']
            base_special_defense = pokemon_json['stats'][4]['base_stat']
            base_speed = pokemon_json['stats'][5]['base_stat']
            height = pokemon_json['height']
            weight = pokemon_json['weight']
            sql = 'UPDATE discord_data.pokecord_poke_data SET "index" =$1, "base_hp" = $2, "base_exp" = $3, "base_attack" = $4, "base_defense" = $5, "base_special_attack" = $6, "base_special_defense" = $7, "base_speed" = $8, "name" = $9, "height" = $10, "weight" = $11 WHERE "ownerid" = $12 and "uid" = $13'
            values = (
                index, base_hp, base_exp, base_attack, base_defense, base_special_attack, base_special_defense,
                base_speed, pokename, height, weight, user.id, orig_data['uid'])
            await helpers.transaction_postgresDatabase(sql, *values)
        return oldname, pokename, evolved

    def evolve(self, pokename, orig_data, new_level):
        evolved = False
        pokemon_json = None
        oldname = orig_data['name']
        info = requests.get(f"https://pokeapi.co/api/v2/pokemon/{orig_data['index']}/").json()
        species_info = requests.get((info['species']['url'])).json()
        results = requests.get(species_info['evolution_chain']['url']).json()
        for a, chain in enumerate(results['chain'].items()):
            if chain[0] == 'species':
                if pokename == chain[1]['name']:
                    for b, evo in enumerate(results['chain']['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "level-up":
                            if evo['evolution_details'][0]['min_level'] is not None:
                                if evo['evolution_details'][0]['min_level'] <= new_level:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
                            elif evo['evolution_details'][0]['min_level'] is None:
                                if randomGenerator(0, 3) == 2:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break

        if evolved is False:
            for a, result in enumerate(results['chain']['evolves_to']):
                if pokename == result['species']['name']:
                    for b, evo in enumerate(result['evolves_to']):
                        if evo['evolution_details'][0]['trigger']['name'] == "level-up":
                            if evo['evolution_details'][0]['min_level'] is not None:
                                if evo['evolution_details'][0]['min_level'] <= new_level:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
                            elif evo['evolution_details'][0]['min_level'] is None:
                                if randomGenerator(0, 3) == 2:
                                    evolved = True
                                    pokename = evo['species']['name']
                                    pokemon_json = requests.get(
                                        requests.get(evo['species']['url']).json()['varieties'][0]['pokemon'][
                                            'url']).json()
                                    break
        return evolved, pokename, pokemon_json

    async def addPokeList(self, ctx, value):
        guild = ctx.guild
        _user = ctx.author
        data = await helpers.get_player_postgresData(_user, guild, "total_pokemon")
        try:
            uid = data['total_pokemon'] + 1
        except KeyError:
            uid = 0
        except TypeError:
            uid = 0
        pokeData = PokeObj(uid, value, _user.id).__dict__
        movesList = []
        ivPer = ivPercentage(pokeData)
        for move in pokeData['moves']:
            mdata = json.dumps(move)
            movesList.append(mdata)
        sql = 'INSERT INTO discord_data.pokecord_poke_data("index", "uid", "type", "lvl", "exp", "color", "height", "weight", "nature", ' \
              '"gender", "base_exp", "base_hp", "base_attack", "base_defense", "base_special_attack", "base_special_defense", ' \
              '"base_speed", "hp_iv", "attack_iv", "defense_iv", "special_attack_iv", "special_defense_iv", "speed_iv", "hp", "battle_hp", "attack", ' \
              '"defense", "sp_attack", "sp_defense", "speed", "item", "selected", "shiny", "lucky", "caughton", "ownerid", "originalownerid", "moves", ' \
              '"name", "traded", "form", "ivpercentage") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, ' \
              '$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42) '
        await helpers.transaction_postgresDatabase(sql, pokeData['index'], pokeData['uid'], pokeData['type'],
                                                   pokeData['lvl'],
                                                   pokeData['exp'], pokeData['color'], pokeData['height'],
                                                   pokeData['weight'],
                                                   pokeData['nature'], pokeData['gender'], pokeData['base_exp'],
                                                   pokeData['base_hp'],
                                                   pokeData['base_attack'], pokeData['base_defense'],
                                                   pokeData['base_special_attack'],
                                                   pokeData['base_special_defense'], pokeData['base_speed'],
                                                   pokeData['hp_iv'],
                                                   pokeData['attack_iv'], pokeData['defense_iv'],
                                                   pokeData['special_attack_iv'],
                                                   pokeData['special_defense_iv'], pokeData['speed_iv'], pokeData['hp'],
                                                   pokeData['hp'],
                                                   pokeData['attack'], pokeData['defense'], pokeData['sp_attack'],
                                                   pokeData['sp_defense'],
                                                   pokeData['speed'], pokeData['item'], pokeData['selected'],
                                                   pokeData['shiny'], False,
                                                   pokeData['caughtBy'][0], pokeData['caughtBy'][1],
                                                   pokeData['caughtBy'][1],
                                                   movesList, value['name'], 0, pokeData['form'], ivPer)

    async def addExpLvlUp(self, user, poke_info, battle: bool = False):
        completed = False
        levelUp = False
        pokename = None
        level = None
        evolved = False
        old_name = poke_info['name'].capitalize()
        currxp = poke_info['exp']
        newxp = gainedExp(poke_info['base_exp'], poke_info['lvl'], poke_info['lucky'], battle)
        updatedxp = currxp + newxp
        pokename = poke_info['name']
        print("Added {} exp to {}".format(newxp, pokename))
        if battle:
            sql = 'UPDATE discord_data.pokecord_poke_data SET "exp" = $1 WHERE "ownerid" = $2 and "uid" = $3'
            values = (updatedxp, user.id, poke_info['uid'])
        else:
            sql = 'UPDATE discord_data.pokecord_poke_data SET "exp" = $1 WHERE "ownerid" = $2 and "selected" = $3'
            values = (updatedxp, user.id, True)
        if updatedxp >= calcExp(poke_info['lvl']):
            level = poke_info['lvl'] + 1
            levelUp = True
            evolved, new_name, new_pokeList = self.evolve(pokename, poke_info, level)
            hp = int(calcStat(poke_info['base_hp'],
                              poke_info['hp_iv'],
                              poke_info['lvl'],
                              poke_info['base_hp'],
                              True))
            attack = int(calcStat(poke_info['base_attack'],
                                  poke_info['attack_iv'],
                                  poke_info['lvl'],
                                  poke_info['base_attack'],
                                  False))
            defense = int(
                calcStat(poke_info['base_defense'],
                         poke_info['defense_iv'], poke_info['lvl'],
                         poke_info['base_defense'], False))
            sp_attack = int(
                calcStat(poke_info['base_special_attack'],
                         poke_info['special_attack_iv'],
                         poke_info['lvl'],
                         poke_info['base_special_attack'], False))
            sp_defense = int(
                calcStat(poke_info['base_special_defense'],
                         poke_info['special_defense_iv'],
                         poke_info['lvl'],
                         poke_info['base_special_defense'], False))
            speed = int(
                calcStat(poke_info['base_speed'], poke_info['speed_iv'],
                         poke_info['lvl'], poke_info['base_speed'],
                         True))
            if battle:
                sql = 'UPDATE discord_data.pokecord_poke_data SET "hp" = $1, "battle_hp" = $2, "attack" = $3, "defense" = $4, "sp_attack" = $5, "sp_defense" = $6, "speed" = $7, "exp" = $8, "lvl" = $9 WHERE "ownerid" = $10 and "uid" = $11'
                values = (
                    hp, hp, attack, defense, sp_attack, sp_defense, speed, updatedxp, level, user.id, poke_info['uid'])
            else:
                sql = 'UPDATE discord_data.pokecord_poke_data SET "hp" = $1, "battle_hp" = $2, "attack" = $3, "defense" = $4, "sp_attack" = $5, "sp_defense" = $6, "speed" = $7, "exp" = $8, "lvl" = $9 WHERE "ownerid" = $10 and "selected" = $11'
                values = (hp, hp, attack, defense, sp_attack, sp_defense, speed, updatedxp, level, user.id, True)
            if evolved:
                pokename = new_name
                if len(new_pokeList['moves']) < 4:
                    moves = [item['move'] for item in random.sample(new_pokeList['moves'], len(new_pokeList['moves']))]
                else:
                    moves = [item['move'] for item in random.sample(new_pokeList['moves'], 4)]
                movesList = []
                for move in moves:
                    mdata = json.dumps(move)
                    movesList.append(mdata)
                index = new_pokeList['id']
                base_hp = new_pokeList['stats'][0]['base_stat']
                base_exp = new_pokeList['base_experience']
                base_attack = new_pokeList['stats'][1]['base_stat']
                base_defense = new_pokeList['stats'][2]['base_stat']
                base_special_attack = new_pokeList['stats'][3]['base_stat']
                base_special_defense = new_pokeList['stats'][4]['base_stat']
                base_speed = new_pokeList['stats'][5]['base_stat']
                height = new_pokeList['height']
                weight = new_pokeList['weight']
                if battle:
                    sql = 'UPDATE discord_data.pokecord_poke_data SET "index" =$1, "base_hp" = $2, "base_exp" = $3, "base_attack" = $4, "base_defense" = $5, "base_special_attack" = $6, "base_special_defense" = $7, "base_speed" = $8, "height" = $9, "hp" = $10, "name" = $11, "attack" = $12, "defense" = $13, "sp_attack" = $14, "sp_defense" = $15, "speed" = $16, "exp" = $17, "lvl" = $18, "weight" = $19 WHERE "ownerid" = $20 and "uid" = $21'
                    values = (
                        index, base_hp, base_exp, base_attack, base_defense, base_special_attack, base_special_defense,
                        base_speed, height, hp, new_name, attack, defense, sp_attack, sp_defense, speed, updatedxp,
                        level,
                        weight, user.id, poke_info['uid'])
                else:
                    sql = 'UPDATE discord_data.pokecord_poke_data SET "index" =$1, "base_hp" = $2, "base_exp" = $3, "base_attack" = $4, "base_defense" = $5, "base_special_attack" = $6, "base_special_defense" = $7, "base_speed" = $8, "height" = $9, "hp" = $10, "name" = $11, "attack" = $12, "defense" = $13, "sp_attack" = $14, "sp_defense" = $15, "speed" = $16, "exp" = $17, "lvl" = $18, "weight" = $19 WHERE "ownerid" = $20 and "selected" = $21'
                    values = (
                        index, base_hp, base_exp, base_attack, base_defense, base_special_attack, base_special_defense,
                        base_speed, height, hp, new_name, attack, defense, sp_attack, sp_defense, speed, updatedxp,
                        level,
                        weight, user.id, True)
            completed = True
        await helpers.transaction_postgresDatabase(sql, *values)
        return completed, old_name, pokename, levelUp, level, evolved

    @c.Cog.listener()
    async def on_ready(self):
        if self.setToSpawn():
            if self.time_to_spawn > datetime.now():
                await asyncio.sleep(self.getSeconds())
            pokeNum = str(randomGenerator(1, 251))
            await self._spawn(pokeNum)

    @c.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.content[1:].startswith("spawn"):
            return
        count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "selected" = $2'
        poke_info = await helpers.query_postgresDatabase(count_sql, message.author.id, True)
        if poke_info:
            data = await helpers.get_player_postgresData(message.author, message.guild, 'lastmessage')
            orig_time = data['lastmessage']
            time_diff = int(time.time()) - orig_time
            diff_seconds = time_diff % 60
            if diff_seconds >= exp_secs:
                completed, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(message.author,
                                                                                                poke_info)
                if evolved:
                    await message.author.send(
                        f"Congrats {message.author.mention}! You have evolved your {old_name.capitalize()} into a {pokename.capitalize()}!")
                elif levelup:
                    await message.author.send(
                        f"Congrats {message.author.mention}! Your {pokename.capitalize()} advanced to level {level}!")
        if self.setToSpawn():
            return
        else:
            self.time_to_spawn = datetime.now() + timedelta(seconds=randomGenerator(45, 120))
            await asyncio.sleep(self.getSeconds())
            await self._spawn()

    @c.command(name="phelp")
    async def blak_cord_help(self, ctx):
        text = "**!pcatch:** Command to catch spawned blakCord Pokemon. Example: !pcatch <pokemon>\n\n" \
               "**!prelease:** Command to release caught blakCord Pokemon. Example: !prelease <uid>\n\n" \
               "**!ptrade:** Command to trade caught blakCord Pokemon. Example: !ptrade @user\n\n" \
               "**!plist:** Lists all blakCord Pokemon in the order you have caught them. Example: !plist *Optional: <page-number> <sorting>*\n\n" \
               "**!pselect:** Selects a Pokemon to be your partner. Example: !pselect <uid>\n\n" \
               "**!pokedex:** Shows your Pokedex. Example: !pokedex <page>\n\n" \
               "**!pinfo:** Shows info on specified pokemon. Example: !pinfo *Optional: <uid>*\n\n" \
               "**!pstore:** Shows items for sale. Example: !pstore\n\n" \
               "**!pstore buy:** Buys specified item from store. Example: !pstore buy <itemID>\n\n" \
               "**!pitems:** Shows items in your bag. Example: !pitems\n\n" \
               "**!pitems use:** Uses specified item on Pokemon. Example: !pitems use <itemID> <uid>\n\n" \
               "**!pitems give:** Gives specified item to Pokemon. Example: !pitems give <itemID> <uid>\n\n" \
               "**!pstar:** Favorites a Pokemon. Example: !pstar <uid>\n\n" \
               "**!punstar:** Removes Pokemon from Favorites. Example: !punstar <uid>\n\n"
        await ctx.send(text)

    @c.command(name="pcatch")
    async def blak_catch(self, ctx, *, pokemon: str):
        """Command to catch spawned blakCord Pokemon.
            Example: !pcatch <pokemon>"""
        if ctx.channel.id == 1024544453177917471:
            if len(ctx.message.mentions) >= 1:
                await ctx.send("Please do not use my resources for such menial tasks!")
            elif helpers.check_role(ctx.message.author, contributorrole) and len(
                    await helpers.get_pokecord_postgresData(ctx.author, "*")) >= 300:
                await ctx.send(
                    f"{ctx.author.mention}, you have reached your Pokemon Storage Limit! Please release Pokemon to make more room!")
            elif not helpers.check_role(ctx.message.author, contributorrole) and len(
                    await helpers.get_pokecord_postgresData(ctx.author, "*")) >= 200:
                await ctx.send(
                    f"{ctx.author.mention}, you have reached your Pokemon Storage Limit! Please release Pokemon to make more room or Subscribe to our Patreon for an extra 100 storage spots!")
            elif self.appeared and not self.caught:
                await self.check_capture(ctx.message, pokemon)
            elif not self.appeared and self.caught:
                await ctx.send("The Pokemon has already been caught!")
            else:
                await ctx.send("There is no Pokemon currently spawned.")

    @c.command(name="prelease")
    async def blak_release(self, ctx, id: int = None):
        """Command to release caught blakCord Pokemon.
            Example: !prelease <uid>"""
        poke_sql = 'SELECT name, starred from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
        pokeinfo = await helpers.query_postgresDatabase(poke_sql, id, ctx.author.id)
        print(pokeinfo)
        pokename = pokeinfo['name']
        if pokeinfo['starred']:
            await ctx.send(
                f"{ctx.author.mention} {pokename.capitalize()} is starred. Are you sure you want to release it?")

            def releaseStarred(m):
                return m.author == ctx.message.author

            releaseAnswer = await self.check_return(ctx, ctx.channel, releaseStarred)
            if "y" in releaseAnswer:
                users_sql = 'DELETE FROM discord_data.pokecord_poke_data WHERE "uid" = $1 AND "ownerid" = $2'
                await helpers.transaction_postgresDatabase(users_sql, id, ctx.author.id)
                await ctx.send(
                    f"{pokename.capitalize()} has been released! Farewell!\n5 credits added to your account!")
                failed = await helpers.add_money(ctx.author, ctx.guild, 100)
                if failed:
                    await ctx.send(f"Transaction Failed: {ctx.author.mention} has too many Credits!")
                    return
            else:
                await ctx.send("Release Cancelled")
        else:
            users_sql = 'DELETE FROM discord_data.pokecord_poke_data WHERE "uid" = $1 AND "ownerid" = $2'
            await helpers.transaction_postgresDatabase(users_sql, id, ctx.author.id)
            await ctx.send(f"{pokename.capitalize()} has been released! Farewell!\n5 credits added to your account!")
            failed = await helpers.add_money(ctx.author, ctx.guild, 100)
            if failed:
                await ctx.send(f"Transaction Failed: {ctx.author.mention} has too many Credits!")
                return

    # @c.command(name='edit_embed')
    async def cmd_edit_embed(self, cmd, message, content=None):
        msg_list = []
        find_message = await message.channel.send(content)
        msg_list.append(await message.channel.send('What in the embed do you want to change?'))
        msg_list.append(await self.bot.wait_for_message(author=message.author))
        msg_list.append(await message.channel.send('What would you like it to change to?'))
        msg_list.append(await self.bot.wait_for_message(author=message.author))
        for msg in msg_list:
            print("{}{}{}".format(helpers.bcolors.WARNING, msg.content, helpers.bcolors.ENDC))
        for embed in find_message.embeds:
            new_embed = embed
            if msg_list[1].content.strip(" ")[1].lower() == "title":
                new_embed.title = msg_list[3].content
            elif msg_list[1].content.strip(" ")[1].lower() == "description":
                new_embed.description = msg_list[3].content
            elif msg_list[1].content.strip(" ")[1].lower() == "color":
                new_embed.color = msg_list[3].content
            elif msg_list[1].content.strip(" ")[1].lower() == "footer":
                new_embed.set_footer(text=msg_list[3].content)
            elif msg_list[1].content.strip(" ")[1].lower() == "thumbnail":
                new_embed.set_thumbnail(url=msg_list[3].content)
            elif msg_list[1].content.strip(" ")[1].lower() == "image":
                new_embed.set_image(url=msg_list[3].content)
            elif msg_list[1].content.strip(" ")[1].lower() == "author":
                new_embed.set_author(name=msg_list[3].content)
            else:
                await message.channel.send('The requested field is not availiable.')
            await self.bot.edit_message(find_message, embed=new_embed)
        await message.channel.delete_messages(msg_list)

    # @c.command(name='rprem')
    # @helpers.is_creator()
    async def prem_cmd(self, ctx):
        prem_role = discord.utils.get(ctx.message.guild.roles, id=619206236587425813)
        for member in prem_role.members:
            if member.id == 318063870025400322:
                num = "133"
            else:
                starter_List = ["1", "4", "7", "25", "133"]
                num = random.choice(starter_List)
            await self._spawn(num, True, True, True)
            await self.check_capture(ctx.message, self.pokestore['name'])

    @c.command(name="ptrade")
    async def blak_trade(self, ctx, member: discord.Member = None, authoruid=None, authorcredits=None):
        """Trade Function for blakCord"""
        if member is None:
            await ctx.send("Please Specify a User!")
            return
        if member == ctx.author:
            await ctx.send("You can't trade with yourself fool!")
            return
        if authoruid is not None:
            if authoruid.isdigit():
                authoruid = int(authoruid)
            else:
                msg = "Input given must be a number!"
                await ctx.send(msg)
                return
        else:
            await ctx.send(f"{ctx.author.mention} please Specify the Pokemon UID you would like to trade.")

            def authorTradePokemonUID(m):
                return m.author == ctx.message.author and m.content.isdigit()

            pokeUIDdata = await self.check_return(ctx, ctx.channel, authorTradePokemonUID)
            authoruid = int(pokeUIDdata)

        poke_sql = 'select * from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
        authorPokeData = await helpers.query_postgresDatabase(poke_sql, authoruid, ctx.author.id)

        if authorPokeData is None:
            await ctx.send(
                "This Pokemon does not exist! Please rerun the command and choose a different Pokemon!")
            return

        if authorPokeData['traded'] >= 2:
            await ctx.send(
                "This Pokemon has already been traded! Please rerun the command and choose a different Pokemon!")
            return

        authorPokeName = authorPokeData['name']
        # if authorcredits is not None:
        #    if authorcredits.isdigit():
        #        authorcredits = int(authorcredits)
        #    else:
        #        msg = "Input given must be a number!"
        #        await ctx.send(msg)
        #        return
        # else:
        #    await ctx.send("Do you want to charge credits for this trade?.")
        #
        #    def authorTradePokemonCreditsBool(m):
        #        return m.author == ctx.message.author
        #
        #    pokeCreditsBool = await self.check_return(self, ctx, ctx.channel, authorTradePokemonCreditsBool())
        #    if "y" in pokeCreditsBool:
        #        await ctx.send("Please Specify the amount of Credits you would like to charge.")
        #
        #        def authorTradePokemonCredits(m):
        #            return m.author == ctx.message.author and m.content.isdigit()
        #
        #        pokeCreditsdata = await self.check_return(self, ctx, ctx.channel, authorTradePokemonCredits())
        #        authorcredits = int(pokeCreditsdata)
        #
        # if numTrade is not None:
        #   for i in range(numTrade):
        #       poke_sql = "select * from discord_data.pokecord_poke_data WHERE uid = $1 and ownerid = $2"
        #       tradePokeData = await helpers.query_postgresDatabase(poke_sql, tradeuid, str(member.id))
        #       tradePokeName = authorPokeData['name']
        #
        #
        #

        await ctx.send(f"{member.mention} please Specify the Pokemon UID you would like to trade.")

        def tradePokemonUID(m):
            return m.author == member and m.content.isdigit()

        pokeUIDdata = await self.check_return(ctx, ctx.channel, tradePokemonUID)
        tradeuid = int(pokeUIDdata)

        tradePokeData = await helpers.query_postgresDatabase(poke_sql, tradeuid, member.id)

        if tradePokeData is None:
            await ctx.send(
                "This Pokemon does not exist! Please rerun the command and choose a different Pokemon!")
            return

        if tradePokeData['traded'] >= 2:
            await ctx.send(
                "This Pokemon has already been traded! Please rerun the command and choose a different Pokemon!")
            return

        tradePokeName = tradePokeData['name']

        await ctx.send(f"{ctx.author.mention} is trading a {authorPokeName} for {member.mention}'s {tradePokeName}.")
        await ctx.send(f"{ctx.author.mention} Is this correct?")

        def authorConfirmTrade(m):
            return m.author == ctx.message.author

        authorConfirmData = await self.check_return(ctx, ctx.channel, authorConfirmTrade)

        await ctx.send(f"{member.mention} Is this correct?")

        def tradeConfirmTrade(m):
            return m.author == member

        tradeConfirmData = await self.check_return(ctx, ctx.channel, tradeConfirmTrade)

        if "y" in tradeConfirmData and "y" in authorConfirmData:
            if authorPokeData['item'] is not None:
                authorItemData = json.loads(authorPokeData['item'])
                authorItem = authorItemData['name']
            else:
                authorItem = None
            if tradePokeData['item'] is not None:
                tradeItemData = json.loads(tradePokeData['item'])
                tradeItem = tradeItemData['name']
            else:
                tradeItem = None
            authoroldname, authorpokename, authorevolved = await self.tradeEvolve(ctx.author, authorPokeName,
                                                                                  authorPokeData,
                                                                                  authorItem)
            await asyncio.sleep(2)
            tradeoldname, tradepokename, tradeevolved = await self.tradeEvolve(member, tradePokeName, tradePokeData,
                                                                               tradeItem)
            await asyncio.sleep(2)
            if tradeevolved:
                tradePokeData = await helpers.query_postgresDatabase(poke_sql, tradeuid, member.id)
                tradePokeName = tradepokename
            if authorevolved:
                authorPokeData = await helpers.query_postgresDatabase(poke_sql, authoruid, ctx.author.id)
                authorPokeName = authorpokename
            await asyncio.sleep(1)
            users_sql = 'DELETE FROM discord_data.pokecord_poke_data WHERE "uid" = $1 AND "ownerid" = $2'
            await helpers.transaction_postgresDatabase(users_sql, authoruid, ctx.author.id)
            await helpers.transaction_postgresDatabase(users_sql, tradeuid, member.id)
            if ctx.author.id == 290035422011326464:
                authorLuckyInt = randomGenerator(1, 5)
            else:
                authorLuckyInt = randomGenerator(1, 20)
            if member.id == 290035422011326464:
                tradeLuckyInt = randomGenerator(1, 5)
            else:
                tradeLuckyInt = randomGenerator(1, 20)
            if authorLuckyInt == 1 or tradeLuckyInt == 1:
                tradePokeLucky = True
                hp_iv_trade = 12
                attack_iv_trade = 12
                defense_iv_trade = 12
                special_attack_iv_trade = 12
                special_defense_iv_trade = 12
                speed_iv_trade = 12
                authorPokeLucky = True
                hp_iv_author = 12
                attack_iv_author = 12
                defense_iv_author = 12
                special_attack_iv_author = 12
                special_defense_iv_author = 12
                speed_iv_author = 12
            else:
                if authorPokeData['lucky']:
                    authorPokeLucky = True
                else:
                    authorPokeLucky = False
                hp_iv_author = authorPokeData['hp_iv']
                attack_iv_author = authorPokeData['attack_iv']
                defense_iv_author = authorPokeData['defense_iv']
                special_attack_iv_author = authorPokeData['special_attack_iv']
                special_defense_iv_author = authorPokeData['special_defense_iv']
                speed_iv_author = authorPokeData['speed_iv']
                if tradePokeData['lucky']:
                    tradePokeLucky = True
                else:
                    tradePokeLucky = False
                hp_iv_trade = tradePokeData['hp_iv']
                attack_iv_trade = tradePokeData['attack_iv']
                defense_iv_trade = tradePokeData['defense_iv']
                special_attack_iv_trade = tradePokeData['special_attack_iv']
                special_defense_iv_trade = tradePokeData['special_defense_iv']
                speed_iv_trade = tradePokeData['speed_iv']

            sql = 'INSERT INTO discord_data.pokecord_poke_data("index", "uid", "type", "lvl", "exp", "color", "height", "weight", "nature", ' \
                  '"gender", "base_exp", "base_hp", "base_attack", "base_defense", "base_special_attack", "base_special_defense", ' \
                  '"base_speed", "hp_iv", "attack_iv", "defense_iv", "special_attack_iv", "special_defense_iv", "speed_iv", "hp", "attack", ' \
                  '"defense", "sp_attack", "sp_defense", "speed", "item", "selected", "shiny", "lucky", "caughton", "ownerid", "originalownerid", "moves", ' \
                  '"name", "traded", "form", "battle_hp") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, ' \
                  '$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41) '
            await helpers.transaction_postgresDatabase(sql, authorPokeData['index'], tradePokeData['uid'],
                                                       authorPokeData['type'],
                                                       authorPokeData['lvl'],
                                                       authorPokeData['exp'], authorPokeData['color'],
                                                       authorPokeData['height'],
                                                       authorPokeData['weight'],
                                                       authorPokeData['nature'], authorPokeData['gender'],
                                                       authorPokeData['base_exp'],
                                                       authorPokeData['base_hp'],
                                                       authorPokeData['base_attack'], authorPokeData['base_defense'],
                                                       authorPokeData['base_special_attack'],
                                                       authorPokeData['base_special_defense'],
                                                       authorPokeData['base_speed'],
                                                       hp_iv_author, attack_iv_author, defense_iv_author,
                                                       special_attack_iv_author, special_defense_iv_author,
                                                       speed_iv_author,
                                                       authorPokeData['hp'],
                                                       authorPokeData['attack'], authorPokeData['defense'],
                                                       authorPokeData['sp_attack'],
                                                       authorPokeData['sp_defense'],
                                                       authorPokeData['speed'], authorPokeData['item'],
                                                       authorPokeData['selected'],
                                                       authorPokeData['shiny'], authorPokeLucky,
                                                       authorPokeData['caughton'], member.id,
                                                       authorPokeData['originalownerid'],
                                                       authorPokeData['moves'], authorPokeData['name'],
                                                       authorPokeData['traded'] + 1,
                                                       authorPokeData['form'], authorPokeData['hp'])

            await helpers.transaction_postgresDatabase(sql, tradePokeData['index'], authorPokeData['uid'],
                                                       tradePokeData['type'],
                                                       tradePokeData['lvl'],
                                                       tradePokeData['exp'], tradePokeData['color'],
                                                       tradePokeData['height'],
                                                       tradePokeData['weight'],
                                                       tradePokeData['nature'], tradePokeData['gender'],
                                                       tradePokeData['base_exp'],
                                                       tradePokeData['base_hp'],
                                                       tradePokeData['base_attack'], tradePokeData['base_defense'],
                                                       tradePokeData['base_special_attack'],
                                                       tradePokeData['base_special_defense'],
                                                       tradePokeData['base_speed'],
                                                       hp_iv_trade, attack_iv_trade, defense_iv_trade,
                                                       special_attack_iv_trade, special_defense_iv_trade,
                                                       speed_iv_trade,
                                                       tradePokeData['hp'],
                                                       tradePokeData['attack'], tradePokeData['defense'],
                                                       tradePokeData['sp_attack'],
                                                       tradePokeData['sp_defense'],
                                                       tradePokeData['speed'], tradePokeData['item'],
                                                       tradePokeData['selected'],
                                                       tradePokeData['shiny'], tradePokeLucky,
                                                       tradePokeData['caughton'], ctx.author.id,
                                                       tradePokeData['originalownerid'],
                                                       tradePokeData['moves'], tradePokeData['name'],
                                                       tradePokeData['traded'] + 1,
                                                       tradePokeData['form'], tradePokeData['hp'])
            if tradeevolved:
                await ctx.send(f"Congratulations, {member.mention} your {tradeoldname} evolved into a {tradePokeName}!")
            if authorevolved:
                await ctx.send(
                    f"Congratulations, {ctx.author.mention} your {authoroldname} evolved into a {authorPokeName}!")
            await ctx.send(
                f"Trade Completed!")
        else:
            await ctx.send("Terminating Trade Process.")

    @c.command(name="pbattle")
    async def blak_battle(self, ctx, member: discord.Member = None, authoruid=None):
        """Battle Function for blakCord"""
        if member is None:
            await ctx.send("Please Specify a User!")
            return
        if member == ctx.author:
            await ctx.send("You can't battle with yourself fool!")
            return
        if authoruid is not None:
            if authoruid.isdigit():
                authoruid = int(authoruid)
            else:
                msg = "Input given must be a number!"
                await ctx.send(msg)
                return
        else:
            await ctx.send(f"{ctx.author.mention} please Specify the Pokemon UID you would like to battle with.")

            def authorBattlePokemonUID(m):
                return m.author == ctx.message.author and m.content.isdigit()

            pokeUIDdata = await self.check_return(ctx, ctx.channel, authorBattlePokemonUID)
            authoruid = int(pokeUIDdata)

        poke_sql = 'select * from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
        authorPokeData = await helpers.query_postgresDatabase(poke_sql, authoruid, ctx.author.id)

        if authorPokeData is None:
            await ctx.send(
                "This Pokemon does not exist! Please rerun the command and choose a different Pokemon!")
            return

        await ctx.send(f"{member.mention} please Specify the Pokemon UID you would like to battle with.")

        def opponentPokemonUID(m):
            return m.author == member and m.content.isdigit()

        pokeUIDdata = await self.check_return(ctx, ctx.channel, opponentPokemonUID)
        opponentuid = int(pokeUIDdata)

        opponentPokeData = await helpers.query_postgresDatabase(poke_sql, opponentuid, member.id)

        if opponentPokeData is None:
            await ctx.send(
                "This Pokemon does not exist! Please rerun the command and choose a different Pokemon!")
            return

        authorPokeName = authorPokeData['name']
        opponentPokeName = opponentPokeData['name']

        await ctx.send(
            f"{ctx.author.mention} is battling a {authorPokeName} against {member.mention}'s {opponentPokeName}.")
        await ctx.send(f"{ctx.author.mention} Is this correct?")

        def authorConfirmTrade(m):
            return m.author == ctx.message.author

        authorConfirmData = await self.check_return(ctx, ctx.channel, authorConfirmTrade)

        await ctx.send(f"{member.mention} Is this correct?")

        def opponentConfirmTrade(m):
            return m.author == member

        tradeConfirmData = await self.check_return(ctx, ctx.channel, opponentConfirmTrade)

        if "y" in tradeConfirmData and "y" in authorConfirmData:
            authorPoke = Battle(authorPokeData['hp'], authorPokeData['battle_hp'])
            # mankeyData, opponentPokeData, 2
            opponentPoke = Battle(opponentPokeData['hp'], opponentPokeData['battle_hp'])
            battling = True
            print("authorPoke Starting Health:", authorPoke.health)
            print("opponentPoke Starting Health:", opponentPoke.health)
            while opponentPoke.health > 0 and authorPoke.health > 0 and battling:
                if opponentPokeData['speed'] > authorPokeData['speed']:
                    if opponentPoke.health > 0 and authorPoke.health > 0:
                        embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                        await ctx.send(f"{member.mention}, please Specify an Move!")
                        await ctx.send(embed=embed)

                        def moveSelect(m):
                            return m.author == member and m.content.isdigit()

                        moveData = await self.check_return(ctx, ctx.channel, moveSelect)
                        move = int(moveData)
                        await opponentPoke.attack(ctx, authorPoke, opponentPokeData, authorPokeData, move)
                    else:
                        battling = False
                    if opponentPoke.health > 0 and authorPoke.health > 0:
                        embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                        await ctx.send(f"{ctx.author.mention}, please Specify an Move!")
                        await ctx.send(embed=embed)

                        def moveSelect(m):
                            return m.author == ctx.message.author and m.content.isdigit()

                        moveData = await self.check_return(ctx, ctx.channel, moveSelect)
                        move = int(moveData)
                        await authorPoke.attack(ctx, opponentPoke, authorPokeData, opponentPokeData, move)
                    else:
                        battling = False
                    # embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                    # await ctx.send(embed=embed)
                else:
                    if opponentPoke.health > 0 and authorPoke.health > 0:
                        embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                        await ctx.send(f"{ctx.author.mention}, please Specify an Move!")
                        await ctx.send(embed=embed)

                        def moveSelect(m):
                            return m.author == ctx.author and m.content.isdigit()

                        moveData = await self.check_return(ctx, ctx.channel, moveSelect)
                        move = int(moveData)
                        await authorPoke.attack(ctx, opponentPoke, authorPokeData, opponentPokeData, move)
                    else:
                        battling = False
                    if opponentPoke.health > 0 and authorPoke.health > 0:
                        embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                        await ctx.send(embed=embed)
                        await ctx.send(f"{member.mention}, please Specify an Move!")

                        def moveSelect(m):
                            return m.author == member and m.content.isdigit()

                        moveData = await self.check_return(ctx, ctx.channel, moveSelect)
                        move = int(moveData)
                        await opponentPoke.attack(ctx, authorPoke, opponentPokeData, authorPokeData, move)
                    else:
                        battling = False
                    # embed = await self.battleEmbed(authorPoke, opponentPoke, authorPokeData, opponentPokeData)
                    # await ctx.send(embed=embed)
            if opponentPoke.health > 0:
                print("opponentPoke Wins!")
                await ctx.send(f"{member.mention} won the battle!")
                completed, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(ctx.message.author,
                                                                                                opponentPokeData, True)
                if evolved:
                    await member.send(
                        f"Congrats {member.mention}! You have evolved your {old_name.capitalize()} into a {pokename.capitalize()}!")
                elif levelup:
                    await member.send(
                        f"Congrats {member.mention}! Your {pokename.capitalize()} advanced to level {level}!")
                winner_credits, loser_credits = battleCredits(authorPokeData['lvl'])
                await ctx.send(f"{ctx.author.mention}, you had to pay {member.mention}, {winner_credits} credits")
                failed = await helpers.add_money(member, ctx.guild, winner_credits)
                if failed:
                    await ctx.send(f"Transaction Failed: {ctx.author.mention} has too many Credits!")
                    return
                null = await helpers.add_money(ctx.author, ctx.guild, loser_credits)
            else:
                print("authorPoke Wins!")
                await ctx.send(f"{ctx.author.mention} won the battle!")
                completed, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(ctx.message.author,
                                                                                                authorPokeData, True)
                if evolved:
                    await ctx.author.send(
                        f"Congrats {ctx.author.mention}! You have evolved your {old_name.capitalize()} into a {pokename.capitalize()}!")
                elif levelup:
                    await ctx.author.send(
                        f"Congrats {ctx.author.mention}! Your {pokename.capitalize()} advanced to level {level}!")
                winner_credits, loser_credits = battleCredits(authorPokeData['lvl'])
                await ctx.send(f"{member.mention}, you had to pay {ctx.author.mention}, {winner_credits} credits")
                failed = await helpers.add_money(ctx.author, ctx.guild, winner_credits)
                if failed:
                    await ctx.send(f"Transaction Failed: {ctx.author.mention} has too many Credits!")
                    return
                null = await helpers.add_money(member, ctx.guild, loser_credits)
        else:
            await ctx.send("Terminating Battle Process.")

    async def battleEmbed(self, authorPoke, opponentPoke, authorData, opponentData):
        guild = discord.utils.get(self.bot.guilds, id=640378786545664030)
        str_title = "__blakCord Battle__"
        embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
        str_desc = ""
        authorPokeName = authorData['name'].title()
        oppenentPokeName = opponentData['name'].title()
        if authorData['form'] is not None:
            if authorData['form'] == 'alolan':
                authorPokeName += " (Alolan)"
            else:
                authorPokeName += f"({authorData['form']})"
        if opponentData['form'] is not None:
            if authorData['form'] == 'alolan':
                oppenentPokeName += " (Alolan)"
            else:
                oppenentPokeName += f"({opponentData['form']})"
        newAuthorMoves = []
        newOpponentMoves = []
        authorMoves = ""
        opponentMoves = ""
        authorTypes = ""
        opponentTypes = ""
        for type in authorData['type']:
            emoji = discord.utils.get(guild.emojis, name=f"{type}1")
            authorTypes += f"{emoji}"
        for item in authorData['moves']:
            word = json.loads(item)
            if len(str(word['name']).split('-')) > 1:
                new_words = str("{}").format(' '.join([word.capitalize() for word in str(word['name']).split('-')]))
                newAuthorMoves.append(new_words)
            else:
                newAuthorMoves.append(str(word['name']).capitalize())
        for type in opponentData['type']:
            emoji = discord.utils.get(guild.emojis, name=f"{type}1")
            opponentTypes += f"{emoji}"
        for item in opponentData['moves']:
            word = json.loads(item)
            if len(str(word['name']).split('-')) > 1:
                new_words = str("{}").format(' '.join([word.capitalize() for word in str(word['name']).split('-')]))
                newOpponentMoves.append(new_words)
            else:
                newOpponentMoves.append(str(word['name']).capitalize())
        a = 0
        for word in newAuthorMoves:
            a += 1
            authorMoves += f"{a}. {word}\n"
        b = 0
        for word in newOpponentMoves:
            b += 1
            opponentMoves += f"{b}. {word}\n"
        embed.add_field(name=authorPokeName, value=f"**HP**: {authorPoke.health}/{authorData['hp']}\n\n{authorMoves}",
                        inline=True)
        embed.add_field(name=oppenentPokeName,
                        value=f"**HP**: {opponentPoke.health}/{opponentData['hp']}\n\n{opponentMoves}", inline=True)
        embed.set_footer(text=embed_footer)
        return embed

    async def storeEmbed(self):
        str_title = "__blakCord Store__"
        embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
        str_desc = ""
        url = "https://pokeapi.co/api/v2/item-category/10/"
        evo_items = requests.get(url).json()
        extra_items = [198, 203, 204, 210]
        itemList = []
        for item in evo_items['items']:
            itemURL = item['url']
            itemDesc = requests.get(itemURL).json()
            for i in range(len(itemDesc['game_indices'])):
                if itemDesc['game_indices'][i]['generation']['name'] == "generation-iii":
                    itemList.append([itemDesc['name'], itemDesc['id'], itemDesc['cost']])
        for num in extra_items:
            extra_url = f"https://pokeapi.co/api/v2/item/{num}"
            itemInfo = requests.get(extra_url).json()
            itemList.append([itemInfo['name'], itemInfo['id'], itemInfo['cost']])
        itemList.sort(key=self.sortItemID)
        print(itemList)
        for items in itemList:
            items[1] = str(items[1])
            if len(items[0]) < 13:
                for a in range(13 - len(items[0])):
                    items[0] += " "
            if len(items[1]) < 3:
                for a in range(3 - len(items[1])):
                    items[1] = " " + items[1]
            items[0] = f"__**{items[0].replace('-', ' ').title()}**__"
            str_desc += f"{items[0]} - **ItemID:** `{items[1]}` - **Price:** `{items[2]}`\n"
        embed.add_field(name="__**EVO Items:**__", value=str_desc[:2048 - len(str_title + embed_footer)], inline=True)
        # embed.description = str_desc[:2048 - len(str_title + embed_footer)]
        embed.set_footer(text=embed_footer)
        return embed

    @c.group(name="pstore")
    async def blak_store(self, ctx):
        if ctx.invoked_subcommand is None:
            if ctx.channel.id != 1024544453177917471:
                await ctx.send("Please use <#1024544453177917471> for this command")
                return
            embed = await self.storeEmbed()
            await ctx.send(embed=embed)

    @blak_store.command(name="buy")
    async def buy(self, ctx, itemID: int = None):
        if ctx.channel.id != 1024544453177917471:
            await ctx.send("Please use <#1024544453177917471> for this command")
            return
        if itemID is None:
            await ctx.send("Please Specify an ItemID")
            return
        data = await helpers.get_player_postgresData(ctx.author, ctx.guild, 'pokecord_items')
        if data['pokecord_items'] is None:
            itemDict = {}
        else:
            itemDict = json.loads(data['pokecord_items'])
        print(itemDict)
        url = f"https://pokeapi.co/api/v2/item/{itemID}/"
        _item = requests.get(url).json()
        pokeItem = PokeItem(_item).__dict__
        if await helpers.enough_money(ctx.author, ctx.guild, pokeItem['cost']):
            if str(_item['id']) in itemDict:
                itemDict[str(_item['id'])]['total'] += 1
            else:
                itemDict[str(_item['id'])] = pokeItem
            users_sql = 'UPDATE discord_data.users SET "pokecord_items" = $1 WHERE "id" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, json.dumps(itemDict), ctx.author.id,
                                                       ctx.guild.id)
            await helpers.withdraw_money(ctx.author, ctx.guild, pokeItem['cost'])
            await ctx.send(f"Successfully purchased a {_item['name'].replace('-', ' ').title()}")
        else:
            await ctx.send("You don't have enough Credits for this purchase!")

    @c.group(name='sitems')
    async def blak_items(self, ctx):
        if ctx.invoked_subcommand is None:
            rawdata = await helpers.get_player_postgresData(ctx.author, ctx.message.guild, 'pokecord_items')
            data = rawdata['pokecord_items']
            if data is None or len(data) == 0:
                await ctx.send(f"{ctx.author.mention}, your bag is empty!")
                return
            else:
                str_title = "__{}'s Item Bag__".format(ctx.author.name)
                itemList = json.loads(data)
                embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                str_desc = ""
                for item, value in itemList.items():
                    if len(value['name']) < 13:
                        for a in range(13 - len(value['name'])):
                            value['name'] += " "
                    if len(item) < 3:
                        for a in range(3 - len(item)):
                            item += " "
                    value['name'] = f"__**{value['name'].replace('-', ' ').title()}**__"
                    str_desc += f"{value['name']} - **ItemID:** `{item}` - **Total:** `{value['total']}`\n"
                # embed.add_field(name="__**Item Bag:**__", value=str_desc[:2048 - len(str_title + embed_footer)],
                #                inline=True)
                embed.description = str_desc[:2048 - len(str_title + embed_footer)]
                embed.set_footer(text=embed_footer)
                await ctx.send(embed=embed)

    @blak_items.command(name="use")
    async def item_use(self, ctx, itemID=None, pokemonUID: int = None):
        rawdata = await helpers.get_player_postgresData(ctx.author, ctx.message.guild, 'pokecord_items')
        data = json.loads(rawdata['pokecord_items'])
        count_sql = " SELECT * FROM discord_data.pokecord_poke_data where ownerid = $1 and uid = $2"
        poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, pokemonUID)
        if data is None or len(data) == 0:
            await ctx.send(f"{ctx.author.mention}, your bag is empty!")
        elif itemID is None or pokemonUID is None:
            await ctx.send("Please Specify a itemID and PokemonUID!")
        elif poke_info is None:
            await ctx.send("PokemonUID does not match any Pokemon in your Box!")
        else:
            item = data[str(itemID)]
            if "stone" in item['name'] or item['name'] in ['dragon-scale', 'up-grade']:
                oldname, pokename, evolved = await self.itemEvolve(ctx, poke_info['name'], poke_info, item['name'])
                if evolved:
                    await ctx.send(
                        f"Congratulations! You evolved your {oldname.capitalize()} into a {pokename.capitalize()}")
                    data[str(itemID)]['total'] -= 1
                    if data[str(itemID)]['total'] == 0:
                        try:
                            del data[str(itemID)]
                        except KeyError:
                            print(f"Key {itemID}  not found")
                            pass
                    users_sql = 'UPDATE discord_data.users SET "pokecord_items" = $1 WHERE "id" = $2 and "ServerID" = $3'
                    await helpers.transaction_postgresDatabase(users_sql, json.dumps(data), ctx.author.id,
                                                               ctx.guild.id)
                else:
                    await ctx.send(f"This item is not compatible with this Pokemon")

    @blak_items.command(name="give")
    async def item_give(self, ctx, itemID=None, pokemonUID: int = None):
        rawdata = await helpers.get_player_postgresData(ctx.author, ctx.message.guild, 'pokecord_items')
        data = json.loads(rawdata['pokecord_items'])
        count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "uid" = $2'
        poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, pokemonUID)
        if data is None or len(data) == 0:
            await ctx.send(f"{ctx.author.mention}, your bag is empty!")
        elif itemID is None or pokemonUID is None:
            await ctx.send("Please Specify a itemID and PokemonUID!")
        elif poke_info is None:
            await ctx.send("PokemonUID does not match any Pokemon in your Box!")
        else:
            item = data[str(itemID)]
            print(item)
            item['total'] -= 1
            if data[str(itemID)]['total'] == 0:
                try:
                    del data[str(itemID)]
                except KeyError:
                    print(f"Key {itemID}  not found")
                    pass
            users_sql = 'UPDATE discord_data.pokecord_poke_data SET "item" = $1 WHERE "ownerid" = $2 and "uid" = $3'
            await helpers.transaction_postgresDatabase(users_sql, json.dumps(item), ctx.author.id, pokemonUID)
            users_sql = 'UPDATE discord_data.users SET "pokecord_items" = $1 WHERE "id" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, json.dumps(data), ctx.author.id,
                                                       ctx.guild.id)
            await ctx.send(f"Gave {poke_info['name'].title()} a(n) {item['name']}")

    @blak_items.command(name="take")
    async def item_take(self, ctx, itemID=None, pokemonUID: int = None):
        rawdata = await helpers.get_player_postgresData(ctx.author, ctx.message.guild, 'pokecord_items')
        data = json.loads(rawdata['pokecord_items'])
        count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "uid" = $2'
        poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, pokemonUID)
        if data is None or len(data) == 0:
            await ctx.send(f"{ctx.author.mention}, your bag is empty!")
        elif itemID is None or pokemonUID is None:
            await ctx.send("Please Specify a itemID and PokemonUID!")
        elif poke_info is None:
            await ctx.send("PokemonUID does not match any Pokemon in your Box!")
        else:
            item = data[str(itemID)]
            print(item)
            item['total'] -= 1
            if data[str(itemID)]['total'] == 0:
                try:
                    del data[str(itemID)]
                except KeyError:
                    print(f"Key {itemID}  not found")
                    pass
            users_sql = 'UPDATE discord_data.pokecord_poke_data SET "item" = $1 WHERE "ownerid" = $2 and "uid" = $3'
            await helpers.transaction_postgresDatabase(users_sql, json.dumps(item), ctx.author.id, pokemonUID)
            users_sql = 'UPDATE discord_data.users SET "pokecord_items" = $1 WHERE "id" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, json.dumps(data), ctx.author.id,
                                                       ctx.guild.id)
            await ctx.send(f"Gave {poke_info['name'].title()} a(n) {item['name']}")

    @helpers.is_creator()
    @c.command(name='pspawn')
    async def cmd_spawn(self, ctx, pokeNum=None, num: int = 0):
        await ctx.message.delete()
        if num == 1:
            shiny = True
        else:
            shiny = False
        await self._spawn(pokeNum, True, shiny)

    async def _spawn(self, message=None, command=False, shiny=False, manual=False):
        self.caught = False
        channel = self.bot.get_channel(1024544453177917471)
        # if command is True:
        #    await channel.send('Previous Pokemon Despawned!')
        if message != None:
            if message.isdigit():
                rnum = int(message)
                if rnum in alolan_pokemon:
                    ind = alolan_pokemon.index(rnum)
                    arnum = alolanIds[ind]
                    rnum = random.choice([rnum, arnum])
                pokeNum = str(rnum)
                url = f"http://pokeapi.co/api/v2/pokemon/{pokeNum}/"
            else:
                msg = "When using spawn must be number if input given"
                await channel.send(msg)
                return
        else:
            # notNewNum = True
            # rnum = None
            # while notNewNum:
            rnum = randomGenerator(1, 386)
            #    if rnum not in self.randNums:
            #        self.randNums.append(rnum)
            #        notNewNum = False
            if rnum in (143, 144, 145, 146, 147, 148, 149, 150, 151, 243, 244, 245, 246, 247, 248, 249, 250, 251, 377,
                        378, 379, 380, 381, 382, 383, 384, 385, 386):
                chance = randomGenerator(1, 300)
                if 150 != chance:
                    anum = randomGenerator(1, 142)
                    bnum = randomGenerator(152, 242)
                    cnum = randomGenerator(252, 376)
                    rnum = random.choice([anum, bnum, cnum])
            orig_rnum = rnum
            if rnum in alolan_pokemon:
                ind = alolan_pokemon.index(rnum)
                arnum = alolanIds[ind]
                rnum = random.choice([orig_rnum, arnum])
            pokeNum = str(rnum)
            url = f"http://pokeapi.co/api/v2/pokemon/{pokeNum}/"
            # Checks if Pokemon number exists. If it does pulls file
            pokeNum = helpers.pokeNumConverter(pokeNum)
        if os.path.isfile("db/pokecordData/{}".format(pokeNum)) is not False:
            with open('db/pokecordData/{}'.format(pokeNum), 'r') as file:
                self.pokestore = json.load(file)
                self.pokestore['form'] = None
                if self.pokestore['id'] in alolanIds:
                    ind = alolanIds.index(rnum)
                    self.pokestore['id'] = alolan_pokemon[ind]
                    self.pokestore['form'] = "alolan"
                elif len(self.pokestore['forms']) > 1 and self.pokestore['id'] != 172:
                    form = random.choice(self.pokestore['forms'])
                    formNameData = form['name'].split("-")[1]
                    if self.pokestore['id'] == 201:
                        if len(formNameData) > 1:
                            name = ""
                            for i in range(2):
                                name += formNameData[i]
                            formNameData = name
                    self.pokestore['form'] = formNameData.upper()
                print(self.pokestore['form'])
        else:
            t0 = datetime.now()
            self.pokestore = requests.post(url).json()
            if len(self.pokestore['name'].split("-")) > 1 and self.pokestore['id'] != 172:
                self.pokestore['name'] = self.pokestore['name'].split("-")[0]
            self.pokestore['form'] = None
            if self.pokestore['id'] in alolanIds:
                ind = alolanIds.index(rnum)
                self.pokestore['id'] = alolan_pokemon[ind]
                self.pokestore['form'] = "alolan"
            elif len(self.pokestore['forms']) > 1:
                form = random.choice(self.pokestore['forms'])
                formNameData = form['name'].split("-")[1]
                if self.pokestore['id'] == 201:
                    if len(formNameData) > 1:
                        name = ""
                        for i in range(2):
                            name += formNameData[i]
                        formNameData = name
                self.pokestore['form'] = formNameData.upper()
            print(self.pokestore['form'])
            pokeNum = helpers.pokeNumConverter(self.pokestore['id'])
            filename = Path(f"db/pokecordData/{pokeNum}")
            filename.touch(exist_ok=True)
            with open(f"db/pokecordData/{pokeNum}", 'w') as file:
                json.dump(self.pokestore, file)
        if shiny:
            self.pokestore['shiny'] = True
        if not manual:
            file = await self.convert_bw(self.pokestore)
            if file is not None:
                embed = discord.Embed()
                embed.title = 'A Wild Pokémon appears!'
                embed.description = f"Guess the pokemon and type {config['prefix']}pcatch <pokemon> to catch it!"
                embed.set_image(url="attachment://poke_image.png")
                if not self.caught:
                    await channel.send('Previous Pokemon Despawned!')
                sent_msg = await channel.send(embed=embed, file=file)

                self.spawn_msg = sent_msg.id
                game = discord.Game("blakCord BETA 0.85!")
                await self.bot.change_presence(status=discord.Status.online, activity=game)
                self.time_to_spawn = None
            else:
                await self._spawn()

    # @c.command(name='missing')
    async def cmd_missing(self, ctx, message=None):
        if self.spawn_msg is None:
            new_embed = discord.Embed()
            for embed in self.spawn_msg.embeds:
                new_embed = embed
                new_embed.set_thumbnail(url=self.imgr_result)
            await self.bot.edit_message(self.spawn_msg, embed=new_embed)

    @c.command(name='ppokedex')
    async def pokeDEX(self, ctx, page: int = 1, sorting='dex'):
        data = await helpers.get_player_postgresData(ctx.author, ctx.message.guild, 'pokedex')
        if data:
            pokeList = data['pokedex']
            pokeList.sort(key=self.sortPokeDEX)
            str_title = "__{}'s PokeDEX__".format(ctx.author.name)
            embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
            poke_count = len(pokeList)
            str_desc = ""
            str_footer = "Obtained {} of 251 Pokemon. Page: {} of {}".format(poke_count, page, int(251 / 15) + 1)
            num = 15 * page
            pokeDEX = []
            for i in range(251):
                # print(i)
                if any(i + 1 == int(sublist[0]) for sublist in pokeList):
                    listItem = next(c for c in pokeList if c[0] == str(i + 1))
                    pokeDEX.append([listItem[0], listItem[1]])
                else:
                    pokeDEX.append([str(i + 1), "..."])
            try:
                for item in pokeDEX[num - 15: num]:
                    str_desc += "__**#{}:**__ {}\n".format(item[0], item[1].upper())
            except:
                str_desc = ""
                for item in data[num - 15:]:
                    str_desc += "__**#{}:**__ {}\n".format(item[0], item[1].upper())
            embed.description = str_desc[:2048 - len(str_title + str_footer)]
            embed.set_footer(text=str_footer)
            await ctx.channel.send(embed=embed)

    @c.command(name='plist')
    async def pokelist(self, ctx, page: int = 1, sorting="uid"):
        """Lists all blakCord Pokemon in the order you have caught them
        Example: $rlist *Optional: <page-number> <sorting>*"""
        # if ctx.channel.id == 1024544453177917471:
        #    await ctx.send("Please use any other channel for this command!")
        #    return
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            str_title = "__{}'s Pokemon__".format(ctx.author.name)
            embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
            count_sql = 'SELECT "name", COUNT(*) FROM discord_data.pokecord_poke_data where "ownerid" = $1 GROUP BY "name"'
            poke_count = len(await helpers.query_postgresDatabase(count_sql, ctx.author.id, multiple=True))
            str_desc = ""
            str_footer = "Obtained {} of 251 Pokemon. Page: {} of {}".format(poke_count, page, int(len(data) / 10) + 1)
            num = 10 * page

            if sorting == "dex":
                data.sort(key=self.sortDEX)
            elif sorting == "uid":
                data.sort(key=self.sortUID)
            elif sorting == "iv":
                for item in data:
                    item['iv'] = int(ivPercentage(item))
                data.sort(key=self.sortIV)
            else:
                data.sort(key=self.sortNAME)
            try:
                for item in data[num - 10: num]:
                    pokename = item['name'].capitalize()
                    attrP = ""
                    if item['form'] is not None:
                        if item['form'] == 'alolan':
                            pokename += " (A)"
                        else:
                            pokename += f"({item['form']})"
                    if item['starred']:
                        attrP += "⭐"
                    if item['shiny']:
                        attrP += "<a:shiny:730173905800790127>"
                    if item['lucky']:
                        attrP += "<:luckpokemon:730175041886486681>"
                    str_desc += "__**{}**__ UID: *{}* - IV: *{}%{}*\n".format(pokename, item['uid'],
                                                                              int(ivPercentage(item)), attrP)
            except:
                str_desc = ""
                for item in data[num - 10:]:
                    str_desc += item
            embed.description = str_desc[:2048 - len(str_title + str_footer)]
            embed.set_footer(text=str_footer)
            user_data = await helpers.get_player_postgresData(ctx.author, ctx.guild, '*')
            try:
                msg_id = user_data['list_msg_id']
                message = await ctx.channel.fetch_message(msg_id)
                await message.delete()
            except:
                pass
            await ctx.message.delete()
            new_message = await ctx.channel.send(embed=embed)
            users_sql = 'UPDATE discord_data.users SET "list_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, ctx.author.id,
                                                       ctx.guild.id)
            # else:
            #    await ctx.channel.send(embed=embed)
            #    users_sql = 'UPDATE discord_data.users SET info_msg_id = $1 WHERE id = $2 and servID = $3'
            #    await helpers.transaction_postgresDatabase(users_sql, ctx.message.id, str(ctx.author.id),
            #                                               str(ctx.guild.id))
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @c.command(name='pselect')
    async def poke_select(self, ctx, id: int = None):
        """Selects a Pokemon to be your partner
        Example: !pselect <uid>"""
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if id is None:
            await ctx.send("Please Specify a Pokemon ID")
            return
        elif data:
            try:
                old_sql = 'UPDATE discord_data.pokecord_poke_data SET "selected" = $1 WHERE "selected" = $2 and "ownerid" = $3'
                await helpers.transaction_postgresDatabase(old_sql, False, True, ctx.author.id)
                poke_sql = 'select "name" from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
                pokeinfo = await helpers.query_postgresDatabase(poke_sql, id, ctx.author.id)
                pokename = pokeinfo['name']
                users_sql = 'UPDATE discord_data.pokecord_poke_data SET "selected" = $1 WHERE "uid" = $2 and "ownerid" = $3'
                await helpers.transaction_postgresDatabase(users_sql, True, id, ctx.author.id)
                msg = "{} set as companion!".format(pokename.capitalize())
                await ctx.channel.send(msg)
            except Exception as e:
                print(e)
                await ctx.send("An error occured! Please try again!")
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @c.command(name='pstar')
    async def poke_star(self, ctx, id: int = None):
        """Stars a Pokemon
        Example: pstar <uid>"""
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if id is None:
            await ctx.send("Please Specify a Pokemon ID")
            return
        elif data:
            try:
                poke_sql = 'select "name" from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
                pokeinfo = await helpers.query_postgresDatabase(poke_sql, id, ctx.author.id)
                print(pokeinfo)
                pokename = pokeinfo['name']
                users_sql = 'UPDATE discord_data.pokecord_poke_data SET "starred" = $1 WHERE "uid" = $2 and "ownerid" = $3'
                await helpers.transaction_postgresDatabase(users_sql, True, id, ctx.author.id)
                msg = "{} starred!".format(pokename.capitalize())
                await ctx.channel.send(msg)
            except Exception as e:
                print(e)
                await ctx.send("An error occured! Please try again!")
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @c.command(name='punstar')
    async def poke_unstar(self, ctx, id: int = None):
        """Un-Stars a Pokemon
        Example: punstar <uid>"""
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if id is None:
            await ctx.send("Please Specify a Pokemon ID")
            return
        elif data:
            try:
                poke_sql = 'select "name" from discord_data.pokecord_poke_data WHERE "uid" = $1 and "ownerid" = $2'
                pokeinfo = await helpers.query_postgresDatabase(poke_sql, id, ctx.author.id)
                print(pokeinfo)
                pokename = pokeinfo['name']
                users_sql = 'UPDATE discord_data.pokecord_poke_data SET "starred" = $1 WHERE "uid" = $2 and "ownerid" = $3'
                await helpers.transaction_postgresDatabase(users_sql, False, id, ctx.author.id)
                msg = "{} unstarred!".format(pokename.capitalize())
                await ctx.channel.send(msg)
            except Exception as e:
                print(e)
                await ctx.send("An error occured! Please try again!")
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @c.group(name='pinfo')
    async def poke_info(self, ctx):
        """Shows info on specified pokemon
        Example: $rinfo *Optional: <uid>*"""
        if ctx.invoked_subcommand is None:
            # if ctx.channel.id == 716718691995222036:
            #    await ctx.send("Please use any other channel for this command!")
            #    return
            try:
                num = int(ctx.message.content.split()[1])
            except:
                num = None
            data = await helpers.get_pokecord_postgresData(ctx.author, "*")
            if data:
                if num is not None:
                    count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "uid" = $2'
                    poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, num)
                else:
                    count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "selected" = $2'
                    poke_info = await helpers.query_postgresDatabase(count_sql, ctx.author.id, True)
                    if poke_info is None:
                        temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                        print(temp)
                        poke_info = temp[0]
                        print(poke_info)
                embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
                if embed is None:
                    str_title = "__{}'s Pokemon__".format(ctx.author.name)
                    str_footer = "Obtained {} of 802 Pokemon".format(len(self.pokelist.keys()))
                    embed = discord.Embed(type="rich", title=str_title, color=0xEEE8AA)
                    str_desc = "End of List! Run Command Again"
                    embed.description = str_desc[:2048 - len(str_title + str_footer)]
                    embed.set_footer(text=str_footer)
                await ctx.message.delete()
                new_message = await ctx.channel.send(embed=embed, file=file)
                users_sql = 'UPDATE discord_data.users SET "info_msg_id" = $1, "position" = $2 WHERE "UserID" = $3 and "ServerID" = $4'
                await helpers.transaction_postgresDatabase(users_sql, new_message.id, int(poke_info['uid']),
                                                           ctx.author.id,
                                                           ctx.guild.id)
            else:
                msg = "{} you have caught no Pokemon".format(ctx.author.name)
                await ctx.channel.send(msg)

    async def embed_info(self, user, pokename, embedPokeList):
        guild = discord.utils.get(self.bot.guilds, id=306822100499300352)
        pokename = pokename.capitalize()
        str_title = "__{}'s Pokemon__".format(user.name)
        count_sql = 'SELECT "name", COUNT(*) FROM discord_data.pokecord_poke_data where "ownerid" = $1 GROUP BY "name"'
        poke_count = len(await helpers.query_postgresDatabase(count_sql, user.id, multiple=True))
        str_footer = "Obtained {} of 802 Pokemon".format(poke_count)
        pokeNum = helpers.pokeNumConverter(embedPokeList['index'])
        page_attr = ""
        if embedPokeList['form'] is not None:
            if embedPokeList['form'] == 'alolan':
                page_attr += "A"
                pokename += " (Alolan)"
            else:
                page_attr += embedPokeList['form']
                pokename += f" ({embedPokeList['form']})"
        if embedPokeList['starred']:
            pokename = "⭐" + pokename
        if embedPokeList['lucky']:
            pokename = "<:luckpokemon:730175041886486681>" + pokename
        if embedPokeList['shiny']:
            pokename = "<a:shiny:730173905800790127>" + pokename
            page_attr += "_s"
        pokename += f" **UID:** {embedPokeList['uid']} **IV%:** {int(ivPercentage(embedPokeList))}%"
        _image = f"{pokeNum}{page_attr}.png"
        if os.path.isfile("./db/pokecordData/Images/{}".format(_image)) is not False:
            img = Image.open("./db/pokecordData/Images/{}".format(_image))
            print("Internal Image")
        else:
            page_url = f"https://archives.bulbagarden.net/wiki/File:HOME{_image}"
            page = requests.get(page_url)
            soup = BeautifulSoup(page.content, 'html.parser')
            for a in soup.findAll('a', href=True, attrs={'class': 'internal'}):
                print(a)
                url = a.get('href')
            response = requests.get(f"{url}")
            try:
                img = Image.open(BytesIO(response.content))
            except UnidentifiedImageError:
                try:
                    page = requests.get(f"https://archives.bulbagarden.net/wiki/File:HOME{_image}")
                    soup = BeautifulSoup(page.content, 'html.parser')
                    for a in soup.findAll('a', href=True, attrs={'class': 'internal'}):
                        print(a)
                        url = a.get('href')
                    response = requests.get(f"{url}")
                    img = Image.open(BytesIO(response.content))
                except UnidentifiedImageError:
                    page_attr = ""
                    if embedPokeList['form'] is not None:
                        if embedPokeList['form'] == 'alolan':
                            page_attr += "_f2"
                    _image = f"{pokeNum}{page_attr}.png"
                    response = requests.get(f"https://assets.pokemon.com/assets/cms2/img/pokedex/full/{_image}")
                    img = Image.open(BytesIO(response.content))
            img.save(f"./db/pokecordData/Images/{_image}")
        file = discord.File(
            "./db/pokecordData/Images/{}".format(_image),
            filename="{}".format(_image))
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
        for type in embedPokeList['type']:
            emoji = discord.utils.get(guild.emojis, name=f"{type}1")
            types += f"{emoji}"
        for item in embedPokeList['moves']:
            word = json.loads(item)
            if len(str(word['name']).split('-')) > 1:
                new_words = str("{}").format(' '.join([word.capitalize() for word in str(word['name']).split('-')]))
                new_items.append(new_words)
            else:
                new_items.append(str(word['name']).capitalize())
        str_desc = "**Name:**  {} {}\n**Type:** {}\n**Nature:**  {}\n**LVL:**  {}\n**HP:**  {} -  **IV:** {}\n**ATK:**  {} -  " \
                   "**IV:** {}\n**DEF:**  {} -  **IV:** {}\n**SP_ATK:**  {} -  **IV:** {}\n**SP_DEF:**  {} -  **" \
                   "IV:** {}\n**SPD:**  {} -  **IV:** {}\n**Moves:**\n- {}\n**Caught On:**  {}".format(
            pokename, gender, types, str(embedPokeList['nature']).capitalize(), embedPokeList['lvl'],
            embedPokeList['hp'],
            embedPokeList['hp_iv'], embedPokeList['attack'], embedPokeList['attack_iv'], embedPokeList['defense'],
            embedPokeList['defense_iv'], embedPokeList['sp_attack'], embedPokeList['special_attack_iv'],
            embedPokeList['sp_defense'], embedPokeList['special_defense_iv'], embedPokeList['speed'],
            embedPokeList['speed_iv'],
            str("{}").format('\n- '.join([word for word in new_items])),
            embedPokeList['caughton'])
        embed.description = str_desc[:2048 - len(str_title + str_footer)]
        # embed.set_image(
        #    url=f"https:{url}"
        # f"https://assets.pokemon.com/assets/cms2/img/pokedex/full/{pokeNum}.png"
        # self.pokestore['sprites']['front_default']
        # )
        embed.set_image(
            url="attachment://{}".format(_image))
        embed.set_footer(text=str_footer)
        return embed, file

    @poke_info.command(name="next")
    async def poke_next(self, ctx):
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
            count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "uid" = $2'
            poke_info = data[position]
            if poke_info is None:
                temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                # print(temp)
                poke_info = temp[0]
                # print(poke_info)
            users_sql = 'UPDATE discord_data.users SET "position" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            # print(int(poke_info['uid']), position)
            await helpers.transaction_postgresDatabase(users_sql, int(poke_info['uid']),
                                                       ctx.author.id, ctx.guild.id)
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Obtained {} of 802 Pokemon".format(len(self.pokelist.keys()))
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
            await ctx.message.delete()
            new_message = await ctx.channel.send(embed=embed, file=file)
            users_sql = 'UPDATE discord_data.users SET "info_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, ctx.author.id,
                                                       ctx.guild.id)
            # else:
            #    await ctx.channel.send(embed=embed)
            #    users_sql = 'UPDATE discord_data.users SET info_msg_id = $1 WHERE id = $2 and servID = $3'
            #    await helpers.transaction_postgresDatabase(users_sql, ctx.message.id, str(ctx.author.id),
            #                                               str(ctx.guild.id))
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @poke_info.command(name="prev")
    async def poke_prev(self, ctx):
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
            # count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "uid" = $2'
            poke_info = data[position]
            if poke_info is None:
                temp = await helpers.get_pokecord_postgresData(ctx.author, "*")
                # print(temp)
                poke_info = temp[0]
                # print(poke_info)
            users_sql = 'UPDATE discord_data.users SET "position" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            # print(int(poke_info['uid']), position)
            await helpers.transaction_postgresDatabase(users_sql, int(poke_info['uid']),
                                                       ctx.author.id, ctx.guild.id)
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Obtained {} of 802 Pokemon".format(len(self.pokelist.keys()))
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
            await ctx.message.delete()
            new_message = await ctx.channel.send(embed=embed, file=file)
            users_sql = 'UPDATE discord_data.users SET "info_msg_id" = $1 WHERE "UserID" = $2 and "ServerID" = $3'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, ctx.author.id,
                                                       ctx.guild.id)
            # else:
            #    await ctx.channel.send(embed=embed)
            #    users_sql = 'UPDATE discord_data.users SET info_msg_id = $1 WHERE id = $2 and servID = $3'
            #    await helpers.transaction_postgresDatabase(users_sql, ctx.message.id, str(ctx.author.id),
            #                                               str(ctx.guild.id))
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @poke_info.command(name="latest")
    async def poke_latest(self, ctx):
        data = await helpers.get_pokecord_postgresData(ctx.author, "*")
        if data:
            data.sort(key=self.sortUID)
            poke_info = data[len(data) - 1]
            embed, file = await self.embed_info(ctx.author, poke_info['name'], poke_info)
            if embed is None:
                str_title = "__{}'s Pokemon__".format(ctx.author.name)
                str_footer = "Obtained {} of 802 Pokemon".format(len(self.pokelist.keys()))
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
            await ctx.message.delete()
            new_message = await ctx.channel.send(embed=embed, file=file)
            users_sql = 'UPDATE discord_data.users SET "info_msg_id" = $1, "position" = $2 WHERE "UserID" = $3 and "ServerID" = $4'
            await helpers.transaction_postgresDatabase(users_sql, new_message.id, int(poke_info['uid']), ctx.author.id,
                                                       ctx.guild.id)
        else:
            msg = "{} you have caught no Pokemon".format(ctx.author.name)
            await ctx.channel.send(msg)

    @c.command(name='bad_gif')
    @helpers.is_owner()
    async def cmd_bad_gif(self, ctx, message=None):
        if message is None:
            if self.pokestore is None:
                msg = "No pokemon is spawned"
                await ctx.channel.send(msg)
                return
            file = open("./db/badGIF.txt", 'a+')
            file.write("{}#{}\n".format(self.pokestore['name'], self.pokestore['id']))
            file.close()
            msg = "Pokemon has been added to file"
            await ctx.channel.send(msg)
        else:
            self.sort_gif_file()

    def sort_gif_file(self):
        with open("./db/badGIF.txt", 'r') as file:
            docText = file.read().strip()
        docText = docText.split("\n")
        with open("./db/sorted_badGIF.txt", 'w') as file:
            file.write("\n".join(sorted(set(docText), key=lambda item: int(item.split('#')[-1]))))

    async def check_capture(self, message, pokemon):
        if self.pokestore is None:
            return False
        if self.pokestore['name'].strip().lower().translate(
                str.maketrans('', '', string.punctuation)) == pokemon.lower().strip().translate(
            str.maketrans('', '', string.punctuation)):
            self.caught = True
            data = await helpers.get_player_postgresData(message.author, message.guild, "total_pokemon")
            try:
                self.pokestore['uid'] = data['total_pokemon'] + 1
            except KeyError:
                self.pokestore['uid'] = 1
            except TypeError:
                self.pokestore['uid'] = 1
            if 'shiny' not in self.pokestore:
                if message.author.id == 290035422011326464 and randomGenerator(1, 20) == 1:
                    self.pokestore['shiny'] = True
                elif helpers.check_role(message.author, contributorrole) and randomGenerator(1, 425) == 1:
                    self.pokestore['shiny'] = True
                elif randomGenerator(1, 475) == 1:
                    self.pokestore['shiny'] = True
                else:
                    self.pokestore['shiny'] = False
            pokeNum = helpers.pokeNumConverter(self.pokestore['id'])
            embed = discord.Embed(type="rich", title="Gotcha!", color=0xEEE8AA)
            name = self.pokestore['name'].upper()
            page_attr = ""
            if self.pokestore['form'] is not None:
                if self.pokestore['form'] == 'alolan':
                    page_attr += "A"
                else:
                    page_attr += self.pokestore['form']
            if self.pokestore['shiny']:
                page_attr += "_s"
                name = "<a:shiny:730173905800790127> " + name
            _image = f"{pokeNum}{page_attr}.png"
            if os.path.isfile("./db/pokecordData/Images/{}".format(_image)) is not False:
                img = Image.open("./db/pokecordData/Images/{}".format(_image))
                print("Internal Image")
            else:
                url = f"https://archives.bulbagarden.net/wiki/File:HOME{_image}"
                response = requests.get(f"{url}")
                try:
                    img = Image.open(BytesIO(response.content))
                except UnidentifiedImageError:
                    try:
                        page = requests.get(f"https://archives.bulbagarden.net/wiki/File:HOME{_image}")
                        soup = BeautifulSoup(page.content, 'html.parser')
                        for a in soup.findAll('a', href=True, attrs={'class': 'internal'}):
                            print(a)
                            url = a.get('href')
                        response = requests.get(f"{url}")
                        img = Image.open(BytesIO(response.content))
                    except UnidentifiedImageError:
                        page_attr = ""
                        if self.pokestore['form'] is not None:
                            if self.pokestore['form'] == 'alolan':
                                page_attr += "_f2"
                        _image = f"{pokeNum}{page_attr}.png"
                        response = requests.get(f"https://assets.pokemon.com/assets/cms2/img/pokedex/full/{_image}")
                        img = Image.open(BytesIO(response.content))
                img.save(f"./db/pokecordData/Images/{_image}")
            file = discord.File(
                "./db/pokecordData/Images/{}".format(_image),
                filename="{}".format(_image))
            embed.description = "{} was caught by {}".format(self.pokestore['name'].upper(), message.author.mention)
            embed.set_image(
                url="attachment://{}".format(_image))
            # self.pokestore['sprites']['front_default']
            pokedexData = await helpers.get_player_postgresData(message.author, message.guild, 'pokedex')
            pokedex = pokedexData['pokedex']
            if pokedex is not None:
                if self.pokestore['name'] not in pokedex:
                    pokedex.append([str(self.pokestore['id']), self.pokestore['name']])
            else:
                pokedex = [[str(self.pokestore['id']), self.pokestore['name']]]
            users_sql = 'UPDATE discord_data.users SET "total_pokemon" = $1, "pokedex" = $2 WHERE "UserID" = $3 and "ServerID" = $4'
            await helpers.transaction_postgresDatabase(users_sql, self.pokestore['uid'], pokedex, message.author.id,
                                                       message.guild.id)
            await message.channel.send(embed=embed, file=file)
            await self.addPokeList(message, self.pokestore)
            self.pokestore = None
            return True
        return False

    async def convert_bw(self, poke, silhouette=True):
        txtfile_name = "./db/pokecordData/Images/poke_image.png"
        pokeNum = helpers.pokeNumConverter(poke['id'])
        page_attr = ""
        url = None
        if poke['form'] is not None:
            if poke['form'] == 'alolan':
                page_attr += "A"
            else:
                page_attr += self.pokestore['form']
        _image = f"{pokeNum}{page_attr}.png"
        if os.path.isfile("./db/pokecordData/Images/{}".format(_image)) is not False:
            img = Image.open("./db/pokecordData/Images/{}".format(_image))
        else:
            page = requests.get(f"https://archives.bulbagarden.net/wiki/File:HOME{_image}")
            soup = BeautifulSoup(page.content, 'html.parser')
            for a in soup.findAll('a', href=True, attrs={'class': 'internal'}):
                print(a)
                url = a.get('href')
            response = requests.get(f"{url}")
            try:
                img = Image.open(BytesIO(response.content))
            except UnidentifiedImageError:
                try:
                    page = requests.get(f"https://archives.bulbagarden.net/wiki/File:HOME{_image}")
                    soup = BeautifulSoup(page.content, 'html.parser')
                    for a in soup.findAll('a', href=True, attrs={'class': 'internal'}):
                        print(a)
                        url = a.get('href')
                    response = requests.get(f"{url}")
                    img = Image.open(BytesIO(response.content))
                except UnidentifiedImageError:
                    page_attr = ""
                    if poke['form'] is not None:
                        if poke['form'] == 'alolan':
                            page_attr += "_f2"
                    _image = f"{pokeNum}{page_attr}.png"
                    response = requests.get(f"https://assets.pokemon.com/assets/cms2/img/pokedex/full/{_image}")
                    img = Image.open(BytesIO(response.content))
            img.save(f"./db/pokecordData/Images/{_image}")
        shape_img = img.convert('RGBA')
        if silhouette:
            txtfile_name = "./db/pokecordData/Images/bw_image.png"
            pixdata = shape_img.load()
            width, height = shape_img.size
            for x in range(0, width - 1):
                for y in range(0, height - 1):
                    if pixdata[x, y][3] != 0:
                        pixdata[x, y] = helpers.black
        shape_img.save(txtfile_name)

        try:
            self.imgr_result = discord.File(
                "./db/pokecordData/Images/bw_image.png",
                filename="poke_image.png")
        except Exception as Err:
            print(Err)
            raise Err
        return self.imgr_result

    async def convert_gif_bw(self, poke):
        txtfile_name = "./db/pokecordData/Images/PokeGIF.gif"
        response = requests.get("https://play.pokemonshowdown.com/sprites/xyani/" + poke['name'] + ".gif")
        frames = Image.open(BytesIO(response.content))
        p = frames.getpalette()
        last_frame = frames.convert('RGBA')
        all_frames = []
        width, height = last_frame.size
        compilation = Image.new('RGBA', size=(width * 5, height * 10))

        for i in range(frames.n_frames):
            frames.seek(i)
            if len(all_frames) <= 50:
                compilation.paste(frames.convert('RGBA'),
                                  box=(width * divmod(len(all_frames), 6)[1], height * divmod(len(all_frames), 9)[0]))

            if i != 0:
                curr_frame = frames.convert('RGBA')
                disp_frame = Image.alpha_composite(prev_frame, curr_frame)
            else:
                disp_frame = frames.convert('RGBA')
            pixdata = disp_frame.load()
            for x in range(width - 1):
                for y in range(height - 1):
                    if pixdata[x, y][3] == 255:
                        pixdata[x, y] = helpers.black
                    else:
                        pixdata[x, y] = helpers.white
            all_frames.append(disp_frame)

            prev_frame = frames.convert('RGBA')
        compilation.save("./db/pokecordData/Images/GIFcollage.png")
        all_frames[0].save(txtfile_name, save_all=True, optimize=True, append_images=all_frames[1:], loop=1000)
        # Upload to Imgr
        try:
            self.imgr_result = helpers.imgr_client.upload_from_path(txtfile_name, config=None, anon=True)['link']
        except Exception as Err:
            print(Err)
            raise Err
        return self.imgr_result

    async def wait_msg_delete(self, msg, after):
        await asyncio.sleep(after)
        await self.bot.delete_message(msg)

    @c.command(name='clean')
    @helpers.is_owner()
    async def cmd_clean(self, ctx, numMessages: int = 0):
        if numMessages == 0:
            for msg in self.bot.cached_messages:
                await msg.delete()
        else:
            deleted = await ctx.channel.purge(limit=numMessages + 1)

    @c.command(name='debug', help='Admin testing bot')  # , hidden=True)
    @helpers.is_owner()
    async def cmd_debug(self, ctx, *, message):
        embed = discord.Embed(type="rich", title="__Debug__", color=0x7F0000)
        embed.set_footer(text=message[:2048])
        try:
            embed.description = str(eval(message))
        except Exception as Err:
            print(f"Hit debug except: {Err}")
            embed.add_field(name="Error", value=Err)
        await ctx.send(embed=embed)
        await ctx.message.delete()
        return


def setup(bot):
    bot.add_cog(PokeCord(bot))
