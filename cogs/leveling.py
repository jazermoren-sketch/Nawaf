import discord
from discord import app_commands
from discord.ext import commands
from database import connect

class Leveling(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.Cog.listener()
    async def on_message(self,message):
        if message.author.bot or not message.guild: return
        with connect() as con:
            con.execute("INSERT OR IGNORE INTO xp(guild_id,user_id) VALUES(?,?)",(message.guild.id,message.author.id))
            row=con.execute("SELECT xp,level FROM xp WHERE guild_id=? AND user_id=?",(message.guild.id,message.author.id)).fetchone()
            new_xp=row['xp']+10
            new_level=int((new_xp//100)**0.5)
            con.execute("UPDATE xp SET xp=?,level=? WHERE guild_id=? AND user_id=?",(new_xp,new_level,message.guild.id,message.author.id))
        if new_level>row['level']:
            await message.channel.send(f"🎉 مبروك {message.author.mention}! وصلت للمستوى **{new_level}**.")

    @app_commands.command(name="level",description="عرض مستواك")
    async def level(self,interaction,member:discord.Member=None):
        member=member or interaction.user
        with connect() as con:
            row=con.execute("SELECT xp,level FROM xp WHERE guild_id=? AND user_id=?",(interaction.guild.id,member.id)).fetchone()
        xp=row['xp'] if row else 0; level=row['level'] if row else 0
        await interaction.response.send_message(f"📈 **{member.display_name}**\nالمستوى: **{level}**\nXP: **{xp}**")

async def setup(bot): await bot.add_cog(Leveling(bot))
