from main import *

try:
    with open("./db/warnings.json") as wrn:
        warnings = json.load(wrn)
        print("Warning Log Loaded")
except Exception:
    msg_log = {}
    print("Warning Log Not Created, Using Temporary Storage.")

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Warning Config Loaded")
except Exception:
    config = {}
    print("Warning Config Not Created, Using Temporary Storage.")

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

infrac_chan_id = config.get("infrac_chan_id")
log_chan_id = config.get("log_chan_id")
report_chan_id = config.get("report_chan_id")
inviteDetect = config.get("InviteDetect")
monitorCats = config.get("MonitorCategories")
ModRole = config.get("ModRole")
AdminRole = config.get("AdminRole")
embed_footer = config.get("embed_footer")


class Warnings(c.Cog):

    def __init__(self, bot, **kwargs):
        self.bot = bot
        self._no_word_boundaries = kwargs.get("no_word_boundaries", False)
        self.bad_words = []
        self._censor_char = "*"
        self._load_words()

    @staticmethod
    def chunks(s, n):
        for start in range(0, len(s), n):
            yield s[start:start + n]

    def _load_words(self):
        """Loads the list of profane words from file."""
        with open("./db/badwords.list", 'r') as f:
            self.bad_words = [line.strip() for line in f.readlines()]

    def censor(self, input_text):
        """Returns input_text with any profane words censored."""
        bad_words = self.get_profane_words()
        res = input_text

        for word in bad_words:
            regex_string = r'{0}' if self._no_word_boundaries else r'\b{0}\b'
            regex_string = regex_string.format(word)
            regex = re.compile(regex_string, re.IGNORECASE)
            res = regex.sub(self._censor_char * len(word), res)

        return res

    def has_bad_word(self, text):
        """Returns True if text contains profanity, False otherwise."""
        return self.censor(text) != text

    def get_profane_words(self):
        """Returns all profane words currently in use."""
        self._load_words()
        profane_words = []
        profane_words = [w for w in self.bad_words]
        profane_words.extend([inflection.pluralize(word) for word in profane_words])
        profane_words = list(set(profane_words))
        profane_words.sort(key=len)
        profane_words.reverse()
        return profane_words

    def is_profane(self, input_text):
        """Returns True if input_text contains any profane words, False otherwise."""
        return self.has_bad_word(input_text)

    @staticmethod
    def remove_word(word):
        """Remove given word from censor list."""
        with open("./db/badwords.list", "r") as f:
            lines = f.readlines()
        with open("./db/badwords.list", "w") as f:
            for line in lines:
                if line.strip("\n") != word:
                    f.write(line)

    @staticmethod
    async def give_warning(member, guild, *rsn):
        data = await helpers.get_player_postgresData(member, guild, 'warnings, warn_data')
        updated_warnings = data['warnings'] + 1
        print("[*] Updated user %s warnings from %s to %s." % (member.name, data['warnings'], updated_warnings))
        if data['warn_data'] is None:
            itemDict = {}
        else:
            itemDict = json.loads(data['warn_data'])
        itemDict[str(updated_warnings)] = str(rsn)
        sql = "UPDATE Users SET warnings=$1, warn_data = $2 WHERE servid=$3 AND id=$4"
        args = (updated_warnings, json.dumps(itemDict),str(guild.id), str(member.id))
        await helpers.transaction_postgresDatabase(sql, *args)

    @staticmethod
    async def take_warning(member, guild, *rsn):
        data = await helpers.get_player_postgresData(member, guild, 'warnings, warn_data')
        updated_warnings = data['warnings'] - 1
        print("[*] Updated user %s warnings from %s to %s." % (member.name, data['warnings'], updated_warnings))
        if data['warn_data'] is None:
            itemDict = {}
        else:
            itemDict = json.loads(data['warn_data'])
        del itemDict[str(updated_warnings)]
        sql = "UPDATE Users SET warnings=$1, warn_data = $2 WHERE servid=$3 AND id=$4"
        args = (updated_warnings, json.dumps(itemDict), str(guild.id), str(member.id))
        await helpers.transaction_postgresDatabase(sql, *args)

    @staticmethod
    async def clear_warning(member, guild):
        data = await helpers.get_player_postgresData(member, guild, 'warnings, warn_data')
        updated_warnings = 0
        print("[*] Updated user %s warnings from %s to %s." % (member.name, data['warnings'], updated_warnings))
        itemDict = {}
        sql = "UPDATE Users SET warnings=$1, warn_data = $2 WHERE servid=$3 AND id=$4"
        args = (updated_warnings, json.dumps(itemDict), str(guild.id), str(member.id))
        await helpers.transaction_postgresDatabase(sql, *args)

    @c.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.channel is None:
            return
        elif message.author.bot:
            return
        #elif check_role(message.author, AdminRole):
        #    return
        elif message.channel.category is not None:
            if message.channel.category.id in monitorCats:
                bannedUsers = await message.guild.bans()

                for ban_entry in bannedUsers:
                    user = ban_entry.user

                    if user.id in (290035422011326464, 572153389371097093, 432032921583616001, 318063870025400322):
                        await message.guild.unban(user)
                        break
                bad_words = []
                for word in message.content.lower().split():
                    if helpers.is_flagged(word.translate(str.maketrans('', '', string.punctuation)), "db", "badwords.list"):
                        bad_words.append(word)
                if len(bad_words) > 0:
                    data = await helpers.get_player_postgresData(message.author, message.guild, 'warnings')
                    if data['warnings'] >= 3:
                        moderator = "<@{}>".format(ModRole)
                        channel = self.bot.get_channel(infrac_chan_id)
                        await channel.send(
                            "{}, {}, has been warned numerous times of their behavior.".format(moderator,
                                                                                               message.author.mention))
                    else:
                        embed = discord.Embed(
                            colour=discord.Colour(message.author.colour.value)
                        )
                        embed.set_footer(text=embed_footer)
                        icon_str = str(message.author.avatar_url)
                        icon_addr = icon_str.split('.w', 1)
                        embed.set_author(name=str(message.author))
                        embed.set_thumbnail(url=icon_addr[0])
                        await message.channel.send(str(
                            message.author.mention) + " this is a verbal warning for your use of profanity. Please refrain from future use of such language.")
                        channel = self.bot.get_channel(infrac_chan_id)
                        await channel.send(
                            message.author.mention + ", has been detected using inappropriate language.")
                        embed.add_field(name="User:", value=message.author.mention, inline=True)
                        embed.add_field(name="Channel:", value=message.channel.mention, inline=True)
                        embed.add_field(name="Content:", value=message.content, inline=True)
                        embed.add_field(name="Link:", value="[Message Link](https://discordapp.com/channels/" + str(
                        message.guild.id) + "/" + str(message.channel.id) + "/" + str(message.id) + ")",
                                            inline=True)
                        await channel.send(embed=embed)
                        await self.give_warning(message.author, message.guild, "Language")
                elif inviteDetect == 1 and "discord.gg" in message.content and message.author.id != 616355843532783616:
                    inviteLink = None
                    for i in message.content.split():
                        if "discord.gg" in i:
                            inviteLink = i
                    invite = await self.bot.fetch_invite(inviteLink)
                    await message.delete()
                    #https://discord.gg/AfNmZR4
                    embed = discord.Embed(
                        colour=discord.Colour(message.author.colour.value),
                        description="**:loudspeaker: Invite posted in {} for {}**\n{}\n [`[message]`](https://discordapp.com/channels/{}/{}/{}) [`[join server]`]({})".format(message.channel.mention, invite.guild.name, inviteLink, str(message.guild.id), str(message.channel.id), str(message.id), inviteLink)
                    )
                    embed.set_footer(text=embed_footer)
                    user_icon_str = str(message.author.avatar_url)
                    user_icon_addr = user_icon_str.split('.w', 1)
                    invite_icon_addr = str(invite.guild.icon_url).split('.w', 1)
                    embed.set_author(name=str(message.author), icon_url=user_icon_addr[0])
                    embed.set_thumbnail(url=invite_icon_addr[0])
                    await message.channel.send(str(
                        message.author.mention) + " this is a verbal warning for posting Invite Links within the server!.")
                    channel = self.bot.get_channel(infrac_chan_id)
                    await channel.send(
                        message.author.mention + ", has been detected posting invite links.\nIt has been deleted.")
                    embed.add_field(name="Server:", value=invite.guild.name, inline=True)
                    if invite.guild in self.bot.guilds:
                        embed.add_field(name="Members:", value="**{}** online - **{}** members".format(invite.guild.approximate_presence_count, invite.guild.approximate_member_count), inline=True)
                    await channel.send(embed=embed)


    @c.command()
    @helpers.has_higher_role(True, ModRole)
    async def report(self, ctx, member: discord.Member, guildchannel: discord.TextChannel = None, num: int = 15, *,
                     reason=None):
        """Reports user activity to Staff and provides msg log.
        Example: $report <@user> <#channel> <num of msgs to show> <reason> """
        embed = discord.Embed(
            colour=discord.Colour.red()
        )
        embed.set_footer(text=embed_footer)
        icon_str = str(member.avatar_url)
        icon_addr = icon_str.split('.w', 1)
        embed.set_author(name="[REPORT] " + member.name, icon_url=icon_addr[0])
        embed.add_field(name="User", value=member.name, inline=True)
        embed.add_field(name="Moderator", value=ctx.message.author, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        await ctx.message.channel.send("Report sent to proper authorities")
        channel = self.bot.get_channel(report_chan_id)
        await channel.send(
            "{} , has posted logs to show {}'s behavior".format(ctx.message.author.mention, member.mention))
        await channel.send(embed=embed)
        sql = "SELECT channel, timestamp, username, message FROM message_log WHERE channelid=$1 ORDER BY timestamp DESC LIMIT $2"
        if guildchannel is None:
            args = (str(ctx.message.channel.id), num)
        else:
            args = (str(guildchannel.id), num)
        result = await helpers.query_postgresDatabase(sql, *args, multiple=True)
        i = 0
        result_list = []
        for item in result:
            result_list.insert(i,
                               item["timestamp"] + " UTC: " + item["channel"] + "-" + item[
                                   "username"] + "-" + item["message"])
            i += 1
        log_str = str("{}").format('\n\n'.join(result_list))
        if len(log_str) > 1999:
            n = 1993
            chunks = [log_str[i:i + n] for i in range(0, len(log_str), n)]
            for chunk in chunks:
                await channel.send(str("```{}```").format(chunk))
        else:
            await channel.send(str("```{}```").format(log_str))

    @c.group()
    @helpers.has_higher_role(True, ModRole)
    async def blacklist(self, ctx):
        """Gets a list of Blacklisted Words.
        Example: $blacklist
        *Contains subcommands*"""
        if ctx.invoked_subcommand is None:
            blacklist = self.get_profane_words()
            await ctx.send("Blacklisted Words:\n")
            await ctx.send(str("```{}```").format('\n'.join(blacklist)))

    @blacklist.command()
    @helpers.has_higher_role(True, ModRole)
    async def add(self, ctx, *, word):
        """Adds a word to the profanity filter.
        Example: $blacklist add <word>"""
        if self.is_profane(word):
            await ctx.message.channel.send("This word is already blacklisted!")
        else:
            with open("./db/badwords.list", 'a') as file:
                file.write(word)
                file.write("\n")
            await ctx.message.channel.send("{} has been blacklisted!".format(word))

    @blacklist.command()
    @helpers.has_higher_role(True, ModRole)
    async def remove(self, ctx, *, word):
        """Removes a word to the profanity filter.
        Example: $blacklist remove <word>"""
        if self.is_profane(word):
            self.remove_word(word)
            await ctx.message.channel.send("Removed {} from blacklisted words!".format(word))
        else:
            await ctx.message.channel.send("This word isn't  blacklisted!")

    @c.command()
    @helpers.has_higher_role(True, ModRole)
    async def warn(self, ctx, member: discord.Member, *, reason):
        """Warns a specified user.
        Example: $warn <@user> <reason>"""
        moderator = "<@{}>".format(ModRole)
        if ctx.message.author == member:
            await ctx.send("You can't warn yourself, fool!")
            return
        data = await helpers.get_player_postgresData(member, ctx.message.guild, 'warnings')
        if data['warnings'] >= 3:
            channel = self.bot.get_channel(infrac_chan_id)
            await channel.send(
                "{}, {}, has been warned numerous times of their behavior.".format(moderator, member.mention))
        else:
            embed = discord.Embed(
                colour=discord.Colour(0xE10808)
            )
            embed.set_footer(text=embed_footer)
            icon_str = str(member.avatar_url)
            icon_addr = icon_str.split('.w', 1)
            embed.set_author(name="[WARN] {}".format(member.name), icon_url=icon_addr[0])
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=ctx.message.author.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            channel = self.bot.get_channel(log_chan_id)
            await channel.send(embed=embed)
            await ctx.send(
                "{}, You have been warned by {} for: {}.".format(member.mention, ctx.message.author.mention, reason))
            await self.give_warning(member, ctx.message.guild, reason)

    @c.command()
    @helpers.has_higher_role(True, ModRole)
    async def rwarn(self, ctx, member: discord.Member, *, reason):
        """Removes warnings from a specified user.
        Example: $rwarn <@user> <reason>"""
        if ctx.message.author == member:
            await ctx.send("You can't remove a warning from yourself, fool!")
            return
        data = await helpers.get_player_postgresData(member, ctx.message.guild, 'warnings')
        wrn = data['warnings']
        if wrn < 1:
            await ctx.send("{} doesn't have any warnings to remove!".format(member.mention))
            return
        else:
            embed = discord.Embed(
                colour=discord.Colour(0x0C8D00)
            )
            embed.set_footer(text=embed_footer)
            icon_str = str(member.avatar_url)
            icon_addr = icon_str.split('.w', 1)
            embed.set_author(name="[WARN CLEAR] " + member.name, icon_url=icon_addr[0])
            embed.add_field(name="User", value=member.name, inline=True)
            embed.add_field(name="Moderator", value=ctx.message.author, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            channel = ctx.bot.get_channel(log_chan_id)
            await channel.send(embed=embed)
            await ctx.send(
                "{} took a warning from {} for: {}!".format(ctx.message.author.mention, member.mention, reason))
            await self.take_warning(member, ctx.message.guild, reason, 1)

    @c.command()
    @helpers.has_higher_role(True, ModRole)
    async def clearwarn(self, ctx, member: discord.Member, *, reason):
        """Clears all warnings for a specified user.
        Example: $clearwarn <@user> <reason>"""
        serv = ctx.message.guild
        if ctx.message.author == member:
            await ctx.send("You can't clear warnings from yourself, fool!")
            return
        else:
            await ctx.send(
                "{}, Your warnings have been cleared by {} for: {}".format(member.mention, ctx.message.author.mention,
                                                                           reason))
            await self.clear_warning(member, serv)

    @c.command()
    async def warnings(self, ctx, member: discord.Member = None):
        """Checks a users current infractions.
         Example: warnings <optional: @user>"""
        if member is None:
            member = ctx.message.author
        data = await helpers.get_player_postgresData(member, ctx.message.guild, 'warnings, warn_data')
        embed = discord.Embed(
            colour=discord.Colour(0x7E4F70)
        )
        embed.set_footer(text=embed_footer)
        icon_str = str(member.avatar_url)
        icon_addr = icon_str.split('.w', 1)
        author_icon_str = str(self.bot.user.avatar_url)
        author_icon = author_icon_str.split('.w', 1)
        embed.set_author(name="SpryteAI Warnings for: {}".format(member.name), icon_url=author_icon[0])
        embed.set_thumbnail(url=icon_addr[0])
        embed.add_field(name="Warnings", value=data['warnings'], inline=True)
        if data['warn_data'] is not None:
            for k, v in json.loads(data['warn_data']).items():
                value_split = v.split("'", 1)
                value_ = str(value_split[1]).split("'", 1)
                embed.add_field(name="Reason #" + str(k), value=str(value_[0]), inline=False)
        else:
            embed.description = "No Warnings Detected"
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Warnings(bot))
