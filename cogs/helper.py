import asyncio
import logging

import discord
from discord.ext import commands

class Duration(commands.Converter):
    """Convert the duration in the form of [number][unit] into minutes."""
    async def convert(self, ctx, argument) -> int:
        try:
            value = int(argument[:-1])
            if value < 1:
                raise ValueError
        except ValueError:
            raise commands.BadArgument("Value must be a positive integer, eg 7d")

        unit = argument[-1].lower()
        if unit == 'm':
            return value
        elif unit == 'h':
            return value * 60
        elif unit == 'd':
            return value * 1440
        else:
            raise commands.BadArgument("Unit must be 'm', 'h' or 'd' for minutes, hours and days respectively. Eg 7d")

class PositiveInt(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            n = int(argument)
            if n < 1:
                raise ValueError
            return n
        except ValueError:
            raise commands.BadArgument("Argument provided is not a positive integer.")

def schedule_task(loop, sleep_seconds: int, coro) -> asyncio.Task:
        """
        A helper function that schedules a coroutine `coro` to be run on `loop`
        `sleep_seconds` seconds in the future. If `sleep_seconds` is negative, 
        the coroutine will be run as soon as possible.
        
        Returns the task object.
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError("Argument must be a coroutine object.")
        async def coroutine():
            try:
                await asyncio.sleep(max(sleep_seconds, 0))
                await coro
            except asyncio.CancelledError:
                logging.warn("Cancelled unfinished task.")
        return loop.create_task(coroutine())

async def smart_send(target: discord.abc.Messageable, msg, sep=2000):
    """
    A helper coroutine that automatically sends more than one message should the
    content be more than `sep` characters long. The messages will be cut at spaces
    or line breaks.
    """
    original = msg
    send = list()
    while len(msg) > sep:
        cut = min(max(msg[:sep].rfind('\n'), msg[:sep].rfind(' ')), sep)
        send.append(msg[:cut])
        msg = msg[cut + 1:]
    send.append(msg)
    
    try:
        for message in send:
            await target.send(message)
    except discord.HTTPException as e:
        logging.error(f"Error while smart sending. Error {e}")
        try:
            with open('text.txt', 'w', encoding="utf-8") as f:
                f.write(original)
            await target.send("Error in paginating message.", file=discord.File(fp='text.txt'))
        except Exception:
            await target.send(f"{e}: Error sending message.")
    

