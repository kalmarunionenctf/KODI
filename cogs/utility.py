import config_vars
import collections
import string
import urllib.parse
import random
import json
import discord
from discord.ext import commands

# This can be thought of as a miscellaneous category (anything 'utility' based.)


class Utility(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def get_verifications(self, user):
        verifications = {}
        try:
            with open(config_vars.verifications_json_path, "r") as f:
                jsonStates = json.loads(f.read())
                for verifier_id, verified_sets in jsonStates.items():
                    verified_set = next(
                        (verified_set for verified_set in verified_sets if verified_set['user'] == user.id), None)
                    if verified_set:
                        verifications[self.bot.get_user(int(
                            verifier_id))] = verified_set['at']
        except FileNotFoundError:
            print(
                f'verifications.json not found at {config_vars.verifications_json_path}')
        return verifications

    @ commands.command(aliases=['who'])
    async def whois(self, ctx, user_name):
        user = next((user for user in ctx.guild.members if user.name.lower(
        ) == user_name.lower()), None)
        if user:
            verifications = self.get_verifications(user)
            if verifications:
                await ctx.send(f'`{user}`. History:')
                for verifier, at in verifications.items():
                    await ctx.send(
                        f'{at.split(".")[0]}: Verified by `{verifier}`')
            else:
                await ctx.send(f'I have no history on `{user}`. They were either here before me or was added directly by an admin.')

    @ commands.command(aliases=['char'])
    async def characters(self, ctx, string):
        await ctx.send(len(string))

    @ commands.command(aliases=['wc'])
    async def wordcount(self, ctx, *args):
        await ctx.send(len(args))

    @ commands.command(aliases=['rev'])
    async def reverse(self, ctx, message):
        await ctx.send(message[:: (- 1)])

    @ commands.command()
    async def counteach(self, ctx, message):
        # Count the amount of characters in a string.
        count = {}

        for char in message:
            if char in count.keys():
                count[char] += 1
            else:
                count[char] = 1

        await ctx.send(str(count))

    @ commands.command(aliases=['head'])
    async def magicb(self, ctx, filetype):
        # Get the magic bytes from a filetype
        file = open('magic.json').read()
        alldata = json.loads(file)
        try:
            messy_signs = str(alldata[filetype]['signs'])
            signs = messy_signs.split('[')[1].split(',')[0].split(']')[
                0].replace("'", '')
            filetype = alldata[filetype]['mime']
            await ctx.send(f'''{filetype}: {signs}''')
        except:  # if the filetype is not in magicb.json...
            await ctx.send(f"{filetype} not found :(  If you think this filetype should be included please do `>request \"magicb {filetype}\"`")

    @ commands.command()
    async def twitter(self, ctx, twituser):
        await ctx.send('https://twitter.com/' + twituser)

    @ commands.command()
    async def github(self, ctx, gituser):
        await ctx.send('https://github.com/' + gituser)

    @ commands.command(aliases=['5050', 'flip'])
    async def cointoss(self, ctx):
        choice = random.randint(1, 2)

        if choice == 1:
            await ctx.send('heads')

        if choice == 2:
            await ctx.send('tails')


def setup(bot):
    bot.add_cog(Utility(bot))
