from __future__ import annotations

import io

import discord
from discord.ext import commands

# Game artwork supplied for Nawaf.
ROULETTE_ART_URL = (
    "https://cdn.discordapp.com/attachments/1543608188975325268/1544727017243549826/"
    "a3a22b8922412e080f008b2177c2ba80c5ba947a7c003716e06b184059052e15.png?"
    "ex=6a9f8b64&is=6a9e39e4&hm=7c6de5a3d4f20f92f8f1a0c0d7c6e6d9a53d59e2dd7e9d5d8f0d0fd9d0a7a4d9&"
)
MAFIA_ART_URL = (
    "https://cdn.discordapp.com/attachments/1543608188975325268/1544727879659552788/"
    "1788362198735.png?ex=6a9f8b94&is=6a9e3a14&hm=6f4a8e0a1d9c3b7f5b6e4d2f8a1c6f4d9e2b7c1a5d8e0f3c6a9b2d4e7f1a8c5b&"
)


class GameAssets(commands.Cog):
    """Shared game artwork. Roulette uses the supplied artwork for its wheel card."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._roulette_cache: bytes | None = None

    async def cog_load(self):
        roulette = self.bot.get_cog("RouletteMultiMessage")
        if roulette is None:
            return

        async def roulette_wheel_file(session, selected_id: int, final: bool = False):
            data = self._roulette_cache
            if data is None:
                try:
                    import aiohttp

                    timeout = aiohttp.ClientTimeout(total=15)
                    async with aiohttp.ClientSession(timeout=timeout) as http:
                        async with http.get(ROULETTE_ART_URL) as response:
                            if response.status == 200:
                                data = await response.read()
                                if data:
                                    self._roulette_cache = data
                except Exception:
                    data = None

            if not data:
                # Preserve the original generated wheel if the remote artwork is
                # temporarily unavailable.
                return await roulette._original_wheel_file(session, selected_id, final)

            return discord.File(io.BytesIO(data), filename="roulette.png")

        # Keep the existing generated wheel as a safe fallback.
        if not hasattr(roulette, "_original_wheel_file"):
            roulette._original_wheel_file = roulette.wheel_file
        roulette.wheel_file = roulette_wheel_file


async def setup(bot: commands.Bot):
    await bot.add_cog(GameAssets(bot))
