from datetime import datetime
import logging
from os.path import join
import sqlite3
from collections import defaultdict
import typing
import asyncio

import discord
from discord import user
from discord.ext import commands

from config import token, DEFAULT_PREFIX # Contains token = 'xxx'   
from cogs.helper import smart_send, error_embed

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p',
                    handlers=[
                        # Send to both stderr and file at the same time
                        logging.FileHandler(join('logs',f'{datetime.today().date()}.discordbot.log')),
                        logging.StreamHandler()
                    ])

cogs_to_load = ('cogs.admin', 'cogs.fun', 'cogs.nssg', 'cogs.utilities', 'cogs.moderation', 'cogs.games')

################################################################################
#                                XenonBot Class                                #
################################################################################

def command_prefixes(bot, msg):
    # bot.guild_prefix is a defaultdict with defaultfactory the DEFAULT_PREFIX
    return (bot.guild_prefix[msg.guild.id], f'<@{bot.user.id}> ', f'<@!{bot.user.id}> ')

class EmbedHelpCommand(commands.HelpCommand):
    """Adapted from Rapptz's example."""
    COLOUR = discord.Colour.blurple()

    def get_ending_note(self):
        return f"Use {self.clean_prefix}{self.invoked_with} [command] for more info on a command."

    def get_command_signature(self, command):
        return f"{command.qualified_name} {command.signature}"

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Bot Commands", colour=self.COLOUR)
        if self.context.bot.description:
            embed.description = self.context.bot.description

        for cog, commands in mapping.items():
            name = "No Category" if cog is None else cog.qualified_name
            filtered = await self.filter_commands(commands, sort=True)
            if filtered:
                value = '\u2002'.join(c.name for c in commands if not c.hidden)
                if cog and cog.description:
                    value = f"{cog.description}\n{value}"
                
                embed.add_field(name=name, value=value)
        
        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)
    
    async def send_cog_help(self, cog):
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", colour=self.COLOUR)
        if cog.description:
            embed.description = cog.description
        
        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            if not command.hidden:
                embed.add_field(name=self.get_command_signature(command), value=command.short_doc or '...', inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = discord.Embed(title=self.clean_prefix + self.get_command_signature(group), colour=self.COLOUR)
        if group.help:
            embed.description = group.help

        if isinstance(group, commands.Group):
            filtered = await self.filter_commands(group.commands, sort=True)
            for command in filtered:
                if not command.hidden:
                    embed.add_field(name=self.get_command_signature(command), value=command.short_doc or '...', inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    send_command_help = send_group_help
    
class XenonBot(commands.Bot):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.uptime = None
        self.con = sqlite3.connect(join('data', 'data.db'), detect_types=sqlite3.PARSE_DECLTYPES)
        self.con.execute("PRAGMA foreign_keys = 1")
        self.guild_prefix = defaultdict(lambda: DEFAULT_PREFIX)
        self.blacklist = set()

        # Ensure database exists
        self.con.execute("""CREATE TABLE IF NOT EXISTS settings (
                                guild_id    INTEGER PRIMARY KEY NOT NULL,
                                prefix      TEXT                NOT NULL
                            )""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS blacklist (
                                user_id     INTEGER PRIMARY KEY NOT NULL
                            )""")

        # Load guild prefixes and blacklisted users into memory
        for guild_id, prefix in self.con.execute("SELECT guild_id, prefix FROM settings"):
            self.guild_prefix[guild_id] = prefix

        for user_id in self.con.execute("SELECT user_id FROM blacklist"):
            self.blacklist.add(user_id)

        # Load cogs
        for filename in cogs_to_load:
            try:
                self.load_extension(filename)
                logging.info(f"Loaded cog {filename}.")
            except Exception as e:
                logging.error(str(e))
                logging.warning(f"Failed to load cog {filename}.")

    ### Functions relating to guild prefixes ###

    def set_guild_prefix(self, guild, prefix: str):
        """Set the guild's command prefix."""
        self.con.execute("""INSERT INTO settings(guild_id, prefix) VALUES (?, ?)
                            ON CONFLICT(guild_id) DO UPDATE SET prefix=excluded.prefix""",
                            (guild.id, prefix))
        self.con.commit()
        self.guild_prefix[guild.id] = prefix
    
    def get_guild_prefix(self, guild):
        """Return the unique guild prefix. Duh."""
        return self.guild_prefix[guild.id]

    ### Helper functions relating to async ###

    def schedule_task(self, sleep_seconds: int, func: typing.Union[typing.Callable, typing.Coroutine]) -> asyncio.Task:
        """
        A helper function that schedules a callable to be called `sleep_seconds` in the 
        future. If `sleep_seconds` is negative, the callback will be called as soon as possible.

        Arguments can be passed in into `func` using `functools.partial`.

        Returns the task object.
        """
        if not (callable(func) or asyncio.iscoroutine(func)):
            raise TypeError("Argument must be callable.")
        async def coroutine():
            try:
                await asyncio.sleep(max(sleep_seconds, 0))
                if asyncio.iscoroutinefunction(func):
                    return await func()
                elif asyncio.iscoroutine(func):
                    return await func
                else:
                    return func()
            except asyncio.CancelledError:
                logging.warning("Cancelled unfinished task.")
        return self.loop.create_task(coroutine())

    async def confirm_response(self, ctx, timeout=10, ask=True) -> bool:
        positive_responses = {'yes', 'y', 'true', 't', '1', 'enable', 'on'}
        all_responses = positive_responses | {'no', 'n', 'false', 'f', '0', 'disable', 'off'}        

        def correct_response(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in all_responses

        try:
            if ask:
                await ctx.send("Are you sure? (Y/N)")
            response = await self.wait_for('message', check=correct_response, timeout=timeout)
        except asyncio.TimeoutError:
            if ask:
                await ctx.send("No proper response detected.")
            return False

        return response.content.lower() in positive_responses

    # Blacklist functions
    async def blacklist_user(self, ctx, user: typing.Union[discord.User, int]):
        """Globally blacklist a user from using the bot."""
        identity = user if type(user) == int else user.id
        if identity == self.owner_id:
            return await ctx.send("The owner of the bot cannot be blacklisted.")
        try:
            with self.con:
                self.con.execute("INSERT INTO blacklist(user_id) VALUES (?)", (identity,))
        except sqlite3.IntegrityError:
            return await ctx.send(f"{user} is already in the blacklist.")
        else:
            self.blacklist.add(identity)
            logging.info(f"{user} blacklisted.")
            return await ctx.send(f"{user} is now blacklisted.")

    async def unblacklist_user(self, ctx, user: typing.Union[discord.User, int]):
        """Remove a user from the global blacklist."""
        identity = user if type(user) == int else user.id
        if identity not in self.blacklist:
            return await ctx.send(f"{user} is not in the global blacklist.")
        else:
            self.blacklist.remove(identity)
            with self.con:
                self.con.execute("DELETE FROM blacklist WHERE user_id = ?", (identity, ))
            logging.info(f"{user} removed from global blacklist.")
            return await ctx.send(f"{user} removed from the global blacklist.")

    async def check_blacklist(self, ctx):
        """Prints to console the users in the global blacklist."""
        message = ""
        for user_id in self.blacklist:
            message += f"{user_id}: "
            try:
                blacklisted_user = self.get_user(user_id) or await self.fetch_user(user_id)
                message += blacklisted_user.name + '#' + blacklisted_user.discriminator
            except discord.NotFound:
                message += "User Not Found"
            except discord.HTTPException:
                message += "HTTP Error"
            finally:
                message += '\n'
        await smart_send(ctx, message)

    # Listeners
    async def on_ready(self):
        self.uptime = self.uptime or datetime.today()
        await bot.change_presence(activity=discord.Game("Use $help!"))
        logging.info(f"We have logged in as {bot.user}!")

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return
        if isinstance(error, (commands.MissingPermissions, commands.NotOwner)):
            return await ctx.send(embed=error_embed("You do not have the permissions to use this command."))
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(embed=error_embed(f"Missing required arguments for command. Use {ctx.prefix}help [command] for example usage."))
        if (isinstance(error, (commands.BadArgument, commands.BadUnionArgument, commands.NoPrivateMessage, commands.BotMissingPermissions))):
            return await ctx.send(embed=error_embed(str(error)))
        logging.error(f"{type(error)}: {error}")
        raise error

    async def on_message(self, message):
        if message.author.bot or message.author.id in self.blacklist:
            return
        await self.process_commands(message)


logging.info("Starting up the bot.")
bot = XenonBot(
    command_prefix=command_prefixes, 
    help_command=EmbedHelpCommand(),
    intents=discord.Intents.all()
)

### Commands to load cogs ###

@bot.command(hidden=True)
@commands.is_owner()
async def load(ctx, extension):
    """Owner only administrative command used to load a cog."""
    await loading_helper(ctx, extension, "Load")

@bot.command(hidden=True)
@commands.is_owner()
async def unload(ctx, extension):
    """Owner only administrative command used to unload a cog."""
    await loading_helper(ctx, extension, "Unload")

@bot.command(hidden=True)
@commands.is_owner()
async def reload(ctx, extension):
    """Owner only administrative command used to reload a cog."""
    await loading_helper(ctx, extension, "Reload")
        
async def loading_helper(ctx, extension, function):
    """Helper function for the above three functions."""
    funct = {"Load": bot.load_extension, "Unload": bot.unload_extension, "Reload": bot.reload_extension}
    logging.info(f"Request by {ctx.author}: {function} cog {extension}.")
    try: 
        funct[function](f'cogs.{extension}')
        logging.info(f"Request to {function.lower()} cog {extension} successful.")
        return await ctx.send(f"{function}ed cog {extension}")
    except commands.ExtensionError as e:
        logging.error(f"Request to {function.lower()} cog {extension} unsuccessful. Error Type: {type(e)}.\nError Message: {e}")
        return await ctx.send(f"Failed to reload cog {extension}. Error Type: {type(e)}.\nError Message: {e}")

try:
    bot.run(token)

################################################################################
#                                 Cleanup Code                                 #
################################################################################
finally:
    bot.con.close()