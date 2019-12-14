import discord
from discord.ext import tasks, commands
from lib.htb import HTBot
import config as cfg

description = '''HideAndSec's slave bot'''
bot = commands.Bot(command_prefix='>', description=description)

htbot = HTBot(cfg.HTB['email'], cfg.HTB['password'], cfg.HTB['api_token'])

#Start

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=">help"))
    bot.add_cog(tasksCog(bot))

#Tasks

class tasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.htb_login.start()
        self.check_notif.start()
        self.refresh_boxs.start()
        self.manage_channels.start()
        self.refresh_all_users.start()
        #self.refresh_shoutbox.start()

    @tasks.loop(seconds=3.0) #Toutes les 3 secondes, check les notifications
    async def check_notif(self):
        notif = htbot.notif
        #print(notif)
        if notif["update_role"]["state"]:
            content = notif["update_role"]["content"]
            await update_role(content["discord_id"], content["prev_rank"], content["new_rank"])
            htbot.notif["update_role"]["state"] = False

        elif notif["new_user"]["state"]:
            content = notif["new_user"]["content"]
            shoutbox = get_shoutbox_channel()
            guilds = bot.guilds
            for guild in guilds:
                if guild.name == cfg.discord['guild_name']:
                    member = guild.get_member(content["discord_id"])
            await shoutbox.send("👋 Bienvenue {} ! Heureux de t'avoir parmis nous.\nTu es arrivé avec le rang {} !".format(member.mention, content["level"]))
            htbot.notif["new_role"]["state"] = False

        elif notif["box_pwn"]["state"]:
            content = notif["box_pwn"]["content"]
            shoutbox = get_shoutbox_channel()
            guilds = bot.guilds
            for guild in guilds:
                if guild.name == cfg.discord['guild_name']:
                    member = guild.get_member(content["discord_id"])
            await shoutbox.send("👏 {} a eu le {} de {} !".format(member.mention, content["pwn"], content["box_name"]))
            htbot.notif["box_pwn"]["state"] = False

        elif notif["chall_pwn"]["state"]:
            content = notif["chall_pwn"]["content"]
            shoutbox = get_shoutbox_channel()
            guilds = bot.guilds
            for guild in guilds:
                if guild.name == cfg.discord['guild_name']:
                    member = guild.get_member(content["discord_id"])
            await shoutbox.send("👏 {} a réussi le challenge {} de la catégorie {} !".format(member.mention, content["chall_name"], content["chall_type"]))
            htbot.notif["chall_pwn"]["state"] = False

        elif notif["new_box"]["state"]:
            content = notif["new_box"]["content"]
            shoutbox = get_shoutbox_channel()
            if content["incoming"] == True:
                await shoutbox.send("⏱️ La box {} arrive dans {} ! ⏱️".format(content["box_name"], content["time"]))
            else:
                await shoutbox.send("@everyone 🚨 La nouvelle box {} est en ligne ! 🚨\nAurez-vous le first blood ? 🩸".format(content["box_name"]))
                box = htbot.get_box(content["box_name"], matrix=True)
                await shoutbox.send("", file=box["file"], embed=box["embed"])
            htbot.notif["new_box"]["state"] = False

        elif notif["vip_upgrade"]["state"]:
            content = notif["vip_upgrade"]["content"]
            shoutbox = get_shoutbox_channel()
            guilds = bot.guilds
            for guild in guilds:
                if guild.name == cfg.discord['guild_name']:
                    member = guild.get_member(content["discord_id"])
            await shoutbox.send("🍾 est devenu VIP {} ! Préparez le champagne et le caviar 🥂".format(member.mention))
            htbot.notif["vip_upgrade"]["state"] = False


    @tasks.loop(seconds=5.0) #Toutes les 5 secondes
    async def refresh_shoutbox(self):
        await htbot.shoutbox()

    @tasks.loop(seconds=1800.0) #Toutes les 30 minutes
    async def htb_login(self):
        await htbot.login()

    @tasks.loop(seconds=60.0) #Toutes les minutes
    async def refresh_boxs(self):
        await htbot.refresh_boxs()

    @tasks.loop(seconds=600.0) #Toutes les 10 minutes
    async def refresh_all_users(self):
        await htbot.refresh_all_users()

    @tasks.loop(seconds=60.0) #Toutes les minutes
    async def manage_channels(self):
        guilds = bot.guilds
        for guild in guilds:
            if guild.name == cfg.discord['guild_name']:
                categories = guild.categories
                for category in categories:
                    if "box-retired" in category.name.lower():
                        box_retired_cat = category
                    elif "box-active" in category.name.lower():
                        box_active_cat = category
                channels = box_active_cat.text_channels
                for channel in channels:
                    box_status = htbot.check_box(channel.name)
                    if box_status == "retired":
                        await channel.edit(category=box_retired_cat)
                        await channel.send("🔒 **{}** a été retirée, le channel a donc été déplacé vers la catégorie **{}**. 🔒".format(channel.name.capitalize(), box_retired_cat.name))


