import discord
from discord import app_commands
from discord.ext import commands
from database import get_config


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="config", description="عرض إعدادات البوت في السيرفر")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config(self, interaction: discord.Interaction):
        c = get_config(interaction.guild.id)
        e = discord.Embed(title="⚙️ إعدادات Nawaf")
        e.add_field(name="Tickets Category", value=f"<#{c['ticket_category']}>" if c["ticket_category"] else "غير محدد", inline=False)
        e.add_field(name="Applications", value=f"<#{c['application_review_channel']}>" if c["application_review_channel"] else "غير محدد", inline=False)
        e.add_field(name="Announcements", value=f"<#{c['ad_channel']}>" if c["ad_channel"] else "غير محدد", inline=False)
        e.add_field(name="Dhikr", value=f"<#{c['dhikr_channel']}>" if c["dhikr_channel"] else "غير مفعل", inline=False)
        e.add_field(name="Shop Orders", value=f"<#{c['shop_order_channel']}>" if c["shop_order_channel"] else "غير محدد", inline=False)
        e.add_field(name="Currency", value=f"{c['currency_name']} {c['currency_symbol']}", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Config(bot))
