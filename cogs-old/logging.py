from main import *

with open("./config/tokens.json") as tkn:
    keys = json.load(tkn)

with open("./config/config.json") as cfg:
    config = json.load(cfg)


class Logging(c.Cog):

    def __init__(self, bot):
        self.bot = bot

    @c.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return
        else:
            await self.log_messages(message)

    @staticmethod
    async def log_messages(message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        id = message.guild.id
        sql = 'INSERT INTO discord_data.message_log ("servid", "channel", "channelid", "timestamp", "username", "id", "message")' + \
              " VALUES ($1, $2, $3, $4, $5, $6, $7)"
        await helpers.transaction_postgresDatabase(sql, id, message.channel.name, message.channel.id, timestamp, message.author.name, message.author.id, message.content)


def setup(bot):
    bot.add_cog(Logging(bot))
