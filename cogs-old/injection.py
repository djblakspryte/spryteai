from main import *
import pysftp
from urllib.parse import urlparse
import os
import json

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

with open("./config/config.json") as cfg:
    config = json.load(cfg)

owner = keys.get("owner")
host = config.get('isle_host')
host_user = config.get('isle_host_username')
host_pass = keys.get('isle_host_key')
isle_survival = config.get('survival_data_path')
isle_sandbox = config.get('sandbox_data_path')
isle_mode = config.get('isle_mode')
embed_footer = config.get('embed_footer')
default_Growth = "1.0"
default_Hunger = "99999"
default_Thirst = "99999"
default_Stam = "99999"
default_Health = "99999"
default_BleedRate = "0"
default_Gender = ""
default_LegBreak = "false"
default_YPosition = ""
decYPosition = 0

dinoList = [
    {
        'Name': "Acro",
        'CharacterClass': "Acro",
        'bIsBig': True,
        'Price': 1500
    },
    {
        'Name': "Albert",
        'CharacterClass': "Albert",
        'bIsBig': True,
        'Price': 900
    },
    {
        'Name': "Bary",
        'CharacterClass': "Bary",
        'bIsBig': True,
        'Price': 700
    },
    {
        'Name': "Herrera",
        'CharacterClass': "Herrera",
        'bIsBig': False,
        'Price': 0
    },
    {
        'Name': "Spino",
        'CharacterClass': "Spino",
        'bIsBig': True,
        'Price': 15000
    },
    {
        'Name': "Velo",
        'CharacterClass': "Velo",
        'bIsBig': False,
        'Price': 100
    },
    {
        'Name': "Anky",
        'CharacterClass': "Anky",
        'bIsBig': False,
        'Price': 900
    },
    {
        'Name': "Austro",
        'CharacterClass': "Austro",
        'bIsBig': False,
        'Price': 0
    },
    {
        'Name': "Ava",
        'CharacterClass': "Ava",
        'bIsBig': False,
        'Price': 100
    },
    {
        'Name': "Camara",
        'CharacterClass': "Camara",
        'bIsBig': True,
        'Price': 15000
    },
    {
        'Name': "Oro",
        'CharacterClass': "Oro",
        'bIsBig': False,
        'Price': 100
    },
    {
        'Name': "Taco",
        'CharacterClass': "Taco",
        'bIsBig': False,
        'Price': 100
    },
    {
        'Name': "Shant",
        'CharacterClass': "Shant",
        'bIsBig': True,
        'Price': 15000
    },
    {
        'Name': "Stego",
        'CharacterClass': "Stego",
        'bIsBig': False,
        'Price': 900
    },
    {
        'Name': "Theri",
        'CharacterClass': "Theri",
        'bIsBig': True,
        'Price': 1000
    },
    {
        'Name': "Allo",
        'CharacterClass': "AlloAdultS",
        'bIsBig': False,
        'Price': 750
    },
    {
        'Name': "Carno",
        'CharacterClass': "CarnoAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Cerato",
        'CharacterClass': "CeratoAdultS",
        'bIsBig': False,
        'Price': 750
    },
    {
        'Name': "Dilo",
        'CharacterClass': "DiloAdultS",
        'bIsBig': False,
        'Price': 600
    },
    {
        'Name': "Giga",
        'CharacterClass': "GigaAdultS",
        'bIsBig': True,
        'Price': 12000
    },
    {
        'Name': "GigaSub",
        'CharacterClass': "GigaSubS",
        'bIsBig': False,
        'Price': 12000
    },
    {
        'Name': "Sucho",
        'CharacterClass': "SuchoAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Rex",
        'CharacterClass': "RexAdultS",
        'bIsBig': True,
        'Price': 15000
    },
    {
        'Name': "RexSub",
        'CharacterClass': "RexSubS",
        'bIsBig': True,
        'Price': 15000
    },
    {
        'Name': "Utah",
        'CharacterClass': "UtahAdultS",
        'bIsBig': False,
        'Price': 600
    },
    {
        'Name': "Diablo",
        'CharacterClass': "DiabloAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Dryo",
        'CharacterClass': "DryoAdultS",
        'bIsBig': False,
        'Price': 0
    },
    {
        'Name': "Galli",
        'CharacterClass': "GalliAdultS",
        'bIsBig': False,
        'Price': 500
    },
    {
        'Name': "Maia",
        'CharacterClass': "MaiaAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Pachy",
        'CharacterClass': "PachyAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Para",
        'CharacterClass': "ParaAdultS",
        'bIsBig': False,
        'Price': 700
    },
    {
        'Name': "Trike",
        'CharacterClass': "TrikeAdultS",
        'bIsBig': False,
        'Price': 15000
    },
    {
        'Name': "TrikeSub",
        'CharacterClass': "TrikeSubS",
        'bIsBig': False,
        'Price': 15000
    }
]
Pue = {
    'Name': "Pue",
    'CharacterClass': "Puerta",
    'bIsBig': True,
    'Price': 0
}


