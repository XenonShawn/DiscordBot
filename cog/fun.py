import discord
from discord.ext import commands
import pickle

class fun(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.emoji = emoji
        # Allowed reactions are stored by guild ID. The keys of the allowed_reacts dict is the guild ID,
        # with its value being the set of allowed reacts for that guild.
        try:
            with open('allowed_reacts.pkl', 'rb') as f:
                self.allowed_reacts = pickle.load(f)
            print("Loaded saved allowed_reacts")
        except OSError as e:
            print(e)
            self.allowed_reacts = dict()

    def cog_unload(self):
        # Special method, here used to save the allowed_reacts list
        print("Saving fun cog before shutting down...")
        with open('allowed_reacts.pkl', 'wb') as f:
            pickle.dump(self.allowed_reacts, f, pickle.HIGHEST_PROTOCOL)
        print("Saved allowed_reacts.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def add_react(self, ctx: commands.Context, text: str):
        """Adds allowed reacts to the allowed reacts list.
        Usable by users with "Manage Server" permissions only."""
        server = ctx.guild.id
        text = text.lower()
        if self.allowed_reacts.get(server) is None:
            self.allowed_reacts[server] = {text}
        else:
            self.allowed_reacts[server].add(text)
        await ctx.send(f"{text} added to the allowed reactions list.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def remove_react(self, ctx, text: str):
        """Removes allowed reacts from the allowed reacts list.
        Usable by users with "Manage Server" permissions only."""
        server = ctx.guild.id
        if len(self.allowed_reacts.get(server, set())) == 0:
            return await ctx.send("This server has no allowed reacts.")
        text = text.lower()
        if text in self.allowed_reacts[server]:
            self.allowed_reacts[server].remove(text)
            await ctx.send(f"{text} removed from the allowed reacts list.")
        else:
            await ctx.send(f"{text} is not in the allowed reacts list.")

    @commands.command()
    async def allowedreacts(self, ctx):
        """Prints out a list of allowed reacts for use in the $react command."""
        server = ctx.guild.id
        if len(self.allowed_reacts.get(server, set())) == 0:
            return await ctx.send("This server has no allowed reacts.")
        return await ctx.send("Allowed reactions: " + ', '.join(self.allowed_reacts[server]) + ".")

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
    async def react(self, ctx, text: str, message_id: str):
        """Sets the reacts of a message, if allowed in the allowed reactions list.
        'text' is the reaction text and 'message' is the message_id or the link of the message to be reacted.
        Example Usage: $react okboomer https://discordapp.com/channels/655024044/7078986/716643449"""
        server = ctx.guild.id
        message = await ctx.channel.fetch_message(message_id[-18:])
        if self.allowed_reacts.get(server) is not None and text in self.allowed_reacts[server]:
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

    @commands.command()
    @commands.is_owner()
    async def check_emojis(self, ctx):
        """Owner only command for debugging purposes."""
        return await ctx.send(str(self.allowed_reacts))
        

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
    'u1': '🇺',
    'v1': '🇻',
    'w1': '🇼',
    'x1': '🇽',
    'y1': '🇾',
    'z1': '🇿',
    '!1': '❗',
    '?1': '❓'
}

def setup(bot):
    bot.add_cog(fun(bot))