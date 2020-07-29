import discord
from discord.ext import commands
import pickle
import logging
from os.path import join
from datetime import date as date_
import asyncio

class nssg(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        logging.info("Loading NSSG cog files.")
        try:
            with open(join('data', 'ord_date.pkl'), 'rb') as f:
                self.ord_dates = pickle.load(f)
            logging.info("Loaded saved ORD dates.")
        except OSError as e:
            # Unable to find the file
            logging.warning(f"{type(e)}: {e}")
            self.ord_dates = dict()
        self.enlistmentmessages = set()
        self.enlistmentmsgpooling = dict()

    def cog_unload(self):
        logging.info("Saving NSSG cog before shutting down...")
        with open(join('data', 'ord_date.pkl'), 'wb') as f:
            pickle.dump(self.ord_dates, f, pickle.HIGHEST_PROTOCOL)
        logging.info("Saved ORD dates.")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def check_nssg(self, ctx):
        """Owner only command for debugging purposes."""
        print(self.ord_dates)

    @commands.command()
    async def ord(self, ctx, *date: int):
        """
        Return how many days left to/since your ORD.
        Use $ord [day] [month] [year] to set your ORD.

        Example: To set your ORD to 29/02/2020, use $ord 29 02 2020
        Example: To check days to ORD, use $ord
        """
        if not len(date):
            if ctx.author.id not in self.ord_dates:
                return await ctx.send("You have not indicated your ORD. Use $ord [day] [month] [year] to set your ORD.")

            days = (self.ord_dates[ctx.author.id] - date_.today()).days
            if days > 0: await ctx.send(f"{days} days left to ORD!")
            elif days == 0: await ctx.send("WGT, ORDLO!")
            else: await ctx.send(f"{-days} days since ORD!")

        elif len(date) == 3:
            try:
                year = date[2] if date[2] > 50 else date[2] + 2000
                self.ord_dates[ctx.author.id] = date_(year, date[1], date[0])
                return await ctx.send(f"Your ORD is set to {date[0]:02d}/{date[1]:02d}/{year}")
            except ValueError as e:
                return await ctx.send(str(e).capitalize())
        else:
            await ctx.send("Inproper parameters to set your ORD. Use $ord [day] [month] [year] to set your ORD.")

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def enlistment(self, ctx, *, text: str):
        """
        Create an enlistment message.
        """
        await ctx.message.delete()

        embed = discord.Embed(title=f"Enlistment on {text}", colour=discord.Colour.green())
        embed.set_footer(text="React '😭' to add yourself to the list!")
        message = await ctx.send(embed=embed)
        await message.add_reaction('😭')

        self.enlistmentmessages.add(message.id)

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def stop(self, ctx, message: discord.Message):
        """
        Stop tracking an enlistment message.
        """
        if message.id not in self.enlistmentmessages:
            return await ctx.send("No such enlistment message found.")
        await ctx.message.delete()

        embeddict = message.embeds[0].to_dict()
        embeddict['footer']['text'] = "Stopped tracking."
        embeddict['color'] = discord.Colour.red().value
        await message.edit(embed=discord.Embed.from_dict(embeddict))
        self.enlistmentmessages.remove(message.id)

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def restart(self, ctx, message: discord.Message):
        """
        Restart tracking for an enlistment message.
        """
        if (message.author != self.bot.user or len(message.embeds) != 1 
            or not message.embeds[0].title.startswith("Enlistment on ")):
            return await ctx.send("Not an enlistment message")
        
        embeddict = message.embeds[0].to_dict()
        embeddict['footer']['text'] = "React '😭' to add yourself to the list!"
        embeddict['color'] = discord.Colour.green().value
        await message.edit(embed=discord.Embed.from_dict(embeddict))

        self.enlistmentmessages.add(message.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id in self.enlistmentmessages and payload.emoji.name == '😭':
            return await self.update_members(payload)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id in self.enlistmentmessages and payload.emoji.name == '😭':
            return await self.update_members(payload)
    
    async def update_members(self, payload: discord.RawReactionActionEvent):
        try:
            if self.enlistmentmsgpooling.get(payload.message_id, False):
                return
            self.enlistmentmsgpooling[payload.message_id] = True
        
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            # Technically the above can result in None, but it shouldn't happen

            embeddict = message.embeds[0].to_dict()
            content = str()

            # Correct reaction should be in slot 0
            async for user in message.reactions[0].users():
                if user == self.bot.user:
                    continue
                content += f"{user}\n"
                if len(content) > 2000:
                    content = content[:-len(f"{user}\n")] + "..."
                    break
            embeddict['description'] = content
            await message.edit(embed=discord.Embed.from_dict(embeddict))
        finally:
            self.enlistmentmsgpooling[payload.message_id] = False


def setup(bot):
    bot.add_cog(nssg(bot))