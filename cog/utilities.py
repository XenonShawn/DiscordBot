import discord
from discord.ext import commands
from collections import defaultdict
import asyncio
import pickle
import logging
from os.path import join

class utility(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        logging.info("Loading agenda_storage.")
        try:
            with open(join('data', 'agenda_storage.pkl'), 'rb') as f:
                self.agenda_storage = pickle.load(f)
            logging.info("Loaded agenda_storage.")
        except OSError as e:
            logging.warning(f"{type(e)}: {e}")
            # Use a defaultdict so keyerrors won't be thrown when inserting agenda tasks when server does not exist
            self.agenda_storage = defaultdict(list)
        self.voting_on = dict()
    
    def cog_unload(self):
        logging.info("Saving agenda_storage before shutdown...")
        with open(join('data', 'agenda_storage.pkl'), 'wb') as f:
            pickle.dump(self.agenda_storage, f, pickle.HIGHEST_PROTOCOL)
        logging.info("Saved agenda_storage.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clearchat(self, ctx: commands.Context, num: int):
        """Clears a specified number of messages in the current chatroom.
        Usage: $clearchat [num]"""
        if num < 1:
            return await ctx.send("Please input a positive integer.")

        # Double confirm clearing of messages
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send(f"Are you sure you want to clear {num} messages? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=10.0)
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Clear request rejected.")

        if response.content.upper() == 'Y':
            return await ctx.channel.purge(limit=num + 3)
        else:
            return await ctx.send("Clear request cancelled.")

    # Agenda group commands
    @commands.group()
    @commands.has_permissions(manage_guild=True)
    async def agenda(self, ctx: commands.Context):
        """Command for agenda-related functions."""
        if ctx.invoked_subcommand is None:
            if ctx.subcommand_passed is None:
                return await ctx.send(
                "```Usage: $agenda [function] [arguments for function]\n"
                "Used to keep track of topics to be discussed.\n"
                "Use $help agenda [function] if you want a more detailed explanation of each available function.\n"
                "\n"    
                "Functions available:\n"
                "add - Adds tasks to the agenda list. Tasks are delimited by a line break and a dash (-).\n"
                "remove - Removes tasks from the agenda list.\n"
                "clear - Clears the current agenda list.\n"
                "list - Shows the current agenda list.```")
            else:
                return await ctx.send("Invalid function.")

    @agenda.command(name='add')
    async def agenda_add(self, ctx, *, args=None):
        """Adds items to the agenda list. Tasks should be delimited by a line break.
        
        Example: $agenda add Do task 1
        Do task 2
        Do task 3"""

        if args is None:
            return await ctx.send("No input detected.")

        for row in args.splitlines():
            self.agenda_storage[ctx.guild.id].append(row.lstrip())
        return await self.agenda_list_helper(ctx)

    @agenda.command(name='list')
    async def agenda_list(self, ctx):
        """Returns the current items on the agenda list.\n\nExample: $agenda list"""
        return await self.agenda_list_helper(ctx)

    async def agenda_list_helper(self, ctx):
        if len(self.agenda_storage[ctx.guild.id]) == 0:
            return await ctx.send("There are no items on the agenda.")
        result = "The items currently in the agenda are:\n"
        for i, item in enumerate(self.agenda_storage[ctx.guild.id]):
            result += f"{i + 1}: {item}\n"
        return await ctx.send(result)

    @agenda.command(name='remove')
    async def agenda_remove(self, ctx, *, args=None):
        """Removes items from the agenda list. Tasks to be removed should be their task numers delimited by spaces.\n\nExample: $agenda remove 2 5 10"""

        server_id = ctx.guild.id
        l = len(self.agenda_storage[server_id])
        if args is None:
            return await ctx.send("No input detected.")
        if l == 0:
            return await ctx.send("There are no items on the agenda.")
        
        to_delete = list()
        failure = str()
        confirmation = "These items will be removed from the agenda list:\n"
        for item in args.split():
            # Weed out invalid tasks. 
            # Did not require args to be an int so that people don't need to rekey the whole thing if one argument was wrong
            try:
                index = int(item) - 1
                if index < 0 or index > l - 1:
                    raise ValueError
            except ValueError:
                failure += f"Invalid task number {item}\n"
                continue

            if index not in to_delete:
                confirmation += f"{index + 1}: {self.agenda_storage[server_id][index]}\n"
                to_delete.append(index)
        
        if len(to_delete) == 0:
            return await ctx.send(failure + "No valid tasks to delete.")

        # Wait for response
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
                self.agenda_storage[server_id].pop(index)
            await ctx.send("Removed tasks.")
            return await self.agenda_list_helper(ctx)
        else:
            return await ctx.send("Remove request cancelled.")

    @agenda.command(name='clear')
    async def agenda_clear(self, ctx):
        """Clears the agenda list.\n\nExample: $agenda clear"""

        server_id = ctx.guild.id
        if len(self.agenda_storage[server_id]) == 0:
            return await ctx.send("There are no items on the agenda.")

        # Wait for response
        def correct_response(message):
            return message.author == ctx.author and message.content.upper() in ['Y','N']

        try:
            await ctx.send("Are you sure you want to clear the agenda? (Y/N)")
            response = await self.bot.wait_for('message', check=correct_response, timeout=10.0)
        except asyncio.TimeoutError:
            return await ctx.send("No proper response detected. Remove request rejected.")
        
        if response.content.upper() == 'Y':
            self.agenda_storage.pop(server_id)
            return await ctx.send("Cleared the agenda.")
        else:
            return await ctx.send("Clear request cancelled.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def role_count(self, ctx, *, role: discord.Role):
        """Return the number of people with the given role in the current server."""
        return await ctx.send(f"{len(role.members)} member(s) have this role in this server.")
    
    @commands.command()
    @commands.is_owner()
    async def check_agenda(self, ctx):
        """Owner-only command for debugging purposes."""
        print(self.agenda_storage)


        
def setup(bot):
    bot.add_cog(utility(bot))