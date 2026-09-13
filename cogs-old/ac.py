from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Config Config Loaded")
except Exception:
    config = {}
    print("Config Config Not Created, Using Temporary Storage.")

try:
    with open("./db/queue.json") as cfg:
        groups = json.load(cfg)
        print("Invites Config Loaded")
except Exception:
    groups = {}
    print("Invites Config Not Created, Using Temporary Storage.")

queue_hub_id = config.get("queue_hub_id")
queue_post_hub_id = config.get("queue_post_hub_id")
queue_post_chan_id = config.get("queue_post_chan_id")
embed_footer = config.get("embed_footer")


class Queue:

    _instances = set()

    def __init__(self, bot, rating, message, postMessage, name, group_size, number_of_groups):
        self.bot = bot
        self.name = name
        self._instances.add(weakref.ref(self))
        self.host = message.author
        self.rating = rating
        self.group_size = int(group_size)
        self.number_of_groups = int(number_of_groups)
        self.user_limit = int(group_size) * int(number_of_groups)
        # createQueueEntry(queuename, groups)
        self.queue_message_id = str(postMessage.id)
        self.user_queue = groups[self.queue_message_id][self.name]["users"]
        self.queue_items = groups[self.queue_message_id][self.name]["items"]
        self.total_users = 0
        self.queue_full = False
        self.start_queue(self.bot)

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

    @staticmethod
    def get_rating(rating):
        im = Image.open("./assets/5stars.png").convert('RGBA')
        max_rating = 5.0
        percentage = (rating / max_rating)
        width, height = im.size
        im.crop((0, 0, int(width * percentage), height))
        im.save('./assets/temp_stars.png')

    def get_queue_message_id(self):
        return self.queue_message_id

    # Creates the embed to send as a message for the queue
    def get_queue_message_embed(self, bot):
        file = None
        for a, b in groups[self.queue_message_id][self.name]["items"].items():
            description = "{}: {} ea".format(a.title(), b)
        entry_fee = groups[self.queue_message_id][self.name]["entry_fee"]
        if entry_fee is not None:
            description += "\nEntry Fee: {} bells".format(entry_fee)
        embed = discord.Embed(title="Session `{}`\nHosted by: {}".format(self.name, self.host), description=description,
                              colour=discord.Colour.from_rgb(121, 219, 233))
        print(self.rating)
        if self.rating > 0:
            self.get_rating(self.rating)
            file = discord.File(
                "./assets/temp_stars.png",
                filename="temp_stars.png")
            embed.set_thumbnail(
                url="attachment://temp_stars.png")
        embed.add_field(name="Queue Info", value=self.get_queue_info())
        if len(self.user_queue) < 1:
            userList = []
        else:
            userList = ''
            for user_id in self.user_queue:
                user = bot.get_user(user_id)
                userList += "{}\n".format(user.name)
        embed.add_field(name="Users", value=userList)
        return embed, file

    # Sets the message id for later use (changing queue statuses/ending queue
    def set_queue_message_id(self, message):
        self.queue_message_id = str(message.id)

    def start_queue(self, bot):
        return self.get_queue_message_embed(bot)

    def end_queue(self):
        pass

    async def add_user(self, user):
        if not self.queue_full:
            self.user_queue.append(user)
            groups[self.queue_message_id][self.name]["users"] = self.user_queue
            await helpers.update_json("db", groups, "queue")
            self.total_users += 1
        if self.user_limit == self.total_users:
            self.queue_full = True

    async def remove_user(self, user):
        if self.total_users > 0:
            self.user_queue.remove(user)
            groups[self.queue_message_id][self.name]["users"] = self.user_queue
            await helpers.update_json("db", groups, "queue")
            self.total_users -= 1
        if self.user_limit != self.total_users:
            self.queue_full = False

    # Sets the groups and returns them in an embed
    def get_groups_embed(self, bot):
        embed = discord.Embed(colour=discord.Colour.from_rgb(121, 219, 233))
        embed.set_author(name="Group Picker")
        if len(self.user_queue) >= 1:
            userID_list = {}
            for x in range(self.number_of_groups):
                temp = []
                userID_list_temp = []
                if len(self.user_queue) >= 1:
                    for n in range(self.group_size):
                        if len(self.user_queue) >= 1:
                            if self.user_queue[0] not in temp:
                                user_id = random.choice(self.user_queue)
                                user = bot.get_user(user_id)
                                userID_list_temp.append(user_id)
                                temp.append(user.name)
                                self.user_queue.remove(user_id)
                        else:
                            break
                else:
                    break
                embed.add_field(name="Group " + str(x + 1), value=temp)
                userID_list[str(x)] = userID_list_temp
        else:
            userID_list = None
            embed.add_field(name="No Users Exist in Queue",
                            value="Please Wait for Users to React.\nIf No Queue Exists Run `{}ac createq` to start a new one.".format_map(
                                helpers.prefix))
        return embed, userID_list

    def get_queue_info(self):
        return "**User Max:** {}\n**Number of Groups:** {}\n**Group Size:** {}\n**Users in Queue:** {}\n**Queue Full:** {}".format(
            self.user_limit, self.number_of_groups, self.group_size, self.total_users, self.queue_full)


