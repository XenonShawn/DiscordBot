import discord
from discord.ext import commands, tasks as tk
import asyncio
from datetime import date, timedelta, datetime
import pickle

class todo(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Try to initialise the storage and score system. Both `self.storage` and `self.score` are nested dictionaries.
        # self.storage[server_id][user_id] = list of tasks
        # self.score[server_id][user.id][date] = score of user for that day
        # Before accessing any value, you need to check if the key contains a value or not
        try:
            with open('storage.pkl', 'rb') as f:
                self.storage = pickle.load(f)
            with open('score.pkl', 'rb') as f:
                self.score = pickle.load(f)
        except OSError as e:
            print(e)
            self.storage = dict()
            self.score = dict()
        self.regular_save.start()

    def cog_unload(self):
        # Special method that activates when the cog is unloaded
        print("Unloading 'todo' cog: Saving todo list and scores")
        self.save()
        self.regular_save.cancel()

    @tk.loop(minutes=30.0)
    async def regular_save(self):
        print(f"todo cog: Saving details at {datetime.now()}")
        self.save()

    def save(self):
        with open('storage.pkl', 'wb') as f:
            pickle.dump(self.storage, f, pickle.HIGHEST_PROTOCOL)
        with open('score.pkl', 'wb') as f:
            pickle.dump(self.score, f, pickle.HIGHEST_PROTOCOL)

    def storage_helper(self, ctx, user_id=None):
        """Helper function that ensures the `self.storage` nested dictionary is ready for lookup.
        Takes in an optional input `user_id` to prepare the database for that user ID. Otherwise,
        user_id is extracted from the context. It returns the `server_id` and`user_id` used."""
        guild, author = (ctx.guild.id, ctx.author.id)
        if user_id is not None:
            author = user_id
        
        # Checks if guild is in the dictionary
        if self.storage.get(guild) is None:
            self.storage[guild] = {author: list()}
        # Checks if the user is in the dictionary
        elif self.storage[guild].get(author) is None:
            self.storage[guild][author] = list()
        return (guild, author)

    def score_helper(self, ctx, user_id=None):
        """Helper function that ensures the `self.score` nested dictionary is ready for lookup.
        Takes in an optional input `user_id` to prepare the database for that user ID. Otherwise,
        user_id is extracted from the context. It returns the `server_id`,`user_id` and `day` used."""
        guild, author, day = (ctx.guild.id, ctx.author.id, date.today())
        if user_id is not None:
            author = user_id

        # Checks if guild is in the dictionary
        if self.score.get(guild) is None:
            self.score[guild] = {author: {day: 0}}
        # Checks if the user is in the dictionary
        elif self.score[guild].get(author) is None:
            self.score[guild][author] = {day: 0}
        # Checks if the day is in the dictionary
        elif self.score[guild][author].get(day) is None:
            self.score[guild][author][day] = 0
        return (guild, author, day)
        
    def view_todo_list(self, ctx, server_id, user_id):
        """Helper function for `self.todo()` and `self.view()` which returns 
        what the user represented by `user_id` has in their todo list."""
        if len(self.storage[server_id][user_id]) == 0:
            return f"User {self.bot.get_user(user_id)} does not have anything in their todo list."
        else:
            result = f"{self.bot.get_user(user_id)} has the following to do list:\n"
            for n, item in enumerate(self.storage[server_id][user_id]):
                result += f"{n+1:2}: {item}\n"
            return result

    @commands.command()
    async def todo(self, ctx, *, todolist: str):
        """Logs down the todo list, seperated by a line break and a hypen (-).

        Example: $todo - English essay
        - Science chapter 3
        - Mathematics exercise 6"""
        # Obtain necessary infomation to input into self.storage nested dictionary
        server_id, user_id = self.storage_helper(ctx)
        for row in todolist.lstrip().splitlines():
            if row.startswith("-"):
                # If the person already has a todo list, add on the todo list.
                self.storage[server_id][user_id].append(row[1:].strip())
        await ctx.send(self.view_todo_list(ctx, server_id, user_id))
    
    @commands.command(name='list', aliases=['view'])
    async def _list(self, ctx, *user: discord.Member):
        """Shows the todo list of the user. 
        An optional argument can be provided to see the todo list of another user.

        Example: $list @person"""
        if len(user) == 0:
            user_id = ctx.author.id
        else:
            user_id = user[0].id
        server_id, _ = self.storage_helper(ctx, user_id)
        await ctx.send(self.view_todo_list(ctx, server_id, user_id))

    @commands.command()
    async def complete(self, ctx, *completed_tasks):
        """Marks tasks as complete for the user. You can complete multiple tasks at once.
        Each task number should be seperated by a single space.

        Example: $complete 2 4 5"""

        if len(completed_tasks) == 0:
            return await ctx.send("No input detected.")

        # Set up variables and ensure databases are setup
        _, _ = self.storage_helper(ctx)
        server_id, user_id, day = self.score_helper(ctx)
        l = len(self.storage[server_id][user_id])
        result = str()

        # Check for valid input
        if l == 0:
            return await ctx.send("You have no tasks in your todo list.")
        for task in completed_tasks:
            try:
                n = int(task) - 1
                if n + 1 > l or n < 0:
                    raise ValueError
            except ValueError:
                result += f"Invalid task number {task}\n"
                continue

            # Check if task is already completed
            if self.storage[server_id][user_id][n].endswith(" :white_check_mark:"):
                result += f"Task {task} is already completed\n"
            else:
                # Marks the task as completed with a checkmark
                result += f"Completed task {task}: {self.storage[server_id][user_id][n]}\n"
                self.storage[server_id][user_id][n] += " :white_check_mark:"
                self.score[server_id][user_id][day] += 1

        await ctx.send(result + f"Your current score for today is {self.score[server_id][user_id][day]}.")
    
    @commands.command()
    async def cleartodo(self, ctx):
        """Clears the entire todo list of the user.

        Example: $clear"""
        server_id, user_id = self.storage_helper(ctx)

        # Checks if user has a todo list 
        if len(self.storage[server_id][user_id]) == 0:
            return await ctx.send("You have no existing todo list.")
        
        # If user has an existing todo list, confirm that the user wants to clear their list.
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send("Are you sure you want to clear your todo list? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=10.0)
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Clear request rejected.")
        
        if response.content.upper() == 'Y':
            self.storage[server_id][user_id] = list()
            return await ctx.send("Cleared todo list.")
        else:
            return await ctx.send("Clear request cancelled.")
    
    @commands.command()
    async def remove(self, ctx, *tasks):
        """Removes task from the todo list.
        Each task number should be seperated by a single space.
        Example: $remove 2 4 5"""     
        # Checks if user put in an input
        if len(tasks) == 0:
            return await ctx.send("No input detected.")

        # Checks if user has a todo list 
        server_id, user_id = self.storage_helper(ctx)
        l = len(self.storage[server_id][user_id])
        if l == 0:
            return await ctx.send("You have no existing todo list.")

        to_delete = list()
        failure = str()
        confirmation = "The following tasks will be deleted:\n"

        for task in tasks:
            # Weed out invalid tasks
            try:
                n = int(task) - 1
                if n + 1 > l or n < 0:
                    raise ValueError
            except ValueError:
                failure += f"Invalid task number {task}\n"
                continue
            if n not in to_delete:
                confirmation += f"{n+1}: {self.storage[server_id][user_id][n]}\n"
                to_delete.append(n)
        
        if len(to_delete) == 0:
            return await ctx.send(failure + "No valid tasks to delete.")

        # Double confirm deletions
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send(failure + confirmation + "Are you sure you want to remove the above? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=max(len(to_delete) * 5, 10))
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Remove request rejected.")

        if response.content.upper() == 'Y':
            # Sort in reverse order so index remains the same
            for index in sorted(to_delete, reverse=True):
                self.storage[server_id][user_id].pop(index)
            await ctx.send("Removed requested tasks.")
            await ctx.send(self.view_todo_list(ctx, server_id, user_id))
        else:
            return await ctx.send("Remove request cancelled.")

    def view_score(self, ctx, num_days: int, user_id: int):
        """Helper function to return the score of a user `num_days` ago.
        Takes in a `discord.User` argument."""
        server_id, user_id, _ = self.score_helper(ctx, user_id)
        day = date.today() - timedelta(days=float(num_days))
        return self.score[server_id][user_id].get(day, 0)

    @commands.command(name='score')
    async def _score(self, ctx, num_days: int = 0, user: discord.User = None):
        """Function used to retrieve and print out the score.
        Two optional arguments can be taken, the first being the number of days ago,
        and the second being the user_id of the user to be checked.
        Example uses: 
        $score -> gives your current score for today
        $score 2 -> Gives your score 2 days ago
        $score 0 @person -> Give's person's score 0 days ago
        """
        if num_days < 0:
            return await ctx.send("The number of days has to be non-negative.")
        if num_days == 0:
            if user is None:
                return await ctx.send(f"You have a score of {self.view_score(ctx, 0, ctx.author.id)} today.")
            else:
                return await ctx.send(f"{user} has a score of {self.view_score(ctx, 0, user.id)} today.")
        else:
            if user is None:
                return await ctx.send(f"You had a score of {self.view_score(ctx, num_days, ctx.author.id)} {num_days} days ago.")
            else:
                return await ctx.send(f"{user} had a score of {self.view_score(ctx, num_days, user.id)} {num_days} days ago.")

    @commands.command()
    async def highscore(self, ctx, num_days: int = 0):
        """Returns the top 5 people who done the most number of tasks.
        Accepts an optional argument 'num_days', which shows top 5 scores
        for the past 'num_days' days.
        
        Example: $highscore 3"""
        today = date.today()
        server_id = ctx.guild.id
        highscore = list()
        if self.score.get(server_id) is None:
            self.score[server_id] = dict()
        for user_id in self.score[server_id]:
            sum = 0
            for i in range(num_days + 1):
                day = today - timedelta(days=i)
                sum += self.score[server_id][user_id].get(day, 0)
            highscore.append((user_id, sum))
        l = len(highscore)

        if l == 0:
            return await ctx.send("No scored recorded.")
        highscore.sort(key=lambda x:x[1], reverse=True)
        
        if num_days > 0:
            result = f"In the past {num_days} days, the highest {min(l, 5)} scores are:\n"
        else:
            result = f"The highscores for today are:\n"
        for i in range(1, min(6, l + 1)):
            if highscore[i-1][1] == 0:
                if i == 1:
                    result = f"No one in this server has a score yet for today."
                break
            result += f"{i}: {self.bot.get_user(highscore[i-1][0])} with {highscore[i-1][1]} points\n"
        await ctx.send(result)

    @commands.command()
    @commands.is_owner()
    async def check_files(self, ctx):
        """Owner-only command for debugging purposes."""
        print(self.storage)
        print(self.score)
    
    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def change_score(self, ctx, num: int, user: discord.User, days_ago: int = 0):
        if days_ago < 0:
            return await ctx.send("Number of days ago should be non-negative.")
        server_id, user_id, today = self.score_helper(ctx, user.id)
        day = today - timedelta(days=days_ago)
        self.score[server_id][user_id][day] = self.score[server_id][user_id].get(day, 0) + num
        return await ctx.send(f"{user}'s score on {day} is now {self.score[server_id][user_id][day]}.")

def setup(bot):
    bot.add_cog(todo(bot))