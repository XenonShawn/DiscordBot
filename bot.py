from datetime import datetime
import logging
from os.path import join
import json
import asyncio

import discord
from discord.ext import commands

from config import token # Contains token = 'xxx'   

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p',
                    handlers=[
                        # Send to both stderr and file at the same time
                        logging.FileHandler(join('logs',f'{datetime.today().date()}.discordbot.log')),
                        logging.StreamHandler()
                    ])

cogs_to_load = ['cogs.admin',
                'cogs.fun', 
                'cogs.utilities', 
                'cogs.nssg', 
                'cogs.games']

################################################################################
#                                XenonBot Class                                #
################################################################################

def command_prefixes(bot, msg):
    if not msg.guild or msg.guild.id not in bot.guild_prefix:
        prefix = ['$']
    else:
        prefix = [bot.guild_prefix[msg.guild.id]]
    prefix.extend((f'<@{bot.user.id}> ', f'<@!{bot.user.id}> '))
    return prefix

class XenonBot(commands.Bot):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.uptime = None

        # Load server prefixes
        try: 
            with open(join('data', 'guild_prefix.json'), 'r') as f:
                self.guild_prefix = {int(k): v for k, v in json.load(f).items()}
            logging.info("Loaded server prefixes.")
        except Exception as e:
            logging.error(str(e))
            logging.warning("Unable to load server prefixes. Servers which have"
                            "set their prefixes will not be able to use them.")
            self.guild_prefix = dict()

        # Load blacklisted users
        try:
            with open(join('data', 'blacklist.json'), 'r') as f:
                self.blacklist = set(json.load(f))
            logging.info("Loaded blacklisted users")
        except Exception as e:
            logging.error(str(e))
            logging.warning("Unable to load blacklisted users.")
            self.blacklist = set() # set of user ids

        # Load cogs
        for filename in cogs_to_load:
            try:
                self.load_extension(filename)
                logging.info(f"Loaded cog {filename}.")
            except Exception as e:
                logging.error(str(e))
                logging.warning(f"Failed to load cog {filename}.")

    ### Functions relating to guild prefixes ###

    async def set_guild_prefix(self, ctx, prefix: str):
        """Set the guild's command prefix."""
        self.guild_prefix[ctx.guild.id] = prefix
        return await ctx.send(f"The server prefix is now set to '{self.guild_prefix[ctx.guild.id]}'.")
    
    def get_guild_prefix(self, ctx):
        """
        Return the unique guild prefix. Duh.
        Will be used more in the future when I implement my own help function.
        """
        return self.guild_prefix.get(ctx.guild.id, '$')

    # Blacklist functions
    async def blacklist_user(self, ctx, user: discord.User):
        """Globally blacklist a user from using the bot."""
        identity = user.id
        if identity == self.owner_id:
            return await ctx.send("The owner of the bot cannot be blacklisted.")
        elif identity in self.blacklist:
            return await ctx.send(f"{user} is already in the blacklist.")
        else:
            self.blacklist.add(identity)
            logging.info(f"{user} blacklisted.")
            return await ctx.send(f"{user} is now blacklisted.")

    async def unblacklist_user(self, ctx, user: discord.User):
        """Remove a user from the global blacklist."""
        identity = user.id
        if identity not in self.blacklist:
            return await ctx.send(f"{user} is not in the global blacklist.")
        else:
            self.blacklist.remove(identity)
            logging.info(f"{user} removed from global blacklist.")
            return await ctx.send(f"{user} removed from the global blacklist.")

    async def check_blacklist(self, ctx):
        """Prints to console the users in the global blacklist."""
        for user_id in self.blacklist:
            print(user_id)

    # Listeners
    async def on_ready(self):
        self.uptime = self.uptime or datetime.today()
        await bot.change_presence(activity=discord.Game("Use $help!"))
        logging.info(f"We have logged in as {bot.user}!")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions) or isinstance(error, commands.NotOwner):
            return await ctx.send("You do not have the permissions to use this command.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Missing required arguments for command. Use $help [command] for example usage.")
        if isinstance(error, commands.BadArgument) or isinstance(error, commands.BadUnionArgument):
            return await ctx.send(error)
        if isinstance(error, commands.NoPrivateMessage):
            return await ctx.send(error)
        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(error)
        logging.error(f"{type(error)}: {error}")
        raise error

    async def on_message(self, message):
        if message.author.bot or message.author.id in self.blacklist:
            return
        await self.process_commands(message)


logging.info("Starting up the bot.")
bot = XenonBot(command_prefix=command_prefixes)

### Commands to load cogs ###

@bot.command(hidden=True)
@commands.is_owner()
async def load(ctx, extension):
    """Owner only administrative command used to load a cog."""
    logging.info(f"Request by {ctx.author}: Load cog {extension}.")
    try:
        bot.load_extension(f'cogs.{extension}')
        logging.info(f"Request to load cog {extension} successful.")
        return await ctx.send(f"Loaded cog {extension}.")
    except commands.ExtensionError as e:
        logging.error(f"Request to load cog {extension} unsuccessful. Error Type: {type(e)}.\nError Message: {e}")
        return await ctx.send(f"Failed to load cog {extension}. Error Type: {type(e)}.\nError Message: {e}")

@bot.command(hidden=True)
@commands.is_owner()
async def unload(ctx, extension):
    """Owner only administrative command used to unload a cog."""
    logging.info(f"Request by {ctx.author}: Unoad cog {extension}.")
    try:
        bot.unload_extension(f'cogs.{extension}')
        logging.info(f"Request to unload cog {extension} successful.")
        return await ctx.send(f"Unloaded cog {extension}")
    except commands.ExtensionNotLoaded as e:
        logging.error(f"Request to unload cog {extension} unsuccessful. Error Type: {type(e)}.\nError Message: {e}")
        return await ctx.send(f"Failed to unload cog {extension}. Error Type: {type(e)}.\nError Message: {e}")

@bot.command(hidden=True)
@commands.is_owner()
async def reload(ctx, extension):
    """Owner only administrative command used to reload a cog."""
    logging.info(f"Request by {ctx.author}: Reload cog {extension}.")
    try:
        bot.reload_extension(f'cogs.{extension}')
        logging.info(f"Request to reload cog {extension} successful.")
        return await ctx.send(f"Reloaded cog {extension}")
    except commands.ExtensionError as e:
        logging.error(f"Request to reload cog {extension} unsuccessful. Error Type: {type(e)}.\nError Message: {e}")
        return await ctx.send(f"Failed to reload cog {extension}. Error Type: {type(e)}.\nError Message: {e}")

try:
    bot.run(token)
    
################################################################################
#                                 Cleanup Code                                 #
################################################################################
finally:
    try:
        with open(join('data', 'guild_prefix.json'), 'w') as f:
            json.dump(bot.guild_prefix, f)
        logging.info("Saved server prefixes.")
    except Exception as e:
        logging.error(str(e))
        logging.warning("Unable to save server prefixes!")

    try:
        with open(join('data', 'blacklist.json'), 'w') as f:
            json.dump(list(bot.blacklist), f)
        logging.info("Saved blacklist.")
    except Exception as e:
        logging.error(str(e))
        logging.warning("Unable to save blacklist!")