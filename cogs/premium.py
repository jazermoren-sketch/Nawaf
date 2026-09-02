from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database import connect

BOT_OWNER_ID = 1472570059367911587
MIN_ROULETTE_PLAYERS = 4
DEFAULT_ROULETTE_MAX = 15
ABSOLUTE_ROULETTE_MAX = 2000
SUPPORT_INVITE = "https://discord.gg/Tmnb2QBs2d"

DURATION_RE = re.compile(r"^(\d+)(y|mo|w|d|h|m|s)$", re.IGNORECASE)
DURATION_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 60 * 60 * 24 * 7,
    "mo": 60 * 60 * 24 * 30,
    "y": 60 * 60 * 24 * 365,
}

UPSELL_TEXT = (
    "**يمكنك تغيير الحد الاقصى للاعبين هذه الميزة حصرية للبريميوم فقط**\n"
    "للتواصل لاخد البريميوم خش ذا السيرفر و منشن "
    f"<@{BOT_OWNER_ID}> و ادفع له بالطرق المتاحة و بيعطيك بريميوم بالمدة على حسب لي شريته انت\n"
    f"{SUPPORT_INVITE}"
)


def ensure_premium_table() -> None:
    with connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_premium (
                guild_id INTEGER PRIMARY KEY,
                activated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                activated_by INTEGER NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS roulette_premium_config (
                guild_id INTEGER PRIMARY KEY,
                maximum_players INTEGER NOT NULL DEFAULT 15
            )
            """
        )


def get_premium_expiry(guild_id: int) -> int | None:
    ensure_premium_table()
    with connect() as con:
        row = con.execute(
            "SELECT expires_at FROM guild_premium WHERE guild_id=?",
            (guild_id,),
        ).fetchone()
    if not row:
        return None
    expiry = int(row[0])
    if expiry <= int(time.time()):
        with connect() as con:
            con.execute("DELETE FROM guild_premium WHERE guild_id=?", (guild_id,))
        return None
    return expiry


def is_premium(guild_id: int) -> bool:
    return get_premium_expiry(guild_id) is not None


def get_roulette_max(guild_id: int) -> int:
    if not is_premium(guild_id):
        return DEFAULT_ROULETTE_MAX
    with connect() as con:
        row = con.execute(
            "SELECT maximum_players FROM roulette_premium_config WHERE guild_id=?",
            (guild_id,),
        ).fetchone()
    if not row:
        return DEFAULT_ROULETTE_MAX
    return max(MIN_ROULETTE_PLAYERS, min(ABSOLUTE_ROULETTE_MAX, int(row[0])))


def set_roulette_max(guild_id: int, maximum_players: int) -> None:
    with connect() as con:
        con.execute(
            """
            INSERT INTO roulette_premium_config(guild_id, maximum_players)
            VALUES(?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET maximum_players=excluded.maximum_players
            """,
            (guild_id, maximum_players),
        )


def parse_duration(value: str) -> int | None:
    match = DURATION_RE.fullmatch(value.strip())
    if not match:
        return None
    amount = int(match.group(1))
    if amount <= 0:
        return None
    return amount * DURATION_SECONDS[match.group(2).lower()]


def format_dt(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class Premium(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_premium_table()

    @app_commands.command(
        name="maximum-number-players-roullete",
        description="تحديد الحد الأقصى للاعبين في روليت السيرفر للبريميوم",
    )
    @app_commands.describe(maximum="الحد الأقصى من 4 إلى 2000 لاعب")
    async def maximum_number_players_roullete(
        self, interaction: discord.Interaction, maximum: app_commands.Range[int, 4, 2000]
    ):
        if not interaction.guild:
            return await interaction.response.send_message("❌ هاد الأمر خاص بالسيرفرات.", ephemeral=True)
        if not is_premium(interaction.guild.id):
            return await interaction.response.send_message(UPSELL_TEXT, ephemeral=True)
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ غير صاحب السيرفر يقدر يبدل الحد الأقصى للاعبين.", ephemeral=True
            )
        set_roulette_max(interaction.guild.id, int(maximum))
        await interaction.response.send_message(
            f"✅ تم تحديد الحد الأقصى للروليت في **{maximum} لاعب**.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content.lower().startswith("prm "):
            return
        if message.author.id != BOT_OWNER_ID:
            return

        duration_text = content[4:].strip()
        seconds = parse_duration(duration_text)
        if seconds is None:
            await message.reply(
                "❌ الصيغة غير صحيحة. استعمل مثلاً: `prm 1mo` أو `prm 1y` أو `prm 2w`.",
                mention_author=False,
            )
            return

        now = int(time.time())
        expires = now + seconds
        with connect() as con:
            con.execute(
                """
                INSERT INTO guild_premium(guild_id, activated_at, expires_at, activated_by)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    activated_at=excluded.activated_at,
                    expires_at=excluded.expires_at,
                    activated_by=excluded.activated_by
                """,
                (message.guild.id, now, expires, BOT_OWNER_ID),
            )

        embed = discord.Embed(
            title="💎 تم تفعيل البريميوم",
            description=(
                f"**تم تفعيل البريميوم لسيرفر {message.guild.name}**\n\n"
                f"**تاريخ تفعيل:** {format_dt(now)}\n"
                f"**تاريخ انتهاء:** {format_dt(expires)}\n"
                f"**ايدي صاحب السيرفر:** {message.guild.owner_id}\n"
                f"**ايدي سيرفر:** {message.guild.id}"
            ),
            color=discord.Color.gold(),
        )
        await message.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))
