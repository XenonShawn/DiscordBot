import discord
from discord.ext import commands
import pickle
import logging
from os.path import join
from datetime import date as date_

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
                self.ord_dates[ctx.author.id] = date_(date[2], date[1], date[0])
                return await ctx.send(f"Your ORD is set to {date[0]:02d}/{date[1]:02d}/{date[2]}")
            except ValueError as e:
                return await ctx.send(str(e).capitalize())
        else:
            await ctx.send("Inproper parameters to set your ORD. Use $ord [day] [month] [year] to set your ORD.")
        

def setup(bot):
    bot.add_cog(nssg(bot))