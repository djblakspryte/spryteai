from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Invites Config Loaded")
except Exception:
    config = {}
    print("Invites Config Not Created, Using Temporary Storage.")

embed_footer = config.get("embed_footer")
welcome_chan_id = config.get("welcome_chan_id")
leave_chan_id = config.get("leave_chan_id")


async def join_invite_checker(results, vanity_invite, invites):
    i = 0
    Found = False
    print("Starting Invite Function...")
    for result in results:
        if vanity_invite is not None:
            if result['invitecode'] == vanity_invite.code:
                if result['inviteuses'] != vanity_invite.uses:
                    validInvite = vanity_invite
                    inviter_name = "VANITY"
                    print("Vanity Invite Join")
                    Found = True
                    return validInvite, inviter_name, Found
        else:
            for invite in invites:
                if result['invitecode'] == invite.code and result['inviteuses'] != invite.uses:
                    validInvite = invite
                    inviter = validInvite.inviter
                    inviter_name = inviter.name
                    print("{} Invite Join".format(inviter_name))
                    Found = True
                    return validInvite, inviter_name, Found
    if not Found:
        return None, None, Found


async def leave_invite_checker(member, guild, vanity_invite, invites):
    Found = False
    print("Starting Invite Function...")
    data = await helpers.get_player_postgresData(member, guild, 'invitecode')
    if vanity_invite is not None:
        if data['invitecode'] == vanity_invite.code:
            validInvite = vanity_invite
            inviter_name = "VANITY"
            print("Vanity Invite Leave")
            Found = True
            return validInvite, inviter_name, Found
    else:
        for invite in invites:
            if data['invitecode'] == invite.code:
                validInvite = invite
                inviter = validInvite.inviter
                inviter_name = inviter.name
                print("{} Invite Leave".format(inviter_name))
                Found = True
                return validInvite, inviter_name, Found
    if not Found:
        return None, None, Found


async def update_invites(ctx):
    invites = await ctx.guild.invites()
    trun_sql = "TRUNCATE TABLE discord_data.invites;"
    await helpers.transaction_postgresDatabase(trun_sql)
    init_sql = "INSERT INTO discord_data.invites (servid, inviterid, invitecode, inviteuses) VALUES ($1, $2, $3, $4)"
    for invite in invites:
        await helpers.transaction_postgresDatabase(init_sql, str(invite.guild.id), str(invite.inviter.id), invite.code, invite.uses)
        vanity_invite = await ctx.guild.vanity_invite()
        if vanity_invite is not None:
            await helpers.transaction_postgresDatabase(init_sql, str(vanity_invite.guild.id), None, vanity_invite.code, vanity_invite.uses)


