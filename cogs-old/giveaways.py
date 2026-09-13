from main import *

with open("./config/config.json") as cfg:
    config = json.load(cfg)
    print("Loaded Bank Config")

ModRole = config.get("ModRole")
embed_footer = config.get("embed_footer")
letters = string.ascii_lowercase


class Giveaways(c.Cog):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def randomString(stringLength=8):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(stringLength))

    @staticmethod
    async def lottery_pick(bot, channel, amount, time_secs, answer, process_name):

        embed = discord.Embed(
            colour=discord.Colour(0x95A5A6),
            title="<a:HyperTada:611922514591088652>**LOTTERY EVENT**<a:HyperTada:611922514591088652>"
        )
        if answer:
            contrib_str = "*Contributor Only*"
        else:
            contrib_str = '\u200b'
        embed.add_field(name=contrib_str,
                        value="Reward: {} credits\nTime Length: {}".format(amount, helpers.display_time(time_secs)),
                        inline=True)
        embed.set_footer(text="{}\nProcess Name: {}".format(embed_footer, process_name))
        message = await channel.send(embed=embed)
        await message.add_reaction('💰')
        print(process_name)
        remaining_secs = time_secs
        for sec in range(time_secs):
            try:
                if (sec % 10) == 0:
                    print(message.embeds[0].fields[0])
                    print(helpers.display_time(remaining_secs))
                    embed.set_field_at(0, name=contrib_str, value="Reward: {} credits\nTime Length: {}".format(amount, helpers.display_time(remaining_secs)),  inline=True)
                    await message.edit(embed=embed)
                # print("Sleep {}".format(sec))
                # print(sec % 10)
                await asyncio.sleep(1)
                remaining_secs -= 1
            except asyncio.CancelledError:
                print('Process {}: cancel sleep'.format(process_name))
                raise
                return
        after_react_message = await channel.fetch_message(message.id)
        members = await after_react_message.reactions[0].users().flatten()
        bot_index = members.index(bot.user)
        members.pop(bot_index)
        if len(members) > 0:
            winner = random.choice(members)
            await helpers.withdraw_money(bot.user, message.guild, amount)
            failed = await helpers.add_money(winner, message.guild, amount)
            if not failed:
                new_embed = discord.Embed(
                    colour=discord.Colour(0x95A5A6),
                    title="<a:HyperTada:611922514591088652>**LOTTERY EVENT ENDED**<a:HyperTada:611922514591088652>"
                )
                new_embed.add_field(name='\u200b',
                                    value="Winner: {}\nReward: {} credits".format(winner.mention, amount), inline=True)
                await after_react_message.edit(embed=new_embed)
                await after_react_message.channel.send(
                    "Congratulations {} you won {} credits!".format(winner.mention, amount))
                return
            else:
                await after_react_message.channel.send(f"Transaction Failed: {winner.mention} has too many Credits!")
        else:
            await after_react_message.channel.send('No users reacted to this event! Terminating lottery...')
            return

    @staticmethod
    async def giveaway_pick(bot, sponsor, channel, prize, time_secs, answer, num, process_name):
        embed = discord.Embed(
            colour=discord.Colour(0x95A5A6),
            title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT**<a:HyperTada:611922514591088652>"
        )
        if answer:
            contrib_str = "*Contributor Only*"
        else:
            contrib_str = '\u200b'
        embed.add_field(name=contrib_str,
                        value="Sponsor: {}\nReward: {}\nTime Length: {}".format(sponsor.mention, prize,
                                                                                helpers.display_time(time_secs)), inline=True)
        embed.set_footer(text=embed_footer)
        message = await channel.send(embed=embed)
        await message.add_reaction('🎁')
        print(message.content)
        print(process_name)
        remaining_secs = time_secs
        for sec in range(time_secs):
            try:
                if (sec % 10) == 0:
                    print(helpers.display_time(remaining_secs))
                    embed.set_field_at(0, name=contrib_str, value="Sponsor: {}\nReward: {}\nTime Length: {}".format(sponsor.mention, prize,
                                                                                helpers.display_time(remaining_secs)),
                                       inline=True)
                await asyncio.sleep(1)
                remaining_secs -= 1
            except asyncio.CancelledError:
                print('Process {}: cancel sleep'.format(process_name))
                raise
                return
        after_react_message = await channel.fetch_message(message.id)
        members = await after_react_message.reactions[0].users().flatten()
        bot_index = members.index(bot.user)
        members.pop(bot_index)
        if num > 1:
            if len(members) >= num:
                winners = ""
                for i in range(num):
                    if i == (num - 1):
                        winner = random.choice(members)
                        winners += "and {}".format(winner.mention)
                        index = members.index(winner)
                        members.pop(index)
                    else:
                        winner = random.choice(members)
                        winners += "{}, ".format(winner.mention)
                        index = members.index(winner)
                        members.pop(index)
                new_embed = discord.Embed(
                    colour=discord.Colour(0x95A5A6),
                    title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT ENDED**<a:HyperTada:611922514591088652>"
                )
                new_embed.add_field(name='\u200b',
                                    value="Sponsor: {}\nReward: {}\nWinners: {}".format(sponsor.mention,
                                                                                        prize, winners), inline=True)
                await after_react_message.edit(embed=new_embed)
                await after_react_message.channel.send(
                    "Congratulations to {}!\nYou all won: {}!\nPlease contact {} for your prize!".format(winners, prize,
                                                                                                         sponsor.mention))
                return
            else:
                await after_react_message.channel.send(
                    'Not enough users reacted to this event! Terminating giveaway...')
        else:
            if len(members) > 0:
                winner = random.choice(members)
                new_embed = discord.Embed(
                    colour=discord.Colour(0x95A5A6),
                    title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT ENDED**<a:HyperTada:611922514591088652>"
                )
                new_embed.add_field(name='\u200b',
                                    value="Sponsor: {}\nReward: {}\nWinner: {}".format(sponsor.mention, prize,
                                                                                       winner.mention), inline=True)
                await after_react_message.edit(embed=new_embed)
                await after_react_message.channel.send(
                    "Congratulations {} you won: {}!\nPlease contact {} for your prize!".format(winner.mention, prize,
                                                                                                sponsor.mention))
                return
            else:
                await after_react_message.channel.send('No users reacted to this event! Terminating giveaway...')
                return

    @helpers.has_higher_role(True, ModRole)
    @c.group()
    async def lottery(self, ctx):
        """Start a lottery event.
        Example: $lottery
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:

            answer = False

            randomname = self.randomString()

            await ctx.channel.send("Preparing to start a Lottery Event!")

            await asyncio.sleep(2)

            await ctx.channel.send("Please Specify the winning amount.")

            def amount_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                amount_msg = await self.bot.wait_for('message', timeout=60.0, check=amount_check)
                amount = int(amount_msg.content.replace(" ", ""))
                if not await helpers.enough_money(self.bot.user, ctx.message.guild, amount):
                    await ctx.channel.send(
                        "{} does not have enough funds for this!\nPlease run this command again!".format(
                            self.bot.user.mention))
                    return
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please specify a channel to host the event.")

            def channel_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                channel_msg = await self.bot.wait_for('message', timeout=60.0, check=channel_check)
                channel_id = int(
                    channel_msg.content.replace("<", "").replace(">", "").replace("#", "").replace("!", ""))
                post_channel = self.bot.get_channel(channel_id)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please specify how long the event will last! Examples: (10s, 15m, 20h, 25d)")

            def time_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                time_msg = await self.bot.wait_for('message', timeout=60.0, check=time_check)
                if "s" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("s", ""))
                if "m" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("m", "")) * 60
                elif "h" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("h", "")) * 60 * 60
                elif "d" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("d", "")) * 60 * 60 * 24
                print(wait_time)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Is this event for contributor/donator/special role?.")

            def special_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel and m.content.lower() in (
                    "y", "yes", "n", "no")

            try:
                special_msg = await self.bot.wait_for('message', timeout=60.0, check=special_check)
                response = special_msg.content.lower()

                if response in ("y", "yes"):
                    answer = True
                else:
                    answer = False
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Lottery Event has been created!")

            globals()[randomname] = self.bot.loop.create_task(self.lottery_pick(self.bot, post_channel, amount, wait_time, answer, randomname))
            # task.set_name(message.id)
            # print(self.bot.loop.get_task())

    @lottery.command()
    async def cancel(self, ctx, process_name: str):
        """Cancels a Specified Lottery.
        Example: $lottery cancel <lottery-name>"""
        globals()[process_name].cancel()
        await ctx.send("Lottery {} Cancelled!".format(process_name))

    @lottery.command()
    async def reroll(self, ctx, *args):
        """Rerolls winner of lottery.
        Example: $lottery reroll <message-id>"""
        #print(type(self))
        #print(type(ctx))
        #print(type(args))
        if len(args) < 1:
            ctx.send("Please Specify a MessageID")
        else:
            try:
                #channel_id = int(args[1].replace("<", "").replace(">", "").replace("#", "").replace("!", ""))
                #print(type(channel_id))
                #post_channel = self.bot.get_channel(channel_id)
                #print(type(post_channel))
                message_id = int(args[0].replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                #print(type(message_id))
                message = await self.bot.fetch_message(message_id)
                #print(type(message))
            except Exception as e:
                await ctx.send("Cannot find message!")
                print(e)
                return
        if message is None:
            await ctx.send("Cannot find message!")
            return
        else:
            members = await message.reactions[0].users().flatten()
            bot_index = members.index(self.bot.user)
            members.pop(bot_index)
            value_strs = message.embeds[0].fields[0].value.split("\n")
            amount = int(value_strs[0].split()[1])
            if len(members) > 0:
                winner = random.choice(members)
                await helpers.withdraw_money(bot.user, message.guild, amount)
                failed = await helpers.add_money(winner, message.guild, amount)
                if not failed:
                    new_embed = discord.Embed(
                        colour=discord.Colour(0x95A5A6),
                        title="<a:HyperTada:611922514591088652>**LOTTERY EVENT ENDED**<a:HyperTada:611922514591088652>"
                    )
                    new_embed.add_field(name='\u200b',
                                        value="Winner: {}\nReward: {} credits".format(winner.mention, amount),
                                        inline=True)
                    await message.edit(embed=new_embed)
                    await message.channel.send(
                        "Congratulations {} you won {} credits!".format(winner.mention, amount))
                    return
                else:
                    await message.channel.send(
                        f"Transaction Failed: {winner.mention} has too many Credits!")
            else:
                await message.channel.send('No users reacted to this event! Terminating lottery...')
                return

    @helpers.has_higher_role(True, ModRole)
    @c.group(pass_context=True, no_pm=True, name='giveaway', aliases=['ga', 'give', 'giveaways'])
    async def giveaway(self, ctx):
        """Starts a giveaway event.
        Example: $giveaway
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:

            answer = False

            await ctx.channel.send("Preparing to start a Giveaway Event!")

            await asyncio.sleep(2)

            await ctx.channel.send("Please Specify the winning prize.")

            def prize_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                prize_msg = await self.bot.wait_for('message', timeout=60.0, check=prize_check)
                prize = prize_msg.content
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please Specify the amount of winners. LIMIT: 15")

            def winners_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                winners_msg = await self.bot.wait_for('message', timeout=60.0, check=winners_check)
                winners = int(winners_msg.content)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please specify a channel to host the event.")

            def channel_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                channel_msg = await self.bot.wait_for('message', timeout=60.0, check=channel_check)
                channel_id = int(
                    channel_msg.content.replace("<", "").replace(">", "").replace("#", "").replace("!", ""))
                post_channel = self.bot.get_channel(channel_id)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please specify a user to sponsor the event.")

            def sponsor_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                sponsor_msg = await self.bot.wait_for('message', timeout=60.0, check=sponsor_check)
                sponsor_id = int(
                    sponsor_msg.content.replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                sponsor = discord.utils.get(ctx.guild.members, id=sponsor_id)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Please specify how long the event will last! Examples: (10s, 15m, 20h, 25d)")

            def time_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                time_msg = await self.bot.wait_for('message', timeout=60.0, check=time_check)
                if "s" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("s", ""))
                if "m" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("m", "")) * 60
                elif "h" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("h", "")) * 60 * 60
                elif "d" in time_msg.content.lower():
                    wait_time = int(time_msg.content.lower().replace(" ", "").replace("d", "")) * 60 * 60 * 24
                print(wait_time)
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Is this event for contributor/donator/special role?.")

            def special_check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel and m.content.lower() in (
                    "y", "yes", "n", "no")

            try:
                special_msg = await self.bot.wait_for('message', timeout=60.0, check=special_check)
                response = special_msg.content.lower()

                if response in ("y", "yes"):
                    answer = True
                else:
                    answer = False
            except asyncio.TimeoutError:
                await ctx.channel.send('This Process has timed out. Please Run the command again')
                return

            await ctx.channel.send("Giveaway Event has been created!")
            self.bot.loop.create_task(
                self.giveaway_pick(self.bot, sponsor, post_channel, prize, wait_time, answer, winners))

    @giveaway.command()
    async def reroll(self, ctx, *args):
        """Rerolls Winners for Giveaway.
        Example: $giveaway reroll <message-id> <@user1> <@user2> etc."""
        if len(args) < 1:
            ctx.send("Please Specify a MessageID")
        else:
            try:
                message_id = int(args[0].replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                message = await ctx.fetch_message(message_id)
            except Exception as e:
                await ctx.send("Cannot find message!", e)
                return
        if message is None:
            await ctx.send("Cannot find message!")
            return
        else:
            members = await message.reactions[0].users().flatten()
            bot_index = members.index(self.bot.user)
            members.pop(bot_index)
            if len(args[1:]) >= 1:
                for arg in args[1:]:
                    usr_id = int(arg.replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                    user = discord.utils.get(ctx.guild.members, id=usr_id)
                    index = members.index(user)
                    members.pop(index)
                if len(members) >= len(args[1:]):
                    winners = ""
                    for i in range(len(args[1:])):
                        if i == (len(args[1:]) - 1):
                            winner = random.choice(members)
                            winners += "and {}".format(winner.mention)
                            index = members.index(winner)
                            members.pop(index)
                        else:
                            winner = random.choice(members)
                            winners += "{}, ".format(winner.mention)
                            index = members.index(winner)
                            members.pop(index)
                    value_strs = message.embeds[0].fields[0].value.split("\n")
                    sponsor_str = value_strs[0]
                    sponsor_id = int(
                        sponsor_str.split()[1].replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                    sponsor = discord.utils.get(ctx.guild.members, id=sponsor_id)
                    winner_str = value_strs[2].split()[0]
                    prize_str = value_strs[1]
                    prize = prize_str.split()[1]
                    new_embed = discord.Embed(
                        colour=discord.Colour(0x95A5A6),
                        title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT ENDED**<a:HyperTada:611922514591088652>"
                    )
                    new_embed.add_field(name='\u200b',
                                        value="{}\n{}\n{} {}".format(sponsor_str, prize_str, winner_str,
                                                                     winner.mention), inline=True)
                    await message.edit(embed=new_embed)
                    await message.channel.send(
                        "Congratulations to {}!\nYou all won: {}!\nPlease contact {} for your prize!".format(winners,
                                                                                                             prize,
                                                                                                             sponsor.mention))
                    return
                else:
                    new_embed = discord.Embed(
                        colour=discord.Colour(0x95A5A6),
                        title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT CANCELLED**<a:HyperTada:611922514591088652>"
                    )
                    await message.edit(embed=new_embed)
                    await message.channel.send('Not enough users reacted to this event! Terminating giveaway...')
            else:
                if len(members) >= 1:
                    winner = random.choice(members)
                    value_strs = message.embeds[0].fields[0].value.split("\n")
                    sponsor_str = value_strs[0]
                    sponsor_id = int(
                        sponsor_str.split()[1].replace("<", "").replace(">", "").replace("@", "").replace("!", ""))
                    sponsor = discord.utils.get(ctx.guild.members, id=sponsor_id)
                    prize_str = value_strs[1]
                    prize = prize_str.split()[1]
                    winner_str = value_strs[2].split()[0]
                    new_embed = discord.Embed(
                        colour=discord.Colour(0x95A5A6),
                        title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT ENDED**<a:HyperTada:611922514591088652>"
                    )
                    new_embed.add_field(name='\u200b',
                                        value="{}\n{}\n{} {}".format(sponsor_str, prize_str, winner_str,
                                                                     winner.mention), inline=True)
                    await message.edit(embed=new_embed)
                    await message.channel.send(
                        "Congratulations {} you won: {}!\nPlease contact {} for your prize!".format(winner.mention,
                                                                                                    prize,
                                                                                                    sponsor.mention))
                    return
                else:
                    new_embed = discord.Embed(
                        colour=discord.Colour(0x95A5A6),
                        title="<a:HyperTada:611922514591088652>**GIVEAWAY EVENT CANCELLED**<a:HyperTada:611922514591088652>"
                    )
                    await message.edit(embed=new_embed)
                    await message.channel.send('No users reacted to this event! Terminating giveaway...')
                    return


def setup(bot):
    bot.add_cog(Giveaways(bot))
