import helpers
from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Reputation Config Loaded")
except Exception:
    config = {}
    print("Reputation Config Not Created, Using Temporary Storage.")

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

ModRole = config.get("ModRole")
AdminRole = config.get("AdminRole")
embed_footer = config.get("embed_footer")


class Reputation(c.Cog):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def give_reputation(member, guild, reputation: int):
        data = await helpers.get_player_postgresData(member, guild, 'Reputation')
        updated_reputation = data['Reputation'] + reputation
        sql = 'UPDATE discord_data.users SET "Reputation"=$1 WHERE "ServerID"=$2 AND "UserID"=$3'
        await helpers.transaction_postgresDatabase(sql, updated_reputation, guild.id, member.id)
        print("[*] Updated user %s reputation points from %s to %s." % (
        member.name, data['Reputation'], updated_reputation))

    @staticmethod
    async def set_rep(member, guild, reputation: int):
        data = await helpers.get_player_postgresData(member, guild, 'Reputation')
        sql = 'UPDATE discord_data.users SET "Reputation"=$1 WHERE "ServerID"=$2 AND "UserID"=$3'
        await helpers.transaction_postgresDatabase(sql, reputation, guild.id, member.id)
        print("[*] Updated user %s reputation points from %s to %s." % (
        member.name, data['Reputation'], reputation))

    @c.command()
    async def rep(self, ctx, member: discord.Member = None):
        """Checks a users current reputation.
        Example: $rep <optional: @user>)"""
        if member is None:
            member = ctx.message.author
        data = await helpers.get_player_postgresData(member, ctx.message.guild, 'Reputation')
        embed = discord.Embed(
            colour=discord.Colour.red()
        )
        embed.set_footer(text=embed_footer)
        icon_str = str(member.avatar_url)
        icon_addr = icon_str.split('.w', 1)
        author_icon_str = str(self.bot.user.avatar_url)
        author_icon = author_icon_str.split('.w', 1)
        embed.set_author(name="SpryteAI Rep Stat for: {}".format(member.name), icon_url=author_icon[0])
        embed.set_thumbnail(url=icon_addr[0])
        embed.add_field(name="Rep", value=data['Reputation'], inline=True)
        await ctx.send(embed=embed)

    @c.command()
    async def giverep(self, ctx, member: discord.Member):
        """Gives Rep to a specified user.
        Example: $giverep <@user>.
        Cannot be yourself."""
        if ctx.message.author.id == member.id:
            await ctx.send("You can't give yourself reputation points, fool!")
            return
        await ctx.send("Gave {} 1 reputation point!".format(member.mention))
        await self.give_reputation(member, ctx.message.guild, 1)

    @c.command()
    async def takerep(self, ctx, member: discord.Member):
        """Removes Rep from a specified user.
        Example: $takerep <@user>
        Cannot be yourself."""
        data = await helpers.get_player_postgresData(member, ctx.message.guild, 'reputation')
        rep = data['reputation']
        if ctx.message.author.id == member.id:
            await ctx.send("You can't take reputation points from yourself, fool!")
            return
        if rep <= 0:
            await ctx.send("{} doesn't have any rep points to take!".format(member.mention))
        else:
            await ctx.send("Took a reputation point from {}!".format(member.mention))
            await self.give_reputation(member, ctx.message.guild, -1)

    @c.command()
    @helpers.is_creator()
    async def setrep(self, ctx, member: discord.Member, rep: int):
        """Sets rep of a specified user.
        Example: $setrep <@user> <number>"""
        if ctx.message.author.id == member.id:
            await ctx.send("You can't give yourself reputation points, fool!")
            return
        if rep <= -1:
            await ctx.send("You can't give {} negative points!".format(member.mention))
            return
        if rep >= 1000000000:
            await ctx.send("You can't give {} more than 1000000000 points!".format(member.mention))
            return
        else:
            await ctx.send("Gave {}, {} reputation points!".format(member.mention, rep))
            await self.set_rep(member, ctx.message.guild, rep)


def setup(bot):
    bot.add_cog(Reputation(bot))
