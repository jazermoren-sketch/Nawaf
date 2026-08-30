import discord
from discord import app_commands
from discord.ext import commands
from database import connect, get_config, set_config

class Economy(commands.Cog):
    def __init__(self,bot): self.bot=bot
    def ensure(self,guild_id,user_id):
        with connect() as con: con.execute('INSERT OR IGNORE INTO balances(guild_id,user_id,balance) VALUES(?,?,0)',(guild_id,user_id))
    @app_commands.command(name='balance',description='عرض رصيدك')
    async def balance(self,interaction,member:discord.Member=None):
        member=member or interaction.user; self.ensure(interaction.guild.id,member.id); cfg=get_config(interaction.guild.id)
        with connect() as con: row=con.execute('SELECT balance FROM balances WHERE guild_id=? AND user_id=?',(interaction.guild.id,member.id)).fetchone()
        await interaction.response.send_message(f"💰 رصيد {member.mention}: **{row['balance']} {cfg['currency_name']} {cfg['currency_symbol']}**")
    @app_commands.command(name='pay',description='تحويل العملة لعضو')
    async def pay(self,interaction,member:discord.Member,amount:int):
        if amount<=0 or member.bot or member.id==interaction.user.id: return await interaction.response.send_message('❌ بيانات التحويل غير صالحة.',ephemeral=True)
        self.ensure(interaction.guild.id,interaction.user.id); self.ensure(interaction.guild.id,member.id)
        with connect() as con:
            row=con.execute('SELECT balance FROM balances WHERE guild_id=? AND user_id=?',(interaction.guild.id,interaction.user.id)).fetchone()
            if row['balance']<amount: return await interaction.response.send_message('❌ رصيدك غير كافٍ.',ephemeral=True)
            con.execute('UPDATE balances SET balance=balance-? WHERE guild_id=? AND user_id=?',(amount,interaction.guild.id,interaction.user.id))
            con.execute('UPDATE balances SET balance=balance+? WHERE guild_id=? AND user_id=?',(amount,interaction.guild.id,member.id))
        await interaction.response.send_message(f'✅ تم تحويل **{amount}** إلى {member.mention}.')
    @app_commands.command(name='currency-settings',description='تغيير اسم ورمز العملة')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def currency_settings(self,interaction,name:str,symbol:str='🪙'):
        set_config(interaction.guild.id,currency_name=name[:40],currency_symbol=symbol[:10])
        await interaction.response.send_message(f'✅ العملة أصبحت: **{name} {symbol}**',ephemeral=True)
    @app_commands.command(name='currency-add',description='إضافة عملة لعضو')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self,interaction,member:discord.Member,amount:int):
        if amount<=0: return await interaction.response.send_message('❌ المبلغ غير صالح.',ephemeral=True)
        self.ensure(interaction.guild.id,member.id)
        with connect() as con: con.execute('UPDATE balances SET balance=balance+? WHERE guild_id=? AND user_id=?',(amount,interaction.guild.id,member.id))
        await interaction.response.send_message(f'✅ تمت إضافة **{amount}** لــ{member.mention}.',ephemeral=True)

async def setup(bot): await bot.add_cog(Economy(bot))
