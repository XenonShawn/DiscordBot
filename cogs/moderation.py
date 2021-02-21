from datetime import datetime, timedelta
from collections import defaultdict
import logging
import typing
import asyncio

import discord
from discord.ext import commands

from cogs.helper import Duration, PositiveInt, smart_send


class BannedUser(commands.Converter):
    """Convert the ID into a user."""
    async def convert(self, ctx: commands.Context, argument) -> discord.User:
        try:
            snowflake = discord.Object(int(argument))
            banentry = await ctx.guild.fetch_ban(snowflake)
        except ValueError:
            raise commands.BadArgument("Invalid ID. Unbans must be made with the ID of the user.")
        except discord.NotFound:
            raise commands.BadArgument("No banned user of such ID was found.")
        return banentry.user

class ModerationError(commands.CommandError):
    pass

class Moderation(commands.Cog, name='moderation'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.con = self.bot.con
        self.ongoing = defaultdict(dict)

        # Ensure table exists
        self.con.execute("""CREATE TABLE IF NOT EXISTS modlog (
                                guild_id        INTEGER NOT NULL,
                                moderator       TEXT NOT NULL,
                                moderator_id    INTEGER NOT NULL,
                                user            TEXT NOT NULL,
                                user_id         INTEGER NOT NULL,
                                timestamp       TIMESTAMP NOT NULL,
                                type            TEXT NOT NULL,
                                duration        INTEGER,
                                reason          TEXT,
                                complete        INTEGER NOT NULL)""")
                
        self.con.execute("""CREATE TABLE IF NOT EXISTS moderationsettings (
                                guild_id        INTEGER NOT NULL UNIQUE,
                                channel_id      INTEGER,
                                role_id         INTEGER)""")

        # Loads up the entire database and starts running tasks
        self.loop.create_task(self.restart_tasks())
    
    def cog_unload(self):
        for server in self.ongoing.values():
            for task in server.values():
                task.cancel()

    async def restart_tasks(self):

        ### TO DO NEED WAIT FOR BOT TO BE READY FIRST
        temp = {
            'mute': self.unmute_helper,
            'ban': self.unban_helper
        }
        for row in self.con.execute("""SELECT guild_id, user_id, timestamp, type, duration FROM modlog
                                            WHERE complete = 0
                                            ORDER BY timestamp"""):
            # Check if still valid
            guild = self.bot.get_guild(row[0])
            if guild is None:
                self.update_modlog(row[0], row[1])
                continue
            member = guild.get_member(row[1])
            if member is None:
                try:
                    member = (await guild.fetch_ban(discord.Object(row[1]))).user
                except discord.NotFound:
                    self.update_modlog(row[0], row[1])
                    continue
            try:
                coro = temp[row[3]](guild, member, row[4])
            except KeyError:
                continue

            now = datetime.now()
            end_punishment = row[2] + timedelta(minutes=row[4])
            delta = (end_punishment - now).total_seconds()            

            self.ongoing[guild][member] = self.schedule_task(delta, coro)
            logging.info(f"Task created for {member} in {guild}.")

    async def cog_check(self, ctx):
        """Checks that the bot has permissions before these functionalities can be used."""
        p = ctx.channel.permissions_for(ctx.guild.me)
        required = discord.Permissions(kick_members=True, ban_members=True,
                                       manage_channels=True, read_messages=True,
                                       manage_messages=True, send_messages=True,
                                       manage_roles=True)
        if required.is_subset(p):
            return True
        # Lazy make my own list, just have the bot create the list every time xd
        raise commands.BotMissingPermissions([perm for perm, value in iter(required) if value == True])

    async def cog_command_error(self, ctx, error):
        if isinstance(error, ModerationError) or isinstance(error, discord.HTTPException):
            return await ctx.send(str(error))
    
    ############################################################################
    #                 Setting of Modlog Channel and Mute Roles                 #
    ############################################################################

    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_messages=True)
    async def modlogchannel(self, ctx: commands.Context):
        """View the existing modlog channel for the server."""
        if ctx.subcommand_passed is None:
            channel = await self.getmodlogchannel(ctx.guild)
            await ctx.send(f"This server's modlog channel is set to: {channel}.\nUse `$modlogchannel set #channel` to set the channel.")
        else:
            await ctx.send("Invalid command passed. Use `$help modlogchannel` for help.")

    @modlogchannel.command(name='set')
    async def modlogchannel_set(self, ctx, *, textchannel: discord.TextChannel):
        """Set the modlog channel for the server."""
        with self.con:
            self.con.execute("""INSERT INTO moderationsettings(guild_id, channel_id) VALUES (?, ?)
                                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id""",
                                (ctx.guild.id, textchannel.id))
        await ctx.send(f"Modlog channel set to: {textchannel.mention}")
    
    @modlogchannel.command(name='reset')
    async def modlogchannel_reset(self, ctx):
        """Reset this server's modlog channel."""
        with self.con:
            self.con.execute("""INSERT INTO moderationsettings(guild_id, channel_id) VALUES (?, NULL)
                            ON CONFLICT(guild_id) DO UPDATE SET channel_id=NULL""",
                            (ctx.guild.id,))
        await ctx.send("Modlog channel set to: None")

    ### Role

    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_messages=True)
    async def muterole(self, ctx: commands.Context):
        """View the existing mute role for the server."""
        if ctx.subcommand_passed is None:
            role = await self.getmuterole(ctx.guild)
            await ctx.send(f"This server's mute role is set to: {role}.\nUse `$muterole help [role]` to see available options.")
        else:
            await ctx.send("Invalid command passed. Use `$help muterole` for help.")
    
    @muterole.command(name='set')
    async def muterole_set(self, ctx, *, role: discord.Role):
        """Set the mute role for the server."""
        with self.con:
            self.con.execute("""INSERT INTO moderationsettings(guild_id, role_id) VALUES (?, ?)
                                ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id""",
                                (ctx.guild.id, role.id))
        await ctx.send(f"Mute role set to: {role}")

    @muterole.command(name='reset')
    async def muterole_reset(self, ctx):
        """Reset this server's mute role."""
        with self.con:
            self.con.execute("""INSERT INTO moderationsettings(guild_id, role_id) VALUES (?, NULL)
                            ON CONFLICT(guild_id) DO UPDATE SET role_id=NULL""",
                            (ctx.guild.id,))
        await ctx.send("Mute role set to: None")

    @muterole.command(name='create')
    async def muterole_create(self, ctx):
        """Have the bot automatically create a mute role."""
        await ctx.send("Please wait a few seconds...")

        # Create permissions instance and create role
        permissions = discord.Permissions.none()
        permissions.update(read_messages=True, read_message_history=True, send_messages=False)
        role = await ctx.guild.create_role(name='Bot Muted', permissions=permissions)
        failure = str()

        # Set permissions for role in all channels
        for channel in ctx.guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False)
            except discord.HTTPException:
                failure += f"channel, "
                continue

        if failure:
            failure = "Unable to change permissions for these channels: " + failure[:-2]
            while len(failure) > 2000:
                await ctx.send(failure[:2000])
                failure = failure[2000:]

        # Update moderationsettings
        with self.con:
            self.con.execute("""INSERT INTO moderationsettings(guild_id, role_id) VALUES (?, ?)
                            ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id""",
                            (ctx.guild.id, role.id))
        await ctx.send(f"Mute role set to: {role}")
        

    ############################################################################
    #                             Helper Functions                             #
    ############################################################################

    async def getmodlogchannel(self, guild: discord.Guild):
        """Return the moderation channel for the server, or None if unavailable."""
        channel_id_tuple = self.con.execute("SELECT channel_id FROM moderationsettings WHERE guild_id = ?", (guild.id,)).fetchone()
        # If guild is not in the db, then the above will return None. If the guild is in the db but has no channel, the above will return (None,)
        # The bottom first 'and' statement will result in channel being set to None if the above conditions are met
        # Else, the above will return (channel_id,), resulting in channel being set to the mention string
        return channel_id_tuple and channel_id_tuple[0] and await self.bot.fetch_channel(channel_id_tuple[0])

    async def getmuterole(self, guild: discord.Guild):
        """Return the role used to mute users, or None if unavailable."""
        role_id_tuple = self.con.execute("SELECT role_id FROM moderationsettings WHERE guild_id = ?", (guild.id,)).fetchone()
        # See explanation for the and statements above in the modlog channel section
        return role_id_tuple and role_id_tuple[0] and guild.get_role(role_id_tuple[0])

    async def log(self, guild: discord.Guild, moderator: discord.Member,
                  user: discord.abc.User, type_: str, reason: str,
                  duration: int=None, *, broadcast=True, send_user=True):
        """
        Log the moderator action into the database and return the embed. If
        `broadcast` is `True`, then it will send it to the modlog channel.
        If `send_user` is also `True`, it will also send it to the member.

        `broadcast` should be used in the `modnote` command.
        `send_user` should be used in the `ban` command.
        """
        # Update database
        time = datetime.now()
        complete = 1 if duration == -1 else 0
        with self.con:
            self.con.execute("""INSERT INTO modlog(guild_id, moderator, moderator_id,
                                                   user, user_id, timestamp,
                                                   type, duration, reason, complete)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (guild.id, str(moderator), moderator.id, str(user), 
                            user.id, time, type_, duration, reason, complete))

        # Creation of embed
        d = 'NA' if duration is None else ('Forever' if duration == -1 else f'{duration} Minutes')
        embed = discord.Embed(title=f"{type_.capitalize()} | {user}", colour=discord.Colour.blue())
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Duration", value=d, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {user.id} | {time}")

        # Broadcast to modlog channel and user if applicable
        if broadcast:
            modlogchannel = await self.getmodlogchannel(guild)
            if modlogchannel is not None:
                await modlogchannel.send(embed=embed)
            if send_user:
                await user.send(embed=embed)
        return embed
        
    def schedule_task(self, sleep_seconds: int, coro) -> asyncio.Task:
        """
        A helper coroutine that schedules runs a coroutine `coro` `sleep_seconds`
        seconds in the future. If `sleep_seconds` is negative, the coroutine will
        be run as soon as possible.
        
        Returns the task object.
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError("Argument must be a coroutine object.")
        async def coroutine():
            try:
                await asyncio.sleep(max(sleep_seconds, 0)) # Convers to seconds
                await coro
            except asyncio.CancelledError:
                logging.warn("Cancelled task from moderation.")
        return self.loop.create_task(coroutine())

    def update_modlog(self, guild_id, user_id):
        with self.con:
            self.con.execute("""UPDATE modlog SET complete = 1 WHERE 
                            guild_id = ? AND user_id = ? AND complete = 0""", 
                            (guild_id, user_id))

    def cancel_task(self, guild: discord.Guild, user: discord.Member):
        """Cancel any ongoing task for the member provided, and update the modlog."""
        if user in self.ongoing[guild]:
            self.ongoing[guild][user].cancel()
            self.update_modlog(guild.id, user.id)
            del self.ongoing[guild][user]

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Track when a member leaves the guild."""
        self.cancel_task(member.guild, member)
        # Members permanently muted will not have a task. Have to manually check
        muterole = await self.getmuterole(member.guild)
        if muterole is not None and muterole in member.roles:
            guild = member.guild
            await self.log(guild, guild.me, member, 'unmute', "User left the server.", send_user=False)

    ############################################################################
    #                        Actual Moderation Commands                        #
    ############################################################################

    @commands.command(hidden=True)
    @commands.is_owner()
    async def check_moderation(self, ctx):
        print(self.ongoing)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str='-'):
        """
        Warn a user. A message will be sent to the modlog and to the user.
        
        Usage: $warn [user] [optional reason]
        """
        embed = await self.log(ctx.guild, ctx.author, user, 'warn', reason)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_guild_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason: str='-'):
        """
        Kick a user. A message will be sent to the modlog and to the user.
        
        Usage: $kick [user] [optional reason]
        """
        self.cancel_task(ctx.guild, user)
        embed = await self.log(ctx.guild, ctx.author, user, 'kick', reason)
        await ctx.send(embed=embed)
        await ctx.guild.kick(user, reason=reason)

    @commands.command()
    @commands.has_guild_permissions(manage_messages=True)
    async def mute(self, ctx, user: discord.Member, duration: typing.Optional[Duration]=-1, *, reason: str='-'):
        """
        Mute a user. An optional duration can be stated. 
        A message will be sent to the modlog and to the user.
        
        Usage: $mute [user] [optional duration, X(m/h/d)] [optional reason]
        Example: $mute @badperson 7d trolling
        Example: $mute @badperson 3h
        """
        # Check if muterole exists
        muterole = await self.getmuterole(ctx.guild)
        if muterole is None:
            return await ctx.send("No mute role has been set for this server. Use $muterole for more information.")
        
        # Check if existing task already exists (eg member is already muted)
        self.cancel_task(ctx.guild, user)

        embed = await self.log(ctx.guild, ctx.author, user, 'mute', reason, duration)
        await ctx.send(embed=embed)
        await user.add_roles(muterole, reason=reason)

        # Call for unmute
        if duration > 0:
            task = self.schedule_task(duration * 60, self.unmute_helper(ctx.guild, user, duration))
            self.ongoing[ctx.guild][user] = task

    async def unmute_helper(self, guild: discord.Guild, user: discord.Member, duration: int=None):
        """A helper function to automatically unmute a user."""
        # Check if user is muted and if role exists
        muterole = await self.getmuterole(guild)
        if muterole is None or muterole not in user.roles:
            raise ModerationError("User to be unmuted is not muted, had no muterole, or the server muterole isn't set.")
        
        # Update modlog to set everything to complete
        self.update_modlog(guild.id, user.id)

        if duration is not None:
            # Send embed
            await self.log(guild, guild.me, user, 'unmute', f"Automatic unmute after {duration} minutes.")
            await user.remove_roles(muterole, reason=f"Automatic unmute after {duration} minutes.")

        return muterole

    @commands.command()
    @commands.has_guild_permissions(manage_messages=True)
    async def unmute(self, ctx, user: discord.Member, reason: str='-'):
        """Unmute a user. A message will be sent to the modlog and to the user."""
        # Get the muterole if it exists and remove ti from the user
        muterole = await self.unmute_helper(ctx.guild, user)
        await user.remove_roles(muterole, reason=reason)

        # Update modlog and database
        embed = await self.log(ctx.guild, ctx.author, user, 'unmute', reason)
        await ctx.send(embed=embed)

        # Cancel scheduled unmute if necessary
        self.cancel_task(ctx.guild, user)

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, duration: typing.Optional[Duration]=-1, *, reason: str='-'):
        """
        Ban a user. An optional duration can be stated. 
        A message will be sent to the modlog and to the user.
        
        Usage: $ban [user] [optional duration, X(m/h/d)] [optional reason]
        Example: $ban @badperson 7d trolling
        Example: $ban @badperson 3h
        """
        # Cancel any existing task
        self.cancel_task(ctx.guild, user)
        embed = await self.log(ctx.guild, ctx.author, user, 'ban', reason, duration)
        await ctx.send(embed=embed)
        await user.ban(reason=reason, delete_message_days=0)

        # Call for unban
        if duration > 0:
            task = self.schedule_task(duration * 60, self.unban_helper(ctx.guild, user, duration))
            self.ongoing[ctx.guild][user] = task

    async def unban_helper(self, guild, user: discord.User, duration: int=None):
        """A helper function to automatically unban a user."""
        # Check if user is banned
        try:
            banentry = await guild.fetch_ban(user)
        except discord.NotFound:
            raise ModerationError("User to be unbanned is not banned!")

        self.update_modlog(guild.id, user.id)

        if duration is not None:
            await self.log(guild, guild.me, user, 'unban', f"Automatic unban after {duration} minutes.", send_user=False)
            await guild.unban(user, reason=f"Automatic unban after {duration} minutes.")
    
    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user: BannedUser, reason: str='-'):
        """
        Unban a user. A message will be sent to the modlog and to the user.
        To unban a user, their unique discord ID has to be given instead of
        mentioning them. The ID of the banned user is in the modlog.

        Usage: $unban [user id] [optional reason]
        Example: $unban 123456789123456789 second chance
        """
        # Unnecessary to use unban_helper here, as we already checked that user
        # is banned via the `BannedUser` converter, but I'll just leave it.
        # Essentially just updating database.
        await self.unban_helper(ctx.guild, user)
        embed = await self.log(ctx.guild, ctx.author, user, 'unban', reason, send_user=False)
        await ctx.send(embed=embed)
        await ctx.guild.unban(user, reason=reason)

        # Cancel scheduled task if necessary
        self.cancel_task(ctx.guild, user)

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def modnote(self, ctx, user: typing.Union[discord.Member, BannedUser], *, note: str):
        """
        Writes a note into the modlog database for future reference.

        Usage: $modnote [user] [note]
        Example: $modnote @badperson This person has been repeatedly spamming.
        """
        embed = await self.log(ctx.guild, ctx.author, user, 'modnote', note, broadcast=False)
        await ctx.send(embed=embed)

    @modnote.error
    async def modnote_error(self, ctx, error):
        if isinstance(error, commands.BadUnionArgument):
            await ctx.send(str(error))

    @commands.command()
    @commands.has_guild_permissions(manage_guild=True)
    async def modlog(self, ctx, user: typing.Union[discord.Member, BannedUser], 
                     number: typing.Optional[PositiveInt]=5, *, filter_: str=''):
        """
        Return the `number` most recent logs in the modlog for that user. The
        filter can be used to find logs that contain that word or words.
        The number of logs to draw is optional, and is set to a default of 5.

        Usage: $modlog [user] [number=5] [filter]
        Example: $modlog @badperson 10 mute
        Example: $modlog @badperson spamming in channel
        """
        result = str()
        # Searching in sqlite is case-insensitive
        search = '%' + filter_ + '%'
        c = self.con.execute("""SELECT moderator, user, timestamp, type, duration, reason 
                                FROM modlog 
                                WHERE guild_id = ?
                                    AND user_id = ?
                                    AND (type LIKE ? OR reason LIKE ?)
                                ORDER BY timestamp DESC""",
                            (ctx.guild.id, user.id, search, search))
        for i in range(number):
            r = c.fetchone()
            if r is None:
                break
            punishment = r[3].capitalize()
            if r[4] is not None and r[4] > 0:
                punishment += f" for {r[4]} minutes"
            result = f"[{r[2]}] ({r[0]}) {punishment} | {r[1]} - Reason: {r[5]}\n" + result
        else:
            i = number
        
        c.close()

        # Format result
        addon = "1 log" if i == 1 else f"{i} logs"
        addon += f" found for the user {user}:"
        if filter_:
            addon = addon[:-1] + f" with filter {filter_}:"
        result = addon + '\n' + result

        await smart_send(ctx, result)


def setup(bot):
    bot.add_cog(Moderation(bot))