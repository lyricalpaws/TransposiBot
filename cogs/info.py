import time
import discord
import psutil
import os
import asyncio
import io
import requests
import dhooks
import json
import unicodedata
import inspect
import random

from urllib.parse import quote
from collections import Counter
from dhooks import Webhook
from discord.ext import commands
from datetime import datetime
from utils import repo, default, permissions, pawgenator


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = default.get("config.json")
        self.process = psutil.Process(os.getpid())
        self.counter = Counter()

    def cleanup_code(self, content):
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])
        return content.strip("` \n")

    async def getserverstuff(self, ctx):
        query = "SELECT * FROM adminpanel WHERE serverid = $1;"
        row = await self.bot.db.fetchrow(query, ctx.guild.id)
        if row is None:
            query = "INSERT INTO adminpanel VALUES ($1, $2, $3, $4, $5, $6, $7);"
            await self.bot.db.execute(query, ctx.guild.id, 0, 0, 1, 0, 0, 0)
            query = "SELECT * FROM adminpanel WHERE serverid = $1;"
            row = await self.bot.db.fetchrow(query, ctx.guild.id)
        return row

    def get_bot_uptime(self, *, brief=False):
        now = datetime.utcnow()
        delta = now - self.bot.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if not brief:
            if days:
                fmt = "{d} days, {h} hours, {m} minutes, and {s} seconds"
            else:
                fmt = "{h} hours, {m} minutes, and {s} seconds"
        else:
            fmt = "{h}h {m}m {s}s"
            if days:
                fmt = "{d}d " + fmt

        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    async def category_gen(self, ctx):
        categories = {}

        for command in set(ctx.bot.walk_commands()):
            try:
                if command.category not in categories:
                    categories.update({command.category: []})
            except AttributeError:
                cog = command.cog_name or "Bot"
                if command.cog_name not in categories:
                    categories.update({cog: []})

        for command in set(ctx.bot.walk_commands()):
            if not command.hidden:
                try:
                    if command.category:
                        categories[command.category].append(command)
                except AttributeError:
                    cog = command.cog_name or "Bot"
                    categories[cog].append(command)

        return categories

    async def commandMapper(self, ctx):
        pages = []

        for category, commands in (await self.category_gen(ctx)).items():
            if not commands:
                continue
            cog = ctx.bot.get_cog(category)
            if cog:
                category = f"**⚙️ {category}**"
            commands = ", ".join([c.qualified_name for c in commands])
            embed = (
                discord.Embed(
                    color=random.randint(0x000000, 0xFFFFFF),
                    title=f"{ctx.bot.user.display_name} Commands",
                    description=f"{category}",
                )
                .set_footer(
                    text=f"Type {ctx.prefix}help <command> for more help".replace(
                        ctx.me.mention, "@Pawbot "
                    ),
                    icon_url=ctx.author.avatar_url,
                )
                .add_field(name="**Commands:**", value=f"``{commands}``")
            )
            pages.append(embed)
        await pawgenator.SimplePaginator(
            extras=sorted(pages, key=lambda d: d.description)
        ).paginate(ctx)

    async def cogMapper(self, ctx, entity, cogname: str):
        try:
            await ctx.send(
                embed=discord.Embed(
                    color=random.randint(0x000000, 0xFFFFFF),
                    title=f"{ctx.bot.user.display_name} Commands",
                    description=f"**⚙️ {cogname}**",
                )
                .add_field(
                    name="**Commands:**",
                    value=f"``{', '.join([c.qualified_name for c in set(ctx.bot.walk_commands()) if c.cog_name == cogname])}``",
                )
                .set_footer(
                    text=f"Type {ctx.prefix}help <command> for more help".replace(
                        ctx.me.mention, "@Pawbot "
                    ),
                    icon_url=ctx.author.avatar_url,
                )
            )
        except BaseException:
            await ctx.send(
                f":x: | **Command or category not found. Use {ctx.prefix}help**",
                delete_after=10,
            )

    @commands.command(aliases=["?"])
    async def help(self, ctx, *, command: str = None):
        """View Bot Help Menu"""
        if not command:
            await self.commandMapper(ctx)
        else:
            entity = self.bot.get_cog(command) or self.bot.get_command(command)
            if entity is None:
                return await ctx.send(
                    f":x: | **Command or category not found. Use {ctx.prefix}help**",
                    delete_after=10,
                )
            if isinstance(entity, commands.Command):
                await pawgenator.SimplePaginator(
                    title=f"Command: {entity.name}",
                    entries=[
                        f"**:bulb: Command Help**\n```ini\n[{entity.help}]```",
                        f"**:video_game: Command Signature**\n```ini\n{entity.signature}```",
                    ],
                    length=1,
                    colour=random.randint(0x000000, 0xFFFFFF),
                ).paginate(ctx)
            else:
                await self.cogMapper(ctx, entity, command)

    @commands.command()
    async def ping(self, ctx):
        """ Pong! """
        before = time.monotonic()
        message = await ctx.send("Did you just ping me?!")
        ping = (time.monotonic() - before) * 1000
        await message.edit(
            content=f"`MSG :: {int(ping)}ms\nAPI :: {round(self.bot.latency * 1000)}ms`"
        )

    @commands.command()
    @commands.guild_only()
    async def avatar(self, ctx, user: discord.Member = None):
        """ Get the avatar of you or someone else """
        rowcheck = await self.getserverstuff(ctx)

        if user is None:
            user = ctx.author

        if rowcheck["embeds"] == 0 or not permissions.can_embed(ctx):
            return await ctx.send(user.avatar_url)

        embed = discord.Embed(colour=249_742)
        embed.set_image(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def joinedat(self, ctx, user: discord.Member = None):
        """ Check when a user joined the current server """
        rowcheck = await self.getserverstuff(ctx)

        if user is None:
            user = ctx.author

        if rowcheck["embeds"] == 0 or not permissions.can_embed(ctx):
            return await ctx.send(
                f"**{user}** joined **{ctx.guild.name}**\n{default.date(user.joined_at)}"
            )

        embed = discord.Embed(colour=249_742)
        embed.set_thumbnail(url=user.avatar_url)
        embed.description = (
            f"**{user}** joined **{ctx.guild.name}**\n{default.date(user.joined_at)}"
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def server(self, ctx):
        """ Check info about current server """
        if ctx.invoked_subcommand is None:

            rowcheck = await self.getserverstuff(ctx)

            findbots = sum(1 for member in ctx.guild.members if member.bot)

            emojilist = "​"
            for Emoji in ctx.guild.emojis:
                emojilist += f"{Emoji} "
            if len(emojilist) > 1024:
                emojilist = "Too long!"

            if rowcheck["embeds"] == 0 or not permissions.can_embed(ctx):
                return await ctx.send(
                    f"```\nServer Name: {ctx.guild.name}\nServer ID: {ctx.guild.id}\nMembers: {ctx.guild.member_count}\nBots: {findbots}\nOwner: {ctx.guild.owner}\nRegion: {ctx.guild.region}\nCreated At: {default.date(ctx.guild.created_at)}\n```\nEmojis: {emojilist}"
                )

            embed = discord.Embed(colour=249_742)
            embed.set_thumbnail(url=ctx.guild.icon_url)
            embed.add_field(name="Server Name", value=ctx.guild.name, inline=True)
            embed.add_field(name="Server ID", value=ctx.guild.id, inline=True)
            embed.add_field(name="Members", value=ctx.guild.member_count, inline=True)
            embed.add_field(name="Bots", value=findbots, inline=True)
            embed.add_field(name="Owner", value=ctx.guild.owner, inline=True)
            embed.add_field(name="Region", value=ctx.guild.region, inline=True)
            embed.add_field(name="Emojis", value=emojilist, inline=False)
            embed.add_field(
                name="Created", value=default.date(ctx.guild.created_at), inline=False
            )
            await ctx.send(
                content=f"ℹ information about **{ctx.guild.name}**", embed=embed
            )

    @commands.command()
    @commands.guild_only()
    async def user(self, ctx, user: discord.Member = None):
        """ Get user information """
        rowcheck = await self.getserverstuff(ctx)

        if user is None:
            user = ctx.author

        embed = discord.Embed(colour=249_742)

        usrstatus = user.status

        if usrstatus == "online" or usrstatus == discord.Status.online:
            usrstatus = "<:online:514203909363859459> Online"
        elif usrstatus == "idle" or usrstatus == discord.Status.idle:
            usrstatus = "<:away:514203859057639444> Away"
        elif usrstatus == "dnd" or usrstatus == discord.Status.dnd:
            usrstatus = "<:dnd:514203823888138240> DnD"
        elif usrstatus == "offline" or usrstatus == discord.Status.offline:
            usrstatus = "<:offline:514203770452836359> Offline"
        else:
            usrstatus = "Broken"

        if user.nick:
            nick = user.nick
        else:
            nick = "No Nickname"

        if user.activity:
            usrgame = f"{user.activity.name}"
        else:
            usrgame = "No current game"

        usrroles = ""

        for Role in user.roles:
            if "@everyone" in Role.name:
                usrroles += "| @everyone | "
            else:
                usrroles += f"{Role.name} | "

        if len(usrroles) > 1024:
            usrroles = "Too many to count!"

        if rowcheck["embeds"] == 0 or not permissions.can_embed(ctx):
            return await ctx.send(
                f"Name: `{user.name}#{user.discriminator}`\nNick: `{nick}`\nUID: `{user.id}`\nStatus: {usrstatus}\nGame: `{usrgame}`\nIs a bot? `{user.bot}`\nCreated On: `{default.date(user.created_at)}`\nRoles:\n```\n{usrroles}\n```"
            )

        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(
            name="Name",
            value=f"{user.name}#{user.discriminator}\n{nick}\n({user.id})",
            inline=True,
        )
        embed.add_field(name="Status", value=usrstatus, inline=True)
        embed.add_field(name="Game", value=usrgame, inline=True)
        embed.add_field(name="Is bot?", value=user.bot, inline=True)
        embed.add_field(name="Roles", value=usrroles, inline=False)
        embed.add_field(
            name="Created On", value=default.date(user.created_at), inline=True
        )
        if hasattr(user, "joined_at"):
            embed.add_field(
                name="Joined this server",
                value=default.date(user.joined_at),
                inline=True,
            )
        await ctx.send(content=f"ℹ About **{user.name}**", embed=embed)

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def poll(self, ctx, time, *, question):
        """
        Creates a poll
        """
        await ctx.message.delete()
        time = int(time)
        pollmsg = await ctx.send(
            f"{ctx.message.author.mention} created a poll that will end after {time} seconds!\n**{question}**\n\nReact with :thumbsup: or :thumbsdown: to vote!"
        )
        await pollmsg.add_reaction("👍")
        await pollmsg.add_reaction("👎")
        await asyncio.sleep(time)
        reactiongrab = await ctx.channel.get_message(pollmsg.id)
        for reaction in reactiongrab.reactions:
            if reaction.emoji == str("👍"):
                upvote_count = reaction.count
            else:
                if reaction.emoji == str("👎"):
                    downvote_count = reaction.count
                else:
                    pass
        await pollmsg.edit(
            content=f"{ctx.message.author.mention} created a poll that will end after {time} seconds!\n**{question}**\n\nTime's up!\n👍 = {upvote_count-1}\n\n👎 = {downvote_count-1}"
        )

    @commands.command()
    async def jumbo(self, ctx, emoji: discord.PartialEmoji):
        """ Makes your emoji  B I G """

        def url_to_bytes(url):
            data = requests.get(url)
            content = io.BytesIO(data.content)
            filename = url.rsplit("/", 1)[-1]
            return {"content": content, "filename": filename}

        file = url_to_bytes(emoji.url)
        await ctx.send(file=discord.File(file["content"], file["filename"]))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def calc(self, ctx, *, calculation: str):
        """ Performs a calculation """
        r = requests.get(
            f"https://www.calcatraz.com/calculator/api?c={quote(calculation)}"
        )
        await ctx.send(r.text)

    @commands.command(name="eval")
    @commands.cooldown(rate=1, per=10.0, type=commands.BucketType.user)
    async def _eval(self, ctx, *, code: commands.clean_content):
        """ Runs a piece of python code """
        r = requests.post(
            "http://coliru.stacked-crooked.com/compile",
            data=json.dumps(
                {"cmd": "python3 main.cpp", "src": self.cleanup_code(code)}
            ),
        )
        emoji = self.bot.get_emoji(508_388_437_661_843_483)
        await ctx.message.add_reaction(emoji)
        await ctx.send(
            f"```py\n{r.text}\n```\n(This is **not** an open eval, everything is sandboxed)"
        )

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def osu(self, ctx, osuplayer, usrhex: str = 170_041):
        """ Shows an osu! profile. """
        embed = discord.Embed(color=random.randint(0x000000, 0xFFFFFF))
        embed.set_image(
            url="http://lemmmy.pw/osusig/sig.php?colour=hex{0}&uname={1}&pp=1&countryrank&removeavmargin&flagshadow&flagstroke&darktriangles&onlineindicator=undefined&xpbar&xpbarhex".format(
                usrhex, osuplayer
            )
        )
        embed.set_footer(
            text="Powered by lemmmy.pw",
            icon_url="https://raw.githubusercontent.com/F4stZ4p/resources-for-discord-bot/master/osusmall.ico",
        )
        await ctx.send(embed=embed)


    @commands.command(aliases=["t"])
    @commands.guild_only()
    async def tag(self, ctx, *, tagname: str):
        query = "SELECT * FROM tags WHERE serverid=$1 AND tagname=$2;"
        r = await self.bot.db.fetchrow(query, ctx.guild.id, tagname)
        if not r:
            return await ctx.send("No tag found...")
        await ctx.send(r["tagtext"])

    @commands.command(aliases=["tl"])
    @commands.guild_only()
    async def tags(self, ctx):
        query = "SELECT tagname FROM tags WHERE serverid=$1;"
        query = await self.bot.db.fetch(query, ctx.guild.id)
        msg = ""
        for r in query:
            msg += f"`{r['tagname']}` "
        if not msg:
            msg = "No tags found..."
        await ctx.send(msg)

    @commands.command(aliases=["at"])
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def addtag(self, ctx, tagname: str, *, tagtext: str):
        query = "SELECT * FROM tags WHERE serverid=$1 AND tagname=$2;"
        query = await self.bot.db.fetchrow(query, ctx.guild.id, tagname)
        if query:
            return await ctx.send("That tag already exists!")
        query = "INSERT INTO tags VALUES ($1, $2, $3);"
        await self.bot.db.execute(query, ctx.guild.id, tagname, tagtext)
        await ctx.send(f"Created the tag `{tagname}`!")

    @commands.command(aliases=["dt"])
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def deltag(self, ctx, tagname: str):
        query = "SELECT * FROM tags WHERE serverid=$1 AND tagname=$2;"
        query = await self.bot.db.fetchrow(query, ctx.guild.id, tagname)
        if not query:
            return await ctx.send("No tag found...")
        query = "DELETE FROM tags WHERE serverid=$1 AND tagname=$2;"
        query = await self.bot.db.execute(query, ctx.guild.id, tagname)
        await ctx.send(f"Successfully deleted {tagname}")


def setup(bot):
    bot.add_cog(Information(bot))
