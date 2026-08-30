import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from database import connect, get_config, set_config

class RatingModal(discord.ui.Modal, title="تقييم التذكرة"):
    stars = discord.ui.TextInput(label="التقييم من 1 إلى 5", min_length=1, max_length=1, placeholder="5")
    note = discord.ui.TextInput(label="ملاحظة", required=False, style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, channel_id, owner_id):
        super().__init__(); self.channel_id=channel_id; self.owner_id=owner_id
    async def on_submit(self, interaction):
        try: value=int(self.stars.value)
        except ValueError: value=0
        if value not in range(1,6):
            return await interaction.response.send_message("❌ التقييم يجب أن يكون من 1 إلى 5.", ephemeral=True)
        with connect() as con:
            row=con.execute("SELECT owner_id, closed_by FROM tickets WHERE channel_id=?", (self.channel_id,)).fetchone()
            if not row or row["owner_id"] != interaction.user.id or not row["closed_by"]:
                return await interaction.response.send_message("❌ لا يمكنك تقييم هذه التذكرة.", ephemeral=True)
            con.execute("UPDATE tickets SET rating=?, note=? WHERE channel_id=?", (value, self.note.value, self.channel_id))
        await interaction.response.send_message("⭐ شكراً على تقييمك وملاحظتك!", ephemeral=True)

class CloseView(discord.ui.View):
    def __init__(self, cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="nawaf:ticket:close")
    async def close(self, interaction, button): await self.cog.close_ticket(interaction)

class TicketView(discord.ui.View):
    def __init__(self, cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="🎫 فتح تذكرة", style=discord.ButtonStyle.primary, custom_id="nawaf:ticket:open")
    async def open(self, interaction, button): await self.cog.open_ticket(interaction)

class Tickets(commands.Cog):
    def __init__(self, bot): self.bot=bot

    async def open_ticket(self, interaction):
        guild=interaction.guild
        with connect() as con:
            old=con.execute("SELECT channel_id FROM tickets WHERE guild_id=? AND owner_id=? AND closed_by IS NULL", (guild.id,interaction.user.id)).fetchone()
        if old:
            return await interaction.response.send_message(f"❌ عندك تذكرة مفتوحة بالفعل: <#{old['channel_id']}>", ephemeral=True)
        cfg=get_config(guild.id)
        category=guild.get_channel(cfg["ticket_category"]) if cfg["ticket_category"] else None
        overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)}
        for role in guild.roles:
            if role.permissions.manage_channels:
                overwrites[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
        channel=await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category, overwrites=overwrites)
        with connect() as con: con.execute("INSERT INTO tickets(channel_id,guild_id,owner_id) VALUES(?,?,?)",(channel.id,guild.id,interaction.user.id))
        await channel.send(f"🎫 {interaction.user.mention} مرحباً بك، اشرح طلبك هنا.", view=CloseView(self))
        await interaction.response.send_message(f"✅ تم فتح التذكرة: {channel.mention}", ephemeral=True)

    async def close_ticket(self, interaction):
        with connect() as con:
            row=con.execute("SELECT owner_id FROM tickets WHERE channel_id=? AND closed_by IS NULL",(interaction.channel.id,)).fetchone()
            if not row: return await interaction.response.send_message("❌ هذه ليست تذكرة مفتوحة.",ephemeral=True)
            if interaction.user.id==row["owner_id"]: return await interaction.response.send_message("❌ صاحب التذكرة لا يمكنه إغلاقها بنفسه.",ephemeral=True)
            con.execute("UPDATE tickets SET closed_by=?,closed_at=? WHERE channel_id=?",(interaction.user.id,datetime.utcnow().isoformat(),interaction.channel.id))
        await interaction.channel.send(f"🔒 تم إغلاق التذكرة بواسطة {interaction.user.mention}. صاحب التذكرة يمكنه الآن التقييم.", view=RatingButton(self, row["owner_id"]))
        await interaction.response.send_message("✅ تم تسجيل إغلاق التذكرة.",ephemeral=True)

    @app_commands.command(name="ticket-panel", description="إرسال Panel فتح التذاكر")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction, channel: discord.TextChannel):
        embed=discord.Embed(title="🎫 الدعم الفني",description="اضغط على الزر لفتح تذكرة.")
        msg=await channel.send(embed=embed,view=TicketView(self))
        set_config(interaction.guild.id,ticket_panel_channel=channel.id,ticket_panel_message=msg.id)
        await interaction.response.send_message("✅ تم إرسال Panel التذاكر.",ephemeral=True)

    @app_commands.command(name="ticket-category", description="تحديد Category التذاكر")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def category(self, interaction, category: discord.CategoryChannel):
        set_config(interaction.guild.id,ticket_category=category.id)
        await interaction.response.send_message(f"✅ Category: {category.name}",ephemeral=True)

class RatingButton(discord.ui.View):
    def __init__(self,cog,owner_id): super().__init__(timeout=None); self.owner_id=owner_id
    @discord.ui.button(label="⭐ تقييم التذكرة",style=discord.ButtonStyle.success,custom_id="nawaf:ticket:rating")
    async def rate(self,interaction,button):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message("❌ هذا الزر مخصص لصاحب التذكرة.",ephemeral=True)
        await interaction.response.send_modal(RatingModal(interaction.channel.id,self.owner_id))

async def setup(bot): await bot.add_cog(Tickets(bot))
