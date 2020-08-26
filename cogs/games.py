import discord
from discord.ext import commands
import logging
import pickle as pkl
from os.path import join, isfile, isdir
from os import listdir
from collections import defaultdict
import asyncio
import random

class PositiveInt(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            n = int(argument)
            if n < 1:
                raise ValueError
            return n
        except ValueError:
            raise commands.BadArgument("Argument provided is not a positive integer.")

class GamesError(commands.errors.CommandError):
    pass

def specialisedDict():
    return dict(channel=0, score=defaultdict(int))

def gamesDict():
    return [None,   # discord.Message => The game's signup message
            False,  # bool => Whether the game is accepting signups
            set()]  # set => Set of players who signed up for the game

class Games(commands.Cog, name='games'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.embed_pooling = defaultdict(bool) # Used to group edits to embeds together. See embed_editor_helper
        self.games_info = defaultdict(gamesDict) # Key is guild Id
        self.prefix = self.bot.get_guild_prefix # Used in help commands
        logging.info("Attempting to load designated games channel.")
        try:
            with open(join('data', 'games_data.pkl'), 'rb') as f:
                self.data = defaultdict(specialisedDict, pkl.load(f))
            logging.info("Loaded designated games channels.")
        except OSError as e:
            # Unable to find the file
            logging.warning(f"{type(e)}: {e}")
            self.data = defaultdict(specialisedDict)
        self.word_placing = ('1st', '2nd', '3rd', 
                             '4th', '5th', '6th', 
                             '7th', '8th', '9th')
        self.alphabet = 'abcdefghijklmnopqrstuvwxyz'
        
    def cog_unload(self):
        logging.info("Saving games information before unloading of cog.")
        with open(join('data', 'games_data.pkl'), 'wb') as f:
            pkl.dump(dict(self.data), f)
        logging.info("Saved games information.")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def check_games(self, ctx):
        """Owner-only command for debugging purposes."""
        print(self.data)
        print(self.games_info)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, GamesError):
            await ctx.send(str(error))

    ############################################################################
    #Functions relating to self.data, ie Games channel settings and scoreboards#
    ############################################################################

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def game_channel(self, ctx, *, channel: discord.TextChannel=None):
        """
        Return the set game channel is a text channel is not provided.
        Else, set the provided text channel as the new games channel.
        """
        if channel is None:
            channel_id = self.data[ctx.guild.id]['channel']
            if channel_id is None:
                return await ctx.send("There is no games channel for this server.")
            return await ctx.send(f"The current games channel is {self.bot.get_channel(channel_id)}.")
        self.data[ctx.guild.id]['channel'] = channel.id
        return await ctx.send(f"The games channel is now set to {channel}")

    @commands.command()
    async def scoreboard(self, ctx, member: discord.Member=None):
        """
        Return the user's cumulative score from winning games in this server.
        If another 'member' is provided, their score would be provided instead.
        """
        member = member or ctx.author
        await ctx.send(f"{member} has a score of {self.data[ctx.guild.id]['score'][member.id]}.")

    @commands.command()
    async def highscore(self, ctx, num: PositiveInt=5):
        """Return the top `num` people in the server in terms of score, up to 9 people."""
        num = min(num, len(self.data[ctx.guild.id]['score']), 9)
        if not num:
            return await ctx.send("Nobody has a score yet.")
        lst = sorted(self.data[ctx.guild.id]['score'].items(), key=lambda x:x[1], reverse=True)
        result = str()
        for i in range(num):
            result += f"{self.bot.get_user(lst[i][0])} - {lst[i][1]} points\n"
        return await ctx.send(result)

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def changescore(self, ctx, num: int, *, user: discord.Member):
        """Change the score of a specified user."""
        self.data[ctx.guild.id]['score'][user.id] += num
        return await ctx.send(f"{user}'s score has been changed to {self.data[ctx.guild.id]['score'][user.id]}.")
        
    ############################################################################
    #              Commands relating to helper function for games              #
    ############################################################################

    @commands.group()
    async def signups(self, ctx: commands.Context):
        """Used to start games in the designated games channel."""
        if ctx.invoked_subcommand is None:
            if ctx.subcommand_passed is None:
                # No subcommand passed at all
                return await ctx.send(f"Use '{self.prefix(ctx)}help signups' for more information.")
            else:
                # Invalid subcommand passed
                return await ctx.send("No such game exists.")
        else:
            if ctx.channel.id != self.data[ctx.guild.id]['channel']:
                raise GamesError("Games can only be played in the designated channel.")                
    
    def _existing_game(self, ctx):
        if self.games_info[ctx.guild.id][1]:
            raise GamesError("Only one game can be played at a time.")

    async def signups_helper(self, ctx, game: str, minimum: int=2, maximum: int=50, rounds: int=1) -> bool:
        """Helper function for signups. Returns `True` if game can start, `False` if cancelled. """
        guild = ctx.guild.id #`guild` is actually the guild's id, but using guild to shorten the variable
        # Check if there is an existing game
        self._existing_game(ctx)

        # Creation of embed to start signups
        embed = discord.Embed(title=f"Game of '{game.capitalize()}' by {ctx.author}",
                              description=f"Sign up by reacting 🙋‍♂️ to this message!\n{rounds} Rounds\nMinimum Players: {minimum}\nMaximum Players: {maximum}",
                              color=discord.Colour(random.randint(0, 16777215)))
        embed.add_field(name="Current Signups", value='None', inline=True)
        embed.set_footer(text=f"React ▶️ to close signups and start the game or react ⏹️ to cancel the game.\nOnly the host or server moderators can start or cancel the game.")
        self.games_info[guild][0] = await ctx.send(embed=embed)

        reactions = ('🙋‍♂️', '▶️', '⏹️')
        for emoji in reactions:
            await self.games_info[guild][0].add_reaction(emoji)
        self.games_info[guild][1] = True
        
        # Not sure if it is a bug, but somehow the bot when it reacts the stop button,
        # can stop the game. No idea how, but just to resolve it:
        await asyncio.sleep(1)

        # Wait for signal to start or cancel game
        def stop_signups_check(reaction, user:discord.Member):
            return (reaction.emoji in ['▶️', '⏹️']
                    and reaction.message.id == self.games_info[guild][0].id
                    and (user.id == ctx.author.id 
                        or ctx.channel.permissions_for(user).manage_guild))
        while True:
            signal, user = await self.bot.wait_for('reaction_add', check=stop_signups_check)
            if signal.emoji == '▶️':
                player_count = len(self.games_info[guild][2])
                # Check if number of players fits the requirement
                if player_count >= minimum and player_count <= maximum:
                    self.games_info[guild][1] = False # Ensure that number of players don't change
                    await ctx.send(f"Request by {user}: Starting Game")
                    return True
                else:
                    await ctx.send(f"Recevied request to start game by {user}, but number of players does not meet requirement.")
            elif signal.emoji == '⏹️':
                await ctx.send(f"Game cancelled by {user}.")
                self.games_info[guild] = gamesDict()
                return False
            else:
                raise Exception # Shouldn't happen by the nature of the above code
    
    async def embed_editor(self, guild):
        """
        This pools the updates together to prevent the bot from being rate limited.
        The embed for the games signup message is updated 3 seconds after the
        first signal to update is sent.
        """
        if self.embed_pooling:
            return
        self.embed_pooling = True
        await asyncio.sleep(3.0)
        current_embed = self.games_info[guild.id][0].embeds[0].to_dict()
        current_embed['fields'][0]['value'] = '\n'.join(f'{p}' for p in self.games_info[guild.id][2]) or "None"
        self.embed_pooling = False
        await self.games_info[guild.id][0].edit(embed=discord.Embed.from_dict(current_embed))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if (self.games_info[user.guild.id][1] # Whether signups are open
            and reaction.emoji == '🙋‍♂️' 
            and reaction.message.id == self.games_info[user.guild.id][0].id):

            self.games_info[user.guild.id][2].add(user)
            return await self.embed_editor(user.guild)
    
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if (self.games_info[user.guild.id][1]
            and reaction.emoji == '🙋‍♂️' 
            and reaction.message.id == self.games_info[user.guild.id][0].id):
            
            self.games_info[user.guild.id][2].remove(user)
            return await self.embed_editor(user.guild)

    async def finish_game(self, ctx: commands.Context, score: dict):
        """
        Output the results of the game played in a scoreboard manner. This coroutine
        automativally gives points to everyone in first place and clears the games
        data in `self.games_info`. `ctx` should be the context of the signups message
        and `score` should be a dictionary of `discord.Member`s as keys and `int`s
        as the repective values.
        """
        # Print out scoreboard, and winner, then give the winners their points
        scoreboard = sorted(score.items(), key=lambda x:x[1], reverse=True)
        result = "**SCOREBOARD:**\n"
        condition = min(len(scoreboard), 9)

        # Find up to the 9th place
        # ranking_index[i] will give the index of the first person in the (i+1)th place
        ranking_index = [0]

        for i in range(1, len(scoreboard)):
            if scoreboard[i][1] == scoreboard[i-1][1]:
                continue
            ranking_index.append(i)
            if i >= condition: # Only want up to the 9th place
                break
        else:
            ranking_index.append(len(scoreboard))
        
        # Construct results of game and send to channel
        for i in range(len(ranking_index) - 1):
            result += (self.word_placing[i] 
                      + f" place - {scoreboard[i][1]} points - "
                      + ', '.join(str(x[0]) for x in scoreboard[ranking_index[i]:ranking_index[i+1]])
                      + '\n')

        # Give points to everyone in first place
        for person in scoreboard[ranking_index[0]:ranking_index[1]]:
            self.data[ctx.guild.id]['score'][person[0].id] += 1

        result += "Players in first place have earned one point each."
        await ctx.send(result)
        # Clear the database
        self.games_info[ctx.guild.id] = gamesDict()


    ############################################################################
    #                                Games Code                                #
    ############################################################################

    @signups.command(name='fishing')
    async def _signups_fishing(self, ctx: commands.Context, num_rounds: PositiveInt=5):
        """Starts the fishing game with a specified number of rounds.

        A minimum of 2 players is required.
        
        When each round starts, the bot will wait a random amount of time before
        sending a message that says "There is a tug on the fishing rod!". The
        first player to type "catch" will receive a point for that round.
        """
        # Start signups:
        status = await self.signups_helper(ctx, 'fishing', rounds=num_rounds)
        if not status:
            return None

        scoreboard = defaultdict(int)
        for i in range(num_rounds):
            await asyncio.sleep(5 * random.random() + 5)
            await ctx.send(f"Round {i+1} of {num_rounds}: There is a tug on the fishing rod! Type 'catch' to catch the fish!")

            def catch_check(message):
                return (message.content.lower() == "catch" 
                        and message.author in self.games_info[ctx.guild.id][2])
            try:
                message = await self.bot.wait_for('message', check=catch_check, timeout=7)
                scoreboard[message.author] += 1
                result = f"{message.author} caught the fish!\n"
            except asyncio.TimeoutError:
                result = "Nobody caught the fish!\n"
            if i == num_rounds - 1:
                await ctx.send(result + "Ending the game...")
            else:
                await ctx.send(result + "Moving to the next round...")
        
        return await self.finish_game(ctx, scoreboard)
                               
    @signups.command(name='fishwords', aliases=['fishingwords'])
    async def _signups_fishwords(self, ctx, num_rounds: PositiveInt=5, min_length: PositiveInt=8, max_length: PositiveInt=12):
        """Starts the fishing for words game with a specified number of rounds.

        A minimum of 2 players is required.
        
        When each round starts, the bot will wait a random amount of time before
        sending a message that contains three to five words (of random characters 
        of the alphabet). The random words will have a length between 8 and 12 
        characters, inclusive. The first player to type one of the words will 
        receive points equal to the length of the word they typed.
        """
        # Start signups:
        if not await self.signups_helper(ctx, 'fishing for words', rounds=num_rounds):
            return None

        def randWord(min_len=8, max_len=12):
            word_length = random.randint(min_len, max_len)
            word = str()
            for _ in range(word_length):
                word += self.alphabet[random.randint(0, 25)]
            return word

        scoreboard = defaultdict(int)
        for i in range(num_rounds):
            await asyncio.sleep(5 * random.random() + 3)
            send_msg = f"Round {i+1} of {num_rounds}: Words are:**\n"
            words = tuple(randWord(min_length, max_length) for _ in range(random.randint(3, 5)))
            await ctx.send(send_msg + '\n'.join(words) + '**')

            def catch_check(message):
                return (message.content.lower() in words
                        and message.author in self.games_info[ctx.guild.id][2])
            try:
                message = await self.bot.wait_for('message', check=catch_check, timeout=7)
                scoreboard[message.author] += len(message.content)
                result = f"{message.author} typed {message.content}!\n"
            except asyncio.TimeoutError:
                result = "Nobody typed the words in time!\n"
            if i == num_rounds - 1:
                await ctx.send(result + "Ending the game...")
            else:
                await ctx.send(result + "Moving to the next round...")
        
        return await self.finish_game(ctx, scoreboard)

    @commands.command()
    async def hangman(self, ctx: commands.Context, category = None):
        """
        Starts a game of Hangman, Singaporean style. No signups is required.
        No points are given to the 'winner' of the game.
        """
        # Check if there is an existing game
        self._existing_game(ctx)

        # Get hangman word from category
        choice = self.hangman_choose(category)
        self.games_info[ctx.guild.id][1] = True
        guessed = set()
        comparison = set()
        for letter in choice:
            if letter.isalpha():
                comparison.add(letter)
        
        category = category.capitalize() if category else "Random"

        def produce_embed(description, colour):
            hangman = (
                '💔💀',
                '1️⃣😭', 
                '2️⃣😢', 
                '3️⃣😠',
                '4️⃣😓',
                '5️⃣😅',
                '6️⃣😄'
            )
            embed = discord.Embed(title=f"Game of Hangman ({category})", description=description, color=colour)
            n = 6 - len(guessed - comparison) # Number of chances left
            embed.add_field(name=hangman[n] + f" {n} chances left!",
                            value=f"`{' '.join(guessed)}`")
            return (embed, n)
        
        colour = {
            True: discord.Colour.green(), # True meaning correct response
            False: discord.Colour.red() # False meaning incorrect response
        }
        status = True
        description = "Game started!"

        while True:
            display_words = '\n`'
            for letter in choice:
                if letter in guessed or not letter.isalpha():
                    display_words += f"{letter} "
                else:
                    display_words += "_ "
            display_words = display_words[:-1] + '`'

            embed, chances_left = produce_embed(description + display_words, colour[status])
            await ctx.send(embed=embed)

            if chances_left <= 0:
                result = 'lose'; break

            # Receive response
            def hangman_check(message: discord.Message):
                content = message.content.lower()
                return (message.channel.id == self.data[ctx.guild.id]['channel'] 
                        and (content == choice 
                            or len(content) == 1 
                                and content.isalpha() 
                                and content not in guessed
                            )
                       )
            try:
                message = await self.bot.wait_for('message', check=hangman_check, timeout=120)
            except asyncio.TimeoutError:
                result = 'timeout'; break
            
            content = message.content.lower()
            if content == choice:
                result = 'win'; break

            # If not, then the message was an unguessed character
            guessed.add(content)
            if guessed.issuperset(comparison):
                result = 'win'; break

            # If not, then the game has not ended
            status = content in comparison
            if status:
                description = f"`{message.author}`'s guessed a letter `{content}`!"
            else:
                description = f"`{message.author}`'s guess of letter `{content}` is wrong!"
        
        if result == "win":
            await ctx.send(f"`{message.author}` guessed the word! It was `{choice}`!")
        elif result == "lose":
            await ctx.send(f"You lost! The word was `{choice}`!")
        elif result == "timeout":
            await ctx.send(f"Timeout. The word was `{choice}`!")
        
        # Clear the database
        self.games_info[ctx.guild.id] = gamesDict()

    def hangman_choose(self, category: str):
        """Helper function to choose a word for hangman based on category."""

        path = join('.', 'data', 'hangman')
        if not isdir(path):
            raise GamesError("No hangman folder detected in data folder.")
        
        if category is None:
            # Check that there is at least one text file
            categories = [f for f in listdir(path) if f.endswith('.txt')]
            if not len(categories):
                raise GamesError("No text files detect in hangman folder.")
            path = join(path, random.choice(categories))
        else:
            # Check that the category text file exists
            path = join(path, category + '.txt')
            if not isfile(path):
                raise GamesError("That category does not exist.")

        with open(path, 'r') as f:
            words = f.readlines()
        return random.choice(words).strip().lower()

    @commands.command()
    async def hangmanlist(self, ctx):
        """Shows the list of available hangman categories."""
        path = join('.', 'data', 'hangman')
        if not isdir(path):
            raise GamesError("No hangman folder detected in data folder.")
        categories = [f[:-4] for f in listdir(path) if f.endswith('.txt')]

        embed = discord.Embed(title="Hangman Categories",
                              description='\n'.join(categories), 
                              color=discord.Colour.blue())
        await ctx.send(embed=embed)



    # @signups.command(name='connect4', aliases=['connectfour'])
    # async def _signups_connect4(self, ctx):
    #     """
    #     Starts a game of Connect Four.

    #     Exactly two players is required to play this game.
    #     Player who initiated the signups will go first.
    #     """
    #     raise NotImplementedError
    #     # Start Signups
    #     if not await self.signups_helper(ctx, 'Connect 4', maximum=2):
    #         return None
        
    #     # Decides who goes first
    #     convert = commands.MemberConverter().convert
    #     async def check(message):
    #         return (message.author in self.games_info[ctx.guild.id][2] and
    #                 await convert(ctx, message.content) in self.games_info[ctx.guild.id][2])
    #     try:
    #         await ctx.send("Out of the two players, who should go first? Mention their name.")
    #         message = await self.bot.wait_for('message', check=check, timeout=60)
    #     except asyncio.TimeoutError:
    #         return await ctx.send("No response detected. Game cancelled.\n")

    #     # Information required by game
    #     blank = ':black_large_square:'
    #     red = ':red_square:' # Player 1
    #     blue = ':blue_square:' # Player 2
    #     gameboard = [[blank] * 7] * 6
    #     player1 = convert(ctx, message.content)
    #     players = [player1,
    #                (self.games_info[ctx.guild.id][2] - {player1}).pop()]
    #     del player1

    #     def displayboard_text():
    #         """Send the current game board into the chat."""
    #         send = ":regional_indicator_a: :regional_indicator_b: :regional_indicator_c: :regional_indicator_d: :regional_indicator_e: :regional_indicator_f: :regional_indicator_g:\n"
    #         for row in gameboard:
    #             send += ' '.join(row) + '\n'
    #         return send

    #     # Start Game
    #     current_player = 0
    #     counter = defaultdict(int)
    #     def check_message(message):
    #         return (message.author == players[current_player] and
    #                 message.content.lower() in ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'surrender'))

    #     while True:
    #         await ctx.send(displayboard_text() + f"{players[current_player]}'s turn. Type which column you want to drop the token, or 'surrender' to lose.")
    #         second_time = False

    #         while True:
    #             try:
    #                 message = await self.bot.wait_for('message', check=check_message, timeout=30)
    #                 content = message.content.lower()
    #             except asyncio.TimeoutError:
    #                 if second_time:
    #                     # Consider it as surrender
    #                     content = 'surrender'
    #                     break
    #                 second_time = True
    #                 ctx.send(f"{players[current_player].mention}, you have 30s left to make a response.")

    #             if content == 'surrender':
    #                 await ctx.send(f"{players[current_player].mention} has surrendered.")
    #                 break
    #             elif counter[content] < 6:
    #                 counter[content] += 1
    #         break
    #     pass

    # @signups.command(name='aitp', aliases=['assassininthepalace'])
    # async def _signups_aith(self, ctx):
    #     """Starts a game of Assassin in the Palace.

    #     A minimum of 3 players is required.

    #     ---(Game Rules)---
    #     One person is designated as the King, another one will be desginated as
    #     the Assassin, and the remaining players will be designated as a Guard.
    #     The King and the Guards are part of the 'good' faction, and wins as long
    #     as the Assassin is killed or the King survives. The assassin wins if the
    #     King is dead.

    #     Everyone in the game is allowed to vote one person to be killed at a time
    #     by using '$vote @playername'. 

    #     ---(Role Infomation)---
    #     King: Your goal is to survive. You have no other information on who the
    #     Guards are.

    #     Guard: Your goal is to protect your King, the name of which will be given
    #     to you in PMs. 
        
    #     Assassin: Your goal is to kill the king. You have a one time ability to
    #     assassinate anyone in the game by using '$kill @playername'. If you fail
    #     to kill the king, you are discovered and you lose immediately. Should you 
    #     be voted out of the game, and have yet to use your ability, you will 
    #     desperately kill the person who places the last vote on you.

    #     ---(Role PM Format)---
    #     King: "You are the King! You have no abilities, but your survival is crucial
    #     to your kingdom. Avoid assassination at all costs! The guards know your
    #     identity, but you do not know theirs."

    #     Guard: "You are a Guard, loyally protecting your King 'NAME' from the evil
    #     assassin! You an every other guard know the identity of the King."

    #     Assassin: "You are the Assassin, wishing to assassinate the king! You have
    #     a one-shot assassination attempt, which you can make any time before you
    #     are voted out by typing '$kill @playername' in chat. Be warned though, if
    #     you assassinated the wrong person, you will instantly lose! If you are voted
    #     before you assassinated anyone, you'll automatically kill the last person
    #     who voted you out in desperation of killing the king.
    #     """
    #     pass

        
def setup(bot):
    bot.add_cog(Games(bot))