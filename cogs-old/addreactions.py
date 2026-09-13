from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Reactions Config Loaded")
except Exception:
    config = {}
    print("Reactions Config Not Created, Using Temporary Storage.")


def getReactionChannels(dict):
    return list(dict.keys())


class Addreactions(c.Cog):
    def __init__(self, bot):
        self.bot = bot

    @c.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return
        if str(message.channel.id) in getReactionChannels(config["autoreaction_keywords"]):
            for keyword in config["autoreaction_keywords"][str(message.channel.id)]:
                if not isinstance(keyword, list):
                    if keyword.lower() in str(message.content).lower():
                        for reaction in config["autoreaction_emojis"][str(message.channel.id)]:
                            if not isinstance(reaction, list):
                                await message.add_reaction(str(reaction))
                elif isinstance(keyword, list):
                    for sec_keyword in keyword:
                        if sec_keyword.lower() in str(message.content).lower():
                            for reaction in config["autoreaction_emojis"][str(message.channel.id)]:
                                if isinstance(reaction, list):
                                    for sec_reaction in reaction:
                                        await message.add_reaction(str(sec_reaction))

    @helpers.is_creator()
    @c.command()
    async def addreactions(self, channel: discord.TextChannel, *, content):
        print(channel.name)


def setup(bot):
    bot.add_cog(Addreactions(bot))