async def composeStore(user, page: int = None):
    dinoListEndIndex = page * 5
    dinoListStartIndex = dinoListEndIndex - 5
    embed_str = "--------------------\n"
    embed_str += "|  Name   | Price  |\n"
    embed_str += "|---------|--------|\n"
    if helpers.check_role(user, AdminRole):
        for i, item in enumerate(dinoList):
            if item['Name'] == "Pue":
                dinoList.pop(i)
        dinoList.append(Pue)
    i = 0
    for item in dinoList[dinoListStartIndex:dinoListEndIndex]:
        i += 1
        dinoName = item['Name'] + "          "
        dinoPrice = str(item['Price']) + "          "
        embed_str += f"|{dinoName[:9]}| {dinoPrice[:7]}|\n"
        if i != 5:
            embed_str += f"|---------|--------|\n"
        print(embed_str)
    embed_str += "--------------------"
    embed = discord.Embed(
        colour=discord.Colour(0x7E4F70)
    )
    embed.add_field(name="Inventory", value=f"`{embed_str}`", inline=False)
    embed.set_footer(text=f"Powered by BlakSpryte · Page: {page}")
    return embed


class Paginator(discordbuttons.Paginator):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Sftp:
    def __init__(self, hostname, username, password, port=8822):
        """Constructor Method"""
        # Set connection object to None (initial value)
        self.connection = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port

    def connect(self):
        """Connects to the sftp server and returns the sftp connection object"""

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        cnopts = cnopts

        try:
            # Get the sftp connection object
            self.connection = pysftp.Connection(
                host=self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
                cnopts=cnopts
            )
        except Exception as err:
            raise Exception(err)
        finally:
            print(f"Connected to {self.hostname} as {self.username}.")

    def disconnect(self):
        """Closes the sftp connection"""
        self.connection.close()
        print(f"Disconnected from host {self.hostname}")

    def listdir(self, remote_path):
        """lists all the files and directories in the specified path and returns them"""
        for obj in self.connection.listdir(remote_path):
            yield obj

    def listdir_attr(self, remote_path):
        """lists all the files and directories (with their attributes) in the specified path and returns them"""
        for attr in self.connection.listdir_attr(remote_path):
            yield attr

    def download(self, remote_path, target_local_path):
        """
        Downloads the file from remote sftp server to local.
        Also, by default extracts the file to the specified target_local_path
        """

        try:
            print(
                f"downloading from {self.hostname} as {self.username} [(remote path : {remote_path});(local path: {target_local_path})] "
            )

            # Create the target directory if it does not exist
            path, _ = os.path.split(target_local_path)
            if not os.path.isdir(path):
                try:
                    os.makedirs(path)
                except Exception as err:
                    raise Exception(err)

            # Download from remote sftp server to local
            self.connection.get(remote_path, target_local_path)
            print("download completed")

        except Exception as err:
            raise Exception(err)

    def upload(self, source_local_path, remote_path):
        """
        Uploads the source files from local to the sftp server.
        """

        try:
            print(
                f"uploading to {self.hostname} as {self.username} [(remote path: {remote_path});(source local path: {source_local_path})]"
            )

            # Download file from SFTP
            self.connection.put(source_local_path, remote_path)
            print("upload completed")

        except Exception as err:
            raise Exception(err)


