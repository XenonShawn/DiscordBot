import logging
import sqlite3
from collections import Counter

import discord
from discord.ext import commands

def lowercase_string(argument):
    return argument.lower()

class Fun(commands.Cog, name='fun'):

    def __init__(self, bot):
        self.bot = bot
        self.emoji = emoji
        self.con = bot.con
        self.con.execute("""CREATE TABLE IF NOT EXISTS allowedreacts (
                                guild_id INTEGER NOT NULL,
                                word TEXT NOT NULL,
                                UNIQUE(guild_id, word))""")

    def cog_unload(self):
        pass

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def addreact(self, ctx, text: lowercase_string):
        """
        Adds allowed reacts to the allowed reacts list.
        Usable by users with "Manage Server" permissions only.
        """
        if len(text) > 20:
            return await ctx.send("Reaction cannot exceed 20 characters.")
        try:
            with self.con:
                self.con.execute("INSERT INTO allowedreacts VALUES(?, ?)", (ctx.guild.id, text))
        except sqlite3.IntegrityError:
            # Technically sending in PMs can also trigger this
            return await ctx.send("That word is already in the allowed reactions list.")
        else:
            return await ctx.send(f"{text} added to the allowed reactions list.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def removereact(self, ctx, text: str):
        """
        Removes allowed reacts from the allowed reacts list.
        Usable by users with "Manage Server" permissions only.
        """
        with self.con:
            n = self.con.execute("DELETE FROM allowedreacts WHERE guild_id = ? AND word = ?", (ctx.guild.id, text)).rowcount
        if n == 0:
            return await ctx.send(f"{text} is not in the allowed reactions list.")
        elif n == 1:
            return await ctx.send(f"{text} removed from the allowed reactions list.")
        else:
            logging.error("Deleted more than one reaction for removereact")
            return await ctx.send("An error has occured.")

    @commands.command()
    async def allowedreacts(self, ctx):
        """Prints out a list of allowed reacts for use in the $react command."""

        text = "Allowed Reacts: "
        for row in self.con.execute("SELECT word FROM allowedreacts WHERE guild_id = ?", (ctx.guild.id, )):
            text += f"`{row[0]}`, "
        if text == "Allowed Reacts: ":
            text = "This server has no allowed reacts."
        else:
            text = text[:-2] + '.'
        return await ctx.send(text)

    async def textemoji(self, message: discord.Message, string: str):
        """Converts the string to unicode emojis."""
        string = string.replace('ok', '🆗', 1)        
        repeats = Counter()
        for ch in string:
            try:
                await message.add_reaction(emoji[ch][repeats[ch]])
                repeats[ch] += 1
            except IndexError:
                continue
    
    @commands.command()
    async def react(self, ctx, text: lowercase_string, message: discord.Message):
        """Sets the reacts of a message, if allowed in the allowed reactions list.
        'text' is the reaction text and 'message' is the message_id or the link of the message to be reacted.
        Example Usage: $react okboomer https://discordapp.com/channels/655024044/7078986/716643449"""

        if self.con.execute("SELECT * FROM allowedreacts WHERE guild_id = ? AND word = ?", (ctx.guild.id, text)).fetchone():
            await ctx.message.delete()
            return await self.textemoji(message, text)
        else:
            return await ctx.send(f"`{text}` is not an allowed reaction.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def adminreact(self, ctx, text: lowercase_string, message: discord.Message):
        """Sets the reacts of a message. Skips checking allowed reactions.
        'text' is the reaction text and 'message' is the message_id of the message to be reacted.
        Example Usage: $react omg 123456789"""
        await ctx.message.delete()
        return await self.textemoji(message, text)

emoji = {
    'a': ['🇦', '🅰️'], 
    'b': ['🇧', '🅱️'], 
    'c': ['🇨', '©️'], 
    'd': ['🇩'], 
    'e': ['🇪'], 
    'f': ['🇫'], 
    'g': ['🇬'], 
    'h': ['🇭'], 
    'i': ['🇮', 'ℹ️'], 
    'j': ['🇯'], 
    'k': ['🇰'], 
    'l': ['🇱'], 
    'm': ['🇲', 'Ⓜ️'],
    'n': ['🇳'], 
    'o': ['🇴', '🅾️', '⭕'], 
    'p': ['🇵', '🅿️'], 
    'q': ['🇶'], 
    'r': ['🇷', '®️'], 
    's': ['🇸', '💲'], 
    't': ['🇹', '✝'], 
    'u': ['🇺'], 
    'v': ['🇻'], 
    'w': ['🇼'], 
    'x': ['🇽'], 
    'y': ['🇾'], 
    'z': ['🇿'], 
    '!': ['❗'], 
    '?': ['❓'], 
    ' ': ['🟦'],  
    '1': ['1️⃣'], 
    '2': ['2️⃣'], 
    '3': ['3️⃣'], 
    '4': ['4️⃣'], 
    '5': ['5️⃣'], 
    '6': ['6️⃣'], 
    '7': ['7️⃣'], 
    '8': ['8️⃣'], 
    '9': ['9️⃣'],
    '🆗': ['🆗']
}

def setup(bot):
    bot.add_cog(Fun(bot))
    