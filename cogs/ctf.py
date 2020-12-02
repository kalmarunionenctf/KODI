import config_vars
import discord
from discord.ext import tasks, commands
from ctfd_ctfpad_integration import CTFdCTFPadIntegration
import string
import json
import requests
import sys
import traceback
import re
import time
from requests_pkcs12 import Pkcs12Adapter
sys.path.append("..")

# All commands relating to server specific CTF data
# Credentials provided for pulling challenges from the CTFd platform are NOT stored in the database.
# they are stored in a pinned message in the discord channel.


def in_ctf_channel():
    async def tocheck(ctx):
        # A check for ctf context specific commands
        if config_vars.teamdb[str(ctx.guild.id)].find_one({'name': str(ctx.message.channel)}):
            return True
        else:
            await ctx.send("You must be in a created ctf channel to use ctf commands!")
            return False
    return commands.check(tocheck)


def in_announcements_channel():
    async def tocheck(ctx):
        # A check for ctf context specific commands
        if ctx.message.channel.name == announcements_channel_name:
            return True
        else:
            return False
    return commands.check(tocheck)


def strip_string(tostrip, whitelist):
    # A string validator to correspond with a provided whitelist.
    stripped = ''.join([ch for ch in tostrip if ch in whitelist])
    return stripped.strip()


