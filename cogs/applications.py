import discord, json
from discord import app_commands
from discord.ext import commands
from database import connect, get_config, set_config

class ApplicationModal(discord.ui.Modal,title="التقديم"):
    name=discord.ui.TextInput(label="الاسم",max_length=100)
    age=discord.ui.TextInput(label="العمر",max_length=3)
    experience=discord.ui.TextInput(label="الخبرة",style=discord.TextStyle.paragraph,max_length=1000)
    reason=discord.ui.TextInput(label="لماذا تريد الانضمام؟",style=discord.TextStyle.paragraph,max_length=1000)
    async def on_submit(self,interaction):
        answers=json.dumps({'name':self.name.value,'age':self.age.value,'experience':self.experience.value,'reason':self.reason.value},ensure_ascii=False)
        with connect() as con:
            cur=con.execute("INSERT INTO applications(guild_id,user_id,answers) VALUES(?,?,?)",(interaction.guild.id,interaction.user.id,answers)); app_id=cur.lastrowid
        cfg=get_config(interaction.guild.id); ch=interaction.guild.get_channel(cfg['application_review_channel']) if cfg['application_review_channel'] else None
        if ch:
            e=discord.Embed(title=f"📝 تقديم #{app_id}",description=f"المتقدم: {interaction.user.mention}")
            data=json.loads(answers); e.add_field(name="الاسم",value=data['name'],inline=True); e.add_field(name="العمر",value=data['age'],inline=True); e.add_field(name="الخبرة",value=data['experience'],inline=False); e.add_field(name="السبب",value=data['reason'],inline=False)
            await ch.send(embed=e,view=ApplicationReview(app_id))
        await interaction.response.send_message("✅ تم إرسال التقديم للإدارة.",ephemeral=True)

class ApplicationReview(discord.ui.View):
    def __init__(self,app_id): super().__init__(timeout=None); self.app_id=app_id
    async def decide(self,interaction,status):
        with connect() as con:
            con.execute("UPDATE applications SET status=?,reviewer_id=? WHERE id=?",(status,interaction.user.id,self.app_id))
            row=con.execute("SELECT user_id,guild_id FROM applications WHERE id=?",(self.app_id,)).fetchone()
        member=interaction.guild.get_member(row['user_id'])
        if member:
            try: await member.send(f"📝 نتيجة التقديم #{self.app_id}: **{status}**")
            except discord.HTTPException: pass
        await interaction.response.send_message(f"✅ تم تسجيل: {status}",ephemeral=True)
    @discord.ui.button(label="قبول",style=discord.ButtonStyle.success,custom_id="nawaf:app:accept")
    async def accept(self,i,b): await self.decide(i,'accepted')
    @discord.ui.button(label="رفض",style=discord.ButtonStyle.danger,custom_id="nawaf:app:reject")
    async def reject(self,i,b): await self.decide(i,'rejected')

class Applications(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @app_commands.command(name='application-panel',description='إرسال Panel التقديم')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self,interaction,channel:discord.TextChannel):
        e=discord.Embed(title='📝 التقديم',description='اضغط على الزر وعمّر الاستمارة.')
        msg=await channel.send(embed=e,view=ApplicationPanel())
        set_config(interaction.guild.id,application_panel_channel=channel.id,application_panel_message=msg.id)
        await interaction.response.send_message('✅ تم إرسال Panel التقديم.',ephemeral=True)
    @app_commands.command(name='application-review-channel',description='تحديد روم مراجعة التقديمات')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def review_channel(self,interaction,channel:discord.TextChannel):
        set_config(interaction.guild.id,application_review_channel=channel.id)
        await interaction.response.send_message(f'✅ {channel.mention}',ephemeral=True)

class ApplicationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label='📝 تقديم',style=discord.ButtonStyle.primary,custom_id='nawaf:application:open')
    async def open(self,interaction,b): await interaction.response.send_modal(ApplicationModal())

async def setup(bot): await bot.add_cog(Applications(bot))
