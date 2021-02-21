import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from cogs.helper import smart_send, Duration # Cog loading is based on where bot.py is

# I could have added a guild-specific timezones, but since I do not intend for
# this bot to be used by non-Singaporean guilds, I will not over-engineer it.
# If for some reason you are using this bot, then change the timezone or something.
# This is used as SQLite3 library spits out naive datetime instances, see below.
TIMEZONE = 8

class Utility(commands.Cog, name='utilities'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.con = bot.con
        self.loop = asyncio.get_event_loop()
        self.tasks = set()
        self.con.execute("""CREATE TABLE IF NOT EXISTS reminders (
                                guild_id    INTEGER NOT NULL,
                                channel_id  INTEGER NOT NULL,
                                message_id  INTEGER UNIQUE NOT NULL,
                                end         TIMESTAMP NOT NULL,
                                text        TEXT NOT NULL)""")
        for row in self.con.execute("SELECT * FROM reminders"):
            # SQLite3 datetime comes out timezone naive, so need to change the timezone 
            delta = (row[3].replace(tzinfo=timezone(timedelta(hours=TIMEZONE))) - datetime.now(timezone(timedelta(hours=TIMEZONE)))).total_seconds()
            self.tasks.add(self.bot.schedule_task(delta, self.end_reminder(row)))
            logging.info("Scheduled a reminder task.")
        
    def cog_unload(self):
        for task in self.tasks:
            task.cancel()

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clearchat(self, ctx: commands.Context, num: int):
        """Clears a specified number of messages in the current chatroom.
        Usage: $clearchat [num]"""
        if num < 1:
            return await ctx.send("Please input a positive integer.")

        # Double confirm clearing of messages
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ('Y','N')

        try:
            await ctx.send(f"Are you sure you want to clear {num} messages? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=10.0)
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Clear request rejected.")

        if response.content.upper() == 'Y':
            return await ctx.channel.purge(limit=num + 3)
        else:
            return await ctx.send("Clear request cancelled.")
    
    @commands.command(aliases=['count_role', 'role_count'])
    @commands.has_permissions(manage_guild=True)
    async def countrole(self, ctx, *, role: discord.Role):
        """Count the number of people with the given role in the current server."""
        return await ctx.send(f"{len(role.members)} member(s) have this role in this server.")

    @commands.command(aliases=['remind'])
    async def remindme(self, ctx, duration: Duration, *, text):
        """
        Have the bot send a reminder after a specified duration.

        Usage: $remindme [duration, X(m/h/d)] [text]
        Example: $remindme 90m Watch tv show
        Example: $remindme 8d Join game
        """
        now = datetime.now(timezone(timedelta(hours=TIMEZONE)))
        end = now + timedelta(minutes=duration)

        embed = discord.Embed(title=f"Reminder Created by {ctx.author}", 
                              description=text, 
                              colour=discord.Colour.blue(),
                              timestamp=end)
        embed.set_thumbnail(url=ctx.author.avatar_url)
        embed.add_field(name="The bot will remind all who reacted 🤚 below.", 
                        value=f"Reminding in {duration} minutes!", inline=False)
        embed.set_footer(text="Time to remind")
        message = await ctx.send(embed=embed)
        await message.add_reaction('🤚')
        
        row = (ctx.guild.id, ctx.channel.id, message.id, end, text)
        with self.con:
            self.con.execute("INSERT INTO reminders VALUES (?, ?, ?, ?, ?)", row)
        self.tasks.add(self.bot.schedule_task(duration * 60, self.end_reminder(row)))

    async def end_reminder(self, db_row):
        """Function run upon reminder timer up."""
        with self.con:
            self.con.execute("DELETE FROM reminders WHERE message_id = ?", (db_row[2],))
        self.tasks.discard(db_row[2])
        
        channel = self.bot.get_channel(db_row[1])
        if channel is None:
            return # Channel no longer exists, just ignore
        message = await channel.fetch_message(db_row[2])
        if message is None:
            return # Message no longer exists, just ignore

        users = (x.mention for x in await message.reactions[0].users().flatten() if x != self.bot.user)
        if users:
            text = f"Reminder for `{db_row[4]}`: " + ', '.join(users) + '.'
            await smart_send(channel, text)

        # Amend reminder message embed to show it is done
        embeddict = message.embeds[0].to_dict()
        embeddict['fields'][0]['value'] = "Reminded!"
        embeddict['color'] = discord.Colour.red().value
        await message.edit(embed=discord.Embed.from_dict(embeddict))


def setup(bot):
    bot.add_cog(Utility(bot))