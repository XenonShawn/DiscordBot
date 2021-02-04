import discord
from discord.ext import commands
import logging
import sqlite3

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

    async def textemoji(self, ctx, message: discord.Message, string: str):
        """Converts the string to unicode emojis."""
        # Ugly code
        string = string.lower()
        repeats = dict()
        ok = True
        i = 0
        while i < len(string):
            letter = string[i]
            # Checks for OK
            if ok and letter == 'o':
                if string[i:].startswith('ok'):
                    # Set ok flag to false so it doesn't get called again
                    ok = False
                    await message.add_reaction(emoji['ok'])
                    i += 2
                    continue
            # Checks if letter was used before.
            repeats[letter] = 1 + repeats.get(letter, 0)
            try:
                await message.add_reaction(emoji[letter + str(repeats[letter])])
            except KeyError:
                i += 1
                continue
            i += 1
        # return await ctx.message.delete()
    
    @commands.command()
    async def react(self, ctx, text: str, message: discord.Message):
        """Sets the reacts of a message, if allowed in the allowed reactions list.
        'text' is the reaction text and 'message' is the message_id or the link of the message to be reacted.
        Example Usage: $react okboomer https://discordapp.com/channels/655024044/7078986/716643449"""

        if self.con.execute("SELECT * FROM allowedreacts WHERE guild_id = ? AND word = ?", (ctx.guild.id, text)).fetchone():
            return await self.textemoji(ctx, message, text)
        else:
            return await ctx.send(f"{text} is not an allowed reaction.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def adminreact(self, ctx, text: str, message_id: str):
        """Sets the reacts of a message. Skips checking allowed reactions.
        'text' is the reaction text and 'message' is the message_id of the message to be reacted.
        Example Usage: $react omg 123456789"""
        message = await ctx.channel.fetch_message(message_id[-18:])
        return await self.textemoji(ctx, message, text)

emoji = {
    'a1': '🇦',
    'a2': '🅰️',
    'b1': '🇧',
    'b2': '🅱️',
    'c1': '🇨',
    'c2': '©️',
    'd1': '🇩',
    'e1': '🇪',
    'f1': '🇫',
    'g1': '🇬',
    'h1': '🇭',
    'i1': '🇮',
    'i2': 'ℹ️',
    'j1': '🇯',
    'k1': '🇰',
    'l1': '🇱',
    'm1': '🇲',
    'm2': 'Ⓜ️',
    'n1': '🇳',
    'o1': '🇴',
    'o2': '🅾️',
    'o3': '⭕',
    'ok': '🆗',
    'p1': '🇵',
    'p2': '🅿️',
    'q1': '🇶',
    'r1': '🇷',
    'r2': '®️',
    's1': '🇸',
    's2': '💲',
    't1': '🇹',
    't2': '✝️',
    'u1': '🇺',
    'v1': '🇻',
    'w1': '🇼',
    'x1': '🇽',
    'y1': '🇾',
    'z1': '🇿',
    '!1': '❗',
    '?1': '❓',
    ' 1': '🟦',
    '11': '1️⃣', 
    '21': '2️⃣',
    '31': '3️⃣',
    '41': '4️⃣',
    '51': '5️⃣',
    '61': '6️⃣',
    '71': '7️⃣',
    '81': '8️⃣',
    '91': '9️⃣'
}

def setup(bot):
    bot.add_cog(Fun(bot))