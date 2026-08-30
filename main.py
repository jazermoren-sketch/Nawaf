import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = (
    "cogs.permissions",
    "cogs.messages",
    "cogs.tickets",
    "cogs.leveling",
    "cogs.applications",
    "cogs.announcements",
    "cogs.dhikr",
    "cogs.economy",
    "cogs.shop",
    "cogs.config",
    "cogs.health",
)


async def load_cogs():
    for extension in COGS:
        try:
            await bot.load_extension(extension)
            print(f"[OK] Loaded {extension}")
        except Exception as exc:
            print(f"[ERROR] Failed to load {extension}: {exc!r}")
            raise


@bot.event
async def on_ready():
    print(f"Nawaf logged in as {bot.user} ({bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")


@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 {round(bot.latency * 1000)}ms")


async def main():
    init_db()
    await load_cogs()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is missing from .env")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
