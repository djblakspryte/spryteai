from main import *

import reverse_geocoder as rg

try:
    with open("./db/pokemon.json") as pkm:
        pokemon = json.load(pkm)
        print("Pokemon List Loaded")
except Exception:
    pokemon = {}
    print("Pokemon List Not Loaded.")

try:
    with open("./db/coords.json") as crds:
        coords = json.load(crds)
        print("Coords Tag List Loaded")
except Exception:
    coords = {}
    print("Coords Tag List Not Loaded.")

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Coords Config Loaded")
except Exception:
    config = {}
    print("Coords Config Not Created, Using Temporary Storage.")

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

with open("./db/countries.json") as ctr:
    countries = json.load(ctr)

ModRole = config.get("ModRole")
AdminRole = config.get("AdminRole")
embed_footer = config.get("embed_footer")
sniff_group_id = config.get("sniffgroupid")
post_group_id = config.get("postgroupid")
post_guild_id = config.get("postguildid")
coords_chan_id = config.get("coords_chan_ids")
DBPassword = keys.get("DBPassword")
DBUser = config.get("DBUser")
DBHost = config.get("DBHost")
DBServer = config.get("DBServer")
tag = '\u200b'
sqloop = asyncio.get_event_loop()

weather = ["sunny", "p_cloudy", "windy", "rainy", "cloudy", "foggy", "snowy"]
weather_emotes = ["☀️", "⛅", "💨", "🌧️", "☁️", "🌫️", "❄️"]


def getPostCategories(dict):
    return list(dict.keys())


async def getPokeInfo(**kwargs):
    if kwargs['name'] is not None:
        icon_number = None
        kwargs['name'] = str(kwargs['name']).translate(str.maketrans('', '', string.punctuation)).replace(" ", "")
        for name in pokemon:
            if name.lower().translate(str.maketrans('', '', string.punctuation)).replace(" ", "") in \
                    kwargs['name']:
                icon_number = pokemon[str(name)]
            break
        if icon_number is None:
            if kwargs['name'] == "MrMime":
                kwargs['name'] = "Mr Mime"
            elif kwargs['name'] == "NidoranM":
                kwargs['name'] = "Nidoran (M)"
            elif kwargs['name'] == "NidoranF":
                kwargs['name'] = "Nidoran (F)"
            icon_number = pokemon[str(kwargs['name'])]
    if kwargs['iv'] is not None and "?" not in kwargs['iv']:
        kwargs['iv'] = str(int(
            float(kwargs['iv'].replace(" ", "").replace("*", "").replace(" ", "").replace("(", "").replace(")", ""))))
    for k in kwargs:
        kwargs[k] = kwargs[k].replace(" ", "").replace("*", "").replace(" ", "").replace("(", "").replace(")", "")
        item = kwargs[k]
        if len(item) < 1:
            # print(i, item)
            kwargs[k] = None
            # string.pop(i)
            # string.insert(i, None)
        elif any(var in item for var in weather):
            for var in weather:
                if var in item:
                    kwargs[k] = var
                    break
    kwargs["icon_num"] = icon_number
    return kwargs