class InvalidProvider(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class CredentialsNotFound(Exception):
    pass


class NonceNotFound(Exception):
    pass


class CTF(commands.Cog):
    ctfd_ctfpad_integrations = {}

    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def ctf(self, ctx):
        if ctx.invoked_subcommand is None:
            # If the subcommand passed does not exist, its type is None
            ctf_commands = list(
                set([c.qualified_name for c in CTF.walk_commands(self)][1:]))
            # update this to include params
            await ctx.send(f"Current ctf commands are: {', '.join(ctf_commands)}")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=["new"])
    async def create(self, ctx, name, flag_prefix=None):
        # Create a new channel in the CTF category (default='Current CTFs' or configured with the configuration extension)
        try:
            sconf = config_vars.serverdb[str(ctx.guild.id) + '-CONF']
            servcat = sconf.find_one({'name': "category_name"})['ctf_category']
        except:
            servcat = "Current CTFs"

        category = discord.utils.get(ctx.guild.categories, name=servcat)
        if category == None:  # Checks if category exists, if it doesn't it will create it.
            await ctx.guild.create_category(name=servcat)
            category = discord.utils.get(ctx.guild.categories, name=servcat)

        ctf_name = strip_string(name, set(
            string.ascii_letters + string.digits + ' ' + '-')).replace(' ', '-').lower()
        if ctf_name[0] == '-':
            # edge case where channel names can't start with a space (but can end in one)
            ctf_name = ctf_name[1:]
        # There cannot be 2 spaces (which are converted to '-') in a row when creating a channel.  This makes sure these are taken out.
        new_ctf_name = ctf_name
        prev = ''
        while '--' in ctf_name:
            for i, c in enumerate(ctf_name):
                if c == prev and c == '-':
                    new_ctf_name = ctf_name[:i] + ctf_name[i+1:]
                prev = c
            ctf_name = new_ctf_name

        await ctx.guild.create_text_channel(name=ctf_name, category=category)
        server = config_vars.teamdb[str(ctx.guild.id)]
        await ctx.guild.create_role(name=ctf_name, mentionable=True)
        ctf_info = {'name': ctf_name, "text_channel": ctf_name,
                    'flag_prefix': flag_prefix}
        server.update({'name': ctf_name}, {"$set": ctf_info}, upsert=True)
        # Give a visual confirmation of completion.
        await ctx.message.add_reaction("✅")

    # @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    # @commands.has_permissions(manage_channels=True)
    # @ctf.command()
    # @in_ctf_channel()
    # async def delete(self, ctx):
    #     Delete role from server, delete entry from db
    #     try:
    #         role = discord.utils.get(
    #             ctx.guild.roles, name=str(ctx.message.channel))
    #         await role.delete()
    #         await ctx.send(f"`{role.name}` role deleted")
    #     except:  # role most likely already deleted with archive
    #         pass
    #     config_vars.teamdb[str(ctx.guild.id)].remove(
    #         {'name': str(ctx.message.channel)})
    #     await ctx.send(f"`{str(ctx.message.channel)}` deleted from db")
    #     if ctx.channel in self.ctfd_ctfpad_integrations:
    #         del self.ctfd_ctfpad_integrations[ctx.channel]
    #         await ctx.send(f"CTFd integration for `{str(ctx.message.channel)}` stopped")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=["over"])
    @in_ctf_channel()
    async def archive(self, ctx):
        # Delete the role, and move the ctf channel to either the default category (Archive) or whatever has been configured.
        role = discord.utils.get(
            ctx.guild.roles, name=str(ctx.message.channel))
        await role.delete()
        await ctx.send(f"`{role.name}` role deleted, archiving channel.")
        try:
            sconf = config_vars.serverdb[str(ctx.guild.id) + '-CONF']
            servarchive = sconf.find_one({'name': "archive_category_name"})[
                'archive_category']
        except:
            servarchive = "ARCHIVE"  # default

        category = discord.utils.get(ctx.guild.categories, name=servarchive)
        if category == None:  # Checks if category exists, if it doesn't it will create it.
            await ctx.guild.create_category(name=servarchive)
            category = discord.utils.get(
                ctx.guild.categories, name=servarchive)
        await ctx.message.channel.edit(syncpermissoins=True, category=category)
        if ctx.channel in self.ctfd_ctfpad_integrations:
            del self.ctfd_ctfpad_integrations[ctx.channel]
            await ctx.send(f"CTFd integration for `{str(ctx.message.channel)}` stopped")

    @ctf.command()
    @in_ctf_channel()
    async def end(self, ctx):
        # This command is deprecated, but due to getting so many DMs from people who didn't use >help, I've decided to just have this as my solution.
        await ctx.send("You can now use either `>ctf delete` (which will delete all data), or `>ctf archive/over` \
which will move the channel and delete the role, but retain challenge info(`>config archive_category \
\"archive category\"` to specify where to archive.")

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command()
    @commands.has_role(config_vars.priveldged_role_name)
    @in_ctf_channel()
    async def join(self, ctx):
        # Give the user the role of whatever ctf channel they're currently in.
        role = discord.utils.get(
            ctx.guild.roles, name=str(ctx.message.channel))
        user = ctx.message.author
        await user.add_roles(role)
        await ctx.send(f"{user} has joined the {str(ctx.message.channel)} team!")

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command()
    @commands.has_role(config_vars.priveldged_role_name)
    @in_ctf_channel()
    async def leave(self, ctx):
        # Remove from the user the role of the ctf channel they're currently in.
        role = discord.utils.get(
            ctx.guild.roles, name=str(ctx.message.channel))
        user = ctx.message.author
        await user.remove_roles(role)
        await ctx.send(f"{user} has left the {str(ctx.message.channel)} team.")

    @ctf.group(aliases=["chal", "chall", "challenges"])
    @in_ctf_channel()
    async def challenge(self, ctx):
        pass

    @staticmethod
    def updateChallenge(ctx, name, status):
        # Update the db with a new challenge and its status
        server = config_vars.teamdb[str(ctx.guild.id)]
        whitelist = set(string.ascii_letters+string.digits+' ' +
                        '-'+'!'+'#'+'_'+'['+']'+'('+')'+'?'+'@'+'+'+'<'+'>')
        challenge = {strip_string(str(name), whitelist): status}
        ctf = server.find_one({'name': str(ctx.message.channel)})
        try:  # If there are existing challenges already...
            challenges = ctf['challenges']
            challenges.update(challenge)
        except:
            challenges = challenge
        ctf_info = {'name': str(ctx.message.channel),
                    'challenges': challenges
                    }
        server.update({'name': str(ctx.message.channel)},
                      {"$set": ctf_info}, upsert=True)

    def get_integration_channel(self, ctfd_ctfpad_integration):
        return next((channel for channel, integration in self.ctfd_ctfpad_integrations.items(
        ) if integration == ctfd_ctfpad_integration), None)

    def send_to_integration_channel(self, ctfd_ctfpad_integration, message):
        '''Sends a message to channel associated with a CTFd/CTFPad integration'''
        channel = self.get_integration_channel(ctfd_ctfpad_integration)
        self.bot.loop.create_task(channel.send(message))

    def add_challenge_to_integration_ctf(self, ctfd_ctfpad_integration, name, category):
        '''Adds a challenge to the CTF associated with a CTFd/CTFPad integration'''
        channel = self.get_integration_channel(ctfd_ctfpad_integration)
        fake_ctx = type('FakeCTX', (object,), {'message': type('FakeMessage', (object,), {
                        'channel': channel}), 'guild': channel.guild, 'send': channel.send})()
        self.bot.loop.create_task(self.add(fake_ctx, name))

    @challenge.command(aliases=["a"])
    @in_ctf_channel()
    async def add(self, ctx, name):
        CTF.updateChallenge(ctx, name, 'Unsolved')
        await ctx.send(f"`{name}` has been added to the challenge list for `{str(ctx.message.channel)}`")

    @challenge.command(aliases=['s', 'solve'])
    @commands.has_role(config_vars.priveldged_role_name)
    @in_ctf_channel()
    async def solved(self, ctx, name):
        solve = f"Solved - {str(ctx.message.author)}"
        CTF.updateChallenge(ctx, name, solve)
        await ctx.send(f":triangular_flag_on_post: `{name}` has been solved by `{str(ctx.message.author)}`")

    @challenge.command(aliases=['w'])
    @in_ctf_channel()
    async def working(self, ctx, name):
        work = f"Working - {str(ctx.message.author)}"
        CTF.updateChallenge(ctx, name, work)
        await ctx.send(f"`{str(ctx.message.author)}` is working on `{name}`!")

    @challenge.command(aliases=['r', 'delete', 'd'])
    @commands.has_role(config_vars.priveldged_role_name)
    @in_ctf_channel()
    async def remove(self, ctx, name):
        # Typos can happen (remove a ctf challenge from the list)
        ctf = config_vars.teamdb[str(ctx.guild.id)].find_one(
            {'name': str(ctx.message.channel)})
        challenges = ctf['challenges']
        whitelist = set(string.ascii_letters+string.digits+' ' +
                        '-'+'!'+'#'+'_'+'['+']'+'('+')'+'?'+'@'+'+'+'<'+'>')
        name = strip_string(name, whitelist)
        challenges.pop(name, None)
        ctf_info = {'name': str(ctx.message.channel),
                    'challenges': challenges
                    }
        config_vars.teamdb[str(ctx.guild.id)].update(
            {'name': str(ctx.message.channel)}, {"$set": ctf_info}, upsert=True)
        await ctx.send(f"Removed `{name}`")

    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @ctf.command(aliases=['ctfd'])
    @in_ctf_channel()
    async def integrate(self, ctx, ctfd_url, start_time=None, refresh_interval=None, max_refresh=None):
        ctf_name = ctx.channel.name
        pinned = await ctx.message.channel.pins()
        try:
            ctfd_token = self.get_creds(pinned)
        except CredentialsNotFound as cnfm:
            await ctx.send(cnfm)
            return
        try:
            ctfd_ctfpad_integration = CTFdCTFPadIntegration(
                self, ctf_name, ctfd_url, ctfd_token, refresh_interval=None, max_refresh=None, start_time=None)
        except ConnectionError as e:
            ctx.channel.send(
                f'Connection error during integration\n`{e}`')
            return
        self.ctfd_ctfpad_integrations[ctx.channel] = ctfd_ctfpad_integration

    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @ctf.command(aliases=['login'])
    @in_ctf_channel()
    async def setcreds(self, ctx, token):
        # Creates a pinned message with the credntials supplied by the user
        pinned = await ctx.message.channel.pins()
        for pin in pinned:
            if "CTF bot token set." in pin.content:
                # Look for previously pinned credntials, and remove them if they exist.
                await pin.unpin()
        msg = await ctx.send(f"CTF bot token set. Token:{token}")
        await msg.pin()

    @commands.bot_has_permissions(manage_messages=True)
    @ctf.command(aliases=['getcreds'])
    @in_ctf_channel()
    async def creds(self, ctx):
        # Send a message with the credntials
        pinned = await ctx.message.channel.pins()
        try:
            token = CTF.get_creds(pinned)
            await ctx.send(f"Discord bot token:`{token}`")
        except CredentialsNotFound as cnfm:
            await ctx.send(cnfm)

    @staticmethod
    def get_creds(pinned):
        for pin in pinned:
            print(pin.content)
            if "CTF bot token set." in pin.content:
                token = pin.content.split("Token:")[1]
                print(f'Token: {token}')
                return token
        raise CredentialsNotFound(
            "Set credentials with `>ctf setcreds \"token\"`")

    @staticmethod
    def gen_page(challengelist):
        # Function for generating each page (message) for the list of challenges in a ctf.
        challenge_page = ""
        challenge_pages = []
        for c in challengelist:
            # Discord message sizes cannot exceed 2000 characters.
            # This will create a new message every 2k characters.
            if not len(challenge_page + c) >= 1989:
                challenge_page += c
                if c == challengelist[-1]:  # if it is the last item
                    challenge_pages.append(challenge_page)

            elif len(challenge_page + c) >= 1989:
                challenge_pages.append(challenge_page)
                challenge_page = ""
                challenge_page += c

        # print(challenge_pages)
        return challenge_pages

    @challenge.command(aliases=['ls', 'l'])
    @in_ctf_channel()
    async def list(self, ctx):
        # list the challenges in the current ctf.
        ctf_challenge_list = []
        server = config_vars.teamdb[str(ctx.guild.id)]
        ctf = server.find_one({'name': str(ctx.message.channel)})
        try:
            ctf_challenge_list = []
            for k, v in ctf['challenges'].items():
                challenge = f"[{k}]: {v}\n"
                ctf_challenge_list.append(challenge)

            for page in CTF.gen_page(ctf_challenge_list):
                await ctx.send(f"```ini\n{page}```")
                # ```ini``` makes things in '[]' blue which looks nice :)
        except KeyError as e:  # If nothing has been added to the challenges list
            await ctx.send("Add some challenges with `>ctf challenge add \"challenge name\"`")
        except:
            traceback.print_exc()

    # @ctf.event
    # @in_announcements_channel()
    # async def on_reaction_add(reaction, user):
    #     if reaction.channel_mentions
    #     Role = discord.utils.get(
    #         user.server.roles, name="YOUR_ROLE_NAME_HERE")
    #     await client.add_roles(user, Role)


def setup(bot):
    bot.add_cog(CTF(bot))
