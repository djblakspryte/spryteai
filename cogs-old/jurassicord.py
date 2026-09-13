from main import *

from datetimetest import datetime, timedelta

import requests
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from pathlib import Path
from bs4 import BeautifulSoup
import uuid

with open("./config/config.json") as cfg:
    config = json.load(cfg)
    print("Loaded blakCord Config")

exp_secs = config.get("exp_secs")
contributorrole = config.get("ContributorRole")
embed_footer = config.get("embed_footer")

def randomGenerator(num1, num2):
    #anum = random.randint(num1, num2)
    #bnum = random.randint(num1, num2)
    #cnum = random.randint(num1, num2)
    #dnum = random.randint(num1, num2)
    #enum = random.randint(num1, num2)
    #fnum = random.randint(num1, num2)
    #gnum = random.randint(num1, num2)
    randomlist = random.sample(range(num1, num2), 7)
    # print(anum, bnum, cnum, dnum, enum, fnum)
    #choice_list = [anum, bnum, cnum, dnum, enum, fnum, gnum]
    znum = random.randint(0, len(randomlist) - 1)
    rnum = randomlist[znum]
    return rnum

def get_random_files2(ext, top=os.getcwd()):
    file_list = list(Path(top).glob(f"**/*.{ext}"))
    if not len(file_list):
        return f"No files matched that extension: {ext}"
    rand = random.randint(0, len(file_list) - 1)
    return file_list[rand]

class JurassiCord(c.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.time_to_spawn = None
        self.pokestore = None
        self.imgr_results = None
        self.imgr_result = None
        self.spawn_msg = None
        self.caught = False
        self.randNums = []

    def __getstate__(self):
        return ({
            'time': self.time_to_spawn,
            'store': self.pokestore,
            'imgr': self.imgr_results,
            'msg': self.spawn_msg
        })
        pass

    def __setstate__(self, dictState):
        self.time_to_spawn = dictState['time']
        self.pokestore = dictState['store']
        self.imgr_results = dictState['imgr']
        self.spawn_msg = dictState['msg']
        pass

    def setToSpawn(self):
        if self.time_to_spawn is None:
            return False
        else:
            return True

    @c.Cog.listener()
    async def on_ready(self):
        if self.setToSpawn():
            if self.time_to_spawn is not None:
                if self.time_to_spawn > datetime.now():
                    await asyncio.sleep(self.getSeconds())
            else:
                await asyncio.sleep(10)
            image = get_random_files2("png", "./assets/DinoAssets/Images/")
            dino = os.path.basename(image)[:-4]
            print(image, dino)
            #await self._spawn(dino)

    @c.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.content[1:].startswith("spawn"):
            return
        count_sql = 'SELECT * FROM discord_data.pokecord_poke_data where "ownerid" = $1 and "selected" = $2'
        poke_info = await helpers.query_postgresDatabase(count_sql, message.author.id, True)
        if poke_info:
            data = await helpers.get_player_postgresData(message.author, message.guild, 'lastmessage')
            orig_time = data['lastmessage']
            time_diff = int(time.time()) - orig_time
            diff_seconds = time_diff % 60
            if diff_seconds >= exp_secs:
                completed, old_name, pokename, levelup, level, evolved = await self.addExpLvlUp(message.author,
                                                                                                poke_info)
                if evolved:
                    await message.author.send(
                        f"Congrats {message.author.mention}! You have evolved your {old_name.capitalize()} into a {pokename.capitalize()}!")
                elif levelup:
                    await message.author.send(
                        f"Congrats {message.author.mention}! Your {pokename.capitalize()} advanced to level {level}!")
        if self.setToSpawn():
            return
        else:
            if self.time_to_spawn is not None:
                if self.time_to_spawn > datetime.now():
                    await asyncio.sleep(self.getSeconds())
            else:
                await asyncio.sleep(10)
            image = get_random_files2("png", "./assets/DinoAssets/Images/")
            dino = os.path.basename(image)[:-4]
            print(image, dino)
            # await self._spawn(dino)


def setup(bot):
    bot.add_cog(JurassiCord(bot))