# re __future__ statement:
# https://docs.python.org/2/library/__future__.html
from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Config File Loaded")
except Exception:
    config = {}
    print("Nests: Config File Not Created, Using Temporary Storage.")

try:
    with open("./config/tokens.json") as tkn:
        keys = json.load(tkn)
except Exception:
    keys = {}
    print("Nests: Keys File Not Created, Using Temporary Storage")

try:
    with open("./db/pokemon.json") as pkm:
        pokemon = json.load(pkm)
        print("Nests: Pokemon List Loaded")
except Exception:
    pokemon = {}
    print("Nests: Pokemon List Not Loaded.")

with open("./db/countries.json") as ctr:
    countries = json.load(ctr)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = keys.get('SPREADSHEET_ID')
RANGE_NAME = 'Current Nests!A3:B50'
NEST2 = 'Current Nests!A3:D5'
NEST_ALL_CELLS = 'Current Nests'
GPX_ALL_CELLS = 'Nest Database!A2:D350'
contributorrole = config.get("ContributorRole")
ModRole = config.get("ModRole")
nest_error_channel = config.get('nest_error_channel')
nest_chans = config.get('nest_channels')
emoji_servers = config.get("emoji_servers")
embed_footer = config.get("embed_footer")

# Global stuffs
nesting_pkmn_list = open("./db/nesting_pokemon.txt").read().splitlines()
prefix = config.get("prefix")
gpx_dict = {}
pkmn_dict = {}


def time_in_range(start, x):
    """Return true if x is in the range [start, end]"""
    start_time = datetime.fromtimestamp(start)
    x_time = datetime.fromtimestamp(x)
    end_time = start_time + timedelta(seconds=180)
    if start_time <= end_time:
        return start_time <= x_time <= end_time
    else:
        return start_time <= x_time or x_time <= end_time


def build_dicts():
    """ Helper for nest commands & functions.
    Uses the Google Sheets API to build a dictionary from current nests."""
    nestvalues = nest_main()
    for row in nestvalues:
        if row is not None:
            key = ''.join(row[0:1]).lower()  # Storing as lower case so we can ignoring cases when searching
            value = list((row[1:]))
            if key and value:
                pkmn_dict[key] = value
    gpxvalues = gpx_main()
    for item in gpxvalues:
        if item is not None:
            gkey = str(item[0])
            gvalue = list((item[2:]))
            if gkey is not None and gvalue:
                gpx_dict[gkey] = gvalue

    return pkmn_dict, gpx_dict