def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for a in range(stringLength)).upper()


async def createQueueEntry(queueName, dodoCode, groups, setupMessage, postMessage, price: int, item: str = None, entry_fee: int = None, wait_time: int = None):
    if item is None:
        item = "Turnips"
    if str(postMessage.id) not in groups:
        groups[str(postMessage.id)] = {}
    if queueName not in groups[str(postMessage.id)]:
        groups[str(postMessage.id)][queueName] = {}
    else:
        queueName = randomString()
        groups[str(postMessage.id)][queueName] = {}
    if "users" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["users"] = []
    if "host_id" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["host_id"] = setupMessage.author.id
    if "entry_fee" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["entry_fee"] = entry_fee
    if "wait_time" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["wait_time"] = wait_time
    if "items" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["items"] = {}
    if item not in groups[str(postMessage.id)][queueName]["items"]:
        groups[str(postMessage.id)][queueName]["items"][item] = price
    if "dodoCode" not in groups[str(postMessage.id)][queueName]:
        groups[str(postMessage.id)][queueName]["dodoCode"] = dodoCode
    await helpers.update_json("db", groups, "queue")


async def check_return(self, ctx, channel, check, timeout: int = 60):
    try:
        msg = await self.bot.wait_for('message', timeout=float(int(timeout)), check=check)
        value = msg.content.replace(" ", "").lower()
        return value
    except asyncio.TimeoutError:
        await check_error(self, ctx, channel)
        return None


async def check_error(self, ctx, channel):
    await channel.send("OOF! Sorry! Please rerun the command to restart the process")
    await channel.send("I will now delete this channel...")
    await asyncio.sleep(3)
    await channel.delete()


async def set_rating(member, guild, newRating: int):
    data = await helpers.get_player_postgresData(member, guild, 'acrating')
    rating = data['acrating']
    updated_rating = ((rating * rating) + newRating) / (rating + 1)
    sql = "UPDATE discord_data.users SET acrating=$1 WHERE servid=$2 AND id=$3"
    await helpers.transaction_postgresDatabase(sql, updated_rating, str(guild.id), str(member.id))
    print("[*] Updated user %s rating from %s to %s." % (
        member.name, data['acrating'], updated_rating))


async def start_queue(bot, setupMessage, postMessage, randomString, group_size, number_of_groups, channel, item, itemPrice, entry_fee_value, wait_time, dodoCode):
    is_instance = False
    for obj in Queue.getinstances():
        if obj.name.upper() == randomString.upper():
            is_instance = True
    if not is_instance:
        queueName = randomString
        data = await helpers.get_player_postgresData(setupMessage.author, setupMessage.guild, 'acrating')
        rating = data['acrating']
        globals()[queueName] = Queue(bot, rating, setupMessage, postMessage, randomString, group_size, number_of_groups)
        embed, file = globals()[queueName].get_queue_message_embed(bot)
        if file is not None:
            newMessage = await postMessage.channel.send(content=None, file=file, embed=embed)
        else:
            newMessage = await postMessage.channel.send(content=None, embed=embed)
        await createQueueEntry(queueName, dodoCode, groups, setupMessage, newMessage, itemPrice, item,
                               entry_fee_value, wait_time)
        globals()[queueName].set_queue_message_id(newMessage)
        await newMessage.add_reaction("✅")
        groups.pop(str(postMessage.id), None)
        await helpers.update_json("db", groups, "queue")
        await postMessage.delete()


async def end_queue(message, queueName):
    queueName = queueName.upper()
    if globals()[queueName] is not None:
        groups.pop(str(message.id), None)
        await helpers.update_json("db", groups, "queue")
        await message.delete()
        globals()[queueName] = None
        channel = discord.utils.get(message.guild.channels, name=str(queueName).lower())
        await channel.send("I will now delete the setup channel and queue message...")
        await asyncio.sleep(3)
        await channel.delete()


