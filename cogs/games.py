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

    def add_points(self, guild_id: int, user_id: int, amount: int):
        with connect() as con:
            con.execute("INSERT OR IGNORE INTO points(guild_id,user_id,points) VALUES(?,?,0)", (guild_id, user_id))
            con.execute("UPDATE points SET points=points+? WHERE guild_id=? AND user_id=?", (amount, guild_id, user_id))

    @app_commands.command(name="game-start", description="تشغيل لعبة جماعية للأعضاء")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(game=[
        app_commands.Choice(name="الروليت", value="roulette"),
        app_commands.Choice(name="معركة النرد", value="dice_battle"),
    ])
    async def game_start(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
        reward: app_commands.Range[int, 0, 1000] = 5,
        max_players: app_commands.Range[int, 2, 15] = 15,
    ):
        key = (interaction.guild.id, interaction.channel.id)
        if key in self.sessions:
            return await interaction.response.send_message("❌ كاينة لعبة جماعية مفتوحة فهاد الروم.", ephemeral=True)
        spec = GROUP_GAMES[game.value]
        maximum = min(max_players, spec["max"], 15)
        if maximum < spec["min"]:
            maximum = spec["min"]
        session = GameSession(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            starter_id=interaction.user.id,
            game_type=game.value,
            reward=reward,
            min_players=spec["min"],
            max_players=maximum,
            players=[interaction.user.id],
        )
        self.sessions[key] = session
        await interaction.response.send_message(
            f"🎮 **{spec['name']}** بدأت!\n👥 اللاعبين: **1/{maximum}**\n📌 الحد الأدنى: **{spec['min']}**\n"
            f"🏆 الفائز يحصل على **{reward} نقطة**.\n\nاكتب `/game-join` للدخول، و`/game-spin` لبدء الجولة."
        )

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
        self.sessions.pop(key, None)
        await interaction.response.send_message(f"{result}\n\n🏆 الفائز: <@{winner_id}>\n⭐ ربح **{session.reward} نقطة**.")

    @app_commands.command(name="game-end", description="إغلاق اللعبة الجماعية الحالية")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def game_end(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.channel.id)
        if not self.sessions.pop(key, None):
            return await interaction.response.send_message("❌ ما كايناش لعبة جماعية مفتوحة هنا.", ephemeral=True)
        await interaction.response.send_message("🛑 تم إغلاق اللعبة الجماعية.")

    @app_commands.command(name="games", description="عرض الألعاب الجماعية والفردية")
    async def games(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "🎮 **الألعاب الجماعية:** الروليت، معركة النرد — الإدارة هي اللي تشغلها، من 2 حتى 15 لاعب.\n"
            "🎯 **الألعاب الفردية:** /coinflip و /solo-dice و /rps — لا تمنح نقاطاً."
        )

    @app_commands.command(name="coinflip", description="لعبة فردية: وجه أو كتابة")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 النتيجة: **{random.choice(('وجه', 'كتابة'))}**")

    @app_commands.command(name="solo-dice", description="لعبة فردية: رمية نرد")
    async def solo_dice(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎲 رميتك: **{random.randint(1, 6)}**")

    @app_commands.command(name="rps", description="لعبة فردية: حجر ورق مقص")
    @app_commands.choices(choice=[
        app_commands.Choice(name="حجر", value="حجر"),
        app_commands.Choice(name="ورق", value="ورق"),
        app_commands.Choice(name="مقص", value="مقص"),
    ])
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
