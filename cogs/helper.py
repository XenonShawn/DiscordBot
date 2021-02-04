import asyncio
import logging
import typing

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

def schedule_task(loop, sleep_seconds: int, func: typing.Callable) -> asyncio.Task:
        """
        A helper function that schedules a callable to be called `sleep_seconds` in
        the future, on event loop `loop`. If `sleep_seconds` is negative, 
        the callback will be called as soon as possible.

        Arguments can be passed in into `func` using `functools.partial`.

        Returns the task object.

        Depreciated: A coroutine object can be passed in directly, and it will be awaited
        without being called a second time. Functionality still exists to ensure compatibility.
        """
        if not (callable(func) or asyncio.iscoroutine(func)):
            raise TypeError("Argument must be callable.")
        async def coroutine():
            try:
                await asyncio.sleep(max(sleep_seconds, 0))
                if asyncio.iscoroutinefunction(func):
                    await func()
                elif asyncio.iscoroutine(func):
                    await func
                else:
                    func()
            except asyncio.CancelledError:
                logging.warn("Cancelled unfinished task.")
        if asyncio.iscoroutine(func):
            logging.warn("Passing a coroutine object into `schedule_task` is depreciated.")
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
    

