from main import *

ts = time.time()
embed_footer = config.get("embed_footer")
join_role = config.get('join_role')
join_channel = config.get('join_channel')

welcomePhrases = ["Welcome, {0}!", "Huzzah! {0} has joined the server!", "Hey look!! {0} has arrived"]


async def newuserdm(self, member):
    path = './db/welcome.txt'
    welcome_file = open(path, 'r')
    welcome = welcome_file.read()
    print("Recognised that a member called " + member.name + " joined")
    await member.send(welcome)
    print("Sent message to " + member.name)
    welcome_file.close()
    phrase = random.choice(welcomePhrases)
    channel = self.bot.get_channel(join_channel)
    await channel.send(phrase.format(member.mention))


class Users(c.Cog):

    def __init__(self, bot):
        self.bot = bot

    @c.Cog.listener()
    async def on_member_join(self, member):
        role = discord.utils.get(member.guild.roles, id=join_role)
        if member is not None and not member.bot:
            if role not in member.roles:
                await member.add_roles(role)
        await helpers.check_usersdb(member, member.guild, "On Member Join")
        await helpers.get_player_postgresData(member, member.guild, 'UserName')
        await newuserdm(self, member)
        """
        with open("./db/usersdb.json") as udb:
            usersdb = json.load(udb)
            usersdb[str(member.id)]["nicknames"][str(ts)] = str(member.nick)
            usersdb[str(member.id)]["usernames"][str(ts)] = str(member)
        await helpers.update_json("db", usersdb, "usersdb")"""

    @c.Cog.listener()
    async def on_member_remove(self, member):
        print("Removing user {} from DB".format(member.name))
        await asyncio.sleep(4)
        await helpers.remove_user_from_postgresDB(member, member.guild)

    """@c.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            if after.nick is not None:
                await helpers.check_usersdb(after)
                with open("./db/usersdb.json") as udb:
                    usersdb = json.load(udb)
                    print("Updating nicknames")
                    try:
                        if len(usersdb[str(after.id)]["nicknames"].keys()) > 4:
                            i = 0
                            for key in list(usersdb[str(after.id)]["nicknames"].keys()):
                                if i == 0:
                                    usersdb[str(after.id)]["nicknames"].pop(key)
                                i += 1
                                if i > len(usersdb[str(after.id)]["nicknames"]):
                                    i = 0
                    except KeyError:
                        pass
                usersdb[str(after.id)]["nicknames"][str(ts)] = str(after.nick)
                await helpers.update_json("db", usersdb, "usersdb")"""

    """@c.Cog.listener()
    async def on_user_update(self, before, after):
        if before.name != after.name:
            if after.name is not None:
                await helpers.check_usersdb(after)
                with open("./db/usersdb.json") as udb:
                    usersdb = json.load(udb)
                    print("Updating Usernames")
                    try:
                        if len(usersdb[str(after.id)]["usernames"].keys()) > 4:
                            i = 0
                            for key in list(usersdb[str(after.id)]["usernames"].keys()):
                                if i == 0:
                                    usersdb[str(after.id)]["usernames"].pop(key)
                                i += 1
                                if i > len(usersdb[str(after.id)]["usernames"]):
                                    i = 0
                    except KeyError:
                        pass
                    usersdb[str(after.id)]["usernames"][str(ts)] = str(after.name)
                    await helpers.update_json("db", usersdb, "usersdb")"""

    #@c.group(aliases=['gc', 'gamer'])
    async def gamercard(self, ctx):
        """Information about user that they can configure.
        Includes: PoGo Code, Switch Code, AC Native Fruit, AC Island Name
        Example: $me <optional: @user>
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            print(ctx.message.mentions)
            if len(ctx.message.mentions) > 1:
                await ctx.send("Please only specify one user!")
            if 2 > len(ctx.message.mentions) > 0:
                user = ctx.message.mentions[0]
            else:
                user = ctx.author
            queryList = ['switchcode', 'pogocode', 'nativefruit', 'islandname']
            embed = discord.Embed(
                colour=discord.Colour(0x7E4F70)
            )
            embed.set_footer(text=embed_footer)
            icon_str = str(user.avatar_url)
            icon_addr = icon_str.split('.w', 1)
            author_icon_str = str(self.bot.user.avatar_url)
            author_icon = author_icon_str.split('.w', 1)
            embed.set_author(name="SpryteAI User Info for: " + str(user.name), icon_url=author_icon[0])
            embed.set_thumbnail(url=icon_addr[0])
            for query in queryList:
                data = await helpers.get_player_postgresData(user, ctx.message.guild, query.lower())
                if data[query.lower()] is not None:
                    embed.add_field(name=query, value=data[query], inline=True)
            if len(embed.fields) < 1:
                embed.add_field(name='\u200b', value="No Data Available", inline=True)
            await ctx.send(embed=embed)

    #@gamercard.command()
    async def switchcode(self, ctx, *, code):
        """Sets Users Switch Code.
        $me switchcode SW-XXXX-XXXX-XXXX"""
        if len(code) != 17:
            await ctx.send("Invalid Code! Please make sure the code is valid and includes `SW` and dashes")
            return
        sql = "UPDATE Users SET switchcode=$1 WHERE servid=$2 AND id=$3"
        args = (code, str(ctx.guild.id), str(ctx.author.id))
        await helpers.transaction_postgresDatabase(sql, *args)
        await ctx.send(f"Updated user {ctx.author.name}'s SwitchCode to {code}.")

    #@gamercard.command()
    async def pogocode(self, ctx, *, code):
        """Sets Users Switch Code.
                $me pogocode XXXX XXXX XXXX"""
        if len(code.replace(" ", "")) != 12:
            await ctx.send("Invalid Code! Please make sure the code is valid.")
            return
        sql = "UPDATE Users SET pogocode=$1 WHERE servid=$2 AND id=$3"
        args = (code, str(ctx.guild.id), str(ctx.author.id))
        await helpers.transaction_postgresDatabase(sql, *args)
        await ctx.send(f"Updated user {ctx.author.name}'s PogoCode to {code}.")

    #@gamercard.group()
    async def ac(self):
        ...

    #@ac.command()
    async def island(self):
        ...

    #@ac.command()
    async def fruit(self):
        ...


def setup(bot):
    bot.add_cog(Users(bot))