#Commands

@bot.command()
async def hello(ctx):
    """Says Hello World"""
    await ctx.send("Hello World")

@bot.command()
async def echo(ctx, *, content='🤔'):
    """A simple echo command"""
    await ctx.send(content)

@bot.command()
async def ping(ctx):
    """Want to ping pong ?"""
    await ctx.send(":ping_pong: Pong ! {}".format(bot.latency))

async def send_verif_instructions(user):
    embed = discord.Embed(color=0x9acc14)
    embed.add_field(name="Step 1: Log in to your HackTheBox Account", value="Log in to your HackTheBox account and go to the settings page.")
    embed.set_image(url="https://image.noelshack.com/fichiers/2019/48/3/1574858388-unknown.png")
    await user.send(embed=embed)
    embed = discord.Embed(color=0x9acc14)
    embed.add_field(name="Step 2: Locate the Identification key", value="In the settings tab, you should be able to identify a field called \"Account Identifier\", click on the green button to copy the string.")
    embed.set_image(url="https://image.noelshack.com/fichiers/2019/48/3/1574858586-capture.png")
    await user.send(embed=embed)
    embed = discord.Embed(color=0x9acc14)
    embed.add_field(name="Step 3: Verify", value="Proceed to send the bot your account identification string by:\n>verify <string>\n\nYour rank will be synchronized with HTB shortly.")
    embed.set_image(url="https://image.noelshack.com/fichiers/2019/48/3/1574859271-egqgqegqeg.png")
    await user.send(embed=embed)

@bot.command()
async def verify(ctx, content=""):
    """Verify your HTB account"""
    if str(ctx.channel.type) == "private":
        if content:
            verify_rep = htbot.verify_user(ctx.author.id, content)
            if verify_rep == "already_in":
                await ctx.send("You already have verified your HTB account.")
            elif verify_rep == "wrong_id":
                await ctx.send("This Account Identifier does not work.\nAre you sure you followed the instructions correctly ?")
            else:
                guilds = bot.guilds
                for guild in guilds:
                    if guild.name == cfg.discord['guild_name']:
                        roles = guild.roles
                        role_name = cfg.roles[verify_rep.lower()]
                        for role in roles:
                            if role.name == role_name:
                                member = guild.get_member(ctx.author.id)
                                await member.add_roles(role)
                embed = discord.Embed(title="Roles added", description=cfg.roles[verify_rep.lower()], color=0x14ff08)
                await ctx.send(embed=embed)
        else:
            await ctx.send("Je crois que tu as oublié ton Account Identifier.")
            await send_verif_instructions(ctx.author)
    else:
        if content:
            await ctx.message.delete()
            await ctx.send("😱 N'envoie pas ça ici {} !\nViens donc en privé, je t'ai envoyé les instructions.".format(ctx.author.mention))
            await send_verif_instructions(ctx.author)
        else:
            await ctx.send("{} Viens en privé, je t'ai envoyé les instructions.".format(ctx.author.mention))
            await send_verif_instructions(ctx.author)

@bot.command()
async def get_box(ctx, name="", matrix=""):
    """Get info on a box"""
    if name:
        tasks = bot.get_cog('tasksCog')
        tasks.refresh_boxs.stop()
        if matrix:
            if matrix.lower() == "matrix":
                box = htbot.get_box(name, matrix=True)
            else:
                await ctx.send("Paramètres incorrectes.")
                return False
        else:
            box = htbot.get_box(name)

        if box:
            if matrix:
                await ctx.send("", file=box["file"], embed=box["embed"])
            else:
                await ctx.send("", embed=box["embed"])
        else:
            await ctx.send("Cette box n'existe pas.")
        try:
            tasks.refresh_boxs.start()
        except RuntimeError:
            pass
    else:
        await ctx.send("Tu n'as pas précisé la box.")

@bot.command()
async def last_box(ctx, matrix=""):
    """Get info on the newest box"""
    tasks = bot.get_cog('tasksCog')
    tasks.refresh_boxs.stop()
    if matrix:
        if matrix.lower() == "matrix":
            box = htbot.get_box(matrix=True, last=True)
        else:
            await ctx.send("Paramètres incorrectes.")
            return False
    else:
        box = htbot.get_box(last=True)

    if matrix:
        await ctx.send("", file=box["file"], embed=box["embed"])
    else:
        await ctx.send("", embed=box["embed"])
    try:
        tasks.refresh_boxs.start()
    except RuntimeError:
        pass

@bot.command()
async def get_user(ctx, name=""):
    """Stalk your competitors"""
    if name:
        htb_id = htbot.htb_id_by_name(name)
        if htb_id:
            embed = htbot.get_user(str(htb_id))
            await ctx.send(embed=embed)
        else:
            await ctx.send("Utilisateur non trouvé.")
    else:
        await ctx.send("T'as pas oublié un truc ? :tired_face:")

