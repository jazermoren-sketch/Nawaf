import random
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from database import connect


GROUP_GAMES = {
    "roulette": {"name": "الروليت", "min": 2, "max": 15},
    "dice_battle": {"name": "معركة النرد", "min": 2, "max": 15},
}


@dataclass
class GameSession:
    guild_id: int
    channel_id: int
    starter_id: int
    game_type: str
    reward: int
    min_players: int
    max_players: int
    players: list[int] = field(default_factory=list)


class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[tuple[int, int], GameSession] = {}

    async def _reply(self, message: discord.Message, content: str):
        return await message.reply(content, mention_author=False)

    def add_points(self, guild_id: int, user_id: int, amount: int):
        with connect() as con:
            con.execute("INSERT OR IGNORE INTO points(guild_id,user_id,points) VALUES(?,?,0)", (guild_id, user_id))
            con.execute("UPDATE points SET points=points+? WHERE guild_id=? AND user_id=?", (amount, guild_id, user_id))

    def start_session(self, guild: discord.Guild, channel_id: int, starter_id: int, game_type: str, reward: int = 5, max_players: int = 15):
        key = (guild.id, channel_id)
        if key in self.sessions:
            return None, "❌ كاينة لعبة جماعية مفتوحة فهاد الروم."
        spec = GROUP_GAMES[game_type]
        maximum = max(2, min(max_players, spec["max"], 15))
        session = GameSession(guild.id, channel_id, starter_id, game_type, reward, spec["min"], maximum, [starter_id])
        self.sessions[key] = session
        return session, None

    def finish_session(self, session: GameSession):
        if session.game_type == "roulette":
            winner_id = random.choice(session.players)
            result = "🎰 الروليت اختارت لاعباً عشوائياً."
        else:
            rolls = {uid: random.randint(1, 6) for uid in session.players}
            best = max(rolls.values())
            winners = [uid for uid, value in rolls.items() if value == best]
            winner_id = random.choice(winners)
            result = "🎲 " + " | ".join(f"<@{uid}>: {value}" for uid, value in rolls.items())
            if len(winners) > 1:
                result += f"\n🤝 تعادل، وتم اختيار <@{winner_id}> من المتعادلين."
        self.add_points(session.guild_id, winner_id, session.reward)
        self.sessions.pop((session.guild_id, session.channel_id), None)
        return f"{result}\n\n🏆 الفائز: <@{winner_id}>\n⭐ ربح **{session.reward} نقطة**."

    @app_commands.command(name="game-start", description="تشغيل لعبة جماعية للأعضاء")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(game=[
        app_commands.Choice(name="الروليت", value="roulette"),
        app_commands.Choice(name="معركة النرد", value="dice_battle"),
    ])
    async def game_start(self, interaction: discord.Interaction, game: app_commands.Choice[str], reward: app_commands.Range[int, 0, 1000] = 5, max_players: app_commands.Range[int, 2, 15] = 15):
        session, error = self.start_session(interaction.guild, interaction.channel.id, interaction.user.id, game.value, reward, max_players)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)
        spec = GROUP_GAMES[game.value]
        await interaction.response.send_message(f"🎮 **{spec['name']}** بدأت!\n👥 اللاعبين: **1/{session.max_players}**\n📌 الحد الأدنى: **{session.min_players}**\n🏆 الفائز يحصل على **{reward} نقطة**.\n\nاكتب `!دخول` للدخول، و`!ابدأ` لبدء الجولة.")

    @app_commands.command(name="game-join", description="الدخول في اللعبة الجماعية الحالية")
    async def game_join(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.channel.id)
        session = self.sessions.get(key)
        if not session:
            return await interaction.response.send_message("❌ ما كايناش لعبة جماعية مفتوحة هنا.", ephemeral=True)
        if interaction.user.id in session.players:
            return await interaction.response.send_message("⚠️ أنت داخل اللعبة أصلاً.", ephemeral=True)
        if len(session.players) >= session.max_players:
            return await interaction.response.send_message(f"❌ اللعبة عامرة. الحد الأقصى هو {session.max_players} لاعب.", ephemeral=True)
        session.players.append(interaction.user.id)
        await interaction.response.send_message(f"✅ دخل {interaction.user.mention} للعبة. **{len(session.players)}/{session.max_players}**")

    @app_commands.command(name="game-leave", description="الخروج من اللعبة الجماعية الحالية")
    async def game_leave(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.channel.id)
        session = self.sessions.get(key)
        if not session or interaction.user.id not in session.players:
            return await interaction.response.send_message("❌ ما نتايش داخل لعبة جماعية هنا.", ephemeral=True)
        if interaction.user.id == session.starter_id:
            return await interaction.response.send_message("❌ مشغل اللعبة ما يقدرش يخرج؛ استعمل `/game-end`.", ephemeral=True)
        session.players.remove(interaction.user.id)
        await interaction.response.send_message(f"✅ خرج {interaction.user.mention} من اللعبة.")

    @app_commands.command(name="game-spin", description="بدء الجولة وتحديد الفائز")
    async def game_spin(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.channel.id)
        session = self.sessions.get(key)
        if not session:
            return await interaction.response.send_message("❌ ما كايناش لعبة جماعية مفتوحة هنا.", ephemeral=True)
        if interaction.user.id != session.starter_id and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ غير مشغل اللعبة أو الإدارة يقدر يبدأ الجولة.", ephemeral=True)
        if len(session.players) < session.min_players:
            return await interaction.response.send_message(f"❌ خاص على الأقل **{session.min_players} لاعبين** باش تبدأ اللعبة.", ephemeral=True)
        await interaction.response.send_message(self.finish_session(session))

    @app_commands.command(name="game-end", description="إغلاق اللعبة الجماعية الحالية")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def game_end(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.channel.id)
        if not self.sessions.pop(key, None):
            return await interaction.response.send_message("❌ ما كايناش لعبة جماعية مفتوحة هنا.", ephemeral=True)
        await interaction.response.send_message("🛑 تم إغلاق اللعبة الجماعية.")

    async def _prefix_start(self, message: discord.Message, game_type: str, args: list[str]):
        if not isinstance(message.author, discord.Member) or not message.author.guild_permissions.manage_guild:
            return await self._reply(message, "❌ غير الإدارة تقدر تشغل الألعاب الجماعية.")
        reward = 5
        maximum = 15
        if args and args[0].isdigit():
            reward = max(0, min(int(args[0]), 1000))
        if len(args) > 1 and args[1].isdigit():
            maximum = max(2, min(int(args[1]), 15))
        session, error = self.start_session(message.guild, message.channel.id, message.author.id, game_type, reward, maximum)
        if error:
            return await self._reply(message, error)
        spec = GROUP_GAMES[game_type]
        await self._reply(message, f"🎮 **{spec['name']}** بدأت!\n👥 اللاعبين: **1/{session.max_players}**\n📌 الحد الأدنى: **{session.min_players}**\n🏆 الفائز يحصل على **{reward} نقطة**.\n\n`!دخول` للدخول — `!خروج` للخروج — `!ابدأ` لبدء الجولة.")

    async def _prefix_join(self, message: discord.Message):
        session = self.sessions.get((message.guild.id, message.channel.id))
        if not session:
            return await self._reply(message, "❌ ما كايناش لعبة جماعية مفتوحة هنا.")
        if message.author.id in session.players:
            return await self._reply(message, "⚠️ أنت داخل اللعبة أصلاً.")
        if len(session.players) >= session.max_players:
            return await self._reply(message, f"❌ اللعبة عامرة. الحد الأقصى هو {session.max_players} لاعب.")
        session.players.append(message.author.id)
        await self._reply(message, f"✅ دخل {message.author.mention} للعبة. **{len(session.players)}/{session.max_players}**")

    async def _prefix_leave(self, message: discord.Message):
        session = self.sessions.get((message.guild.id, message.channel.id))
        if not session or message.author.id not in session.players:
            return await self._reply(message, "❌ ما نتايش داخل لعبة جماعية هنا.")
        if message.author.id == session.starter_id:
            return await self._reply(message, "❌ مشغل اللعبة ما يقدرش يخرج؛ استعمل `!انهاء`.")
        session.players.remove(message.author.id)
        await self._reply(message, f"✅ خرج {message.author.mention} من اللعبة.")

    async def _prefix_spin(self, message: discord.Message):
        session = self.sessions.get((message.guild.id, message.channel.id))
        if not session:
            return await self._reply(message, "❌ ما كايناش لعبة جماعية مفتوحة هنا.")
        if not isinstance(message.author, discord.Member) or (message.author.id != session.starter_id and not message.author.guild_permissions.manage_guild):
            return await self._reply(message, "❌ غير مشغل اللعبة أو الإدارة يقدر يبدأ الجولة.")
        if len(session.players) < session.min_players:
            return await self._reply(message, f"❌ خاص على الأقل **{session.min_players} لاعبين** باش تبدأ اللعبة.")
        await self._reply(message, self.finish_session(session))

    async def _prefix_end(self, message: discord.Message):
        if not isinstance(message.author, discord.Member) or not message.author.guild_permissions.manage_guild:
            return await self._reply(message, "❌ غير الإدارة تقدر تسالي اللعبة.")
        if not self.sessions.pop((message.guild.id, message.channel.id), None):
            return await self._reply(message, "❌ ما كايناش لعبة جماعية مفتوحة هنا.")
        await self._reply(message, "🛑 تم إغلاق اللعبة الجماعية.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if content.startswith("!روليت"):
            await self._prefix_start(message, "roulette", content.split()[1:])
        elif content.startswith("!نرد"):
            await self._prefix_start(message, "dice_battle", content.split()[1:])
        elif content == "!دخول":
            await self._prefix_join(message)
        elif content == "!خروج":
            await self._prefix_leave(message)
        elif content in {"!ابدأ", "!بدء"}:
            await self._prefix_spin(message)
        elif content in {"!انهاء", "!إنهاء"}:
            await self._prefix_end(message)
        elif content == "!العاب":
            await self._reply(message, "🎮 `!روليت [النقاط] [الحد]`\n🎲 `!نرد [النقاط] [الحد]`\n👥 `!دخول` — `!خروج`\n▶️ `!ابدأ` — 🛑 `!انهاء`\n\nالحد الأقصى 15 لاعب، والألعاب الفردية لا تعطي نقاطاً.")

    @app_commands.command(name="games", description="عرض الألعاب الجماعية والفردية")
    async def games(self, interaction: discord.Interaction):
        await interaction.response.send_message("🎮 **الجماعية:** الروليت، معركة النرد — الإدارة تشغلها، من 2 حتى 15 لاعب.\n🎯 **الفردية:** /coinflip و /solo-dice و /rps — بدون نقاط.")

    @app_commands.command(name="coinflip", description="لعبة فردية: وجه أو كتابة")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 النتيجة: **{random.choice(('وجه', 'كتابة'))}**")

    @app_commands.command(name="solo-dice", description="لعبة فردية: رمية نرد")
    async def solo_dice(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎲 رميتك: **{random.randint(1, 6)}**")

    @app_commands.command(name="rps", description="لعبة فردية: حجر ورق مقص")
    @app_commands.choices(choice=[app_commands.Choice(name="حجر", value="حجر"), app_commands.Choice(name="ورق", value="ورق"), app_commands.Choice(name="مقص", value="مقص")])
    async def rps(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
        bot_choice = random.choice(("حجر", "ورق", "مقص"))
        if choice.value == bot_choice:
            result = "تعادل"
        elif (choice.value, bot_choice) in (("حجر", "مقص"), ("ورق", "حجر"), ("مقص", "ورق")):
            result = "فزت"
        else:
            result = "خسرت"
        await interaction.response.send_message(f"✊ اختيارك: **{choice.value}** | 🤖: **{bot_choice}**\n**{result}** — بدون نقاط.")

    @app_commands.command(name="points", description="عرض نقاطك أو نقاط عضو")
    async def points(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        with connect() as con:
            row = con.execute("SELECT points FROM points WHERE guild_id=? AND user_id=?", (interaction.guild.id, member.id)).fetchone()
        value = row["points"] if row else 0
        await interaction.response.send_message(f"⭐ نقاط {member.mention}: **{value}**")


async def setup(bot):
    await bot.add_cog(Games(bot))
