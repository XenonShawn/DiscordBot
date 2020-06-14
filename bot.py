import discord
from discord.ext import commands
from os.path import join
from datetime import datetime
import logging

bot_startup = datetime.today()
fn = bot_startup

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p',
                    handlers=[
                        # Send to both stderr and file at the same time
                        logging.FileHandler(join('logs',f'{fn.day:02d}{fn.month:02d}{fn.year}.{fn.hour:02d}{fn.minute:02d}{fn.second:02d}.discordbot.log')),
                        logging.StreamHandler()
                    ])

del fn # Variable was used only to shorten the line above

logging.info("Starting up the bot.")
bot = commands.Bot(command_prefix='$')
token = 'INSERT TOKEN HERE'

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Use $help!"))
    logging.info(f"We have logged in as {bot.user}!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions) or isinstance(error, commands.NotOwner):
        return await ctx.send("You do not have the permissions to use this command.")
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send("Missing required arguments for command. Use $help [command] for example usage.")
    if isinstance(error, commands.errors.BadArgument):
        return await ctx.send(error)
    logging.error(f"{type(error)}: {error}")
    raise(error)

@bot.command()
async def uptime(ctx):
    """Return the uptime of the bot."""
    delta = datetime.today() - bot_startup
    return await ctx.send(f"{delta.days} days, {delta.seconds // 3600} hours, {delta.seconds // 60 % 60} minutes and {delta.seconds % 60} seconds")

# Commands to load cogs

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

@bot.command()
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

@bot.command()
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

cogs_to_load = ['cogs.fun', 'cogs.utilities']
for filename in cogs_to_load:
    try:
        bot.load_extension(filename)
        logging.info(f"Loaded cog {filename}.")
    except:
        logging.error(f"Failed to load cog {filename}.")
        
bot.run(token)