@bot.command()
async def me(ctx):
    """Get your HTB info"""
    htb_id = htbot.discord_to_htb_id(ctx.author.id)
    if htb_id:
        embed = htbot.get_user(str(htb_id))
        await ctx.send(embed=embed)
    else:
        await ctx.send("Vous n'avez pas enregistré de compte HTB.")

@bot.command()
async def leaderboard(ctx):
    """Get the leaderboard of the guild"""
    board = htbot.leaderboard()
    if board:
        await ctx.send(embed=board)
    else:
        await ctx.send("Aucun compte HTB enregistré.\nFaites >verify pour le faire !")

async def update_role(discord_id, prev_rank, new_rank):
    guilds = bot.guilds
    for guild in guilds:
        if guild.name == cfg.discord['guild_name']:
            member = guild.get_member(discord_id)
            roles = guild.roles
            role_to_delete_name = cfg.roles[prev_rank.lower()]
            role_to_add_name = cfg.roles[new_rank.lower()]
            for role in roles:
                if role.name == role_to_add_name:
                    role_to_add = role
            roles = member.roles
            count = 0
            for role in roles:
                if role.name == role_to_delete_name:
                    roles[count] = role_to_add
                count += 1
            await member.edit(roles=roles)

    shoutbox = get_shoutbox_channel()
    await shoutbox.send("🎉 Félicitations {}, tu es passé au rang {} ! 🎉".format(member.mention, new_rank))


def get_shoutbox_channel():
    guilds = bot.guilds
    for guild in guilds:
        if guild.name == cfg.discord['guild_name']:
            channels = guild.channels
            for channel in channels:
                if channel.name == "shoutbox":
                    return channel

@bot.command()
async def list_boxs(ctx, type=""):
    """list all active boxs, by difficulty or not"""
    type = type.lower()
    if type:
        if type in ["easy", "medium", "hard", "insane"]:
            tasks = bot.get_cog('tasksCog')
            tasks.refresh_boxs.stop()
            embed = htbot.list_boxs(type)
            await ctx.send("", embed=embed)
            try:
                tasks.refresh_boxs.start()
            except RuntimeError:
                pass
        else:
            await ctx.send("Difficulté inconnue.")
    else:
        tasks = bot.get_cog('tasksCog')
        tasks.refresh_boxs.stop()
        embed = htbot.list_boxs()
        await ctx.send("", embed=embed)
        try:
            tasks.refresh_boxs.start()
        except RuntimeError:
            pass

@bot.command()
async def work_on(ctx, box_name=""):
    """Do this command when you start a new box"""

    #Si le nom de la box est précisé
    if box_name:
        box_name = box_name.lower()
        box_status = htbot.check_box(box_name)
        if box_status:
            guilds = bot.guilds
            for guild in guilds:
                if guild.name == cfg.discord['guild_name']:
                    channels = guild.channels
                    for channel in channels:
                        if channel.name == box_name:
                            await ctx.send("Le channel {} est à ta disposition, bonne chance ! ❤".format(channel.mention))
                            return True

                    #Si le channel n'existe pas encore
                    categories = guild.categories
                    if box_status == "active":
                        for category in categories:
                            if "box-active" in category.name.lower():
                                await guild.create_text_channel(name=box_name, category=category)
                                channels = guild.channels
                                for channel in channels:
                                    if channel.name == box_name:
                                        await ctx.send("J'ai créé le channel {}, il est à ta disposition ! Bonne chance ❤".format(channel.mention))
                                        box = htbot.get_box(box_name, matrix=True)
                                        await channel.send("✨ Channel créé ! {}".format(ctx.author.mention))
                                        await channel.send("", file=box["file"], embed=box["embed"])
                                        return True
                    elif box_status == "retired":
                        for category in categories:
                            if "box-retired" in category.name.lower():
                                await guild.create_text_channel(name=box_name, category=category)
                                channels = guild.channels
                                for channel in channels:
                                    if channel.name == box_name:
                                        await ctx.send("J'ai créé le channel {}, il est à ta disposition ! Bonne chance ❤".format(channel.mention))
                                        box = htbot.get_box(box_name)
                                        await channel.send("✨ Channel créé ! {}".format(ctx.author.mention))
                                        await channel.send("", embed=box)
                                        return True

        else:
            await ctx.send("Cette box n'existe pas.")

    else:
        if str(ctx.channel.type) == "private":
            await ctx.send("Tu n'as pas oublié quelque chose ?")
        else:
            box_name = ctx.channel.name.lower()
            box_status = htbot.check_box(box_name)
            if box_status:
                await ctx.send("Bonne chance {} ! ❤".format(ctx.author.mention))
            else:
                await ctx.send("Tu n'as pas oublié quelque chose ?")

@bot.command()
async def test(ctx):
    """test comme dhab"""
    pass

bot.run(cfg.discord['bot_token'])