class Injection(c.Cog):

    def __init__(self, bot):
        self.bot = bot

    @bot.event
    async def on_raw_reaction_add(payload):
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        # guild = bot.get_guild(payload.guild_id)
        emoji = payload.emoji.name

        # skip DM messages
        if isinstance(channel, discord.DMChannel):
            return

        # only work if in bot is the author
        # skip messages not by bot
        # skip reactions by the bot
        if message.author.id != bot.user.id or payload.member.id == bot.user.id:
            return

        if emoji == '◀':
            pageIndex = int(message.embeds[0].footer.text[-1])
            dinoListEndIndex = pageIndex * 5
            dinoListStartIndex = dinoListEndIndex - 5
            if dinoListStartIndex > 0:
                pageIndex -= 1
                embed = await composeStore(payload.member, pageIndex)
                await message.edit(embed=embed)
        if emoji == '▶':
            pageIndex = int(message.embeds[0].footer.text[-1])
            dinoListEndIndex = pageIndex * 5
            if dinoListEndIndex < len(dinoList):
                pageIndex += 1
                embed = await composeStore(payload.member, pageIndex)
                await message.edit(embed=embed)

        # remove user reaction
        reaction = discord.utils.get(message.reactions, emoji=emoji)
        await reaction.remove(payload.member)

    @c.command(name='dino')
    async def dino(self, ctx, index: int = 0):
        """Checks a users current dinos.
        Example: $dino <optional: Dino Number>
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            m = await ctx.send(f"Fetching Data for {ctx.message.author}...")
            user = ctx.message.author
            data = await helpers.get_player_postgresData(ctx.message.author, ctx.message.guild, 'steamID')
            dinoData = await helpers.check_usersdb(ctx.message.author, ctx.message.guild, "Dino Check Func")
            steamID = data['steamID']
            print(steamID)
            if steamID == 0:
                await m.edit(
                    content=f'Please configure your Steam64 ID using: {prefix}config set steamid #############')
                return
            if isle_mode == "sandbox":
                path = isle_sandbox
            else:
                path = isle_survival
            sftp_url = f'sftp://{host_user}:{host_pass}@{host}'
            # print("First, please set environment variable SFTPTOGO_URL and try again.")
            # exit(0)

            parsed_url = urlparse(sftp_url)

            sftp = Sftp(
                hostname=parsed_url.hostname,
                username=parsed_url.username,
                password=parsed_url.password,
            )
            embed = discord.Embed(
                colour=discord.Colour(0x7E4F70)
            )
            print(len(dinoData['dinos']))
            # Connect to SFTP
            sftp.connect()

            # Download files from SFTP
            try:
                sftp.download(
                    f'{path}/{steamID}.json', os.path.join(f'temp/{steamID}.json')
                )
                # Disconnect from SFTP
                sftp.disconnect()
            except:
                await m.edit(content=
                             "No User Found on Server. Please ensure you have joined the Isle Server and safelogged.")
                return
            try:
                with open(f'temp/{steamID}.json') as dn:
                    dino = json.load(dn)
                    print(dino)
                    if len(dinoData['dinos']) == 0:
                        dinoData['dinos'].append(dino)
                    else:
                        dinoData['dinos'][0] = dino
                await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", dinoData,
                                          f"{str(ctx.message.author.id)}")
            except:
                pass
            if index == 0:
                msg_string = ""
                for ind, item in enumerate(dinoData['dinos']):
                    print(f"Index: {ind}")
                    if ind == 0:
                        if item['bGender']:
                            gender = ":female_sign:\n"
                        else:
                            gender = ":male_sign:\n"
                        msg_string += f"Current Dino: {item['CharacterClass']} {gender}"
                        print(msg_string)
                    else:
                        if item['bGender']:
                            gender = ":female_sign:\n"
                        else:
                            gender = ":male_sign:\n"
                        msg_string += f"[{ind}]: {item['CharacterClass']} {gender}"

                embed.set_footer(text=embed_footer)
                icon_str = str(user.avatar_url)
                icon_addr = icon_str.split('.w', 1)
                author_icon_str = str(self.bot.user.avatar_url)
                author_icon = author_icon_str.split('.w', 1)
                embed.set_author(name="SpryteHaven Dinos ", icon_url=author_icon[0])
                embed.set_thumbnail(url=icon_addr[0])
                embed.add_field(name=f"Inventory", value=f"{msg_string}", inline=True)
                await user.send(content=None, embed=embed)
                await m.edit(content="Check your DM's for your dinos :) ")
            else:
                if index <= (len(dinoData['dinos']) - 1) and len(dinoData['dinos']) >= 2:
                    await m.edit(content="Swapping Dinos....")
                    sftp.connect()
                    try:
                        sftp.download(
                            f'{path}/{steamID}.json', os.path.join(f'temp/{steamID}.json')
                        )
                        try:
                            with open(f'temp/{steamID}.json') as dn:
                                dino = json.load(dn)
                                print(dino)
                                dinoData['dinos'][0] = dino
                            await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", dinoData,
                                                      f"{str(ctx.message.author.id)}")
                        except:
                            pass
                    except:
                        pass
                    dinoData = await helpers.check_usersdb(ctx.message.author, ctx.message.guild,
                                                       "Dino Func After Download")
                    dinoData['dinos'][0], dinoData['dinos'][index] = dinoData['dinos'][index], dinoData['dinos'][0]
                    dino1 = dinoData['dinos'][0]
                    dino2 = dinoData['dinos'][index]
                    if dino1['bGender']:
                        gender1 = ':female_sign:'
                    else:
                        gender1 = ':male_sign:'
                    if dino2['bGender']:
                        gender2 = ':female_sign:'
                    else:
                        gender2 = ':male_sign:'
                    await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", dinoData, f"{str(ctx.message.author.id)}")
                    # Upload files to SFTP location from local
                    local_path = f'./temp/{steamID}.json'
                    remote_path = f'{path}/{steamID}.json'
                    await helpers.update_json(f"temp/", dinoData['dinos'][0], f"{str(steamID)}")
                    # with open(local_path, "w+") as dn:
                    #    dn.write(dinoData['dinos'][0])
                    sftp.upload(local_path, remote_path)
                    sftp.disconnect()
                    await m.edit(
                        content=f"{dino2['CharacterClass']} {gender2} swapped for {dino1['CharacterClass']} {gender1}")
                else:
                    await m.edit(content="Need More Dinos")

    @c.command(name='buy')
    async def dinobuy(self, ctx, *args):
        """Buys Dino.
        Example: $buy Acro male
        *Contains subcommands*"""
        if len(args) == 0:
            embed = await composeStore(ctx.message.author, 1)
            msg = await ctx.send(embed=embed)
            reactionList = ['◀', '▶']
            for emoji in reactionList:
                await msg.add_reaction(emoji)
        else:
            data = await helpers.get_player_postgresData(ctx.message.author, ctx.message.guild, 'steamID')
            dinoData = await helpers.check_usersdb(ctx.message.author, ctx.message.guild, "Dino Buy Func")
            if len(dinoData['dinos']) >= 5:
                await ctx.send('You have too many dinos!')
                return
            steamID = data['steamID']
            print(steamID)
            if steamID == 0:
                await ctx.send(f'Please configure your Steam64 ID using: {prefix}config steamid #############')
                return
            if isle_mode == "sandbox":
                path = isle_sandbox
            else:
                path = isle_survival
            sftp_url = f'sftp://{host_user}:{host_pass}@{host}'

            parsed_url = urlparse(sftp_url)

            sftp = Sftp(
                hostname=parsed_url.hostname,
                username=parsed_url.username,
                password=parsed_url.password,
            )
            gender = None
            characterClass = None
            price = None
            if helpers.check_role(ctx.message.author, AdminRole):
                for i, item in enumerate(dinoList):
                    if item['Name'] == "Pue":
                        dinoList.pop(i)
                dinoList.append(Pue)
            for arg in args:
                if (str(arg).lower()) == "male":
                    gender = False
                elif (str(arg).lower()) == "female":
                    gender = True
                for dino in dinoList:
                    if str(arg).lower() == dino['Name'].lower():
                        characterClass = dino['CharacterClass']
                        isBig = dino['bIsBig']
                        price = dino['Price']
            if gender is None:
                await ctx.send('Please Specify a Gender')
                return
            elif characterClass is None:
                await ctx.send('Please Specify a Valid Dino')
                return
            elif not await helpers.enough_money(ctx.message.author, ctx.message.guild, price) and ctx.message.author.id not in owner:
                await ctx.send(f"You need an account with enough funds to purchase more dinos. Try collecting with "
                               "the daily command if you haven't already!")
                return
            sftp.connect()

            # Download files from SFTP
            try:
                sftp.download(
                    f'{path}/{steamID}.json', os.path.join(f'temp/{steamID}.json')
                )
                # Disconnect from SFTP
                sftp.disconnect()
            except:
                await ctx.send("No User Found on Server. Please ensure you have joined the Isle Server and safelogged.")
                return
            try:
                with open(f'temp/{steamID}.json') as dn:
                    dino = json.load(dn)
                    dino['CharacterClass'] = characterClass
                    dino['bIsBig'] = isBig
                    dino['bGender'] = gender
                    dino["Growth"] = default_Growth
                    dino["Hunger"] = default_Hunger
                    dino["Thirst"] = default_Thirst
                    dino["Stamina"] = default_Stam
                    dino["Health"] = default_Health
                    dino["BleedingRate"] = default_BleedRate
                    print(dino)
                    dinoData['dinos'].append(dino)
                await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", dinoData,
                                          f"{str(ctx.message.author.id)}")
                if dino['bGender']:
                    gender1 = ':female_sign:'
                else:
                    gender1 = ':male_sign:'
                # await helpers.withdraw_money(ctx.message.author, ctx.message.guild, price)
                await ctx.send(f"Bought a(n): {dino['CharacterClass']} {gender1}")
            except:
                pass

    @c.command(name='trash')
    async def trashdino(self, ctx, index: int):
        """Trashes Dino.
        Example: $trash #"""
        if index != 0:
            data = await helpers.check_usersdb(ctx.message.author, ctx.message.guild, "Dino Trash Func")
            trashDino = data['dinos'][index]
            del data['dinos'][index]
            await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", data,
                                      f"{str(ctx.message.author.id)}")
            await ctx.send(f"Deleted {trashDino['CharacterClass']} from Inventory")
        else:
            await ctx.send('You cannot delete your Current Dino.')

    @c.command(name='tp')
    async def teleport(self, ctx, destUser: discord.Member):
        """Checks a users current xp.
        Example: $xp <optional: @user>
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            data = await helpers.check_usersdb(ctx.message.author, ctx.message.guild, "Teleport Dino Func")
            destData = await helpers.check_usersdb(destUser, ctx.message.guild, "Teleport Dino Func")
            steamData = await helpers.get_player_postgresData(ctx.message.author, ctx.message.guild, 'steamID')
            destSteamData = await helpers.get_player_postgresData(destUser, ctx.message.guild, 'steamID')
            steamID = steamData['steamID']
            destSteamID = destSteamData['steamID']
            if steamID == 0:
                await ctx.send(
                    f'{ctx.message.author.mention} please configure your Steam64 ID using: {prefix}config steamid #############')
                return
            elif destSteamID == 0:
                await ctx.send(
                    f'{destUser.mention} please configure your Steam64 ID using: {prefix}config steamid #############')
                return
            if isle_mode == "sandbox":
                path = isle_sandbox
            else:
                path = isle_survival
            sftp_url = f'sftp://{host_user}:{host_pass}@{host}'
            # print("First, please set environment variable SFTPTOGO_URL and try again.")
            # exit(0)

            parsed_url = urlparse(sftp_url)

            sftp = Sftp(
                hostname=parsed_url.hostname,
                username=parsed_url.username,
                password=parsed_url.password,
            )
            embed = discord.Embed(
                colour=discord.Colour(0x7E4F70)
            )
            msg = await ctx.send(f"Teleporting to {destUser.mention}....")
            sftp.connect()
            try:
                sftp.download(
                    f'{path}/{steamID}.json', os.path.join(f'temp/{steamID}.json')
                )
                try:
                    with open(f'temp/{steamID}.json') as dn:
                        dino = json.load(dn)
                        print(dino)
                        data['dinos'][0] = dino
                    await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", data,
                                              f"{str(ctx.message.author.id)}")
                    sftp.disconnect()
                except:
                    sftp.disconnect()
                    pass
            except:
                await ctx.send(f"{ctx.message.author.mention} not found on Server")
                sftp.disconnect()
                return
            sftp.connect()
            try:
                sftp.download(
                    f'{path}/{destSteamID}.json', os.path.join(f'temp/{destSteamID}.json')
                )
                try:
                    with open(f'temp/{destSteamID}.json') as destdn:
                        destdino = json.load(destdn)
                        print(destdino)
                        destData['dinos'][0] = destdino
                    await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", destData,
                                              f"{str(destUser.id)}")
                    sftp.disconnect()
                except:
                    sftp.disconnect()
                    pass
            except:
                await ctx.send(f"{destUser.mention} not found on Server")
                sftp.disconnect()
                return
            #destData = await helpers.check_usersdb(destUser, ctx.message.guild, "Teleport Dino Func")
            print(data['dinos'][0]['Location_Thenyaw_Island'], destData['dinos'][0]['Location_Thenyaw_Island'])
            data['dinos'][0]['Location_Thenyaw_Island'] = destData['dinos'][0]['Location_Thenyaw_Island']
            await helpers.update_json(f"db/{str(ctx.message.guild.id)}/", data, f"{str(ctx.message.author.id)}")
            # Upload files to SFTP location from local
            local_path = f'./temp/{steamID}.json'
            remote_path = f'{path}/{steamID}.json'
            await helpers.update_json(f"temp", data['dinos'][0], f"{str(steamID)}")
            sftp.connect()
            sftp.upload(local_path, remote_path)
            sftp.disconnect()
            await msg.edit(
                content=f"Teleported to {destUser.mention}")
        else:
            await ctx.send("Need More Dinos")

    @teleport.error
    async def teleport_error(self, ctx, error):
        await ctx.send(error)


def setup(bot):
    bot.add_cog(Injection(bot))