class Coords(c.Cog):

    def __init__(self, bot, **kwargs):
        self.bot = bot
        self._no_word_boundaries = kwargs.get("no_word_boundaries", False)
        self.shiny_pokemon = []
        self._filter_char = "*"
        self._load_words()

    def _load_words(self):
        with open("./db/shinylist.txt", 'r') as f:
            self.shiny_pokemon = [line.strip() for line in f.readlines()]

    def setColor(self, name):
        info = requests.get("https://pokeapi.co/api/v2/pokemon-color/").json()

        for i in range(info['count']):
            i += 1
            color_json = requests.get(f"https://pokeapi.co/api/v2/pokemon-color/{i}").json()
            for item in color_json["pokemon_species"]:
                if name == item['name']:
                    return color_json['name'].upper()

    @c.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.channel is None:
            return
        guilds = self.bot.guilds
        global tag
        message_content = message.content
        if message.channel.id in coords_chan_id:
            if not message.author.bot:
                if any(item in message.content.lower() for item in ["cp", "iv", "lvl"]):
                    await self.coords_input(message)
        elif (message.channel.category is not None) and (message.channel.category.id == sniff_group_id):
            guild = self.bot.get_guild(post_guild_id)
            if guild is not None:
                if guild.categories is not None:
                    categories = guild.categories
                    for category in categories:
                        if category.id in config["postgroupid"]:
                            content = message.content.split("\\")
                            pokeInfoOrig = await getPokeInfo(weather=content[0], boosted=content[1],
                                                             name=content[2],
                                                             form=content[3], size=content[4], ttl=content[5],
                                                             move1=content[6].split("/")[0],
                                                             move2=content[6].split("/")[1], coords=content[7],
                                                             iv=content[9], ivs=content[10], cp=content[12],
                                                             lvl=content[14], gender=content[15])
                            try:
                                await self.log_pokefeed(pokeInfoOrig)
                            except Exception as e:
                                print("Error in Logging Pokefeed: ", e)
                            channels = category.channels
                            for channel in channels:
                                if channel.name == message.channel.name:
                                    if any(item in message.content.lower() for item in [":iv:", ":lvl:"]):
                                        post_channel = channel
                                        #if coords[str(guild.id)].get(str(channel.id), None) is not None:
                                        #    tag = coords[str(guild.id)].get(str(channel.id))
                                        #else:
                                        tag = '\u200b'
                                        pokeInfo = pokeInfoOrig.copy()
                                        # weather|vb? \ boosted|flp? \ NAME \ form|p \ size|p? \ ttl \ moves|es? \ coords6 \ :iv: \ IV \ ivs|p? \ :cp: \ CP \ :lvl: \ LVL \ gender|?
                                        try:
                                            if int(float(pokeInfo['iv'].replace("*", ""))) == 100:
                                                pokeInfo['iv'] = ":100:"
                                        except:
                                            pokeInfo['iv'] = pokeInfo['iv']
                                        try:
                                            if int(float(pokeInfo['lvl'].replace("*", ""))) == 35:
                                                pokeInfo['lvl'] = "<:max:730136754329223208>"
                                        except:
                                            pokeInfo['lvl'] = pokeInfo['lvl']
                                        location = rg.search(tuple(pokeInfo['coords'].split(',')))
                                        country_code = location[0]['cc'].lower()
                                        city_str = location[0]["name"]
                                        state_str = " " + location[0]['admin1'] + ", "
                                        if len(state_str) < 1:
                                            state_str = " "
                                        elif city_str == state_str:
                                            state_str = " "
                                        for name, ccode in countries.items():
                                            if ccode == location[0]['cc']:
                                                country_str = name
                                        color = self.setColor(pokeInfo['name'])
                                        if color is None:
                                            color_list = [c for c in helpers.colors.keys()]
                                            color = random.choice(color_list)
                                        embed = discord.Embed(
                                            color=helpers.colors[color]
                                        )
                                        embed.set_footer(text=embed_footer)
                                        self._load_words()
                                        if pokeInfo['name'].lower().strip() in self.shiny_pokemon:
                                            file = discord.File(
                                                "./db/emojis/{}s.gif".format(pokeInfo['icon_num']),
                                                filename="{}s.gif".format(pokeInfo['icon_num']))
                                            embed.set_thumbnail(
                                                url="attachment://{}s.gif".format(pokeInfo['icon_num']))
                                            pokeInfo['name'] = "<a:shiny:730173905800790127>{}".format(pokeInfo['name'])
                                        else:
                                            file = discord.File(
                                                "./db/emojis/{}.gif".format(pokeInfo['icon_num']),
                                                filename="{}.gif".format(pokeInfo['icon_num']))
                                            embed.set_thumbnail(
                                                url="attachment://{}.gif".format(pokeInfo['icon_num']))
                                        if pokeInfo['boosted'] is not None:
                                            weather_index = weather.index(pokeInfo['weather'])
                                            weather_emote = weather_emotes[weather_index]
                                            embed.add_field(
                                                name="**{}** (*Weather Boost: {}*)".format(pokeInfo['name'], weather_emote),
                                                value="<:Iv:614498891680972811>: {} <:Cp:614498891974443030>: {} <:Lvl:614498892003934213>: {}".format(
                                                    pokeInfo['iv'], pokeInfo['cp'], pokeInfo['lvl']),
                                                inline=False)
                                        else:
                                            embed.add_field(name="**{}**".format(pokeInfo['name']),
                                                            value="<:Iv:614498891680972811>: {} <:Cp:614498891974443030>: {} <:Lvl:614498892003934213>: {}".format(
                                                                pokeInfo['iv'], pokeInfo['cp'], pokeInfo['lvl']),
                                                            inline=False)
                                        embed.add_field(name="Despawns in *{}*".format(pokeInfo['ttl'].replace(" ", "")),
                                                        value=tag, inline=False)
                                        embed.add_field(
                                            name=":flag_{}: {},{}{}".format(country_code, city_str,
                                                                            state_str, country_str),
                                            value=pokeInfo['coords'], inline=False)
                                        await post_channel.send(
                                            "{} {}: {}".format(tag, pokeInfo['name'], pokeInfo['coords']),
                                            file=file, embed=embed)
                                        #                                    logging.debug("Error in Logging Pokefeed: ", e)
                                        break
                                    elif any(item in message.content.lower() for item in [":mystic:", ":valor:", ":instinct:"]):
                                        post_channel = channel
                                        if coords[str(guild.id)].get(str(channel.id)) is not None:
                                            tag = coords[str(guild.id)].get(str(channel.id))
                                        else:
                                            tag = '\u200b'
                                        # Team 0/ Name 1/ Pokemon 2/ Gender 3/ Moves 4/ CP 5/ TTL 6/ COORDS 7/ EX 8/ FORM 9
                                        raids_message = message_content.split("\\")
                                        if "mystic" in raids_message[0].lower():
                                            team = "<:mystic:695748768364101652>"
                                            team_color = helpers.colors["BLUE"]
                                        elif "valor" in raids_message[0].lower():
                                            team = "<:valor:695748756049625098>"
                                            team_color = helpers.colors["RED"]
                                        elif "instinct" in raids_message[0].lower():
                                            team = "<:instinct:695748733442457631>"
                                            team_color = helpers.colors["GOLD"]
                                        else:
                                            team = ""
                                            team_color = helpers.colors["WHITE"]
                                        raid_location_name = raids_message[1]
                                        raid_pokemon_name = raids_message[2].replace("*", "").replace(
                                            " ", "")
                                        if raids_message[3] is not None:
                                            if "female" in raids_message[3].lower():
                                                raid_pokemon_gender = "<:femalegender:695698183665352736>"
                                            elif "male" in raids_message[3].lower():
                                                raid_pokemon_gender = "<:malegender:695698122860527656>"
                                            else:
                                                raid_pokemon_gender = "<:genderneutral:695696445151510548>"
                                        else:
                                            raid_pokemon_gender = "<:genderneutral:695696445151510548>"
                                        raid_pokemon_name += raid_pokemon_gender
                                        moves_str_list = raids_message[4].split()
                                        moves = " ".join(moves_str_list[1:])
                                        raid_pokemon_CP = raids_message[5].replace("*", "").split()[1]
                                        despawn_time = raids_message[6].replace(" ", "")
                                        coords_value = raids_message[7].replace(" ", "")
                                        if raids_message[8] is not None:
                                            if "ex" in raids_message[8]:
                                                raid_ex_value = " **(EX)**"
                                                raid_location_name += raid_ex_value
                                        if raids_message[9] is not None or len(raids_message[9].replace(" ", "")) > 0:
                                            raid_pokemon_form = raids_message[9]
                                            raid_pokemon_name += " {}".format(raid_pokemon_form)
                                        icon_number = None
                                        for name in pokemon:
                                            if name.lower().replace(".", "").replace(" ", "").replace(
                                                    "(",
                                                    "").replace(
                                                ")", "").replace(":",
                                                                 "") in raid_pokemon_name.lower().replace(
                                                ".", "").replace(" ", "").replace("(", "").replace(")", "").replace(
                                                ":", ""):
                                                icon_number = pokemon[str(name)]
                                                break
                                        if icon_number is None:
                                            icon_number = pokemon[str(raids_message[2].replace("*", "").replace(" ", ""))]
                                        location = rg.search(tuple(coords_value.split(',')))
                                        country_code = location[0]['cc'].lower()
                                        city_str = location[0]["name"]
                                        state_str = " " + location[0]['admin1'] + ", "
                                        if len(state_str) < 1:
                                            state_str = " "
                                        elif city_str == state_str:
                                            state_str = " "
                                        for name, ccode in countries.items():
                                            if ccode == location[0]['cc']:
                                                country_str = name
                                        color_list = [c for c in helpers.colors.values()]
                                        embed = discord.Embed(
                                            color=team_color
                                        )
                                        embed.set_footer(text=embed_footer)
                                        self._load_words()
                                        if raid_pokemon_name.lower().strip() in self.shiny_pokemon:
                                            file = discord.File(
                                                "./db/emojis/{}s.gif".format(icon_number),
                                                filename=icon_number + "s.gif")
                                            embed.set_thumbnail(
                                                url="attachment://{}s.gif".format(icon_number))
                                            poke_name = "\u2728{}".format(raid_pokemon_name)
                                        else:
                                            file = discord.File(
                                                "./db/emojis/{}.gif".format(icon_number),
                                                filename="{}.gif".format(icon_number))
                                            embed.set_thumbnail(
                                                url="attachment://{}.gif".format(icon_number))
                                        embed.add_field(name="{}".format(raid_pokemon_name),
                                                        value="{} {}".format(team, raid_location_name),
                                                        inline=False)
                                        embed.add_field(name="<:cp:665257660605792266>: {}\n{}".format(
                                            raid_pokemon_CP, moves),
                                            value="Despawns in *{}*".format(despawn_time),
                                            inline=False)
                                        embed.add_field(
                                            name=":flag_{}: {},{}{}".format(country_code, city_str,
                                                                            state_str, country_str),
                                            value=coords_value, inline=False)
                                        await post_channel.send(
                                            "{} {}: {}".format(tag, raid_pokemon_name, coords_value),
                                            file=file, embed=embed)
                                        break

    # 13.735600,-89.060811 Ponyta <:iv:642495044338581518> 100 <:lvl:642495077754863616> 20 <:cp:642494936100503583> 1224
    async def coords_input(self, message):
        global tag
        timestamp = time.time()
        message_content = str(message.content).replace(", ", ",")
        coords_message = message_content.split()
        channels = []
        despawn_time = "10:00"
        poke_name = "?"
        poke_IV = "?"
        poke_CP = "?"
        poke_LVL = "?"
        coords_value = "?"
        stats = ""
        individual_attack = None
        individual_defense = None
        individual_stamina = None
        for content in coords_message:
            if "/" in content:
                statspattern = "\d+\/\d+\/\d+"
                statscompiled = re.compile(statspattern, re.I)
                statsraw = statscompiled.search(content)
                if statsraw:
                    stats_raw = content
                    stat_split = stats_raw.split("/")
                    # print(stat_split[0], stat_split[1], stat_split[2])
                    individual_attack = stat_split[0]
                    individual_defense = stat_split[1]
                    individual_stamina = stat_split[2]
                    stats = "(" + stats_raw + ")"
                    print(stats)
            if poke_name == "?":
                for name in pokemon:
                    if name.lower().replace(".", "").replace(" ", "").replace("(", "").replace(")", "").replace(":",
                                                                                                                "") in content.lower().replace(
                        ".", "").replace(" ", "").replace("(", "").replace(")", "").replace(":", ""):
                        icon_number = pokemon[str(name)]
                        poke_name = name.capitalize()
                        break
                    elif str(":" + pokemon[str(name)] + ":") in content.lower().replace(".", "").replace(" ",
                                                                                                         "").replace(
                        "(",
                        "").replace(
                        ")", ""):
                        icon_number = pokemon[str(name)]
                        poke_name = name.capitalize()
                        break
                    else:
                        pass
                # print(poke_name, icon_number)
            if coords_value == "?":
                gpspattern = "[-+]?[0-9]+\.[0-9]+,[-+]?[0-9]+\.[0-9]+"
                gpscompiled = re.compile(gpspattern, re.I)
                gpsraw = gpscompiled.search(content)
                if gpsraw:
                    coords_value = gpsraw.group(0)
            if "iv" in content.lower():
                if content not in pokemon:
                    if 2 < len(content) < 6:
                        ivpattern = "iv[0-9]"
                        ivcompiled = re.compile(ivpattern, re.I)
                        ivraw = ivcompiled.search(content)
                        if ivraw is None:
                            content_split = content.split("iv")
                            poke_IV = str(content_split[0])
                        else:
                            content_split = content.split("iv")
                            poke_IV = str(content_split[1])
                    else:
                        iv_index = coords_message.index(content)
                        poke_IV = coords_message[(iv_index + 1)]
                print(poke_IV)
            if "cp" in content.lower():
                if content not in pokemon:
                    if 2 < len(content) < 7:
                        cppattern = "cp[0-9]"
                        cpcompiled = re.compile(cppattern, re.I)
                        cpraw = cpcompiled.search(content)
                        if cpraw is None:
                            content_split = content.split("cp")
                            poke_CP = str(content_split[0])
                        else:
                            content_split = content.split("cp")
                            poke_CP = str(content_split[1])
                    else:
                        cp_index = coords_message.index(content)
                        poke_CP = coords_message[(cp_index + 1)]
                        if "max" in poke_CP:
                            poke_CP = 35
                print(poke_CP)
            if "lvl" in content.lower():
                if content not in pokemon:
                    if 3 < len(content) < 6:
                        lvlpattern = "lvl[0-9]"
                        lvlcompiled = re.compile(lvlpattern, re.I)
                        lvlraw = lvlcompiled.search(content)
                        if lvlraw is None:
                            content_split = content.split("lvl")
                            poke_LVL = str(content_split[0])
                        else:
                            content_split = content.split("lvl")
                            poke_LVL = str(content_split[1])
                    else:
                        lvl_index = coords_message.index(content)
                        poke_LVL = coords_message[(lvl_index + 1)]
                print(poke_LVL)
            if "<#" in content:
                content_split1 = content.split("<#")
                content_split2 = content_split1[1].split(">")
                channels.append(int(content_split2[0]))
            if ":" in content:
                time_detect_regex = re.compile("[0-5][0-9]+:+[0-5][0-9]", re.I)
                time_detect_search = time_detect_regex.search(content)
                if time_detect_search is not None:
                    time_detect = time_detect_search.group(0)
                else:
                    time_detect = False
                if time_detect:
                    despawn_time = content
        location = rg.search(tuple(coords_value.split(',')))
        city = location[0]["name"]
        for name, ccode in countries.items():
            if ccode == location[0]['cc']:
                country = name
        state = " " + location[0]['admin1'] + ", "
        if len(state) < 1:
            state = " "
        elif city == state:
            state = " "
        country_code = location[0]['cc']
        color_list = [c for c in helpers.colors.values()]
        display_poke_IV = poke_IV
        if "?" not in poke_IV:
            if int(poke_IV) == 100:
                display_poke_IV = ":100:"
        display_poke_LVL = poke_LVL
        if "?" not in poke_LVL:
            if int(poke_LVL) == 35:
                display_poke_LVL = "<:max:730136754329223208>"
        for channel in channels:
            if coords[str(message.guild.id)].get(str(channel)) is not None:
                tag = coords[str(message.guild.id)].get(str(channel))
            else:
                tag = '\u200b'
            embed = discord.Embed(
                color=random.choice(color_list)
            )
            embed.set_footer(text=embed_footer)
            with open("./db/shinylist.txt", "r") as nms:
                if poke_name.lower().strip() in self.shiny_pokemon:
                    file = discord.File("./db/emojis/{}s.gif".format(icon_number),
                                        filename="{}s.gif".format(icon_number))
                    embed.set_thumbnail(url="attachment://{}s.gif".format(icon_number))
                else:
                    file = discord.File("./db/emojis/{}.gif".format(icon_number), filename="{}.gif".format(icon_number))
                    embed.set_thumbnail(url="attachment://{}.gif".format(icon_number))
                if len(stats) > 0:
                    embed.add_field(name="**{}**".format(poke_name),
                                    value="<:iv:665257703270121483>: **{}** {} <:cp:665257660605792266>: **{}** <:lvl:665257730629697548>: **{}**".format(
                                        display_poke_IV, stats, poke_CP, display_poke_LVL),
                                    inline=False)
                else:
                    embed.add_field(name="**{}**".format(poke_name),
                                    value="<:iv:665257703270121483>: **{}** <:cp:665257660605792266>: **{}** <:lvl:665257730629697548>: **{}**".format(
                                        display_poke_IV, poke_CP, display_poke_LVL),
                                    inline=False)
                embed.add_field(name="Despawns in *{}*".format(despawn_time), value=tag, inline=False)
                embed.add_field(name=":flag_{}: {},{}{}".format(country_code, city, state, country),
                                value=coords_value, inline=False)
                post_channel = self.bot.get_channel(int(channel))
                await post_channel.send("{} {}: {}".format(tag, poke_name, coords_value),
                                        file=file, embed=embed)
        if "?" in poke_IV:
            poke_IV = None
        if "?" in poke_CP:
            poke_CP = None
        if "?" in poke_LVL:
            poke_LVL = None
        sql = "INSERT INTO discord_data.pokesearch_db (name, ttl, coords, iv, cp, lvl, country, " \
              "city, timestamp, individual_attack, individual_defense, individual_stamina)" + \
              " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"
        args = (
            poke_name, despawn_time, coords_value, poke_IV, poke_CP, poke_LVL, country, city, timestamp,
            individual_attack,
            individual_defense, individual_stamina)
        await helpers.transaction_postgresDatabase(sql, *args)

    # NAME / ttl / flag|? / coords6 / :iv: / IV / :cp: / CP / :lvl: / LV / country|? / city|? / gender|?
    @staticmethod
    async def log_pokefeed(pokeInfo):
        timestamp = time.time()
        poke_name = pokeInfo['name']
        poke_IV = pokeInfo['iv'].translate(str.maketrans('', '', string.punctuation)).replace(" ", "")
        poke_CP = pokeInfo['cp'].translate(str.maketrans('', '', string.punctuation)).replace(" ", "")
        poke_LVL = pokeInfo['lvl'].translate(str.maketrans('', '', string.punctuation)).replace(" ", "")
        despawn_time = pokeInfo['ttl']
        coords_value = pokeInfo['coords']
        location = rg.search(tuple(coords_value.split(',')))
        city_str = location[0]["name"]
        for name, ccode in countries.items():  # for name, age in dictionary.iteritems():  (for Python 2.x)
            if ccode == location[0]['cc']:
                country_str = name
        if "?" in poke_IV:
            poke_IV = None
        else:
            poke_IV = int(poke_IV)
        if "?" in poke_CP:
            poke_CP = None
        else:
            poke_CP = int(poke_CP)
        if "?" in poke_LVL:
            poke_LVL = None
        else:
            poke_LVL = int(poke_LVL)
        if pokeInfo['ivs'] is not None:
            ivs = pokeInfo['ivs'].split("/")
            individual_attack = int(ivs[0])
            individual_defense = int(ivs[1])
            individual_stamina = int(ivs[2])
        else:
            individual_attack = None
            individual_defense = None
            individual_stamina = None
        # print(city_str, country_str)

        sql = "INSERT INTO discord_data.pokesearch_db (name, ttl, coords, iv, cp, lvl, country, " \
              "city, timestamp, gender, individual_attack, individual_defense, individual_stamina)" + \
              " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)"
        args = (
            poke_name, despawn_time, coords_value, poke_IV, poke_CP, poke_LVL, country_str,
            city_str,
            timestamp, pokeInfo['gender'], individual_attack, individual_defense, individual_stamina)
        await helpers.transaction_postgresDatabase(sql, *args)


def setup(bot):
    bot.add_cog(Coords(bot))
