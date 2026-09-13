from main import *

try:
    with open("./db/pokemon.json") as pkm:
        pokemon = json.load(pkm)
        print("Pokemon List Loaded")
except Exception:
    pokemon = {}
    print("Pokemon List Not Loaded.")

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Pokesearch Config File Loaded")
except Exception:
    config = {}
    print("Pokesearch Config File Not Created, Using Temporary Storage.")

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

with open("./db/countries.json") as ctr:
    countries = json.load(ctr)

pokesearch_channels = config.get("pokesearch_channels")
sniff_group_id = config.get("sniffgroupid")
contributorrole = config.get("ContributorRole")
pokesearch_embed = config.get("pokesearch_embed")
emoji_servers = config.get("emoji_servers")
embed_footer = config.get("embed_footer")
prefix = config.get("prefix")

sqloop = asyncio.get_event_loop()
DBPassword = keys.get("DBPassword")
DBUser = config.get("DBUser")
DBHost = config.get("DBHost")
DBServer = config.get("DBServer")

sql = "SELECT * FROM `pokesearch_db` WHERE "


def time_to_live(start, end, x):
    """Return true if x is in the range [start, end]"""
    start_time = datetime.fromtimestamp(start)
    x_time = datetime.fromtimestamp(x)
    end_split = str(end).split(":")
    minutes_raw = int(end_split[0])
    seconds_raw = int(end_split[1])
    ttl_total_seconds = int((minutes_raw * 60) + seconds_raw)
    end_time = start_time + timedelta(seconds=ttl_total_seconds)
    final_end = datetime.strptime(str(end_time), "%Y-%m-%d %H:%M:%S")
    x_split = str(x_time).split(".")
    time_x = x_split[0]
    final_x = datetime.strptime(str(time_x), "%Y-%m-%d %H:%M:%S")
    ttl = final_end - final_x
    return ttl


