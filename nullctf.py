import discord
from discord.ext.commands import Bot
from discord.ext import commands
import os
import re
import sys

import help_info
import config_vars

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=">", intents=intents)
# The default help command is removed so a custom one can be added.
bot.remove_command('help')

# Each extension corresponds to a file within the cogs directory.  Remove from the list to take away the functionality.
extensions = ['ctf', 'ctftime', 'configuration',
              'encoding', 'cipher', 'utility']
# List of names reserved for those who gave cool ideas or reported something interesting.
# please don't spam me asking to be added.  if you send something interesting to me i will add you to the list.
# If your name is in the list and you use the command '>amicool' you'll get a nice message.
cool_names = ['nullpxl', 'Yiggles', 'JohnHammond', 'voidUpdate', 'Michel Ney', 'theKidOfArcrania', 'l14ck3r0x01', 'hasu', 'KFBI',
              'mrFu', 'warlock_rootx', 'd347h4ck', 'tourpan', 'careless_finch', 'fumenoid', '_wh1t3r0se_', 'The_Crazyman', 'hutli', 'zanderdk']
# This is intended to be circumvented; the idea being that people will change their names to people in this list just so >amicool works for them, and I think that's funny.


@bot.event
async def on_ready():
    print(f"{bot.user.name} - Online")
    print(f"discord.py {discord.__version__}\n")
    print("-------------------------------")

    await bot.change_presence(activity=discord.Game(name=">help | >source"))


@bot.command()
async def help(ctx, page=None):
    # Custom help command.  Each main category is set as a 'page'.
    if page == 'ctftime':
        emb = discord.Embed(description=help_info.ctftime_help, colour=4387968)
        emb.set_author(name='CTFTime Help')
    elif page == 'ctf':
        emb = discord.Embed(description=help_info.ctf_help, colour=4387968)
        emb.set_author(name='CTF Help')
    elif page == 'config':
        emb = discord.Embed(description=help_info.config_help, colour=4387968)
        emb.set_author(name='Configuration Help')
    elif page == 'utility':
        emb = discord.Embed(description=help_info.utility_help, colour=4387968)
        emb.set_author(name='Utilities Help')

    else:
        emb = discord.Embed(description=help_info.help_page, colour=4387968)
        emb.set_author(name='NullCTF Help')

    await attach_embed_info(ctx, emb)
    await ctx.channel.send(embed=emb)


async def attach_embed_info(ctx=None, embed=None):
    embed.set_thumbnail(url=f'{bot.user.avatar_url}')
    return embed


@bot.command()
async def source(ctx):
    # Sends the github link of the bot.
    await ctx.send(help_info.src)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing a required argument.  Do >help")
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have the appropriate permissions to run this command.")
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send("I don't have sufficient permissions!")
    else:
        print("error not caught")
        print(error)


@bot.command()
async def request(ctx, feature):
    # Bot sends a dm to creator with the name of the user and their request.
    creator = await bot.fetch_user(133962599015383041)
    authors_name = str(ctx.author)
    await creator.send(f''':pencil: {authors_name}: {feature}''')
    await ctx.send(f''':pencil: Thanks, "{feature}" has been requested!''')


@bot.command()
async def report(ctx, error_report):
    # Bot sends a dm to creator with the name of the user and their report.
    creator = await bot.fetch_user(133962599015383041)
    authors_name = str(ctx.author)
    await creator.send(f''':triangular_flag_on_post: {authors_name}: {error_report}''')
    await ctx.send(f''':triangular_flag_on_post: Thanks for the help, "{error_report}" has been reported!''')


@bot.command()
async def amicool(ctx):
    authors_name = str(ctx.author).split("#")[0]
    if authors_name in cool_names:
        await ctx.send('You are very cool :]')
    else:
        await ctx.send('lolno')
        await ctx.send('Psst, kid.  Want to be cool?  Find an issue and report it or request a feature!')


def stringify_prefix_and_channel(flags_object):
    pretty_prefixes = ''
    pretty_ctf_channels = ''
    for ctf in flags_object:
        pretty_prefixes += f'"{ctf.flag_prefix}", '
        pretty_ctf_channels += f'{ctf.channel.mention}, '
    if pretty_prefixes:
        pretty_prefixes = pretty_prefixes[:-2]
    if pretty_ctf_channels:
        pretty_ctf_channels = pretty_ctf_channels[:-2]
    return (pretty_prefixes, pretty_ctf_channels)


def get_flags(message):
    flags = {}
    server = config_vars.teamdb[str(message.guild.id)]
    for ctf in server.find():
        if 'flag_prefix' in ctf:
            print(ctf)
            regex = ctf['flag_prefix'] + '{.{6,}}'
            found_flags = re.findall(regex, message.content)
            if found_flags:
                ctf_key
                flags[ctf] = found_flags
    return flags


@bot.event
async def on_message(message):
    print("TEST")
    flags = get_flags(message)
    if flags:
        await message.delete()
        pretty_prefixes, pretty_ctf_channels = stringify_prefix_and_channel(
            flags)
        await message.channel.send(
            content=f'```Message removed - Active CTF flag-prefix detected\nPlease only post flags with prefixes {pretty_prefixes} in {pretty_ctf_channels} respectively```')
    else:
        await bot.process_commands(message)

if __name__ == '__main__':
    sys.path.insert(1, os.getcwd() + '/cogs/')
    for extension in extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print(f'Failed to load cogs : {e}')
    bot.run(config_vars.discord_token)
