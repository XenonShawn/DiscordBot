from datetime import datetime, date
from collections import defaultdict
import json
import asyncio
import logging
from typing import Union
from os.path import isfile
import logging

import aiohttp
import discord
from discord.ext import commands, tasks

from cogs.helper import schedule_task

NSSG_ID = 692230983650377731
CHANNEL_ID = 729654637677903926

class Date(commands.Converter):
    """Convert the input into `datetime.date` if possible."""
    async def convert(self, ctx, argument) -> date:
        for format in ("%d%m%y", "%d%m%Y", "%d %m %y", "%d %m %Y", "%d/%m/%y", "%d/%m/%Y"):
            try:
                return datetime.strptime(argument, format).date()
            except ValueError:
                pass
        return -1
        # raise commands.BadArgument("Unknown date format. A good example of a date format is 'DDMMYY', 'DD/MM/YY' or 'DD/MM/YYYY' such as '15/02/20'.")


class Nssg(commands.Cog, name='nssg'):

    def __init__(self, bot):
        logging.info("Loading NSSG cog files.")

        self.bot = bot
        self.con = bot.con

        # Ensure database exists
        self.con.execute("""CREATE TABLE IF NOT EXISTS nssg (
                                user_id INTEGER UNIQUE NOT NULL,
                                ord DATE NOT NULL)""")

        self.con.execute("""CREATE TABLE IF NOT EXISTS enlistmentmsgs (
                            msg_id      INTEGER UNIQUE NOT NULL,
                            date        TEXT    UNIQUE NOT NULL,
                            num_choices INTEGER
        )""")

        latestEnlistmentMessage = self.con.execute("SELECT date FROM enlistmentmsgs ORDER BY date DESC").fetchone()
        self.lastUpdatedJSON = date.fromisoformat(latestEnlistmentMessage[0]) if latestEnlistmentMessage else date(1, 1, 1)
        self.enlistmentmsgpooling = set()

        now = datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0)).total_seconds()
        logging.info(str(86400 - seconds_since_midnight) + " seconds to midnight.")
        # Update enlistment messages every 12am + 5 seconds
        self.task = schedule_task(self.bot.loop, 86405 - seconds_since_midnight, self.enlistmentmessages.start)

    def cog_unload(self):
        if not self.task.cancelled():
            self.task.cancel()
        self.enlistmentmessages.cancel()
    
    ################################################################################
    #                                  Commands                                    #
    ################################################################################

    @commands.command()
    async def ord(self, ctx, *, ord_date: Union[discord.Member, Date]=None):
        """
        Return how many days left to/since your ORD.
        Use $ord [day]/[month]/[year] to set your ORD.

        Example: To set your ORD to 29/02/2020, use $ord 29/02/2020
        Example: To check days to ORD, use $ord
        """
        if ord_date is None or type(ord_date) == discord.Member:
            result = self.con.execute("SELECT ord FROM nssg WHERE user_id = ?", (ord_date.id if ord_date else ctx.author.id, )).fetchone()
            if result is None:
                if ord_date:
                    return await ctx.send("That user has yet to set their ORD.")
                else:
                    return await ctx.send("You have not indicated your ORD. Use $ord [day]/[month]/[year] to set your ORD, eg $ord 10/1/21.")
                
            days = (result[0] - date.today()).days

            if days > 0: 
                await ctx.send(f"{days} day{'s' if days > 1 else ''} left to ORD!")
            elif days == 0: 
                await ctx.send("WGT, ORDLO!")
            else: 
                await ctx.send(f"{-days} day{'s' if days < -1 else ''} since ORD!")
        elif type(ord_date) == date:
            with self.con:
                self.con.execute("""INSERT INTO nssg(user_id, ord) VALUES (?, ?)
                                    ON CONFLICT(user_id) DO UPDATE SET ord=excluded.ord""",
                                    (ctx.author.id, ord_date))
                return await ctx.send(f"Your ORD is set to {ord_date.strftime('%d/%m/%Y')}")
        else:
            # Manual error handling for now
            return await ctx.send(embed=self.bot.error_embed("Unknown date format. A good date formats includes 'DDMMYY', 'DD/MM/YY' or 'DD/MM/YYYY'.\n Example: 15/02/20"))

    ################################################################################
    #                               Helper Functions                               #
    ################################################################################

    async def getEvents(self) -> dict:
        """
        Helper function used to obtain the enlistment dates from CMPB website, and store it as a json file
        for personal reference.

        This will check the CMPB website once every week to ensure that the json file is up to date. Else,
        it'll import the json file and output it as appropriate.
        """

        if (date.today() - self.lastUpdatedJSON).days >= 7 or not isfile('output.json'):
                
            # Last updated more than 7 days ago, check CMPB website again
            endpoint = 'https://www.cmpb.gov.sg/web/wcm/connect/cmpb/cmpbContent/CMPBHome/before-ns/Enlistment-dates/enlistment-dates?srv=cmpnt&source=library&cmpntname=CMPBDesign/sections/page-2-BeforeNS/enlistment-dates/NAV%20Calendar%20Events%20Json'

            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint) as response:
                    data = json.loads(await response.read())

            events = defaultdict(list)
            today = date.today()

            # Format the received data
            for event in data["calendarEventList"][1:]:

                # Skip if the event date is before current date and after 60 days
                eventDate = datetime.strptime(event['startDate'], '%b %d, %Y').date()
                if not (0 <= (eventDate - today).days <= 60):
                    continue
                
                # Ensure category isn't a public holiday (ie is a BMT enlistment date)
                category = event['categories'][event['categories'].rindex('/')+1:]
                if category != 'Public Holiday':
                    events[str(eventDate)].append(event['title'])

            # Output to a file
            with open('output.json', 'w') as f:
                f.write(json.dumps(events, indent=4))

            self.lastUpdatedJSON = date.today()
        else:
            with open('output.json', 'r') as f:
                events = json.load(f)
        return events

    def createEmbed(self, date_: date, events) -> discord.Embed:
        embed = discord.Embed(title=f"Enlistment on {date_.strftime('%d %b %Y')}", colour=discord.Colour.green())
        for i, event in enumerate(events):
            embed.add_field(name=numbers[i] + ' ' + event, value="None", inline=True)
        embed.set_footer(text="React to add yourself to the list!")
        return embed

    async def completeMessages(self):
        today = str(date.today())
        channel = await self.bot.fetch_channel(CHANNEL_ID)
        for event in self.con.execute("SELECT * FROM enlistmentmsgs WHERE date < ?", (today, )):
            try:
                message = await channel.fetch_message(event[0])
                embeddict = message.embeds[0].to_dict()
                embeddict['color'] = discord.Colour.red().value
                embeddict['footer']['text'] = "Stopped tracking."
                await message.edit(embed=discord.Embed.from_dict(embeddict))
            except discord.NotFound:
                # Message was deleted, probably intentional, nvm, next day will repost
                pass
            except discord.DiscordException as e:
                await channel.send(str(e))
            finally:
                self.con.execute("DELETE FROM enlistmentmsgs WHERE msg_id = ?", (event[0], ))
                self.con.commit()

    ################################################################################
    #                                 Main Functions                               #
    ################################################################################

    @tasks.loop(hours=24)
    async def enlistmentmessages(self):
        
        today = str(date.today())   # Dates in ISO format are comparable using "<" operators
        channel = await self.bot.fetch_channel(CHANNEL_ID)

        events = await self.getEvents()
        eventDatesSorted = sorted(events)

        for eventDate in eventDatesSorted:
            
            # Check date of event, or if event date already exists in database
            if eventDate <= today or self.con.execute("SELECT * FROM enlistmentmsgs WHERE date = ?", (eventDate, )).fetchone():
                continue
            
            # Get embed and post it
            message = await channel.send(embed=self.createEmbed(date.fromisoformat(eventDate), events[eventDate]))
            for i in range(len(events[eventDate])):
                # Add reactions
                await message.add_reaction(numbers[i])

            # Add to database
            self.con.execute("INSERT INTO enlistmentmsgs(msg_id, date, num_choices) VALUES (?, ?, ?)",
                                (message.id, eventDate, len(events[eventDate])))
            self.con.commit()

        # Clear expired events
        await self.completeMessages()

    ################################################################################
    #                                  Listeners                                   #
    ################################################################################

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id != self.bot.user.id:
            info = self.con.execute("SELECT * FROM enlistmentmsgs WHERE msg_id = ?", (payload.message_id, )).fetchone()
            if info and emojis.get(payload.emoji.name, 100) <= info[2]:
                return await self.update_members(payload, info[2])
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id != self.bot.user.id:
            info = self.con.execute("SELECT * FROM enlistmentmsgs WHERE msg_id = ?", (payload.message_id, )).fetchone()
            if info and emojis.get(payload.emoji.name, 100) <= info[2]:
                return await self.update_members(payload, info[2])
    
    async def update_members(self, payload: discord.RawReactionActionEvent, num: int):
        # Pool the messages to reduce number of times needed to edit
        if payload.message_id in self.enlistmentmsgpooling:
            return
        self.enlistmentmsgpooling.add(payload.message_id)
        await asyncio.sleep(1)

        # Need to get message instance again since reactions don't update
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        # Technically the above can result in None, but it shouldn't happen

        embeddict = message.embeds[0].to_dict()
        for i in range(num):
            content = ""
            async for user in message.reactions[i].users():
                if user != self.bot.user:
                    content += f"{user}\n"
                    if len(content) > 1500:
                        content = content[:-len(f"{user}\n")] + "..."
                        break
            embeddict['fields'][i]['value'] = content or "None"
        self.enlistmentmsgpooling.remove(payload.message_id)
        await message.edit(embed=discord.Embed.from_dict(embeddict))
        

numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
emojis = {
    '1️⃣': 1,
    '2️⃣': 2,
    '3️⃣': 3,
    '4️⃣': 4,
    '5️⃣': 5,
    '6️⃣': 6,
    '7️⃣': 7,
    '8️⃣': 8,
    '9️⃣': 9,
    '🔟': 10
}

def setup(bot):
    bot.add_cog(Nssg(bot))