async def pokefind(message):
    #db = await helpers.connect_database()
    poke_Name = None
    poke_IV = None
    poke_CP = None
    poke_LVL = None
    radius = None
    km_mi = None
    gps = None
    message_content = str(str(message.content).replace(", ", ",")).split()
    sql = "SELECT * FROM discord_data.pokesearch_db WHERE timestamp > (extract(epoch from now()) - 1800)"
    sqlval_list = []
    for string in message_content:
        for name in pokemon:
            if str(str(str(str(str(name.lower()).replace(" ", "")).replace("(", "")).replace(")", "")).replace(".",
                                                                                                               "")).lower() in str(
                str(str(str(str(message.content).replace(" ", "")).replace("(", "")).replace(")", "")).replace(".",
                                                                                                               "")).lower():
                poke_Name = name.capitalize()
            if not name == string:
                if gps is None:
                    gpspattern = "[-+]?[0-9]+\.[0-9]+,[-+]?[0-9]+\.[0-9]+"
                    gpscompiled = re.compile(gpspattern, re.I)
                    gpsraw = gpscompiled.search(string)
                    if gpsraw:
                        gps = gpsraw.group(0)
                if "mi" in str(string):
                    radius = string.split("mi")[0]
                    km_mi = "mi"
                if "km" in str(string):
                    radius = string.split("km")[0]
                    km_mi = "km"
                if "iv" in string.lower():
                    if 2 < len(string) < 6:
                        ivpattern = "iv[0-9]"
                        ivcompiled = re.compile(ivpattern, re.I)
                        ivraw = ivcompiled.search(string)
                        if ivraw is None:
                            string_split = string.split("iv")
                            poke_IV = int(str(string_split[0]))
                        else:
                            string_split = string.split("iv")
                            poke_IV = int(str(string_split[1]))
                    else:
                        iv_index = message_content.index(string)
                        poke_IV = int(message_content[(iv_index + 1)])
                if "cp" in string.lower():
                    if 2 < len(string) < 7:
                        cppattern = "cp[0-9]"
                        cpcompiled = re.compile(cppattern, re.I)
                        cpraw = cpcompiled.search(string)
                        if cpraw is None:
                            string_split = string.split("cp")
                            poke_CP = int(str(string_split[0]))
                        else:
                            string_split = string.split("cp")
                            poke_CP = int(str(string_split[1]))
                    else:
                        cp_index = message_content.index(string)
                        poke_CP = int(message_content[(cp_index + 1)])
                if "lvl" in string.lower() or "level" in string.lower():
                    if 3 < len(string) <= 9:
                        if "lvl" in string.lower():
                            lvlpattern = "lvl[0-9]"
                            lvlcompiled = re.compile(lvlpattern, re.I)
                            lvlraw = lvlcompiled.search(string)
                            if lvlraw is None:
                                string_split = string.split("lvl")
                                poke_LVL = int(str(string_split[0]))
                            else:
                                string_split = string.split("lvl")
                                poke_LVL = int(str(string_split[1]))
                        elif "level" in string.lower():
                            lvlpattern = "level[0-9]"
                            lvlcompiled = re.compile(lvlpattern, re.I)
                            lvlraw = lvlcompiled.search(string)
                            if lvlraw is None:
                                string_split = string.split("level")
                                poke_LVL = int(str(string_split[0]))
                            else:
                                string_split = string.split("level")
                                poke_LVL = int(str(string_split[1]))
                    else:
                        lvl_index = message_content.index(string)
                        poke_LVL = int(message_content[(lvl_index + 1)])
    if poke_Name is not None:
        NAME = ' AND name = %s'
        sql += NAME
        sqlval_list.append(poke_Name)
    if poke_IV is not None:
        if poke_IV == 100:
            IV = ' AND iv = %s'
            sql += IV
            sqlval_list.append(poke_IV)
        else:
            IV = ' AND iv >= %s'
            sql += IV
            sqlval_list.append(poke_IV)
    if poke_LVL is not None:
        if poke_LVL == 40:
            LVL = ' AND lvl = %s'
            sql += LVL
            sqlval_list.append(poke_LVL)
        else:
            LVL = ' AND lvl = %s'
            sql += LVL
            sqlval_list.append(poke_LVL)
    if poke_CP is not None:
        CP = 'AND cp >= %s'
        sql += CP
        sqlval_list.append(poke_CP)
    if poke_Name is None:
        if poke_CP is None:
            if poke_LVL is None:
                if poke_IV is None:
                    if gps is None:
                        results = None
                        print("All are None")
                        return results, gps, km_mi, radius
    try:
        for i in range(len(sqlval_list)):
            sql = sql.replace("%s", "${}".format(i + 1), 1)
            sqlval_list = tuple(sqlval_list)
        results = await helpers.query_postgresDatabase(sql, *sqlval_list, multiple=True)
        return results, gps, km_mi, radius
    except Exception as e:
        print("Error getting pokesearch_db data.\n%s" % e)
#        logging.debug("Error in getting PokeData: ", e)


def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    start_time = datetime.fromtimestamp(start)
    x_time = datetime.fromtimestamp(x)
    end_split = str(end).split(":")
    minutes_raw = int(end_split[0])
    seconds_raw = int(end_split[1])
    ttl_total_seconds = int((minutes_raw * 60) + seconds_raw)
    end_time = start_time + timedelta(seconds=ttl_total_seconds)
    if start_time <= end_time:
        return start_time <= x_time <= end_time
    else:
        return start_time <= x_time or x_time <= end_time


