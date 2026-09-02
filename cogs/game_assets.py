from __future__ import annotations

import io

import discord
from discord.ext import commands

# Game artwork supplied for Nawaf.
# The CDN query parameters are intentionally omitted here; the original
# generated wheel remains the fallback when Discord does not serve the asset.
ROULETTE_ART_URL = (
    "https://cdn.discordapp.com/attachments/1543608188975325268/1544727017243549826/"
    "a3a22b8922412e080f008b2177c2ba80c5ba947a7c003716e06b184059052e15.png"
)
MAFIA_ART_URL = (
    "https://cdn.discordapp.com/attachments/1543608188975325268/1544727879659552788/"
    "1788362198735.png"
)


class GameAssets(commands.Cog):
    """Shared game artwork. Roulette uses the supplied roulette artwork."""

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
                return await roulette._original_wheel_file(session, selected_id, final)

            return discord.File(io.BytesIO(data), filename="roulette.png")

        if not hasattr(roulette, "_original_wheel_file"):
            roulette._original_wheel_file = roulette.wheel_file
        roulette.wheel_file = roulette_wheel_file


async def setup(bot: commands.Bot):
    await bot.add_cog(GameAssets(bot))
