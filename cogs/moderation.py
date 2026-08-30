import discord
from discord import app_commands
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @app_commands.command(name='say-member',description='إرسال رسالة خاصة لعضو')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def say_member(self,interaction,member:discord.Member,message:str):
        try:
            await member.send(message)
        except discord.Forbidden:
            return await interaction.response.send_message('❌ العضو لا يستقبل الرسائل الخاصة.',ephemeral=True)
        await interaction.response.send_message(f'✅ تم إرسال الرسالة إلى {member.mention}.',ephemeral=True)

async def setup(bot): await bot.add_cog(Moderation(bot))
