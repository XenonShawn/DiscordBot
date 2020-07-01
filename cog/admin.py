import discord
from discord.ext import commands
from datetime import datetime

class admin(commands.Cog):

    def __init__(self, bot: commands.bot):
        self.bot = bot

    # Globally block DMs
    def bot_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage("DMing is not supported.")
        return True

    @commands.command()
    async def uptime(self, ctx):
        """Return the uptime of the bot."""
        delta = datetime.today() - self.bot.uptime
        return await ctx.send(f"{delta.days} days, {delta.seconds // 3600} hours, {delta.seconds // 60 % 60} minutes and {delta.seconds % 60} seconds")

    ### Check files commands ###

    ### Blacklisting Commands ###

    @commands.command(hidden=True)
    @commands.is_owner()
    async def blacklist(self, ctx, *, user: discord.User):
        """Owner only command to manually blacklist a user."""
        await self.bot.blacklist_user(ctx, user)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unblacklist(self, ctx, *, user: discord.User):
        """Owner only command to manually unblacklist a user."""
        await self.bot.unblacklist_user(ctx, user)

    ### Changing bot prefix ###

    @commands.command(name='setprefix')
    @commands.has_guild_permissions(manage_guild=True)
    async def set_server_prefix(self, ctx, prefix: str):
        """
        Sets the current server's custom prefix.

        To have a word prefix, your word must be quoted and end in a space.
        For example, $setprefix "bot ". This is because Discord removes spaces
        when sending messages, so spaces are not preserved. Multi-word prefixes have 
        to be quoted as well, eg $server_prefixes "bot com ".

        Examples:
        $setprefix . ---> .command [arguments]
        $setprefix x! ---> x!command [arguments]
        $setprefix "x! " ---> x! command [arguments]
        $setprefix "bot " ---> bot command [arguments]
        """
        return await self.bot.set_guild_prefix(ctx, prefix)

    @commands.command(name='serverprefix')
    async def view_server_prefix(self, ctx):
        """Return the list of server prefixes for this bot."""
        result = f"The bot has the following prefixes: '<@{self.bot.user.id}> ' and '{self.bot.get_guild_prefix(ctx)}'."
        return await ctx.send(result)

def setup(bot):
    bot.add_cog(admin(bot))