async def add_user(bot, user, message):
    queueName = list(groups[str(message.id)].keys())[0]
    if user not in globals()[queueName].user_queue:
        await globals()[queueName].add_user(user)
        embed, file = globals()[queueName].get_queue_message_embed(bot)
        await message.edit(content=None, embed=embed)
        return True
    else:
        return False


async def remove_user(bot, user, message):
    queueName = list(groups[str(message.id)].keys())[0]
    if user in globals()[queueName].user_queue:
        await globals()[queueName].remove_user(user)
        embed, file = globals()[queueName].get_queue_message_embed(bot)
        await message.edit(content=None, embed=embed)
        return True
    else:
        return False


async def get_groups(queueName, bot):
    embed, groups = globals()[queueName].get_groups_embed(bot)
    return embed, groups


class AnimalCrossing(c.Cog):

    def __init__(self, bot):
        self.bot = bot

#    @c.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        hub_channel = self.bot.get_channel(queue_post_hub_id)
        channel_id = payload.channel_id
        channel = self.bot.get_channel(channel_id)
        guild_id = payload.guild_id
        guild = self.bot.get_guild(guild_id)
        user_id = payload.user_id
        user = discord.utils.get(guild.members, id=user_id)
        if channel in hub_channel.channels and not user.bot:
            if payload.emoji.name == "✅":
                message = await channel.fetch_message(payload.message_id)
                bot = self.bot
                if not await add_user(self.bot, user.id, message):
                    await user.send("```You can't join a queue if you are already in it!```")

