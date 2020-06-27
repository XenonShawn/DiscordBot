import discord
from discord.ext import commands
import pickle
import logging
from os.path import join
from datetime import date

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

    @commands.command()
    @commands.is_owner()
    async def check_nssg(self, ctx):
        """Owner only command for debugging purposes."""
        print(self.ord_dates)

    @commands.command()
    async def ord(self, ctx, day: int, month: int, year: int):
        """
        Records your ORD.

        Usage: $ord [day] [month] [year]
        """
        # Check for valid date
        try:
            self.ord_dates[ctx.author.id] = date(year, month, day)
            return await ctx.send(f"Your ORD is set to {day:02d}/{month:02d}/{year}.")
        except ValueError as e:
            return await ctx.send(str(e).capitalize()) 

    @commands.command()
    async def countdown(self, ctx, user: discord.User=None):
        """
        Return the number of days left to ORD.

        An optional user can be provided to check their number of days to ORD.
        The user being check must have provided their ORD through $ord.
        Usage: $countdown [optional: user]
        """
        user_id = user.id if user else ctx.author.id
        if user_id not in self.ord_dates:
            if user:
                return await ctx.send("That user has not indicated their ORD.")
            else:
                return await ctx.send("You have not indicated your ORD. Use $ord [day] [month] [year] to set your ORD.")
        days = (self.ord_dates[user_id] - date.today()).days
        if days > 0:
            return await ctx.send(f"{days} days left to ORD!")
        elif days == 0:
            return await ctx.send("WGT, ORDLO!")
        else:
            return await ctx.send(f"{-days} days since ORD!")
        

def setup(bot):
    bot.add_cog(nssg(bot))