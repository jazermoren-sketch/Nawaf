import discord
from discord import app_commands
from discord.ext import commands
from database import connect, get_config, set_config


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="عرض منتجات المتجر")
    async def shop(self, interaction: discord.Interaction):
        with connect() as con:
            products = con.execute(
                "SELECT id, name, description, price, stock FROM shop_products "
                "WHERE guild_id=? AND active=1 ORDER BY id",
                (interaction.guild.id,),
            ).fetchall()

        cfg = get_config(interaction.guild.id)
        if not products:
            return await interaction.response.send_message("🛒 المتجر فارغ حالياً.", ephemeral=True)

        embed = discord.Embed(title="🛒 المتجر", description="استعمل `/shop-buy` للشراء.")
        for product in products[:25]:
            stock = "متوفر دائماً" if product["stock"] < 0 else str(product["stock"])
            description = product["description"] or "بدون وصف"
            embed.add_field(
                name=f"#{product['id']} — {product['name']}",
                value=f"{description}\n💰 **{product['price']} {cfg['currency_symbol']}**\n📦 المخزون: **{stock}**",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop-add", description="إضافة منتج للمتجر")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_add(
        self,
        interaction: discord.Interaction,
        name: str,
        price: int,
        description: str = "",
        stock: int = -1,
    ):
        if price <= 0 or stock == 0 or stock < -1:
            return await interaction.response.send_message("❌ السعر أو المخزون غير صالح.", ephemeral=True)
        if len(name) > 100 or len(description) > 1000:
            return await interaction.response.send_message("❌ اسم أو وصف المنتج طويل جداً.", ephemeral=True)

        with connect() as con:
            cur = con.execute(
                "INSERT INTO shop_products(guild_id,name,description,price,stock) VALUES(?,?,?,?,?)",
                (interaction.guild.id, name, description, price, stock),
            )
            product_id = cur.lastrowid
        await interaction.response.send_message(f"✅ تمت إضافة المنتج **#{product_id} — {name}**.", ephemeral=True)

    @app_commands.command(name="shop-remove", description="حذف منتج من المتجر")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_remove(self, interaction: discord.Interaction, product_id: int):
        with connect() as con:
            row = con.execute(
                "SELECT name FROM shop_products WHERE id=? AND guild_id=? AND active=1",
                (product_id, interaction.guild.id),
            ).fetchone()
            if not row:
                return await interaction.response.send_message("❌ المنتج غير موجود.", ephemeral=True)
            con.execute("UPDATE shop_products SET active=0 WHERE id=?", (product_id,))
        await interaction.response.send_message(f"✅ تم حذف **{row['name']}** من المتجر.", ephemeral=True)

    @app_commands.command(name="shop-settings", description="تحديد روم إشعارات الطلبات")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_settings(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_config(interaction.guild.id, shop_order_channel=channel.id)
        await interaction.response.send_message(f"✅ روم الطلبات: {channel.mention}", ephemeral=True)

    @app_commands.command(name="shop-buy", description="شراء منتج من المتجر")
    async def shop_buy(self, interaction: discord.Interaction, product_id: int, quantity: int = 1):
        if quantity < 1 or quantity > 100:
            return await interaction.response.send_message("❌ الكمية يجب أن تكون بين 1 و100.", ephemeral=True)

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        with connect() as con:
            product = con.execute(
                "SELECT id, name, price, stock FROM shop_products WHERE id=? AND guild_id=? AND active=1",
                (product_id, guild_id),
            ).fetchone()
            if not product:
                return await interaction.response.send_message("❌ المنتج غير موجود أو غير متاح.", ephemeral=True)

            if product["stock"] >= 0 and product["stock"] < quantity:
                return await interaction.response.send_message("❌ المخزون غير كافٍ.", ephemeral=True)

            con.execute(
                "INSERT OR IGNORE INTO balances(guild_id,user_id,balance) VALUES(?,?,0)",
                (guild_id, user_id),
            )
            balance = con.execute(
                "SELECT balance FROM balances WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()["balance"]
            total = product["price"] * quantity
            if balance < total:
                return await interaction.response.send_message("❌ رصيدك غير كافٍ.", ephemeral=True)

            con.execute(
                "UPDATE balances SET balance=balance-? WHERE guild_id=? AND user_id=?",
                (total, guild_id, user_id),
            )
            if product["stock"] >= 0:
                con.execute(
                    "UPDATE shop_products SET stock=stock-? WHERE id=? AND stock>=?",
                    (quantity, product_id, quantity),
                )
            cur = con.execute(
                "INSERT INTO shop_orders(guild_id,user_id,product_id,quantity,total_price) VALUES(?,?,?,?,?)",
                (guild_id, user_id, product_id, quantity, total),
            )
            order_id = cur.lastrowid

        cfg = get_config(guild_id)
        if cfg["shop_order_channel"]:
            channel = interaction.guild.get_channel(cfg["shop_order_channel"])
            if channel:
                await channel.send(
                    f"🛒 **طلب جديد #{order_id}**\n"
                    f"العضو: {interaction.user.mention}\n"
                    f"المنتج: **{product['name']}**\n"
                    f"الكمية: **{quantity}**\n"
                    f"الإجمالي: **{total} {cfg['currency_name']} {cfg['currency_symbol']}**"
                )

        await interaction.response.send_message(
            f"✅ تم الشراء بنجاح!\n"
            f"🛒 المنتج: **{product['name']}**\n"
            f"📦 الكمية: **{quantity}**\n"
            f"💰 الإجمالي: **{total} {cfg['currency_symbol']}**\n"
            f"🧾 رقم الطلب: **#{order_id}**",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Shop(bot))
