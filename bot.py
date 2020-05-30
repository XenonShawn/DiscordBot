import discord
from discord.ext import commands
from os import listdir

bot = commands.Bot(command_prefix='$')
token = 'xxx'

async def is_owner(ctx):
    return ctx.author.id == xxx

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Use $help!"))
    print(f"We have logged in as {bot.user}!")

# Commands to load cogs

@bot.command(help="Administrative command used to load a cog.")
@commands.check(is_owner)
async def load(ctx: commands.Context, extension):
    try:
        bot.load_extension(f'cogs.{extension}')
        print(f"Request by {ctx.author}: Loaded cog {extension}.")
        await ctx.send(f"Loaded cog {extension}.")
    except:
        await ctx.send(f"Failed to load cog {extension}")

@bot.command(help="Administrative command used to unload a cog.")
@commands.check(is_owner)
async def unload(ctx: commands.Context, extension):
    try:
        bot.unload_extension(f'cogs.{extension}')
        print(f"Request by {ctx.author}: Unloaded cog {extension}.")
        await ctx.send(f"Unloaded cog {extension}")
    except:
        await ctx.send(f"Failed to unload cog {extension}")

@bot.command(help="Administrative command used to reload a cog.")
@commands.check(is_owner)
async def reload(ctx: commands.Context, extension):
    try:
        bot.unload_extension(f'cogs.{extension}')
    except:
        await ctx.send(f"Failed to unload cog {extension} during reload.")
        return
    try:
        bot.load_extension(f'cogs.{extension}')
        print(f"Request by {ctx.author}: Reloaded cog {extension}.")
        await ctx.send(f"Reloaded cog {extension}")
    except:
        await ctx.send(f"Failed to load cog {extension} during reload.")

async def error_message(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You do not have the permissions to use this command.")

@load.error
async def load_error(ctx, error):
    await error_message(ctx, error)

@unload.error
async def unload_error(ctx, error):
    await error_message(ctx, error)

@reload.error
async def reload_error(ctx, error):
    await error_message(ctx, error)


# Load all cogs upon initialisation of bot
for filename in listdir('cogs'):
    if filename.endswith('.py'):
        try:
            bot.load_extension(f'cogs.{filename[:-3]}')
            print(f"Loaded cog {filename}.")
        except:
            print(f"Failed to load cog {filename}.")


bot.run(token)