from main import *

try:
    with open("./config/config.json") as cfg:
        config = json.load(cfg)
        print("Reactions Config Loaded")
except Exception:
    config = {}
    print("Reactions Config Not Created, Using Temporary Storage.")

AdminRole = config.get("AdminRole")


async def createSpiderChart(channels):
    channelDict = {
        'chartgroup': ['A', 'B']
    }
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    now_timeStamp = time.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    neg_timeStamp = now_timeStamp.tm_yday - 7
    doubleneg_timeStamp = neg_timeStamp - 7
    past_timeStamp = datetime(datetime.today().timetuple().tm_year, 1, 1) + timedelta(neg_timeStamp - 1)
    doublepast_timeStamp = datetime(datetime.today().timetuple().tm_year, 1, 1) + timedelta(doubleneg_timeStamp - 1)
    lastWeeksql = "SELECT COUNT(*) FROM message_log WHERE `ChannelID`=%s and `Timestamp` < %s and `Timestamp` > %s;"
    thisWeeksql = "SELECT COUNT(*) FROM message_log WHERE `ChannelID`=%s and `Timestamp` > %s"
    for channel in channels:
        if channel.name not in channelDict:
            channelDict[channel.name] = []
            lastWeekargs = (str(channel.id), past_timeStamp, doublepast_timeStamp)
            thisWeekargs = (str(channel.id), past_timeStamp)
            lastWeekValue = await helpers.execute_sql(lastWeeksql, lastWeekargs, True)
            thisWeekValue = await helpers.execute_sql(thisWeeksql, thisWeekargs, True)
            # print(type(thisWeekValue[0]['COUNT(*)']), thisWeekValue[0])
            channelDict[channel.name].append(lastWeekValue[0]['COUNT(*)'])
            channelDict[channel.name].append(thisWeekValue[0]['COUNT(*)'])
            # print(channelDict[channel.name])
    print(channelDict)
    df = pd.DataFrame(channelDict)

    # ------- PART 1: Create background

    # number of variable
    categories = list(df)[1:]
    N = len(categories)

    # What will be the angle of each axis in the plot? (we divide the plot / number of variable)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]

    # Initialise the spider plot
    ax = plt.subplot(111, polar=True)

    # If you want the first axis to be on top:
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)

    # Draw one axe per variable + add labels labels yet
    plt.xticks(angles[:-1], categories)

    # Draw ylabels
    ax.set_rlabel_position(0)
    list0 = df.loc[0].drop('chartgroup').values.flatten().tolist()
    list0.extend(df.loc[1].drop('chartgroup').values.flatten().tolist())
    if any(value >= 30000 for value in list0):
        plt.yticks([10000, 15000, 20000, 25000, 40000], ["10,000", "15,000", "20,000", "25,000", "40,000"],
                   color="grey",
                   size=7)
        plt.ylim(0, 50000)
    elif any(value >= 20000 for value in list0):
        plt.yticks([5000, 10000, 15000, 20000, 25000], ["5000", "10,000", "15,000", "20,000", "25,000"], color="grey",
                   size=7)
        plt.ylim(0, 30000)
    elif any(value >= 10000 for value in list0):
        plt.yticks([500, 1000, 5000, 10000, 15000], ["500", "1,000", "5,000", "10,000", "15,000"], color="grey",
                   size=7)
        plt.ylim(0, 20000)
    elif any(value >= 5000 for value in list0):
        plt.yticks([1000, 2000, 4000, 6000, 8000], ["1,000", "2,000", "4,000", "6,000", "8,000"], color="grey",
                   size=7)
        plt.ylim(0, 10000)
    elif any(value >= 2500 for value in list0):
        plt.yticks([250, 500, 1000, 2500], ["250", "500", "1,000", "2,500"], color="grey",
                   size=7)
        plt.ylim(0, 5000)
    elif any(value >= 1000 for value in list0):
        plt.yticks([250, 500, 750, 1000, 1500, 2000], ["250", "500", "750", "1,000", "1,500", "2,000"], color="grey",
                   size=7)
        plt.ylim(0, 2500)
    else:
        list0.sort()
        list0.append(list0[len(list0) - 1] + 100)
        list0.pop(len(list0) - 2)
        plt.yticks(list0, map(str, list0), color="grey", size=7)
        plt.ylim(0, list0[len(list0) - 1])

    # ------- PART 2: Add plots

    # Plot each individual = each line of the data
    # I don't do a loop, because plotting more than 3 groups makes the chart unreadable

    # Ind1
    values = df.loc[0].drop('chartgroup').values.flatten().tolist()
    values += values[:1]
    ax.plot(angles, values, linewidth=1, linestyle='solid', label="This Week")
    ax.fill(angles, values, 'b', alpha=0.1)

    # Ind2
    values = df.loc[1].drop('chartgroup').values.flatten().tolist()
    values += values[:1]
    ax.plot(angles, values, linewidth=1, linestyle='solid', label="Last Week")
    ax.fill(angles, values, 'r', alpha=0.1)

    # Add legend
    plt.legend(loc='lower right', bbox_to_anchor=(0, 0))

    return plt


class Activity(c.Cog):
    def __init__(self, bot):
        self.bot = bot

    @helpers.has_higher_role(False, AdminRole)
    @c.command()
    async def activity(self, ctx, *args):
        """Shows Activity Chart of Specified Channels. (Min of 3 Channels)
        Example: $activity <#chan1> <#chan2> <#chan3>"""
        # await ctx.send("{} {}".format(lastWeekValue[0], thisWeekValue[0]))
        channels = []
        for arg in args:
            chan_id = int(arg.replace("<", "").replace(">", "").replace("#", "").replace("!", ""))
            channel = self.bot.get_channel(chan_id)
            channels.append(channel)
        print(channels)
        chart = await createSpiderChart(channels)
        chart.savefig('./assets/activity.png')
        chart.close()
        await ctx.send(file=discord.File('./assets/activity.png'))


def setup(bot):
    bot.add_cog(Activity(bot))
