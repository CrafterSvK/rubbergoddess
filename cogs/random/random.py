import random
import requests

import discord
from discord.ext import commands

from cogs.resource import CogText
from core import rubbercog, utils
from core.emote import emote


class Random(rubbercog.Rubbercog):
    """Pick, flip, roll dice"""

    def __init__(self, bot):
        super().__init__(bot)

        self.text = CogText("random")

    @commands.cooldown(rate=3, per=20.0, type=commands.BucketType.user)
    @commands.command()
    async def pick(self, ctx, *args):
        """Pick an option"""
        for i, arg in enumerate(args):
            if arg.endswith("?"):
                args = args[i + 1 :]
                break

        if not len(args):
            return

        option = self.sanitise(random.choice(args))
        if option is not None:
            await ctx.reply(option)

        await utils.room_check(ctx)

    @commands.cooldown(rate=3, per=20.0, type=commands.BucketType.user)
    @commands.command()
    async def flip(self, ctx):
        """Yes/No"""
        option = random.choice(self.text.get("flip"))
        await ctx.reply(option)
        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=20.0, type=commands.BucketType.user)
    @commands.command()
    async def random(self, ctx, first: int, second: int = None):
        """Pick number from interval"""
        if second is None:
            second = 0

        if first > second:
            first, second = second, first

        option = random.randint(first, second)
        await ctx.reply(option)
        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=20, type=commands.BucketType.channel)
    @commands.command(aliases=["unsplash"])
    async def picsum(self, ctx, *, seed: str = None):
        """Get random image from picsum.photos"""
        size = "900/600"
        url = "https://picsum.photos/"
        if seed:
            url += "seed/" + seed + "/"
        url += f"{size}.jpg?random={ctx.message.id}"

        # we cannot use the URL directly, because embed will contain other image than its thumbnail
        image = requests.get(url)
        if image.status_code != 200:
            return await ctx.reply(f"E{image.status_code}")

        # get image info
        # example url: https://i.picsum.photos/id/857/600/360.jpg?hmac=.....
        image_id = image.url.split("/id/", 1)[1].split("/")[0]
        image_info = requests.get(f"https://picsum.photos/id/{image_id}/info")
        try:
            image_url = image_info.json()["url"]
        except Exception:
            image_url = discord.Embed.Empty

        footer = "picsum.photos"
        if seed:
            footer += f" ({seed})"
        embed = self.embed(ctx=ctx, title=discord.Embed.Empty, description=image_url, footer=footer)
        embed.set_image(url=image.url)
        await ctx.reply(embed=embed)

        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=20, type=commands.BucketType.channel)
    @commands.command()
    async def cat(self, ctx):
        """Get random image of a cat"""
        data = requests.get("https://api.thecatapi.com/v1/images/search")
        if data.status_code != 200:
            return await ctx.reply(f"E{data.status_code}")

        embed = self.embed(ctx=ctx, title=discord.Embed.Empty, footer="thecatapi.com")
        embed.set_image(url=data.json()[0]["url"])
        await ctx.reply(embed=embed)

        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=20, type=commands.BucketType.channel)
    @commands.command()
    async def dog(self, ctx):
        """Get random image of a dog"""
        data = requests.get("https://api.thedogapi.com/v1/images/search")
        if data.status_code != 200:
            return await ctx.reply(f"E{data.status_code}")

        embed = self.embed(ctx=ctx, title=discord.Embed.Empty, footer="thedogapi.com")
        embed.set_image(url=data.json()[0]["url"])
        await ctx.reply(embed=embed)

        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=60, type=commands.BucketType.channel)
    @commands.command()
    async def xkcd(self, ctx, number: int = None):
        """Get random xkcd comics

        Arguments
        ---------
        number: Comics number. Omit to get random one.
        """
        # get maximal
        fetched = await utils.fetch_json("https://xkcd.com/info.0.json")
        # get random
        if number is None or number < 1 or number > fetched["num"]:
            number = random.randint(1, fetched["num"])
        # fetch requested
        if number != fetched["num"]:
            fetched = await utils.fetch_json(f"https://xkcd.com/{number}/info.0.json")

        embed = self.embed(
            ctx=ctx,
            title=fetched["title"],
            description="_" + fetched["alt"][:2046] + "_",
            footer="xkcd.com",
        )
        embed.add_field(
            name=(
                f"{fetched['year']}"
                f"-{str(fetched['month']).zfill(2)}"
                f"-{str(fetched['day']).zfill(2)}"
            ),
            value=(
                f"https://xkcd.com/{number}\n"
                + f"https://www.explainxkcd.com/wiki/index.php/{number}"
            ),
            inline=False,
        )
        embed.set_image(url=fetched["img"])
        await ctx.reply(embed=embed)

        await utils.room_check(ctx)

    @commands.cooldown(rate=5, per=60, type=commands.BucketType.channel)
    @commands.command()
    async def dadjoke(self, ctx, *, keyword: str = None):
        """Get random dad joke

        Arguments
        ---------
        keyword: search for a certain keyword in a joke
        """
        if keyword is not None and ("&" in keyword or "?" in keyword):
            await ctx.reply(self.text.get("joke_notfound"))
            return await utils.room_check(ctx)

        param = {"limit": "30"}
        url = "https://icanhazdadjoke.com"
        if keyword != None:
            param["term"] = keyword
            url += "/search"

        fetched = requests.get(url, headers={"Accept": "application/json"}, params=param)

        if keyword != None:
            res = fetched.json()["results"]
            if len(res) == 0:
                await ctx.reply(self.text.get("joke_notfound"))
                return await utils.room_check(ctx)
            result = random.choice(res)
        else:
            result = fetched.json()

        embed = self.embed(
            ctx=ctx,
            description=result["joke"],
            footer="icanhazdadjoke.com",
            url="https://icanhazdadjoke.com/j/" + result["id"],
        )
        await ctx.reply(embed=embed)
        await utils.room_check(ctx)
