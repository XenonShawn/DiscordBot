import discord
from discord.ext import commands

class fun(commands.Cog):

    async def delete_msg(self, ctx: commands.Context):
        """Used to delete a message after an emote command."""
        await ctx.message.delete()

    @commands.command()
    async def hello(self, ctx: commands.Context):
        """Says hello!"""
        await ctx.send(f"Hello, {ctx.author}"[:-5] + "!")

    @commands.command()
    async def oksir(self, ctx: commands.Context, message: discord.Message):
        """Sets the reacts to a message to be OKSIR.
        The ID of the message has to be provided as an argument.
        Usage: $oksir [message id]"""
        emojis = ['🆗', '🇸', '🇮', '🇷']
        for emoji in emojis:
            await message.add_reaction(emoji)
        await self.delete_msg(ctx)
    
    @commands.command()
    async def wgtordlo(self, ctx: commands.Context, message: discord.Message):
        """Sets the reacts to a message to be wgtordlo.
        The ID of the message has to be provided as an argument.
        Usage: $wgtordlo [message id]"""
        emojis = ['🇼', '🇬', '🇹', '🇴', '🇷', '🇩', '🇱', '🅾']
        for emoji in emojis:
            await message.add_reaction(emoji)
        await self.delete_msg(ctx)

    @commands.command()
    async def oksgt(self, ctx: commands.Context, message: discord.Message):
        """Sets the reacts to a message to be oksgt.
        The ID of the message has to be provided as an argument.
        Usage: $oksgt [message id]"""
        emojis = ['🆗', '🇸', '🇬', '🇹']
        for emoji in emojis:
            await message.add_reaction(emoji)
        await self.delete_msg(ctx)

    @commands.command()
    async def okboomer(self, ctx: commands.Context, message: discord.Message):
        # Credits to blazefrost of SGExams
        """Sets the reacts to a message to be okboomer.
        The ID of the message has to be provided as an argument.
        Usage: $oksboomer [message id]"""
        emojis = ['🆗', '🇧', '🅾️', '🇴', '🇲', '🇪', '🇷']
        for emoji in emojis:
            await message.add_reaction(emoji)
        await self.delete_msg(ctx)

def setup(bot):
    bot.add_cog(fun(bot))