def nest_main():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('./config/token.pickle'):
        with open('./config/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                './config/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('./config/token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    nest_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                     range=NEST_ALL_CELLS).execute()
    nest_values = nest_result.get('values', [])

    if not nest_values:
        print('No Nest Data Found.')
    return nest_values


def gpx_main():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    if os.path.exists('./config/token.pickle'):
        with open('./config/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                './config/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('./config/token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()

    gpx_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=GPX_ALL_CELLS).execute()
    gpx_values = gpx_result.get('values', [])

    if not gpx_result:
        print('No Nest Data Found')

    return gpx_values


# ---- Beginning of cog class/functions --- #


class Nests(c.Cog):
    def __init__(self, bot):
        self.bot = bot

    @c.group(name='nest', aliases=['nests'])
    async def nest(self, ctx):
        """Allows user to search for nests with a certain radius.
        Example: $nest 50km 40.611626,-73.963397
        *Contains subcommands*"""
        print(isinstance(ctx.command, c.Group), ctx.invoked_subcommand)
        if ctx.invoked_subcommand is None:
            args = ctx.message.content.replace(", ", ",").replace(" ,", ",").split()
            if ctx.channel.id not in nest_chans:
                await ctx.message.channel.send("Please use the appropriate channels for this command")
                return
            gps = None
            i = 0
            km_mi = None
            radius = None
            if args is None or len(args) < 1:
                await ctx.send("Please Specify a radius and coords!")
                return
            for arg in args:
                if arg in pokemon:
                    await ctx.send("To Search by Pokemon Use: $pokemonnamehere")
                    return
                gpspattern = "\s.+[0-9]+\.[0-9]+,.+[0-9]+\.[0-9]+\s"
                gpscompiled = re.compile(gpspattern, re.I)
                gpsraw = gpscompiled.search(ctx.message.content)
                if not gpsraw:
                    gpspattern = "\s[0-9]+\.[0-9]+,.+[0-9]+\.[0-9]+\s"
                    gpscompiled = re.compile(gpspattern, re.I)
                    gpsraw = gpscompiled.search(ctx.message.content)
                if gpsraw:
                    gps_raw = gpsraw.group(0)
                    gps = gps_raw.replace(" ", "")
                if "mi" in str(arg):
                    radius = arg.split("mi")[0]
                    km_mi = "mi"
                if "km" in str(arg):
                    radius = arg.split("km")[0]
                    km_mi = "km"
            for pkmn in nesting_pkmn_list:
                try:
                    nest_results = pkmn_dict[pkmn.lower()]
                except:
                    continue
                for result in nest_results:
                    (lat, long) = result.split(',')
                    if gps:
                        if km_mi is None:
                            await ctx.message.channel.send("Please Specify a Radius!")
                            return
                        if radius is None:
                            await ctx.message.channel.send("Please Specify a Radius!")
                            return
                    if radius:
                        if gps is None:
                            await ctx.message.channel.send("Please Specify Starting Coordinates!")
                            return
                        elif km_mi == "mi":
                            diff_distance = distance.great_circle(gps, result).miles
                        else:
                            diff_distance = distance.great_circle(gps, result).km
                    if int(diff_distance) <= int(radius):
                        pemoji = helpers.check_emojis(self.bot, pkmn)
                        if pemoji is None:
                            pemoji = ""
                        i += 1
                        location = rg.search(tuple(result.split(',')))
                        city = location[0]["name"]
                        for name, ccode in countries.items():
                            if ccode == location[0]['cc']:
                                country = name
                        state = ", " + location[0]['admin1'] + ", "
                        if len(state) < 1:
                            state = ", "
                        elif city == location[0]['admin1']:
                            state = ", "
                        android_gpx = None
                        ios_gpx = None
                        for gpx in gpx_dict:
                            if len(gpx) > 0:
                                diff_distance = distance.great_circle(gpx, result).km
                                if int(diff_distance) <= int(10):
                                    if len(gpx_dict[gpx]) > 0:
                                        try:
                                            android_gpx = gpx_dict[gpx][0]
                                        except:
                                            android_gpx = None
                                            pass
                                        try:
                                            ios_gpx = gpx_dict[gpx][1]
                                        except:
                                            ios_gpx = None
                                            pass
                                    else:
                                        android_gpx = None
                                        ios_gpx = None
                        country_code = location[0]['cc'].lower()
                        msg = "{}, {}".format(lat, long)
                        embed = discord.Embed(color=0x95A5A6)
                        embed.add_field(name=str(pemoji) + " " + result,
                                        value=city + state + country + f" :flag_{country_code}:",
                                        inline=False)
                        embed.set_footer(text=embed_footer)
                        if android_gpx and ios_gpx is None:
                            embed.add_field(name='\u200b',
                                            value="[Android GPX](" + android_gpx + ")",
                                            inline=True)
                        elif ios_gpx and android_gpx is None:
                            embed.add_field(name='\u200b',
                                            value="[iOS GPX](" + ios_gpx + ")",
                                            inline=True)
                        elif ios_gpx and android_gpx is not None:
                            embed.add_field(name='\u200b',
                                            value="[Android GPX](" + android_gpx + ") | [iOS GPX](" + ios_gpx + ")",
                                            inline=True)
                        if helpers.check_role(ctx.message.author, contributorrole) and i == 1:
                            int_msg = "DM'd results for nest(s) within {}{} of {}:".format(radius, km_mi, gps)
                            await ctx.channel.send(int_msg)
                        if helpers.check_role(ctx.message.author, contributorrole):
                            await ctx.author.send("Found the following nest(s) for " + pkmn.capitalize() + ":\n")
                            await ctx.author.send(msg, embed=embed)
                        else:
                            reactions = ["✅", "❌"]
                            channel_msg = await ctx.channel.send(msg, embed=embed)
                            for reac in reactions:
                                await channel_msg.add_reaction(reac)
            if i == 0:
                await ctx.channel.send(f"Sorry, we haven't found any nests with a {radius}{km_mi} radius of {lat, long}!")

    @nest.command()
    async def list(self, ctx):
        """Shows Nesting Pokemon List.
        Example: $nest list"""
        nestList = helpers.load_words("db", "nesting_pokemon.txt")
        await ctx.send("Nesting Pokemon:\n")
        await ctx.send(str("```{}```").format('\n'.join(nestList)))

    @nest.command()
    @helpers.has_higher_role(True, ModRole)
    async def build(self, ctx):
        """Builds Bot's Nest Database
        Example: $nest build"""
        gpx_dict = {}
        pkmn_dict = {}
        # Would be good to make try/except, but what kind of exception to catch?? KeyError & ...?
        if build_dicts():
            await ctx.channel.send("Nest database built successfully.")
        else:
            await ctx.channel.send("Build failed.")

    @nest.command()
    @helpers.has_higher_role(True, ModRole)
    async def update(self, ctx):
        """Updates Nesting Pokemon List to Current PoGo API List.
        Example: $nest update"""
        try:
            helpers.nesterUpdater()
            await ctx.send("Nesting List updated")
        except Exception as e:
            await ctx.send(f"Error Occurred: {e}")

    @c.Cog.listener()
    async def on_ready(self):
        build_dicts()

    @c.Cog.listener()
    async def on_message(self, ctx):
        """
        Hillari Denny, Kris Carroll, and Cody Morris

        Listener will scan every message in specified channel for the prefix
        Once it finds the prefix, we search the dictionary and report results back to channel
        NOTE: You *must* have run $nest build in order for this function to work"""
        if ctx.guild is None or ctx.channel is None:
            return
        if ctx.content.startswith(prefix):
            search = ctx.content.split()
            query = str(search[0][1:]).lower().replace(".", "").replace(" ", "").replace("(", "").replace(")",
                                                                                                          "").replace(
                ":", "")
            pkmn = None
            nest_results = None
            if ctx.channel.id in nest_chans:
                for cmd in self.bot.commands:
                    if query == cmd.name.lower():
                        return
                command = discord.utils.get(self.bot.commands, name=query)
                if command is None:
                    for item in pokemon:
                        poke = item.lower().replace(".", "").replace(" ", "").replace("(", "").replace(")", "").replace(
                            ":", "")
                        if poke == query:
                            print("Query in List")
                            pkmn = item
                            break
                    if pkmn is None or pkmn not in pokemon:
                        print("Not in List")
                        pkmn = helpers.pokespellcheck(query)
                        # if pkmn.lower() not in nesting_pkmn_list:
                        #    print("Sorry, " + pkmn + " does not nest.")
                        # if pkmn.lower() in nesting_pkmn_list and nest_results is None:
                        #    print("Sorry, we haven't found any nests for " + pkmn + " yet.")
                else:
                    return
                if pkmn in pokemon:
                    try:
                        if len(pkmn_dict) < 1:
                            await ctx.channel.send(f"List is Empty! Please Run `{prefix}nest build`!")
                            return
                        nest_results = pkmn_dict[pkmn.lower()]
                        if helpers.check_role(ctx.message.author, contributorrole):
                            int_msg = "DM'd results for " + pkmn.capitalize() + " nest(s):\n"
                            await ctx.channel.send(int_msg)
                            await ctx.author.send("Found the following nest(s) for " + pkmn.capitalize() + ":\n")
                        else:
                            int_msg = "Found the following nest(s) for " + pkmn.capitalize() + ":\n"
                            await ctx.channel.send(int_msg)
                        for result in nest_results:
                            pemoji = helpers.check_emojis(self.bot, pkmn)
                            if pemoji is None:
                                pemoji = ""
                            (lat, long) = result.split(',')
                            android_gpx = None
                            ios_gpx = None
                            for gpx in gpx_dict:
                                if len(gpx) > 0:
                                    diff_distance = distance.great_circle(gpx, result).km
                                    if int(diff_distance) <= int(10):
                                        if len(gpx_dict[gpx]) > 0:
                                            try:
                                                android_gpx = gpx_dict[gpx][0]
                                            except:
                                                android_gpx = None
                                                pass
                                            try:
                                                ios_gpx = gpx_dict[gpx][1]
                                            except:
                                                ios_gpx = None
                                                pass
                                        else:
                                            android_gpx = None
                                            ios_gpx = None
                            location = rg.search(tuple(result.split(',')))
                            city = location[0]["name"]
                            for name, ccode in countries.items():
                                if ccode == location[0]['cc']:
                                    country = name
                            state = ", " + location[0]['admin1'] + ", "
                            if len(state) < 1:
                                state = ", "
                            elif city == location[0]['admin1']:
                                state = ", "
                            country_code = location[0]['cc'].lower()
                            msg = "{}, {}".format(lat, long)
                            embed = discord.Embed(color=0x95A5A6)
                            embed.add_field(name=str(pemoji) + " " + result,
                                            value=city + state + country + f" :flag_{country_code}:",
                                            inline=False)
                            embed.set_footer(text=embed_footer)
                            if android_gpx and ios_gpx is None:
                                embed.add_field(name='\u200b',
                                                value="[Android GPX](" + android_gpx + ")",
                                                inline=True)
                            elif ios_gpx and android_gpx is None:
                                embed.add_field(name='\u200b',
                                                value="[iOS GPX](" + ios_gpx + ")",
                                                inline=True)
                            elif ios_gpx and android_gpx is not None:
                                embed.add_field(name='\u200b',
                                                value="[Android GPX](" + android_gpx + ") | [iOS GPX](" + ios_gpx + ")",
                                                inline=True)
                            if helpers.check_role(ctx.messge.author, contributorrole):
                                await ctx.author.send(msg, embed=embed)
                            else:
                                reactions = ["✅", "❌"]
                                channel_msg = await ctx.channel.send(msg, embed=embed)
                                for reac in reactions:
                                    await channel_msg.add_reaction(reac)
                    except KeyError:
                        nest_results = None
                        if pkmn.lower() not in nesting_pkmn_list:
                            await ctx.channel.send("Sorry, " + pkmn + " does not nest.")
                        if pkmn.lower() in nesting_pkmn_list and nest_results is None:
                            await ctx.channel.send(
                                "Sorry, we haven't found any nests for " + pkmn + " yet.")
            elif ctx.channel.id not in nest_chans:
                if ctx.content.startswith(prefix):
                    for cmd in self.bot.commands:
                        if query == cmd.name.lower():
                            return
                    pkmn = helpers.pokespellcheck(query)
                    if pkmn in pokemon:
                        await ctx.channel.send("Please use the appropriate channels for this command")
                        return

    @c.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel_id = payload.channel_id
        guild_id = payload.guild_id
        user_id = payload.user_id
        reaction_channel = self.bot.get_channel(payload.channel_id)
        message = await reaction_channel.fetch_message(payload.message_id)
        channel = self.bot.get_channel(nest_error_channel)
        user = self.bot.get_user(user_id)
        if channel_id in nest_chans:
            if user.bot is False:
                guild = discord.utils.find(lambda g: g.id == guild_id, self.bot.guilds)
                role = discord.utils.get(guild.roles, id=644317500661825575)
                if payload.emoji.name == "❌":
                    embeds = message.embeds
                    embed_fields = embeds[0].fields
                    embed_name = embed_fields[0].name
                    for poke, num in pokemon.items():
                        pemoji = ":" + num.lower() + ":"
                        if pemoji in embed_name:
                            await user.send(
                                "Hi, {}!\nThanks for your feedback!\nIf you could please provide us with specifics on what issue you are having?".format(
                                    user.name))

                            def check(m):
                                return not m.author.bot and m.author == user and isinstance(m.channel,
                                                                                            discord.abc.PrivateChannel) is True

                            try:
                                msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                                embed = discord.Embed(
                                    colour=discord.Colour(user.colour.value)
                                )
                                embed.set_footer(text="SpryteAI made by shaunceezy")
                                embed.add_field(name="{} nest invalid!".format(poke),
                                                value="{}, {} has reported the nest for {} as invalid for the reason below:\n\n{}.\n\n[Message Link](https://discordapp.com/channels/{}/{}/{})".format(
                                                    role.mention, user.mention, poke, msg.content, str(guild_id),
                                                    str(channel_id), str(message.id)),
                                                inline=True)
                                await channel.send(embed=embed)
                                await user.send(
                                    "Thanks for your feedback! I have sent a message to our Nest Experts and they will review the nest.")
                            except asyncio.TimeoutError:
                                await user.send('This Process has timed out. Please reach out to us again if needed')
                elif payload.emoji.name == "✅":
                    embeds = message.embeds
                    embed_fields = embeds[0].fields
                    embed_name = embed_fields[0].name
                    for poke, num in pokemon.items():
                        pemoji = ":" + num.lower() + ":"
                        if pemoji in embed_name:
                            await user.send(
                                "Hi, {}!\nThanks for your feedback!\nIf you would like, leave a message for the Nest Expert team!".format(
                                    user.name))

                            def check(m):
                                return not m.author.bot and m.author == user and isinstance(m.channel,
                                                                                            discord.abc.PrivateChannel) is True

                            try:
                                msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                                embed = discord.Embed(
                                    colour=discord.Colour(user.colour.value)
                                )
                                embed.set_footer(text="SpryteAI made by shaunceezy")
                                embed.add_field(name="{} nest validated!".format(poke),
                                                value="{}, {} has reported the nest for {} as valid and has provided this feedback:\n\n{}.\n\n[Message Link](https://discordapp.com/channels/{}/{}/{})".format(
                                                    role.mention, user.mention, poke, msg.content, str(guild_id),
                                                    str(channel_id), str(message.id)),
                                                inline=True)
                                await channel.send(embed=embed)
                                await user.send(
                                    "Thanks for your feedback! I have sent a message to our Nest Experts with your comments.")
                            except asyncio.TimeoutError:
                                await user.send('This Process has timed out. Thanks again for your positive feedback!')
                                embed = discord.Embed(
                                    colour=discord.Colour(user.colour.value)
                                )
                                embed.set_footer(text="SpryteAI made by shaunceezy")
                                embed.add_field(name="{} nest validated!".format(poke),
                                                value="{}, {} has reported the nest for {} as valid.\n\n[Message Link](https://discordapp.com/channels/{}/{}/{})".format(
                                                    role.mention, user.mention, poke, str(guild_id),
                                                    str(channel_id), str(message.id)),
                                                inline=True)
                                await channel.send(embed=embed)

    @c.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            if ctx.message.channel.id in nest_chans:
                if ctx.message.content.startswith(prefix):
                    search = ctx.message.content.split()
                    query = str(search[0][1:]).lower()
                    pkmn = helpers.pokespellcheck(query)
                    if pkmn not in pokemon:
                        await ctx.message.channel.send("Sorry, " + pkmn + " is not a Pokemon or Command.")
            else:
                return
        elif isinstance(error, CheckFailure):
            pass
        else:
            raise error


def setup(bot):
    bot.add_cog(Nests(bot))
