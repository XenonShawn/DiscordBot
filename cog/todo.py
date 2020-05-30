import discord
from discord.ext import commands
import pickle
import asyncio
from discord.ext import tasks

class todo(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.regular_save.start()
        try:
            with open('storage.pkl', 'rb') as f:
                self.storage = pickle.load(f)
            with open('score.pkl', 'rb') as f:
                self.score = pickle.load(f)
        except:
            print("No storage/score file found")
            self.storage = dict()
            self.score = dict()

    @tasks.loop(minutes=30.0)
    async def regular_save(self):
        print("todo cog: Saving details")
        self.save()

    def cog_unload(self):
        # Method used to save the current storage.
        print("Saving before removal...")
        self.save()
        self.regular_save.cancel()

    def save(self):
        try:
            with open('storage.pkl', 'wb') as f:
                pickle.dump(self.storage, f, pickle.HIGHEST_PROTOCOL)
            with open('score.pkl', 'wb') as f:
                pickle.dump(self.score, f, pickle.HIGHEST_PROTOCOL)
        except:
            print("Error while saving.")
        else:
            print("Saved.")
            
    def view_todo_list(self, target: int):
        """Helper function for `todo()` and `view()`.
        `target` is the unique User ID of the user."""
        if self.storage.get(target) is not None:
            result = f"{self.bot.get_user(target)} has the following to do list:\n"
            for n, item in enumerate(self.storage[target]):
                result += f"{n+1:2}: {item}\n"
            return result
        else:
            return f"User {self.bot.get_user(target)} does not have any stored todo list."

    @commands.command()
    async def todo(self, ctx, *, homework: str):
        """Logs down a todo list, identified by user's unique ID.
        Each item in the todo list should be seperated by a line break and a hypen (-).
        Example: $todo - Mathetmatics
        - English
        - Science"""
        result = list()
        for row in homework.lstrip().splitlines():
            if row.startswith("-"):
                result.append(row[1:].lstrip())
        user = ctx.author.id
        if self.storage.get(user) is None:
            self.storage[user] = result
        else:
            self.storage[user].extend(result)
        await ctx.send(self.view_todo_list(user))
    
    @commands.command(name='list')
    async def _list(self, ctx, *user: discord.Member):
        """Shows the todo list of the user. 
        An optional argument can be provided to see the todo list of another user.
        Example: $view @person"""
        if len(user) == 0:
            target = ctx.author.id
        else:
            target = user[0].id
        await ctx.send(self.view_todo_list(target))

    @commands.command()
    async def complete(self, ctx, *tasks):
        """Marks tasks as complete for the user. Can complete multiple tasks at once.
        Each task number should be seperated by a single space.
        Example: $complete 2 4 5"""
        if len(tasks) == 0:
            return await ctx.send("No input detected.")
        result = str()
        user = ctx.author.id
        l = len(self.storage[user])
        for task in tasks:
            # Check if valid input
            try:
                n = int(task) - 1
            except:
                result += f"Invalid task number {task}\n"
                continue
            if n + 1 > l:
                result += f"No such task {task}\n"
            else:
                if self.storage[user][n].endswith(" :white_check_mark:"):
                    result += f"Task {task} is already completed\n"
                else:
                    # Marks the task as completed with a checkmark
                    result += f"Completed task {task}: {self.storage[user][n]}\n"
                    self.storage[user][n] += " :white_check_mark:"
                    # Gives the user a point
                    if self.score.get(user) is None:
                        self.score[user] = 1
                    else:
                        self.score[user] += 1
        await ctx.send(result + f"Your current score is {self.score[user]}.")

    @commands.command(name='score')
    async def _score(self, ctx, *user: discord.Member):
        """Views the score of the user.
        An optional argument can be provided to view the score of another person.
        Example: $score @person"""
        if len(user) == 0:
            target = ctx.author.id
        else:
            target = user[0].id
        if target in self.score:
            await ctx.send(f"{self.bot.get_user(target)} has a score of {self.score[target]}.")
        else:
            await ctx.send("No score detected for that user.")
    
    @commands.command()
    async def highscore(self, ctx):
        """Returns a list of the top 10 people with the highest scores.
        Example: $highscore"""
        scorelist = [(person, points) for person, points in self.score.items()]
        scorelist.sort(key=lambda x:x[1], reverse=True)
        l = len(scorelist)
        if l == 0:
            return await ctx.send("Nobody has completed any task yet.")
        result = ""
        for i in range(1, min(l + 1, 11)):
            result += f"{i}: {self.bot.get_user(scorelist[i-1][0])} with {scorelist[i-1][1]} points\n"
        await ctx.send(result)
        
    @commands.command()
    async def clear(self, ctx):
        """Clears the entire todo list of the user.
        Example: $clear"""
        user = ctx.author.id
        if user not in self.storage:
            return await ctx.send("You have no existing todo list.")

        # If user has existing todo list, double confirm with user that they want to clear
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send("Are you sure you want to clear your todo list? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=10.0)
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Clear request rejected.")
        
        if response.content.upper() == 'Y':
            self.storage.pop(user)
            return await ctx.send("Cleared todo list.")
        else:
            return await ctx.send("Clear request cancelled.")
    
    @commands.command()
    async def remove(self, ctx, *tasks):
        """Removes task from the todo list.
        Each task number should be seperated by a single space.
        Example: $remove 2 4 5"""
        if len(tasks) == 0:
            return await ctx.send("No input detected.")
        failure = str()
        confirmation = "The following tasks will be deleted:\n"
        good = set()
        user = ctx.author.id
        l = len(self.storage[user])
        for task in tasks:
            # Check for valid input. If not, sends
            try:
                n = int(task) - 1
            except:
                failure += f"Invalid task number {task}\n"
                continue
            if n + 1 > l:
                failure += f"No such task {task}\n"
            else:
                if n not in good:
                    confirmation += f"{n+1}: {self.storage[user][n]}\n"
                    good.add(n)
        # Double confirm the deletion
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send(failure + confirmation + "Are you sure you want to remove the above? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=min(len(good) * 5, 10))
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Remove request rejected.")

        if response.content.upper() == 'Y':
            # Define a shift variable, as each time we pop a variable the number changes.
            shift = 0
            for index in good:
                self.storage[user].pop(index - shift)
                shift += 1
            await ctx.send("Cleared requested tasks.")
            await ctx.send(self.view_todo_list(user))
        else:
            return await ctx.send("Clear request cancelled.")
        
def setup(bot):
    bot.add_cog(todo(bot))