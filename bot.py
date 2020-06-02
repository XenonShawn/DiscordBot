import discord
from discord.ext import commands
from os import listdir
import logging

logging.basicConfig(level=logging.INFO)

bot = commands.Bot(command_prefix='$')
token = "INSERT TOKEN HERE"

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Use $help!"))
    print(f"We have logged in as {bot.user}!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("You do not have the permissions to use this command.")
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send("Missing required arguments for command. Use $help [command] for example usage.")
    if isinstance(error, commands.errors.BadArgument):
        return await ctx.send(error)
    print(type(error), error)
    raise(error)

# Commands to load cogs

@bot.command(help="Administrative command used to load a cog.")
@commands.is_owner()
async def load(ctx: commands.Context, extension):
    print(f"Request by {ctx.author}: Load cog {extension}.")
    try:
        bot.load_extension(f'cogs.{extension}')
        await ctx.send(f"Loaded cog {extension}.")
    except commands.ExtensionError as e:
        await ctx.send(f"Failed to load cog {extension}")
        print(e)

@bot.command(help="Administrative command used to unload a cog.")
@commands.is_owner()
async def unload(ctx: commands.Context, extension):
    print(f"Request by {ctx.author}: Unload cog {extension}.")
    try:
        bot.unload_extension(f'cogs.{extension}')
        await ctx.send(f"Unloaded cog {extension}")
    except commands.ExtensionNotLoaded as e:
        await ctx.send(f"Failed to unload cog {extension}")
        print(e)

@bot.command(help="Administrative command used to reload a cog.")
@commands.is_owner()
async def reload(ctx: commands.Context, extension):
    print(f"Request by {ctx.author}: Reload cog {extension}.")
    try:
        bot.unload_extension(f'cogs.{extension}')
    except commands.ExtensionNotLoaded as e:
        await ctx.send(f"Failed to unload cog {extension} during reload.")
        print(e)
        return
    try:
        bot.load_extension(f'cogs.{extension}')
        await ctx.send(f"Reloaded cog {extension}")
    except commands.ExtensionError as e:
        await ctx.send(f"Failed to load cog {extension} during reload.")

cogs_to_load = ['cogs.fun', 'cogs.utilities', 'cogs.todo']
for filename in cogs_to_load:
    try:
        bot.load_extension(filename)
        print(f"Loaded cog {filename}.")
    except:
        print(f"Failed to load cog {filename}.")
        
bot.run(token)