class Pokesearch(c.Cog):

    def __init__(self, bot, **kwargs):
        self.bot = bot
        self._no_word_boundaries = kwargs.get("no_word_boundaries", False)
        self.shiny_pokemon = []
        self._filter_char = "*"
        self._load_words()
        #logging.basicConfig(filename='/home/trbot/RocketBot.log', level=logging.DEBUG)

    def _load_words(self):
        with open("./db/shinylist.txt", 'r') as f:
            self.shiny_pokemon = [line.strip() for line in f.readlines()]

    @c.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

    @c.command()
    async def pokesearch(self, ctx):
        """Search for Pokémon based on name, min IV, min CP, and min LVL

            The following query elements are supported:
                - {COORDS} {radius}(km/mi)
                - IV{xxx.yy}: min IV, whole number
                - CP{xx}: minimum CP, whole number
                - LVL{yy}: minimum level
                - name (nidoranm/f | mrmime)
            Example: $pokesearch <pokename> <50km> <40.611626,-73.963397> <iv100> <lvl30> <cp2000>"""
        if ctx.message.channel.id not in pokesearch_channels:
            await ctx.message.channel.send("Please use the appropriate channels for this command")
            return
        tag = '\u200b'
        color_list = [c for c in helpers.colors.values()]
        try:
            poke_info, gps, km_mi, radius = await pokefind(ctx.message)
        except Exception as e:
            poke_info, gps, km_mi, radius = None, None, None, None
            print(e)
            #logging.debug("Error in Poke_Info: ", e)
            pass
        if len(str(ctx.message.content).split('{}pokesearch'.format(prefix))) < 2:
            await ctx.send(
                """```Search for Pokémon based on name, min IV, min CP, and min LVL\nThe following query elements are supported:\n\t- {COORDS} {xx}(km/mi) \n\t- IV{xxx.yy}: min IV, whole number\n\t- CP{xx}: minimum CP, whole number\n\t- LVL{yy}: minimum level\n\t- name (spaces aren't OK)\ne.g. pokesearch <query> ```""")
            return
        else:
            query = str(ctx.message.content).split('{}pokesearch'.format(prefix))[1]
        a = 0
        i = 0
        result_list = []
        found = False
        try:
            if poke_info is None:
                await ctx.message.channel.send("No {} found!".format(str(query)))
                return
            elif len(poke_info) < 1:
                await ctx.message.channel.send("No {} found!".format(str(query)))
                return
            else:

                for item in poke_info:
                    if i == 0:
                        await ctx.message.channel.send("Searching for {} ...".format(str(query)))
                    if time_in_range(int(float(item['timestamp'])), item['ttl'], time.time()):
                        diff_distance = None
                        ttl_raw = time_to_live(int(float(item['timestamp'])), item['ttl'], time.time())
                        if ttl_raw.total_seconds() < 0:
                            ttl = "00:00:00"
                        else:
                            ttl = str(ttl_raw)
                        location = rg.search(tuple(str(item['coords']).split(',')))
                        country_code = location[0]['cc'].lower()
                        strings = str(
                            str(str(str(str(item["name"]).replace(" ", "")).replace("(", "")).replace(")", "")).replace(
                                ".", "")).lower()
                        if not item['gender']:
                            item['gender'] = ""
                        if gps:
                            if radius is None:
                                await ctx.message.channel.send("Please Specify a Radius!")
                                return
                        if radius:
                            if gps is None:
                                await ctx.message.channel.send("Please Specify Starting Coordinates!")
                                return
                            elif km_mi == "mi":
                                diff_distance = distance.great_circle(gps, item['coords']).miles
                            else:
                                diff_distance = distance.great_circle(gps, item['coords']).km
                            if int(diff_distance) <= int(radius):
                                pemoji = helpers.check_emojis(self.bot, strings)
                                if pemoji is None:
                                    pemoji = ""
                                result_list.insert(a,
                                                   str(pemoji) + " **" + str(item['name']) + "**: " + str(
                                                       item['gender']) + " (" + str(
                                                       ttl) + ") <:Iv:614498891680972811> **" + str(
                                                       item['iv']) + "** <:Cp:614498891974443030> **" + str(
                                                       item['cp']) + "** <:Lvl:614498892003934213> **" + str(
                                                       item['lvl']) + "** :flag_" + country_code + ": " + str(
                                                       item['coords']))
                                a += 1
                                found = True
                        else:
                            pemoji = helpers.check_emojis(self.bot, strings)
                            if pemoji is None:
                                pemoji = ""
                            result_list.insert(a, str(pemoji) + " **" + str(item['name']) + "**: " + str(
                                item['gender']) + " (" + str(
                                ttl) + ") <:Iv:614498891680972811> **" + str(
                                item['iv']) + "** <:Cp:614498891974443030> **" + str(
                                item['cp']) + "** <:Lvl:614498892003934213> **" + str(
                                item['lvl']) + "** :flag_" + country_code + ": " + str(item['coords']))
                            found = True
                            a += 1
                        i += 1
                    else:
                        if i == (len(poke_info) - 1):
                            if not found:
                                await ctx.message.channel.send("No {} found!".format(str(query)))
                                return
                        elif len(poke_info) == 0:
                            if not found:
                                await ctx.message.channel.send("No {} found!".format(str(query)))
                                return
                        i += 1
                if len(result_list) < 1:
                    await ctx.message.channel.send("No {} found!".format(str(query)))
                    return
                elif helpers.check_role(ctx.message.author, contributorrole):
                    await ctx.message.channel.send(
                        "DM'd results for {} to {}".format(str(query), ctx.message.author.mention))
                    if pokesearch_embed == 1:
                        embed = discord.Embed(
                            color=random.choice(color_list)
                        )
                        embed.set_footer(text=embed_footer)
                        # ['**Litwick**:♂ (0:17:16) <:iv:642162842233077780> **26** <:cp:642137250192293918> **12**
                        # <:lvl:642163116511068180> **1** 🇲🇽 27.503005,-99.506300']
                        for result in result_list:
                            item = str(result).split()
                            poke_name_split = str(item[0]).split("**")
                            poke_name = str(poke_name_split[1])
                            icon_number = pokemon[str(poke_name)]
                            with open("./db/shinylist.txt", "r") as nms:
                                pogoshinylist = nms.read()
                                if poke_name in self.shiny_pokemon:
                                    file = discord.File("./db/emojis/" + icon_number + "s.gif",
                                                        filename=icon_number + "s.gif")
                                    embed.set_thumbnail(url="attachment://" + icon_number + "s.gif")
                                else:
                                    file = discord.File("./db/emojis/" + icon_number + ".gif",
                                                        filename=icon_number + ".gif")
                                    embed.set_thumbnail(url="attachment://" + icon_number + ".gif")
                                embed.add_field(name=str(item[1]) + str(item[2]),
                                                value="<:Iv:614498891680972811> **" + str(
                                                    item['iv']) + "** <:Cp:614498891974443030> **" + str(
                                                    item['cp']) + "** <:Lvl:614498892003934213> **" + str(item[8]),
                                                inline=False)
                                embed.add_field(name="Despawns in *" + str(item[3]) + "*", value=tag, inline=False)
                                embed.add_field(name=str(item[10]), value=str(item[11]), inline=False)
                                await ctx.message.author.send(
                                    tag + " " + item[0] + " " + str(item[1]) + ": " + str(item[11]),
                                    file=file, embed=embed)
                    else:
                        if len(result_list) > 10:
                            n = 10
                            chunks = [result_list[i:i + n] for i in range(0, len(result_list), n)]
                            for chunk in chunks:
                                poke_str = str("{}").format('\n'.join(chunk))
                                await ctx.message.author.send(str("{}").format(poke_str))
                        else:
                            poke_str = str("{}").format('\n'.join(result_list))
                            await ctx.message.author.send(str("{}").format(poke_str))
                else:
                    if len(result_list) > 10:
                        n = 10
                        chunks = [result_list[i:i + n] for i in range(0, len(result_list), n)]
                        for chunk in chunks:
                            poke_str = str("{}").format('\n'.join(chunk))
                            await ctx.message.channel.send(str("{}").format(poke_str))
                    else:
                        poke_str = str("{}").format('\n'.join(result_list))
                        await ctx.message.channel.send(str("{}").format(poke_str))
        except Exception as e:
            print(e)
            await ctx.message.channel.send("No {} found!".format(str(query)))
            #logging.debug("Error in Pokesearch: ", e)


def setup(bot):
    bot.add_cog(Pokesearch(bot))