class Invites(c.Cog):
    """Invite Manager Cog. Keeps Track of User Invites and logs incoming and outgoing users."""

    def __init__(self, bot):
        self.bot = bot

    @c.Cog.listener()
    async def on_member_join(self, member):
        invites = await member.guild.invites()
        numUses = 0
        channel = self.bot.get_channel(welcome_chan_id)
        results = await helpers.get_invites_postgresDB(member.guild)
        try:
            vanity_invite = await member.guild.vanity_invite()
        except:
            vanity_invite = None
        validInvite, inviter_name, Found = await join_invite_checker(results, vanity_invite, invites)
        if not Found:
            await channel.send(
                "{} **joined**; But I couldn't figure out who invited them.".format(member.mention))
        else:
            for result in results:
                if validInvite.code == result['invitecode']:
                    numUses = result['inviteuses'] + 1
                    print(numUses)
            await channel.send(
                "{} **joined**; Invited by **{}** [{} invite(s)]\nMembers: {}".format(member.mention,
                                                                                      inviter_name,
                                                                                      numUses,
                                                                                      member.guild.member_count))
            updating_sql = "UPDATE discord_data.users SET invitecode=$1 WHERE servid=$2 AND id=$3"
            await helpers.transaction_postgresDatabase(updating_sql, validInvite.code, str(member.guild.id), str(member.id))
        await update_invites(member)

    @c.Cog.listener()
    async def on_member_remove(self, member):
        channel = self.bot.get_channel(leave_chan_id)
        print("Recognied member {} left".format(member.name))
        invites = await member.guild.invites()
        numUses = 0
        try:
            vanity_invite = await member.guild.vanity_invite()
        except:
            vanity_invite = None
        validInvite, inviter_name, Found = await leave_invite_checker(member, member.guild, vanity_invite, invites)
        Found = False
        if not Found:
            await channel.send(
                "{} **left**; But I couldn't figure out who invited them.".format(member.name))
        else:
            if vanity_invite is not None:
                if validInvite is vanity_invite:
                    numUses += vanity_invite.uses
                    print(numUses)
            else:
                for invite in invites:
                    if invite.inviter.id is validInvite.inviter.id:
                        numUses += invite.uses
                        print(numUses)
            await channel.send(
                "{} **left**; Invited by **{}** [{} invite(s)]\nMembers: {}".format(member.name,
                                                                                    inviter_name,
                                                                                    numUses,
                                                                                    member.guild.member_count))

    @c.Cog.listener()
    async def on_invite_create(self, invite):
        sql = "INSERT INTO discord_data.invites (servid, inviterid, invitecode, inviteuses) VALUES ($1, $2, $3, $4)"
        await helpers.transaction_postgresDatabase(sql, str(invite.guild.id), str(invite.inviter.id), invite.code, invite.uses)
        print("Updated Invites\nCreator: {}\nCode: {}".format(invite.inviter, invite.code))

    @c.group()
    async def invites(self, ctx):
        """Checks a users current invites and uses.
        Example: $invites <optional: @user>
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            args = ctx.message.content.split()
            if len(args) > 1:
                user_id = int(args[1].replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                member = discord.utils.get(ctx.guild.members, id=user_id)
            else:
                member = ctx.message.author
            embed = discord.Embed(
                color=member.color
            )
            embed.set_footer(text=embed_footer)
            icon_str = str(member.avatar_url)
            icon_addr = icon_str.split('.w', 1)
            embed.set_author(name="SpryteAI Invite Statistics for: {}#{}".format(member.name,
                                                                                   member.discriminator))
            embed.set_thumbnail(url=icon_addr[0])
            invites = await ctx.guild.invites()
            numInvites, numUses = 0, 0
            for invite in invites:
                if invite.inviter.id is member.id:
                    numInvites += 1
                    numUses += invite.uses
                    embed.add_field(name="{} - {}".format(invite.channel, invite.code),
                                    value="Joins: {}".format(invite.uses), inline=False)
            if numInvites < 1:
                embed.add_field(name="No Invites Detected!",
                                value="Please React Below to Create a new Invite!", inline=False)
            else:
                embed.add_field(name="Total Invites: {}".format(numInvites),
                                value="Total Joins: {}".format(numUses), inline=False)
            invite_msg = await ctx.send(embed=embed)
            if numInvites < 1:
                await invite_msg.add_reaction('\u2795')

    @helpers.is_creator()
    @invites.command()
    async def init(self, ctx):
        """Refreshes Invites Database.
        Example: $invites init"""
        await update_invites(ctx)

    @invites.command(name='leaderboard', aliases=['lead'])
    async def leaderboard(self, ctx, number: int = 10):
        """Leaderboard for Invites.
        Example: $invites leaderboard <optional: number>"""
        embed = discord.Embed(
            color=ctx.message.author.color
        )
        embed.set_footer(text=embed_footer)
        embed.set_author(name='Top {} Invites Leaderboard'.format(str(number)))
        invites = await ctx.guild.invites()
        members = ctx.guild.members
        leaderboard_dict = {}
        for member in members:
            numInvites, numUses = 0, 0
            for invite in invites:
                if invite.inviter.id is member.id:
                    numInvites += 1
                    numUses += invite.uses
                    if str(member.id) not in leaderboard_dict:
                        leaderboard_dict[str(member.name)] = numUses
                    else:
                        leaderboard_dict[str(member.name)] += numUses
        i = 0
        leaderboard_list = sorted(leaderboard_dict.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        while i < number:
            print(leaderboard_list[i][0], leaderboard_list[i][1])
            embed.add_field(name="#{}. {}".format(i + 1, leaderboard_list[i][0]),
                            value="*Invites:* {}".format(leaderboard_list[i][1]), inline=False)
            i += 1
        await ctx.send(embed=embed)
        # print(leaderboard_dict)

    async def create_invite(self, payload, max_age: int = 0, max_uses: int = 0, temporary: bool = False, unique: bool = False, *, reason = None):
        """Creates an Invite to Server
        Example: $create_invite <#channel> <Optional: max_age(num)> <Optional: max_uses(num)> <Optional: temporary(True/False)> <Optional: unique(True/False)> <Optional: reason>"""
        #guild = discord.utils.find(lambda g: g.id == payload.guild_id, self.bot.guilds)
        channel = self.bot.get_channel(payload.channel_id)
        invite = await channel.create_invite(reason=reason, max_age=max_age, max_uses=max_uses, temporary=temporary, unique=unique)
        await channel.send("Invite `{}` created!\nhttps://discord.gg/{}".format(invite.code, invite.code))
        print("Code: {}\nCreated At: {}\nInviter: {}\nChannel: {}".format(invite.code, invite.created_at, invite.inviter, invite.channel))


    @c.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        print(payload.emoji.name)
        guild = discord.utils.find(lambda g: g.id == payload.guild_id, self.bot.guilds)
        user = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
        if payload.emoji.name == '\u2795' and not user.bot:
            await self.create_invite(payload)


    @helpers.is_creator()
    @invites.group()
    async def config(self, ctx):
        """
        BETA FEATURE
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid config command passed...')

    @config.command(name='joinMessage', aliases=['join'])
    async def joinMessage(self, ctx, *str):
        ...

    @config.command(name='leaveMessage', aliases=['leave'])
    async def leaveMessage(self, ctx, *str):
        ...


def setup(bot):
    bot.add_cog(Invites(bot))