#    @c.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        hub_channel = self.bot.get_channel(queue_post_hub_id)
        channel_id = payload.channel_id
        channel = self.bot.get_channel(channel_id)
        guild_id = payload.guild_id
        guild = self.bot.get_guild(guild_id)
        user_id = payload.user_id
        user = discord.utils.get(guild.members, id=user_id)
        if channel in hub_channel.channels and not user.bot:
            if payload.emoji.name == "✅":
                message = await channel.fetch_message(payload.message_id)
                if not await remove_user(self.bot, user.id, message):
                    await user.send("```You can't leave a queue if you are not in it!```")

    @c.group()
    async def ac(self, ctx):
        """Animal Crossing Command Group
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please Specify a Subcommand")

    @ac.command()
    async def createq(self, ctx):
        """Creates a new AC Queue
        Example: $ac createq"""
        sessionName = randomString()
        overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                      ctx.message.author: discord.PermissionOverwrite(read_messages=True)}
        hub_channel = self.bot.get_channel(queue_hub_id)
        if isinstance(hub_channel, discord.CategoryChannel):
            channel = await hub_channel.create_text_channel(sessionName, overwrites=overwrites)
        else:
            await ctx.send(
                "Queue Hub Category is not Configured! Please use {}config queuehub `catergory id number here` to update this! ")
        await channel.send(
            "Hello, {}! Thank you for using our AC Queue Service!\nThis channel is provided to you to configure your Session to your liking!".format(
                ctx.message.author.mention))
        await asyncio.sleep(2)
        await channel.send("First off, how many users PER GROUP are you willing to host? (Max is 7).")

        def users_per_group(m):
            return m.author == ctx.message.author and m.channel == channel

        group_size = await check_return(self, ctx, channel, users_per_group)
        group_size = int(group_size)
        await channel.send(
            "Ok {} users per group! How many GROUPS are you willing to host? (Max is 20).".format(group_size))

        def groups_total(m):
            return m.author == ctx.message.author and m.channel == channel

        total_groups = await check_return(self, ctx, channel, groups_total)
        total_groups = int(total_groups)
        await channel.send(
            "Ok {} users per group and {} groups making a total of {} users! Is this ok? (Yes or No)".format(group_size,
                                                                                                             total_groups,
                                                                                                             (
                                                                                                                     total_groups * group_size)))

        def total_users_confirm(m):
            return m.author == ctx.message.author and m.channel == channel

        confirm_users = await check_return(self, ctx, channel, total_users_confirm)

        if confirm_users in "yes":

            await channel.send(
                "Ok! What are you selling?")

            def item_check(m):
                return m.author == ctx.message.author and m.channel == channel

            try:
                msg = await self.bot.wait_for('message', timeout=float(int(60)), check=item_check)
                item = msg.content.lower()
            except asyncio.TimeoutError:
                await check_error(self, ctx, channel)
                return None

            if len(item) < 1:
                item = "Turnip"

            await channel.send(
                "Ok! What is your current {} Sell Price?".format(item.title()))

            def item_price_check(m):
                return m.author == ctx.message.author and m.channel == channel

            itemPrice = await check_return(self, ctx, channel, item_price_check)
            itemPrice = int(itemPrice)

            await channel.send(
                "{} Price is set to {} bells. Do you want to charge an Entry Fee?".format(item.title(), itemPrice))

            def entry_fee_check(m):
                return m.author == ctx.message.author and m.channel == channel

            entry_fee = await check_return(self, ctx, channel, entry_fee_check)

            if entry_fee in "yes":

                await channel.send("How much do you want to charge as an Entry Fee?")

                def entry_fee_value_check(m):
                    return m.author == ctx.message.author and m.channel == channel

                entry_fee_value = await check_return(self, ctx, channel, entry_fee_value_check)
                entry_fee_value = int(entry_fee_value)
                await channel.send(
                    "Entry Fee set to {} bells. What is your dodoCode?".format(
                        entry_fee_value))
            else:
                entry_fee_value = None
                await channel.send(
                    "No Entry Fee Set. What is your dodoCode?")

            def dodoCode_check(m):
                return m.author == ctx.message.author and m.channel == channel

            dodoCode = await check_return(self, ctx, channel, dodoCode_check)

            await channel.send("dodoCode set to {}! How long between each group would you like to take a break? ("
                               "Examples: 30s, 5m)".format(dodoCode.upper()))

            def sleep_time_check(m):
                return m.author == ctx.message.author and m.channel == channel

            sleepTime = await check_return(self, ctx, channel, sleep_time_check)
            if "s" in sleepTime.lower():
                wait_time = int(sleepTime.lower().replace(" ", "").replace("s", ""))
            if "m" in sleepTime.lower():
                wait_time = int(sleepTime.lower().replace(" ", "").replace("m", "")) * 60
            elif "h" in sleepTime.lower():
                wait_time = int(sleepTime.lower().replace(" ", "").replace("h", "")) * 60 * 60
            elif "d" in sleepTime.lower():
                wait_time = int(sleepTime.lower().replace(" ", "").replace("d", "")) * 60 * 60 * 24

            await channel.send(
                "{} break is now set!\nAre you ready to begin?".format(helpers.display_time(wait_time)))

            def start_check(m):
                return m.author == ctx.message.author and m.channel == channel

            confirm_start = await check_return(self, ctx, channel, start_check)

            if confirm_start in "yes":
                post_channel = self.bot.get_channel(queue_post_chan_id)
                await channel.send("Starting Session ID: `{}`".format(sessionName.upper()))
                edit_message = await post_channel.send("Starting Session ID: `{}`".format(sessionName.upper()))
                await createQueueEntry(sessionName, dodoCode, groups, ctx.message, edit_message, itemPrice, item, entry_fee_value, wait_time)
                await start_queue(self.bot, ctx.message, edit_message, sessionName, group_size, total_groups,
                                  post_channel, item, itemPrice, entry_fee_value, wait_time, dodoCode)
                await channel.send("Please wait for users to join the queue and type `{}ac startq {}` when you are ready or `{}ac endq {}` when you are finished!.".format(helpers.prefix, sessionName.upper(), helpers.prefix, sessionName.upper()))
            else:
                await check_error(self, ctx, channel)
        else:
            await check_error(self, ctx, channel)

    @ac.command()
    async def startq(self, ctx, queueName: str):
        """Starts specified Queue. Must be the original creator and use channel that was created.
        Example: $ac startq DBDLSDAS"""
        queueName = queueName.upper()
        message_id = globals()[queueName].queue_message_id
        dodoCode = groups[message_id][queueName]["dodoCode"]
        wait_time = groups[message_id][queueName]["wait_time"]
        await ctx.message.delete()
        channel = discord.utils.get(ctx.message.guild.channels, name=str(queueName).lower())
        if ctx.channel.id == channel.id:
            embed, groupList = await get_groups(queueName, self.bot)
            await channel.send(embed=embed)
            await channel.send("Sending DodoCode to Users..")
            for key, value in groupList.items():
                for user_id in value:
                    user_id = int(user_id)
                    user = self.bot.get_user(user_id)
                    await user.send("Please use DodoCode: `{}` to join the island.".format(dodoCode))
                if int(key) == len(groupList) - 1:
                    await channel.send("Last Group! Please type `done` when you are finished.")

                    def done_check(m):
                        return m.author == ctx.message.author and m.channel == channel

                    confirm_done = await check_return(self, ctx, channel, done_check, wait_time)
                    if confirm_done in "done":
                        await channel.send("Waiting for users to rate their experience.")
                        for user_id in value:
                            user_id = int(user_id)
                            user = self.bot.get_user(user_id)
                            await user.send("Please leave a rating of 1 - 5 for {}.".format(ctx.message.author))

                            def rating_check(m):
                                return m.author == user and (int(m.content) in [1, 2, 3, 4, 5])

                            try:
                                msg = await self.bot.wait_for('message', timeout=float(int(20)), check=rating_check)
                                rating = int(msg.content.replace(" ", "").lower())
                            except asyncio.TimeoutError:
                                await user.send("Process Timed Out! Thanks for using our service")
                                rating = None

                            if rating is not None:
                                await set_rating(ctx.message.author, ctx.guild, rating)
                                await user.send("Rating Received! Thanks for using our service")
                        await channel.send("Last Rating Received!.")
                        await channel.send("Thank you for using our AC Queue System!")
                        post_channel = self.bot.get_channel(queue_post_chan_id)
                        message = await post_channel.fetch_message(globals()[queueName].queue_message_id)
                        await end_queue(message, queueName)
                else:
                    await channel.send("Please type `yes` when you are ready for the next group.")

                    def start_check(m):
                        return m.author == ctx.message.author and m.channel == channel

                    confirm_start = await check_return(self, ctx, channel, start_check, wait_time)
                    if confirm_start in "yes":
                        await channel.send("Waiting for users to rate their experience...")
                        for user_id in value:
                            user_id = int(user_id)
                            user = self.bot.get_user(user_id)
                            await user.send("Please leave a rating of 1 - 5 for {}.".format(ctx.message.author))

                            def rating_check(m):
                                return m.author == user and (int(m.content) in [1, 2, 3, 4, 5])

                            try:
                                msg = await self.bot.wait_for('message', timeout=float(int(20)), check=rating_check)
                                rating = int(msg.content.replace(" ", "").lower())
                            except asyncio.TimeoutError:
                                await user.send("Process Timed Out! Thanks for using our service")
                                rating = None

                            if rating is not None:
                                await set_rating(ctx.message.author, ctx.guild, rating)
                                await user.send("Rating Received! Thanks for using our service")
                        await channel.send("Users Rating Received!.")
                        await channel.send("Waiting {} before starting next group.".format(helpers.display_time(wait_time)))
                        await asyncio.sleep(wait_time)
                        await channel.send("Starting next group.")
        else:
            await ctx.message.author.send("You must use the channel specified for queues when starting a queue.")

    @ac.command()
    async def endq(self, ctx, queueName: str):
        """End specified Queue. Must be the original creator and use channel that was created.
        Example: $ac endq DBDLSDAS"""
        queueName = queueName.upper()
        await ctx.message.delete()
        channel = discord.utils.get(ctx.message.guild.channels, name=str(queueName).lower())
        post_channel = self.bot.get_channel(queue_post_chan_id)
        message = await post_channel.fetch_message(globals()[queueName].queue_message_id)
        if ctx.channel.id == channel.id:
            await end_queue(message, queueName)
        else:
            await ctx.message.author.send("You must use the channel specified for queues when ending a queue. "
                                          "For more info use '/help queue'")

    @ac.command()
    async def rating(self, ctx, user: discord.User = None):
        """Check rating of specified user. Leave blank for yourself.
        Example: $ac rating @user"""
        if user is None:
            user = ctx.message.author
        data = await helpers.get_player_postgresData(user, ctx.message.guild, 'acrating')
        rating = data['acrating']
        embed = discord.Embed(
            colour=discord.Colour(0x7E4F70)
        )
        embed.set_footer(text=embed_footer)
        icon_str = str(user.avatar_url)
        icon_addr = icon_str.split('.w', 1)
        embed.set_author(name="SpryteAI Rate Stat for: " + str(user.name), icon_url=icon_addr[0])
        embed.add_field(name="Rating", value=rating, inline=True)
        if rating > 0:
            im = Image.open("./assets/5stars.png").convert('RGBA')
            max_rating = 5.0
            percentage = (rating / max_rating)
            width, height = im.size
            im.crop((0, 0, int(width * percentage), height))
            im.save('./assets/temp_stars.png')
            file = discord.File(
                "./assets/temp_stars.png",
                filename="temp_stars.png")
            embed.set_thumbnail(
                url="attachment://temp_stars.png")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(AnimalCrossing(bot))
