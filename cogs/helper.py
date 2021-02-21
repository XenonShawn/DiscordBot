import logging
import typing
import re
import sqlite3

import discord
from discord.ext import commands

class Duration(commands.Converter):
    """Convert the duration in the form of [number][unit] into minutes."""
    async def convert(self, ctx, argument) -> int:
        match = re.fullmatch(r"^(\d+w)?(\d+d)?(\d+h)?(\d+m)?$", argument)
        if match is None:
            raise commands.BadArgument("Unit must be 'm', 'h', 'd' or 'w' for minutes, hours, days and weeks respectively. Eg 7d")

        value = 0
        for idx, duration in enumerate((10080, 1440, 60, 1), 1):
            if match[idx] is not None:
                value += duration * int(match[idx][:-1])

        if value <= 0:
            raise commands.BadArgument("Value must be a positive integer, eg 7d")
        else:
            return value

class PositiveInt(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            n = int(argument)
            if n < 1:
                raise ValueError
            return n
        except ValueError:
            raise commands.BadArgument("Argument provided is not a positive integer.")

def addColumn(con: sqlite3.Connection, table: str, column: str) -> None:
    "Function which aids in adding a column to the SQLite3 database."
    try:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
    except sqlite3.OperationalError:
        pass

_MAIN_SUBREGEX = r"(?<!\\)```[\s\S]+?(?<!\\)```"

# The above regex is split as follows:
# rf"""(?<!\\)      Negative lookbehind for '\'
#      ```          Check for multiline code blocks
#      [\s\S]       Non-greedily include any character including newlines
#      (?<!\\)      Negative lookbehind for '\'
#      ```"""       Check for multiline code blocks

_MAIN_SUBREGEX += '|' + '|'.join(rf"(?<!\\){c}.+?(?<!\\){c}" for c in (r'\*\*', '__', '`', r'\|\|', '~~'))

# The above regex is split as follows:
# rf"""(?<!\\)      Negative lookbehind for '\'
#      {c}          Substitute in the markdown character
#      .+?          Non-greedily include any character excluding newlines
#      (?<!\\)      Negative lookbehind for '\'
#      {c}"""       Look for markdown ending

_MAIN_SUBREGEX += '|' + '|'.join(rf"(?<!\\){c}(?! )[^{c}]+(?<!\\| ){c}(?!{c})" for c in (r'\*', '_'))

# The above regex is split as follows:
# rf"""(?<!\\)      Negative lookbehind for '\'
#      {c}          Substitute in the markdown character
#      (?! )        Ensure there are no spaces between the markdown character and the main body of text
#      [^{c}]+      Check for the main body, ensuring it doesn't contain the markdown character
#      (?<!\\| )    Negative lookbehind for '\' and space
#      {c}          Look for markdown ending
#      (?!{c})"""   Negative lookahead for the markdown character

# These rules don't exactly cover the way italics works, but it should cover most of it.
# *asd* works, but * asd * doesn't (no spaces)
# **asd* works, but *asd** doesn't
# Doesn't account for things like _asd__asd_ which should work, but isn't captured by the regex

_MAIN_SUBREGEX += '|' + r"^> .+$"

# The above regex is split as follows:
# r"^               Start of line
#   >               Check for a literal right carat and a space
#   .+              Rest of the line is a quote
#   $"              Stops at the end of the line

_MAIN_SUBREGEX

def find_char(string: str, char: str, *, reverse: bool=False) -> typing.Tuple[int, ...]:
    """
    Finds all instances of a single char in a string, and return a list of their indices.
    """
    if len(char) != 1:
        raise TypeError("Input can only be a single character.")
    return tuple(idx for idx, letter in enumerate(string) if letter == char)[::-1 if reverse else 1]

def smart_split(message: str, sep: int=2000) -> typing.List[str]:
    """
    Function which splits the `message` into multiple messages, each which has length of at
    most `sep`. This will take discord markdown into account as far as possible, preferring
    not to cut a message in between markdown text.

    It will try to split the message between:
    1) Line breaks
    2) Spaces
    3) Anywhere, except between markdown
    4) Anywhere, between markdown

    Parameters
    ----------
        message: `str`
            The string that is to be split.
        sep: `int`
            The maximum length of each partition

    Returns
    -------
        A list of strings
    """
    # Find all the markdown positions
    markdown_positions = [(m.start(), m.end()) for m in re.finditer(_MAIN_SUBREGEX, message)]

    invalid_positions = set()
    for item in markdown_positions:
        invalid_positions.update(range(item[0], item[1]))

    def find_valid(string: str):
        for char in ('\n', ' '):
            for idx in find_char(string, char, reverse=True):
                if idx not in invalid_positions:
                    return idx
        # Can't find appropriate line break or space
        for idx in range(sep, 0, -1):
            if idx not in invalid_positions:
                return idx
        # Just return seperation value
        return sep

    result = list()
    while len(message) > sep:
        idx = find_valid(message[:sep]) # Get the best index to split the string at
        result.append(message[:idx])
        message = message[idx:].strip()
    result.append(message) # Append remaining

    return result
    
async def smart_send(target: discord.abc.Messageable, msg, sep=2000) -> typing.Union[typing.List[discord.Message]]:
    """
    A helper coroutine that automatically sends more than one message should the
    content be more than `sep` characters long. The messages will be cut at spaces
    or line breaks, if possible.
    """
    send = smart_split(msg, sep)
    message_list = list()
    try:
        for message in send:
            message_list.append(await target.send(message))
        return message_list
    except discord.HTTPException as e:
        logging.error(f"Error while smart sending. Error {e}")
        try:
            with open('text.txt', 'w', encoding="utf-8") as f:
                f.write(msg)
            return await target.send("Error in paginating message.", file=discord.File(fp='text.txt'))
        except Exception as f:
            return await target.send(f"{(e, f)}: Error sending message.")

def error_embed(message: str, *, error="Error") -> discord.Embed:
    """Helper function to produce an error embed."""
    return discord.Embed(title=error, description = message, colour=discord.Colour.red())