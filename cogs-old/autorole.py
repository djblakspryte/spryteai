from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Config File Loaded")
except Exception:
    config = {}
    print("Config File Not Created, Using Temporary Storage.")


class Autorole(c.Cog):

    def __init__(self, bot, **kwargs):
        self.bot = bot

    async def check_return(self, channel, check, timeout: int = 60):
        try:
            msg = await self.bot.wait_for('message', timeout=float(timeout), check=check)
            value = msg.content.replace(" ", "").lower()
            return value
        except asyncio.TimeoutError:
            await self.check_error(channel)
            return None

    async def check_error(self, channel):
        await channel.send("OOF! Sorry! Please rerun the command to restart the process")

    async def setup(self, ctx):
        guild_id = ctx.guild.id

        await ctx.send(f"Please Specify a Message to React to!")

        def reactMessage(m):
            return m.author == ctx.message.author and m.content.isdigit()

        messageIDdata = await self.check_return(ctx.channel, reactMessage, 60)
        msg_id = int(messageIDdata)

        sql = " SELECT * FROM discord_data.autorole where msg_id = $1"
        data = await helpers.query_postgresDatabase(sql, msg_id)
        print(data)
        if data is None:
            itemDict = {}
            update_sql = 'INSERT INTO discord_data.autorole (msg_id , data ) VALUES ($1, $2)'
        else:
            update_sql = 'UPDATE discord_data.autorole SET data = $2 WHERE msg_id = $1'
            itemDict = json.loads(data['data'])
        #print(itemDict)

        def is_channel(m):
            return m.channel == ctx.channel

        await ctx.channel.purge(limit=2, check=is_channel)
        for i in range(20):

            # print('Please Specify an Emoji!')
            await ctx.send(f"Please Specify an Emoji!")

            def reactEmoji(m):
                return m.author == ctx.message.author

            pokeUIDdata = await self.check_return(ctx.channel, reactEmoji, 60)
            emoji = pokeUIDdata.split(":")[1]

            # print('Please Specify a Role!')
            await ctx.send(f"Please Specify a Role!")

            def reactRoleID(m):
                return m.author == ctx.message.author

            pokeUIDdata = await self.check_return(ctx.channel, reactRoleID, 60)
            role_id = int(pokeUIDdata.translate(str.maketrans('', '', string.punctuation)))

            # print('Do you want to add more?')
            await ctx.send(f"Do you want to add more?")

            def reactAnswer(m):
                return m.author == ctx.message.author

            pokeUIDdata = await self.check_return(ctx.channel, reactAnswer, 60)
            answer = pokeUIDdata

            _emoji = discord.utils.get(ctx.guild.emojis, name=emoji)
            try:
                message = await ctx.channel.fetch_message(msg_id)
                await message.add_reaction(_emoji)
            except:
                pass
            itemDict[emoji] = role_id
            if 'y' in answer:
                await ctx.channel.purge(limit=6, check=is_channel)
                continue
            else:
                await ctx.channel.purge(limit=6, check=is_channel)
                await helpers.transaction_postgresDatabase(update_sql, msg_id, json.dumps(itemDict))
                messageLast = await ctx.send("AutoRole Configuration Complete!")
                await asyncio.sleep(2)
                await messageLast.delete()
                break

    async def assignRole(self, payload, data):
        role = None
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, self.bot.guilds)
        for k, v in data.items():
            if payload.emoji.name == k:
                role = discord.utils.get(guild.roles, id=v)


        if role is not None:
            member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
            if role.name.lower() == 'nsfw':
                await member.send(f"Please Specify Your Age!")
                dmchan = member.dm_channel

                if dmchan is None:
                    await member.create_dm()

                def replyDMMessage(m):
                    return m.author == member and type(m.channel) == discord.channel.DMChannel and m.content.isdigit()

                messageAGEdata = await self.check_return(dmchan, replyDMMessage, 60)
                age = int(messageAGEdata)

                if age < 18:
                    await member.send("Sorry but you must be older than 18 to have this role.")
                    return
            if member is not None and not member.bot:
                await member.add_roles(role)
                print('Added member: {} to role: {}'.format(payload.user_id, str(role)))
            elif member.bot:
                print('Bot Detected Using AutoRole')
            else:
                print("Member not found")
        else:
            print("Role not found")

    async def removeRole(self, payload, data):
        role = None
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, self.bot.guilds)
        for k, v in data.items():
            if payload.emoji.name == k:
                role = discord.utils.get(guild.roles, id=v)

        if role is not None:
            member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
            if member is not None and not member.bot:
                await member.remove_roles(role)
                print('Removed member: {} from role: {}'.format(payload.user_id, str(role)))
            elif member.bot:
                print('Bot Detected Using AutoRole')
            else:
                print("Member not found")
        else:
            print("Role not found")

    @c.command(aliases=['ars'])
    async def autorole_setup_(self, ctx):
        await self.setup(ctx)

    @c.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        sql = " SELECT * FROM discord_data.autorole where msg_id = $1"
        data = await helpers.query_postgresDatabase(sql, payload.message_id)
        #print(data)
        if data is not None:
            ar_data = json.loads(data['data'])
            await self.assignRole(payload, ar_data)

    @c.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        sql = " SELECT * FROM discord_data.autorole where msg_id = $1"
        data = await helpers.query_postgresDatabase(sql, payload.message_id)
        #print(data)
        if data is not None:
            ar_data = json.loads(data['data'])
            await self.removeRole(payload, ar_data)


def setup(bot):
    bot.add_cog(Autorole(bot))
