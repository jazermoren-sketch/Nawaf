from __future__ import annotations

import asyncio
import io
import math
import random

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from cogs.game_channels import is_group_game_channel_allowed
from database import connect

MIN_PLAYERS = 4
MAX_PLAYERS = 15
LOBBY_SECONDS = 30
DECISION_SECONDS = 15
WINNER_REWARD = 5

ELIMINATION_GIF_URL = (
    "https://cdn.discordapp.com/attachments/1476446187656708178/1540328111667941416/"
    "line_1787313239426.gif?ex=6a898dd7&is=6a883c57&hm=d0f114e4e11144e4cb6eca06654f2e963ab10b5032d70f1a8c7a63a9c961a5d5&"
)


class Session:
    def __init__(self, guild_id: int, channel_id: int, starter_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.starter_id = starter_id
        self.players: list[int] = []
        self.active = False
        self.round = 0
        self.lobby_message: discord.Message | None = None
        self.decision_event = asyncio.Event()
        self.decision: tuple[str, int | None] | None = None


class LobbyView(discord.ui.View):
    def __init__(self, game: "RouletteMultiMessage", session: Session):
        super().__init__(timeout=LOBBY_SECONDS + 5)
        self.game = game
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.game.sessions.get(self.game.key(self.session)) is not self.session or self.session.active:
            await interaction.response.send_message("❌ التسجيل سالا.", ephemeral=True)
            return False
        if interaction.user.bot:
            await interaction.response.send_message("❌ البوتات ما كيدخلوش.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="دخول إلى اللعبة", style=discord.ButtonStyle.success, emoji="🎮")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.session.players:
            return await interaction.response.send_message("⚠️ راك داخل اللعبة أصلاً.", ephemeral=True)
        if len(self.session.players) >= MAX_PLAYERS:
            return await interaction.response.send_message("❌ وصلنا للحد الأقصى ديال 15 لاعب.", ephemeral=True)
        self.session.players.append(interaction.user.id)
        await interaction.response.defer()
        await self.game.update_lobby(self.session)

    @discord.ui.button(label="خروج من اللعبة", style=discord.ButtonStyle.danger, emoji="🚪")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.session.players:
            return await interaction.response.send_message("⚠️ راك ماشي داخل اللعبة.", ephemeral=True)
        self.session.players.remove(interaction.user.id)
        await interaction.response.defer()
        await self.game.update_lobby(self.session)


class DecisionView(discord.ui.View):
    def __init__(self, game: "RouletteMultiMessage", session: Session, selected_id: int):
        super().__init__(timeout=DECISION_SECONDS)
        self.game = game
        self.session = session
        self.selected_id = selected_id
        self.done = False

        targets = [uid for uid in session.players if uid != selected_id]
        for index, uid in enumerate(targets):
            member = game.member(session.guild_id, uid)
            label = game.short_name(member.display_name if member else str(uid))
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.danger,
                emoji="🎯",
                row=min(3, index // 5),
            )

            async def callback(interaction: discord.Interaction, target_id: int = uid):
                await self.resolve(interaction, "kick", target_id)

            button.callback = callback
            self.add_item(button)

        random_button = discord.ui.Button(label="طرد عشوائي", style=discord.ButtonStyle.primary, emoji="🎲", row=4)
        withdraw_button = discord.ui.Button(label="انسحاب", style=discord.ButtonStyle.secondary, emoji="🚪", row=4)
        random_button.callback = self.random_kick
        withdraw_button.callback = self.withdraw
        self.add_item(random_button)
        self.add_item(withdraw_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.selected_id:
            await interaction.response.send_message("❌ هاد القرار غير للاعب اللي اختارتو العجلة.", ephemeral=True)
            return False
        if self.done:
            await interaction.response.send_message("❌ القرار سالا.", ephemeral=True)
            return False
        return True

    async def resolve(self, interaction: discord.Interaction, action: str, target_id: int | None = None):
        if self.done:
            return
        self.done = True
        self.session.decision = (action, target_id)
        self.session.decision_event.set()
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

    async def random_kick(self, interaction: discord.Interaction):
        await self.resolve(interaction, "random")

    async def withdraw(self, interaction: discord.Interaction):
        await self.resolve(interaction, "withdraw")


class RouletteMultiMessage(commands.Cog):
    """Fizbo-style multi-message elimination roulette."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[tuple[int, int], Session] = {}

    @staticmethod
    def key(session: Session) -> tuple[int, int]:
        return session.guild_id, session.channel_id

    @staticmethod
    def short_name(name: str, limit: int = 18) -> str:
        name = " ".join(name.split()) or "لاعب"
        return name if len(name) <= limit else name[: limit - 1] + "…"

    def member(self, guild_id: int, user_id: int) -> discord.Member | None:
        guild = self.bot.get_guild(guild_id)
        return guild.get_member(user_id) if guild else None

    def lobby_text(self, session: Session, remaining: int) -> str:
        names = []
        for index, uid in enumerate(session.players, 1):
            member = self.member(session.guild_id, uid)
            names.append(f"{index}. {member.mention if member else f'<@{uid}>'}")
        roster = "\n".join(names) or "مازال حتى لاعب."
        return (
            "🎰 **روليت الإقصاء**\n\n"
            f"👥 المشاركين: **{len(session.players)}/{MAX_PLAYERS}**\n"
            f"✅ الحد الأدنى: **{MIN_PLAYERS} لاعبين**\n"
            f"⏳ البداية التلقائية بعد **{remaining} ثانية**\n\n"
            f"{roster}\n\n"
            "اضغط على **دخول إلى اللعبة** للمشاركة أو **خروج من اللعبة** للانسحاب."
        )

    async def update_lobby(self, session: Session, remaining: int = LOBBY_SECONDS):
        if not session.lobby_message:
            return
        try:
            await session.lobby_message.edit(content=self.lobby_text(session, remaining))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.strip() == "-روليت":
            await self.start_lobby(message)

    async def start_lobby(self, message: discord.Message):
        if not is_group_game_channel_allowed(message.guild.id, message.channel.id):
            return await message.reply("❌ هاد الروم ما مسموحش فيه الألعاب الجماعية.", mention_author=False)

        key = (message.guild.id, message.channel.id)
        if key in self.sessions:
            return await message.reply("❌ كاينة روليت مفتوحة فهاد الروم.", mention_author=False)

        session = Session(message.guild.id, message.channel.id, message.author.id)
        self.sessions[key] = session
        session.lobby_message = await message.channel.send(
            self.lobby_text(session, LOBBY_SECONDS),
            view=LobbyView(self, session),
        )

        try:
            for remaining in range(LOBBY_SECONDS - 1, -1, -1):
                await asyncio.sleep(1)
                if self.sessions.get(key) is not session or session.active:
                    return
                await self.update_lobby(session, remaining)

            if len(session.players) < MIN_PLAYERS:
                self.sessions.pop(key, None)
                await message.channel.send(
                    f"❌ سال وقت التسجيل وما وصلناش لـ **{MIN_PLAYERS} لاعبين**.\nتم إلغاء الروليت."
                )
                await session.lobby_message.edit(view=None)
                return

            session.active = True
            await session.lobby_message.edit(content="✅ **سال وقت التسجيل — الروليت غادي تبدا دابا.**", view=None)
            await asyncio.sleep(1)
            await self.run_game(session, message.channel)
        except asyncio.CancelledError:
            self.sessions.pop(key, None)
            raise

    async def run_game(self, session: Session, channel: discord.TextChannel):
        try:
            while len(session.players) > 2:
                session.round += 1
                selected_id = random.choice(session.players)
                session.decision_event = asyncio.Event()
                session.decision = None

                # Image-only message: the wheel itself points to the chosen player.
                await channel.send(file=await self.wheel_file(session, selected_id))

                view = DecisionView(self, session, selected_id)
                await channel.send(
                    content=(
                        f"**<@{selected_id}>، اختر الشخص لي بدك تطرده**\n\n"
                        f"⏳ عندك **{DECISION_SECONDS} ثانية**."
                    ),
                    view=view,
                )

                try:
                    await asyncio.wait_for(session.decision_event.wait(), timeout=DECISION_SECONDS)
                except asyncio.TimeoutError:
                    if selected_id in session.players:
                        session.players.remove(selected_id)
                    await channel.send(content=f"**تم طرد <@{selected_id}> بسبب الخمول**")
                    await self.send_elimination_gif(channel)
                    await asyncio.sleep(1.5)
                    continue

                action, target_id = session.decision or ("withdraw", None)
                if action == "withdraw":
                    if selected_id in session.players:
                        session.players.remove(selected_id)
                    await channel.send(
                        content=f"**انسحب <@{selected_id}> من اللعبة، ستبدأ الجولة التالية بعد قليل.**"
                    )
                else:
                    if action == "random":
                        target_id = random.choice([uid for uid in session.players if uid != selected_id])
                    if target_id not in session.players or target_id == selected_id:
                        target_id = random.choice([uid for uid in session.players if uid != selected_id])
                    session.players.remove(target_id)
                    await channel.send(
                        content=f"**تم طرد <@{target_id}> من اللعبة، سيتم بدأ الجولة التالية بعد قليل.**"
                    )
                    await self.send_elimination_gif(channel)

                await asyncio.sleep(1.5)

            if len(session.players) == 2:
                winner = random.choice(session.players)
                await channel.send(file=await self.wheel_file(session, winner, final=True))
                await asyncio.sleep(1)
                self.add_points(session.guild_id, winner, WINNER_REWARD)
                await channel.send(
                    content=f"🏆 **الفائز فالروليت هو <@{winner}>!**\n⭐ ربح **{WINNER_REWARD} نقطة**."
                )
        finally:
            session.active = False
            self.sessions.pop(self.key(session), None)

    @staticmethod
    def add_points(guild_id: int, user_id: int, amount: int):
        with connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO points(guild_id,user_id,points) VALUES(?,?,0)",
                (guild_id, user_id),
            )
            con.execute(
                "UPDATE points SET points=points+? WHERE guild_id=? AND user_id=?",
                (amount, guild_id, user_id),
            )

    async def send_elimination_gif(self, channel: discord.TextChannel):
        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http:
                async with http.get(ELIMINATION_GIF_URL) as response:
                    if response.status == 200:
                        data = await response.read()
                        await channel.send(file=discord.File(io.BytesIO(data), filename="elimination.gif"))
                        return
        except Exception:
            pass
        await channel.send(ELIMINATION_GIF_URL)

    async def avatar(self, member: discord.Member) -> bytes | None:
        try:
            return await member.display_avatar.replace(size=128, static_format="png").read()
        except Exception:
            return None

    async def wheel_file(self, session: Session, selected_id: int, final: bool = False) -> discord.File:
        size = 1000
        image = Image.new("RGB", (size, size), (20, 22, 28))
        draw = ImageDraw.Draw(image)
        cx = cy = size // 2
        radius = 390
        members = [self.member(session.guild_id, uid) for uid in session.players]
        members = [m for m in members if m is not None]
        count = max(1, len(members))
        step = 360 / count
        selected_index = next((i for i, m in enumerate(members) if m.id == selected_id), 0)
        rotation = -90 - ((selected_index + 0.5) * step)
        palette = [(70, 91, 132), (109, 72, 123), (64, 125, 105), (141, 89, 59), (77, 108, 145), (125, 75, 94)]

        for i, member in enumerate(members):
            start = rotation + i * step
            end = start + step
            draw.pieslice(
                (cx - radius, cy - radius, cx + radius, cy + radius),
                start=start,
                end=end,
                fill=palette[i % len(palette)],
                outline=(240, 240, 240),
                width=4,
            )

        draw.ellipse((cx - 100, cy - 100, cx + 100, cy + 100), fill=(30, 33, 42), outline=(245, 198, 66), width=8)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 27)
        except OSError:
            font = ImageFont.load_default()

        for i, member in enumerate(members):
            angle = math.radians(rotation + (i + 0.5) * step)
            distance = 285
            x = int(cx + math.cos(angle) * distance)
            y = int(cy + math.sin(angle) * distance)
            avatar = await self.avatar(member)
            if avatar:
                try:
                    av = Image.open(io.BytesIO(avatar)).convert("RGB").resize((84, 84))
                    mask = Image.new("L", (84, 84), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, 83, 83), fill=255)
                    image.paste(av, (x - 42, y - 42), mask)
                except Exception:
                    pass
            draw.ellipse((x - 45, y - 45, x + 45, y + 45), outline=(255, 85, 85) if member.id == selected_id else (255, 255, 255), width=6)
            label = self.short_name(member.display_name, 12)
            box = draw.textbbox((0, 0), label, font=font)
            tw = box[2] - box[0]
            ty = y + 50
            draw.rounded_rectangle((x - tw / 2 - 7, ty - 2, x + tw / 2 + 7, ty + 31), radius=8, fill=(10, 12, 16))
            draw.text((x - tw / 2, ty), label, fill=(255, 255, 255), font=font)

        # Fixed pointer at 12 o'clock; selected player is rotated underneath it.
        draw.polygon([(cx, 15), (cx - 32, 85), (cx + 32, 85)], fill=(255, 70, 70), outline=(255, 230, 230))
        selected_member = next((m for m in members if m.id == selected_id), None)
        result_name = self.short_name(selected_member.display_name if selected_member else "Selected", 22)
        box = draw.textbbox((0, 0), result_name, font=font)
        tw = box[2] - box[0]
        footer_y = size - 55
        draw.rounded_rectangle((cx - tw / 2 - 16, footer_y - 8, cx + tw / 2 + 16, footer_y + 30), radius=12, fill=(245, 198, 66))
        draw.text((cx - tw / 2, footer_y), result_name, fill=(20, 22, 28), font=font)

        if final:
            draw.text((25, 25), "FINAL", fill=(245, 198, 66), font=font)

        buffer = io.BytesIO()
        image.save(buffer, "PNG", optimize=True)
        buffer.seek(0)
        return discord.File(buffer, filename="roulette-wheel.png")


async def setup(bot: commands.Bot):
    await bot.add_cog(RouletteMultiMessage(bot))
