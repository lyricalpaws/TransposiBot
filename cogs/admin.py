import time
import aiohttp
import traceback
import discord
import textwrap
import io
import json
import requests
import shlex
import asyncio
import gc
import os

from subprocess import Popen, PIPE
from io import BytesIO
from bs4 import BeautifulSoup
from dhooks import Webhook
from utils.formats import TabularData, Plural
from contextlib import redirect_stdout
from copy import copy
from typing import Union
from utils import repo, default, http, dataIO
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = default.get("config.json")
        self._last_result = None
        self.sessions = set()

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace("_", " ").replace("guild", "server").title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name="Allowed", value="\n".join(allowed))
        e.add_field(name="Denied", value="\n".join(denied))
        await ctx.send(embed=e)

    async def do_removal(
        self, ctx, limit, predicate, *, before=None, after=None, message=True
    ):
        if limit > 2000:
            return await ctx.send(f"Too many messages to search given ({limit}/2000)")

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(
                limit=limit, before=before, after=after, check=predicate
            )
        except discord.Forbidden:
            return await ctx.send("I do not have permissions to delete messages.")
        except discord.HTTPException as e:
            return await ctx.send(f"Error: {e} (try a smaller search?)")

        deleted = len(deleted)
        if message is True:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(f"🚮 Successfully cleaned up my messages.", delete_after=5)

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    @staticmethod
    def get_syntax_error(e):
        if e.text is None:
            return f"```py\n{e.__class__.__name__}: {e}\n```"
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    @commands.command(aliases=["re"], hidden=True)
    @commands.check(repo.is_owner)
    async def reload(self, ctx, name: str):
        """ Reloads an extension. """
        await ctx.message.add_reaction("a:loading:528744937794043934")
        try:
            self.bot.unload_extension(f"cogs.{name}")
            self.bot.load_extension(f"cogs.{name}")
        except ModuleNotFoundError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        except SyntaxError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def reboot(self, ctx):
        """ Reboot the bot """
        await ctx.send("Rebooting now...")
        time.sleep(1)
        await self.bot.logout()

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def load(self, ctx, name: str):
        """ Loads an extension. """
        await ctx.message.add_reaction("a:loading:528744937794043934")
        try:
            self.bot.load_extension(f"cogs.{name}")
        except ModuleNotFoundError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        except SyntaxError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def unload(self, ctx, name: str):
        """ Unloads an extension. """
        await ctx.message.add_reaction("a:loading:528744937794043934")
        try:
            self.bot.unload_extension(f"cogs.{name}")
        except ModuleNotFoundError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        except SyntaxError as e:
            logchannel = self.bot.get_channel(508_420_200_815_656_966)
            await logchannel.send(f"`[WARN]` `Command Error`\n```py\n{e}\n```")
            await ctx.message.remove_reaction(
                "a:loading:528744937794043934", member=ctx.me
            )
            return await ctx.message.add_reaction(":notdone:528747883571445801")
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.group(hidden=True)
    @commands.check(repo.is_owner)
    async def change(self, ctx):
        if ctx.invoked_subcommand is None:
            _help = await ctx.bot.formatter.format_help_for(ctx, ctx.command)

            for page in _help:
                await ctx.send(page)

    @change.command(name="playing", hidden=True)
    @commands.check(repo.is_owner)
    async def change_playing(self, ctx, *, playing: str):
        """ Change playing status. """
        try:
            await self.bot.change_presence(
                activity=discord.Game(type=0, name=playing),
                status=discord.Status.online,
            )
            dataIO.change_value("config.json", "playing", playing)
            await ctx.send(f"Successfully changed playing status to **{playing}**")
        except discord.InvalidArgument as err:
            await ctx.send(err)
        except Exception as e:
            await ctx.send(e)

    @change.command(name="username", hidden=True)
    @commands.check(repo.is_owner)
    async def change_username(self, ctx, *, name: str):
        """ Change username. """
        try:
            await self.bot.user.edit(username=name)
            await ctx.send(f"Successfully changed username to **{name}**")
        except discord.HTTPException as err:
            await ctx.send(err)

    @change.command(name="nickname", hidden=True)
    @commands.check(repo.is_owner)
    async def change_nickname(self, ctx, *, name: str = None):
        """ Change nickname. """
        try:
            await ctx.guild.me.edit(nick=name)
            if name:
                await ctx.send(f"Successfully changed nickname to **{name}**")
            else:
                await ctx.send("Successfully removed nickname")
        except Exception as err:
            await ctx.send(err)

    @change.command(name="avatar", hidden=True)
    @commands.check(repo.is_owner)
    async def change_avatar(self, ctx, url: str = None):
        """ Change avatar. """
        if url is None and len(ctx.message.attachments) == 1:
            url = ctx.message.attachments[0].url
        else:
            url = url.strip("<>")

        try:
            bio = await http.get(url, res_method="read")
            await self.bot.user.edit(avatar=bio)
            await ctx.send(f"Successfully changed the avatar. Currently using:\n{url}")
        except aiohttp.InvalidURL:
            await ctx.send("The URL is invalid...")
        except discord.InvalidArgument:
            await ctx.send("This URL does not contain a usable image")
        except discord.HTTPException as err:
            await ctx.send(err)

    @commands.command(pass_context=True, name="compile", hidden=True)
    @commands.check(repo.is_owner)
    async def _compile(self, ctx, *, body: str):
        """ Compiles some code """
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_result,
        }

        if "bot.http.token" in body:
            return await ctx.send(f"You can't take my token {ctx.author.name}")
        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            start = time.perf_counter()
            exec(to_compile, env)
        except EnvironmentError as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
        else:
            try:
                value = stdout.getvalue()
                reactiontosend = self.bot.get_emoji(508_388_437_661_843_483)
                await ctx.message.add_reaction(reactiontosend)
                dt = (time.perf_counter() - start) * 1000.0
            except discord.Forbidden:
                return await ctx.send("I couldn't react...")

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")
            else:
                if self.config.token in ret:
                    ret = self.config.realtoken
                self._last_result = ret
                await ctx.send(
                    f"Inputted code:\n```py\n{body}\n```\n\nOutputted Code:\n```py\n{value}{ret}\n```\n*Compiled in {dt:.2f}ms*"
                )

    @commands.group(aliases=["as"], hidden=True)
    @commands.check(repo.is_owner)
    async def sudo(self, ctx):
        """ Run a cmd under an altered context """
        if ctx.invoked_subcommand is None:
            await ctx.send("...")

    @sudo.command(aliases=["user"], hidden=True)
    @commands.check(repo.is_owner)
    async def sudo_user(
        self, ctx, who: Union[discord.Member, discord.User], *, command: str
    ):
        """ Run a cmd under someone else's name """
        msg = copy(ctx.message)
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg)
        await self.bot.invoke(new_ctx)
        await ctx.message.add_reaction(":done:513831607262511124")

    @sudo.command(aliases=["channel"], hidden=True)
    @commands.check(repo.is_owner)
    async def sudo_channel(self, ctx, chid: int, *, command: str):
        """ Run a command in a different channel. """
        cmd = copy(ctx.message)
        cmd.channel = self.bot.get_channel(chid)
        cmd.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(cmd)
        await self.bot.invoke(new_ctx)
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def cogs(self, ctx):
        """ Gives all loaded cogs """
        mod = ", ".join(list(self.bot.cogs))
        await ctx.send(f"The current modules are:\n```\n{mod}\n```")

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""

        query = self.cleanup_code(query)

        is_multistatement = query.count(";") > 1
        if is_multistatement:
            strategy = self.bot.db.execute
        else:
            strategy = self.bot.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f"```py\n{traceback.format_exc()}\n```")

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f"`{dt:.2f}ms: {results}`")

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f"```\n{render}\n```\n*Returned {Plural(row=rows)} in {dt:.2f}ms*"
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode("utf-8"))
            await ctx.send("Too many results...", file=discord.File(fp, "results.txt"))
        else:
            await ctx.send(fmt)

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def cleanup(self, ctx, search=100):
        await ctx.message.add_reaction("a:loading:528744937794043934")

        def predicate(m):
            return m.author == ctx.me

        await self.do_removal(ctx, search, predicate)
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.command(hidden=True)
    @commands.check(repo.is_owner)
    async def shell(self, ctx: commands.Context, *, command: str) -> None:
        """ Run a shell command. """

        def run_shell(command):
            with Popen(command, stdout=PIPE, stderr=PIPE, shell=True) as proc:
                return [std.decode("utf-8") for std in proc.communicate()]

        command = self.cleanup_code(command)
        argv = shlex.split(command)
        stdout, stderr = await self.bot.loop.run_in_executor(None, run_shell, argv)
        if stdout:
            if len(stdout) >= 1500:
                print(stdout)
                return await ctx.send("Too big I'll print it instead")
            await ctx.send(f"```\n{stdout}\n```")
        if stderr:
            if len(stderr) >= 1500:
                print(stderr)
                return await ctx.send("Too big I'll print it instead")
            await ctx.send(f"```\n{stderr}\n```")

    @commands.command(hidden=True, aliases=["pull"])
    @commands.check(repo.is_owner)
    async def update(self, ctx, silently: bool = False):
        """ Gets latest commits and applies them from git """
        await ctx.message.add_reaction("a:loading:528744937794043934")

        def run_shell(command):
            with Popen(command, stdout=PIPE, stderr=PIPE, shell=True) as proc:
                return [std.decode("utf-8") for std in proc.communicate()]

        pull = await self.bot.loop.run_in_executor(
            None, run_shell, "git pull origin master"
        )
        msg = await ctx.send(f"```css\n{pull}\n```", delete_after=6)
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                name = file[:-3]
                self.bot.unload_extension(f"cogs.{name}")
                self.bot.load_extension(f"cogs.{name}")
        await ctx.message.add_reaction(":done:513831607262511124")

    @commands.command(hidden=True, aliases=["botperms"])
    @commands.guild_only()
    @commands.check(repo.is_owner)
    async def botpermissions(self, ctx, *, channel: discord.TextChannel = None):
        """ Shows the bot's permissions in a specific channel. """
        channel = channel or ctx.channel
        member = ctx.guild.me
        await self.say_permissions(ctx, member, channel)

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(repo.is_owner)
    async def speedup(self, ctx):
        await ctx.message.add_reaction("a:loading:528744937794043934")
        gc.collect()
        del gc.garbage[:]
        await ctx.message.remove_reaction("a:loading:528744937794043934", member=ctx.me)
        await ctx.message.add_reaction(":done:513831607262511124")


def setup(bot):
    bot.add_cog(Admin(bot))
