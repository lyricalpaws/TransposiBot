import asyncio
import discord

from collections import Counter
from utils import permissions, default, lists
from discord.ext.commands import AutoShardedBot

config = default.get("config.json")


class Bot(AutoShardedBot):
    def __init__(self, *args, prefix=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = kwargs.pop("db")
        self.counter = Counter()
        self.blacklist = [entry for entry in config.blacklist]
        self.snipes = {}

    async def getserverstuff(self, message):
        query = "SELECT * FROM adminpanel WHERE serverid = $1;"
        row = await self.db.fetchrow(query, message.guild.id)
        if row is None:
            query = "INSERT INTO adminpanel VALUES ($1, $2, $3, $4, $5, $6, $7);"
            await self.db.execute(query, message.guild.id, 0, 0, 1, 0, 0, 0)
            query = "SELECT * FROM adminpanel WHERE serverid = $1;"
            row = await self.db.fetchrow(query, message.guild.id)
        return row

    async def getautomod(self, message):
        query = "SELECT * FROM automod WHERE serverid = $1;"
        row = await self.db.fetchrow(query, message.guild.id)
        if row is None:
            query = "INSERT INTO automod VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);"
            await self.db.execute(query, message.guild.id, 0, 0, 0, 0, 10, 10, 0, 0)
            query = "SELECT * FROM automod WHERE serverid = $1;"
            row = await self.db.fetchrow(query, message.guild.id)
        return row

    async def getstorestuff(self, message):
        storequery = "SELECT * FROM idstore WHERE serverid = $1;"
        storerow = await self.db.fetchrow(storequery, message.guild.id)
        if storerow is None:
            query = "INSERT INTO idstore VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);"
            await self.db.execute(
                query, message.guild.id, "Default", "Default", 0, 0, 0, 0, 0, 0
            )
            query = "SELECT * FROM idstore WHERE serverid = $1;"
            storerow = await self.db.fetchrow(query, message.guild.id)
        return storerow

    async def on_message(self, message):
        uplink = default.get("uplink.json")
        adminpanelcheck = await self.getserverstuff(message)

        if (
            not self.is_ready()
            or message.author.bot
            or not permissions.can_send(message)
            or message.author.id in self.blacklist
        ):
            return
        if message.channel.id == uplink.uplinkchan:
            downlinkchannel = self.get_channel(uplink.downlinkchan)
            await downlinkchannel.send(
                f"{message.author.name}#{message.author.discriminator}: {message.content}"
            )
        if message.channel.id == uplink.downlinkchan:
            uplinkchannel = self.get_channel(uplink.uplinkchan)
            await uplinkchannel.send(
                f"{message.author.name}#{message.author.discriminator}: {message.content}"
            )
        if adminpanelcheck["automod"] == 1:
            automodcheck = await self.getautomod(message)
            serverstorecheck = await self.getstorestuff(message)
            if automodcheck["adblock"] == 1:
                for entry in lists.discordAds:
                    if entry in message.content:
                        if automodcheck["ignorerole"] == 1:
                            ignorerole = message.guild.get_role(
                                serverstorecheck["ignorerolerole"]
                            )
                            if ignorerole not in message.author.roles:
                                try:
                                    await message.delete()
                                    if (
                                        self.counter[
                                            f"{message.author.id}.{message.guild.id}.adblockpinged"
                                        ]
                                        == 1
                                    ):
                                        break
                                    else:
                                        await message.channel.send(
                                            f"{message.author.mention}, ads aren't allowed here!",
                                            delete_after=5,
                                        )
                                    self.counter[
                                        f"{message.author.id}.{message.guild.id}.adblockpinged"
                                    ] += 1
                                    await asyncio.sleep(5)
                                    self.counter[
                                        f"{message.author.id}.{message.guild.id}.adblockpinged"
                                    ] -= 1
                                    break
                                except discord.Forbidden:
                                    pass
                        else:
                            try:
                                await message.delete()
                                if (
                                    self.counter[
                                        f"{message.author.id}.{message.guild.id}.adblockpinged"
                                    ]
                                    == 1
                                ):
                                    break
                                else:
                                    await message.channel.send(
                                        f"{message.author.mention}, ads aren't allowed here!",
                                        delete_after=5,
                                    )
                                self.counter[
                                    f"{message.author.id}.{message.guild.id}.adblockpinged"
                                ] += 1
                                await asyncio.sleep(5)
                                self.counter[
                                    f"{message.author.id}.{message.guild.id}.adblockpinged"
                                ] -= 1
                                break
                            except discord.Forbidden:
                                pass
            if automodcheck["antispam"] == 1:
                if automodcheck["ignorerole"] == 1:
                    ignorerole = message.guild.get_role(
                        serverstorecheck["ignorerolerole"]
                    )
                    if ignorerole not in message.author.roles:
                        if (
                            self.counter[
                                f"{message.author.id}.{message.guild.id}.lastmsg"
                            ]
                            == f"{message.content}"
                        ):
                            try:
                                await message.delete()
                            except discord.Forbidden:
                                pass
                else:
                    if (
                        self.counter[f"{message.author.id}.{message.guild.id}.lastmsg"]
                        == f"{message.content}"
                    ):
                        try:
                            await message.delete()
                        except discord.Forbidden:
                            pass
                self.counter[
                    f"{message.author.id}.{message.guild.id}.lastmsg"
                ] = f"{message.content}"
        await self.process_commands(message)
