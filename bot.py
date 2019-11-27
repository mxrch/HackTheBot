import discord
from discord.ext import tasks, commands
from lib.htb import HTBot
import config as cfg

description = '''HideAndSec's slave bot'''
bot = commands.Bot(command_prefix='>', description=description)

htbot = HTBot(cfg.HTB['username'], cfg.HTB['password'], cfg.HTB['api_token'])

#Start

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

#Tasks

class tasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_boxs.start()

    def refresh_boxs_stop(self):
        self.refresh_boxs.stop()

    def refresh_boxs_start(self):
        self.refresh_boxs.start()

    @tasks.loop(seconds=60.0)
    async def refresh_boxs(self):
        htbot.refresh_boxs()

#Commands

@bot.command()
async def hello(ctx):
    """Says Hello World"""
    await ctx.send("Hello World")

@bot.command()
async def echo(ctx, *, content='bien essayé fdp'):
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
async def get_box(ctx, name):
    """Get info on a box"""
    if name:
        tasks = bot.get_cog('tasksCog')
        tasks.refresh_boxs.stop()
        box = htbot.get_box(name)
        if box:
            await ctx.send("", embed=box)
        else:
            await ctx.send("Cette box n'existe pas.")
        try:
            tasks.refresh_boxs.start()
        except RuntimeError:
            pass
    else:
        await ctx.send("Tu n'as pas précisé la box.")

@bot.command()
async def last_box(ctx):
    """Get info on the newest box"""
    tasks = bot.get_cog('tasksCog')
    tasks.refresh_boxs.stop()
    box = htbot.get_box(last=True)
    await ctx.send("", embed=box)
    try:
        tasks.refresh_boxs.start()
    except RuntimeError:
        pass

@bot.command()
async def test(ctx):
    """Test command"""
    pass

bot.add_cog(tasksCog(bot))
bot.run(cfg.discord['bot_token'])
