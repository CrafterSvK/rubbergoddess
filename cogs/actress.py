import hjson
import os
import shlex
from requests import get

import discord
from discord.ext import commands

from core import check, rubbercog, utils
from core.config import config
from core.text import text


class Actress(rubbercog.Rubbercog):
    """Be a human"""

    def __init__(self, bot):
        super().__init__(bot)

        self.path = os.getcwd() + "/data/actress/reactions.hjson"
        try:
            self.reactions = hjson.load(open(self.path))
        except:
            self.reactions = {}
        self.usage = {}

    ##
    ## Commands
    ##

    """
    ?send text <channel> <text>
    ?send image <channel> <path>

    ?react list
    ?react usage
    ?react add <name>
    type <image|text>
    match <full|start|end|any>
    caps <ignore|match>
    triggers "t1" "t 2"
    response "string"
    users 0 1 2
    channels 0 1 2
    ?react remove <name>
    ?react edit <name>
    match <full|start|end|any>
    caps <ignore|match>
    triggers "t1" "t 2"
    response "string"

    ?image list
    ?image download <url> <filename>
    ?image show <filename>

    ?change avatar
    ?change name
    """

    @commands.check(check.is_mod)
    @commands.group(name="react", aliases=["reaction", "reactions"])
    async def react(self, ctx):
        await utils.send_help(ctx)

    @react.command(name="list")
    async def react_list(self, ctx):
        """List current reactions"""
        try:
            name = next(iter(self.reactions))
            reaction = self.reactions[name]
            embed = self.embed(ctx=ctx, page=(1, len(self.reactions)))
        except StopIteration:
            reaction = None
            embed = self.embed(ctx=ctx)

        if reaction is not None:
            embed = self.fill_reaction_embed(embed, reaction)

        message = await ctx.send(embed=embed)

        if len(self.reactions) > 1:
            await message.add_reaction("◀")
            await message.add_reaction("▶")

    @react.command(name="add")
    async def react_add(self, ctx, name: str = None, *, parameters=None):
        """Add new reaction

        ```
        ?react add <reaction name>
        type <image | text>
        match <full | start | end | any>
        sensitive <true | false>
        triggers "a b c" "d e" f
        responses "abc def"

        users 0 1 2
        channels 0 1 2
        counter 10
        ```
        """
        if name is None:
            return await utils.send_help(ctx)
        elif name in self.reactions.keys():
            raise ReactionNameExists()

        reaction = await self.parse_react_message(ctx.message, strict=True)
        self.reactions[name] = reaction
        self._save_reactions()

        await self.output.info(ctx, f"Reaction **{name}** added.")
        await self.event.sudo(ctx.author, ctx.channel, f"Reaction **{name}** added.")

    @react.command(name="edit")
    async def react_edit(self, ctx, name: str = None, *, parameters=None):
        """Edit reaction

        ```
        ?react edit <reaction name>
        type <image | text>
        match <full | start | end | any>
        sensitive <true | false>
        triggers "a b c" "d e" f
        responses "abc def"

        users 0 1 2
        channels 0 1 2
        counter 10
        ```
        """
        if name is None:
            return await utils.send_help(ctx)
        elif name not in self.reactions.keys():
            raise ReactionNotFound()

        new_reaction = await self.parse_react_message(ctx.message, strict=False)
        reaction = self.reactions[name]

        for key, value in reaction.items():
            if key in new_reaction.keys():
                reaction[key] = new_reaction[key]

        self.reactions[name] = reaction
        self._save_reactions()

        await self.output.info(ctx, f"Reaction **{name}** updated.")
        await self.event.sudo(ctx.author, ctx.channel, f"Reaction **{name}** updated.")

    @react.command(name="remove")
    async def react_remove(self, ctx, name: str = None):
        """Remove reaction"""
        if name is None:
            return await utils.send_help(ctx)
        elif name not in self.reactions.keys():
            raise ReactionNotFound()

        del self.reactions[name]
        self._save_reactions()

        await self.output.info(ctx, f"Reaction **{name}** removed.")
        await self.event.sudo(ctx.author, ctx.channel, f"Reaction **{name}** removed.")

    ##
    ## Listeners
    ##

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        # do we care?
        if user.bot:
            return  # TODO Remove reaction

        if hasattr(reaction, "emoji"):
            if str(reaction.emoji) == "◀":
                page_delta = -1
            elif str(reaction.emoji) == "▶":
                page_delta = 1
            else:
                return  # TODO Remove reaction
        else:
            return  # TODO Remove reaction
        if len(reaction.message.embeds) != 1:
            return
        embed = reaction.message.embeds[0]
        if not embed.title.endswith("react list"):
            return  # TODO Remove reaction
        if embed.footer == discord.Embed.Empty or " | " not in embed.footer.text:
            return  # TODO Remove reaction

        # get page
        footer_text = embed.footer.text
        pages = footer_text.split(" | ")[-1]
        page_current = int(pages.split("/")[0]) - 1

        page = (page_current + page_delta) % len(self.reactions)
        footer_text = footer_text.replace(pages, f"{page+1}/{len(self.reactions)}")

        # update embed
        bot_reaction_name = list(self.reactions.keys())[page]
        bot_reaction = self.reactions[bot_reaction_name]

        embed = self.fill_reaction_embed(embed, bot_reaction)
        embed.set_footer(text=footer_text, icon_url=embed.footer.icon_url)
        await reaction.message.edit(embed=embed)

        # remove reaction
        try:
            await reaction.remove(user)
        except:
            pass

    ##
    ## Helper functions
    ##
    def _save_reactions(self):
        with open(self.path, "w", encoding="utf-8") as f:
            hjson.dump(self.reactions, f, ensure_ascii=False, indent="\t")

    ##
    ## Logic
    ##
    async def parse_react_message(self, message: discord.Message, strict: bool) -> dict:
        content = message.content.replace("`", "").split("\n")[1:]
        result = {}

        # fill values
        for line in content:
            line = line.split(" ", 1)
            key = line[0]
            value = line[1]

            if key not in (
                "type",
                "match",
                "sensitive",
                "triggers",
                "responses",
                "users",
                "channels",
                "counter",
            ):
                raise InvalidReactionKey(key=key)

            # check
            invalid = False
            # fmt: off
            if key == "type" and value not in ("text", "image") \
            or key == "match" and value not in ("full", "start", "end", "any") \
            or key == "sensitive" and value not in ("true", "false") \
            or key == "triggers" and len(value) < 1 \
            or key == "responses" and len(value) < 1:
                invalid = True

            # fmt: on
            if invalid:
                raise ReactionParsingException(key, value)

            # parse
            if key == "sensitive":
                value = value == "true"
            elif key in ("triggers", "responses"):
                # convert to list
                value = shlex.split(value)
            elif key in ("users", "channels"):
                # convert to list of ints
                try:
                    value = [int(x) for x in shlex.split(value)]
                except:
                    raise ReactionParsingException(key, value)
            elif key == "counter":
                try:
                    value = int(value)
                except:
                    raise ReactionParsingException(key, value)

            result[key] = value

        if strict:
            # check if all required values are present
            for key in ("type", "match", "triggers", "response"):
                if key is None:
                    raise discord.MissingRequiredArgument(param=key)

        return result

    def fill_reaction_embed(self, embed: discord.Embed, reaction: dict) -> discord.Embed:
        # reset any previous
        embed.clear_fields()

        for key in ("triggers", "responses"):
            value = "\n".join(reaction[key])
            embed.add_field(name=key, value=value, inline=False)
        for key in ("type", "match", "sensitive"):
            embed.add_field(name=key, value=reaction[key])
        if "users" in reaction.keys() and reaction["users"] is not None:
            users = [self.bot.get_user(x) for x in reaction["users"]]
            value = "\n".join(
                f"`{user.id}` {user.name if hasattr(user, 'name') else '_unknown_'}"
                for user in users
            )
            embed.add_field(name="users", value=value, inline=False)
        if "channels" in reaction.keys() and reaction["channels"] is not None:
            channels = [self.bot.get_channel(x) for x in reaction["channels"]]
            value = "\n".join(f"`{channel.id}` {channel.mention}" for channel in channels)
            embed.add_field(name="channels", value=value, inline=False)
        if "counter" in reaction.keys() and reaction["counter"] is not None:
            embed.add_field(name="countdown", value=str(reaction["counter"]))

        return embed

    ##
    ## Error catching
    ##
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        # try to get original error
        if hasattr(ctx.command, "on_error") or hasattr(ctx.command, "on_command_error"):
            return
        error = getattr(error, "original", error)

        # non-rubbergoddess exceptions are handled globally
        if not isinstance(error, rubbercog.RubbercogException):
            return

        # fmt: off
        # exceptions with parameters
        if isinstance(error, InvalidReactionKey):
            await self.output.error(ctx, text.fill(
                "actress", "InvalidReactionKey", key=error.key))
        elif isinstance(error, ReactionParsingException):
            await self.output.error(ctx, text.fill(
                "actress", "ReactionParsingException", key=error.key, value=error.value))
        # exceptions without parameters
        elif isinstance(error, ActressException):
            await self.output.error(ctx, text.get("actress", type(error).__name__))
        # fmt: on


def setup(bot):
    bot.add_cog(Actress(bot))


class ActressException(rubbercog.RubbercogException):
    pass


class ReactionException(ActressException):
    pass


class ReactionNameExists(ReactionException):
    pass


class ReactionNotFound(ReactionException):
    pass


class InvalidReactionKey(ReactionException):
    def __init__(self, key: str):
        super().__init__()
        self.key = key


class ReactionParsingException(ReactionException):
    def __init__(self, key: str, value: str):
        super().__init__()
        self.key = key
        self.value = value
